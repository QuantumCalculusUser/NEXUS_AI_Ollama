"""Read-only integration with the NVIDIA App's installed MCP bridge on Windows."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


class NvidiaAppError(RuntimeError):
    pass


def bridge_path() -> Path:
    program_files = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    return Path(program_files) / 'NVIDIA Corporation' / 'NVIDIA app' / 'McpServer' / 'NvAppMcpServer.exe'


def is_available() -> bool:
    return os.name == 'nt' and bridge_path().is_file()


def _read_response(process, request_id: int) -> dict:
    """Read the bridge's JSON response for one request in its short-lived session."""
    for _ in range(4):
        line = process.stdout.readline()
        if not line:
            stderr = process.stderr.read().strip() if process.stderr else ''
            raise NvidiaAppError(stderr or 'NVIDIA App MCP bridge closed without a response. Start NVIDIA App, then try again.')
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get('id') == request_id:
            if 'error' in message:
                raise NvidiaAppError(str(message['error']))
            return message.get('result', {})
    raise NvidiaAppError('NVIDIA App MCP bridge returned no matching response.')


def call_tool(name: str, arguments: dict | None = None) -> dict:
    """Call a read-only NVIDIA App MCP tool through its bundled stdio bridge."""
    executable = bridge_path()
    if not is_available():
        raise NvidiaAppError('NVIDIA App MCP bridge is not installed. Install or update NVIDIA App first.')
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    process = subprocess.Popen(
        [str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', creationflags=creationflags,
    )
    try:
        def send(message: dict) -> None:
            process.stdin.write(json.dumps(message, separators=(',', ':')) + '\n')
            process.stdin.flush()

        send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'NEXUS', 'version': '1.0'},
        }})
        _read_response(process, 1)
        send({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}})
        send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
            'name': name, 'arguments': arguments or {},
        }})
        result = _read_response(process, 2)
        if result.get('isError'):
            text = ' '.join(item.get('text', '') for item in result.get('content', []) if isinstance(item, dict))
            raise NvidiaAppError(text or 'NVIDIA App could not complete the request.')
        return result
    except OSError as exc:
        raise NvidiaAppError(f'Could not start NVIDIA App MCP bridge: {exc}') from exc
    finally:
        if process.stdin:
            try: process.stdin.close()
            except OSError: pass
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: process.kill()


def applications() -> list[dict]:
    """Return applications discovered by NVIDIA App and their optimization status."""
    result = call_tool('nvapp_client_get_applications')
    payload = result.get('structuredContent') or {}
    values = payload.get('applications')
    if not isinstance(values, list):
        raise NvidiaAppError('NVIDIA App returned an unexpected applications response.')
    return [item for item in values if isinstance(item, dict)]


def games() -> list[dict]:
    return [item for item in applications() if not item.get('isCreativeApp')]

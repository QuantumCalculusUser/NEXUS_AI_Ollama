"""Local-only context used when a user asks NEXUS about their PC or games."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from .internet import check_internet
from .nvidia_app import NvidiaAppError, games as nvidia_games
from .system_monitor import snapshot


def _existing_dirs(paths):
    seen = set()
    for raw in paths:
        try:
            path = Path(raw).expanduser()
            key = str(path.resolve()).lower()
            if key not in seen and path.is_dir():
                seen.add(key)
                yield path
        except OSError:
            continue


def _acf_value(text: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s+"([^"]*)"', text, re.IGNORECASE)
    return match.group(1).replace('\\\\', '\\') if match else ''


def _steam_library_dirs(steam_roots=None):
    program_files_x86 = os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')
    program_files = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    roots = steam_roots or [Path(program_files_x86) / 'Steam', Path(program_files) / 'Steam']
    libraries = []
    for root in _existing_dirs(roots):
        steamapps = root / 'steamapps'
        if steamapps.is_dir():
            libraries.append(steamapps)
        config = steamapps / 'libraryfolders.vdf'
        if not config.is_file():
            continue
        try:
            raw = config.read_text(encoding='utf-8', errors='replace')
            for value in re.findall(r'"path"\s+"([^"]+)"', raw, re.IGNORECASE):
                library = Path(value.replace('\\\\', '\\')) / 'steamapps'
                if library.is_dir():
                    libraries.append(library)
        except OSError:
            continue
    return list(_existing_dirs(libraries))


def steam_games(steam_roots=None) -> list[dict[str, str]]:
    games = []
    for library in _steam_library_dirs(steam_roots):
        try:
            manifests = library.glob('appmanifest_*.acf')
            for manifest in manifests:
                raw = manifest.read_text(encoding='utf-8', errors='replace')
                name = _acf_value(raw, 'name')
                install_dir = _acf_value(raw, 'installdir')
                if name:
                    games.append({'name': name, 'source': 'Steam', 'path': str(library / 'common' / install_dir) if install_dir else ''})
        except OSError:
            continue
    return games


def epic_games(manifest_root=None) -> list[dict[str, str]]:
    program_data = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
    root = Path(manifest_root) if manifest_root else Path(program_data) / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests'
    games = []
    try:
        for manifest in root.glob('*.item'):
            data = json.loads(manifest.read_text(encoding='utf-8', errors='replace'))
            name = str(data.get('DisplayName') or data.get('AppName') or '').strip()
            if name:
                games.append({'name': name, 'source': 'Epic Games', 'path': str(data.get('InstallLocation') or '')})
    except (OSError, json.JSONDecodeError):
        pass
    return games


def folder_games() -> list[dict[str, str]]:
    program_files = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    program_files_x86 = os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')
    candidates = [
        (Path(program_files) / 'EA Games', 'EA app'),
        (Path(program_files_x86) / 'Ubisoft' / 'Ubisoft Game Launcher' / 'games', 'Ubisoft Connect'),
        (Path('C:/GOG Games'), 'GOG'),
        (Path('C:/Games'), 'Local install folder'),
    ]
    games = []
    for folder, source in candidates:
        try:
            for child in folder.iterdir():
                if child.is_dir():
                    games.append({'name': child.name, 'source': source, 'path': str(child)})
        except OSError:
            continue
    return games


def installed_games() -> list[dict[str, str]]:
    """Discover installed games from launcher manifests and known install folders."""
    found = steam_games() + epic_games() + folder_games()
    unique = {}
    for game in found:
        key = (game['name'].casefold(), game['path'].casefold())
        unique.setdefault(key, game)
    return sorted(unique.values(), key=lambda game: (game['name'].casefold(), game['source']))


_FILE_STOP_WORDS = {
    'a', 'about', 'access', 'all', 'and', 'are', 'can', 'directory', 'every', 'file', 'files',
    'find', 'folder', 'for', 'from', 'give', 'in', 'list', 'look', 'me', 'my', 'of', 'on',
    'search', 'show', 'tell', 'the', 'to', 'what', 'with', 'you', 'system', 'stuff',
}


def search_user_files(request: str, limit: int = 30, max_seconds: float = 3.0) -> list[dict[str, str]]:
    """Search filenames only in the standard user folders; never reads file contents."""
    tokens = [word.casefold() for word in re.findall(r"[\w.-]+", request) if len(word) > 1 and word.casefold() not in _FILE_STOP_WORDS]
    roots = [Path.home() / name for name in ('Desktop', 'Documents', 'Downloads')]
    matches = []
    started = time.monotonic()
    for root in _existing_dirs(roots):
        try:
            for directory, dirs, files in os.walk(root, onerror=lambda _error: None):
                if time.monotonic() - started > max_seconds or len(matches) >= limit:
                    return matches
                dirs[:] = [name for name in dirs if not name.startswith('.')][:150]
                for filename in files:
                    lowered = filename.casefold()
                    if tokens and not all(token in lowered for token in tokens):
                        continue
                    path = Path(directory) / filename
                    try:
                        size = path.stat().st_size
                        matches.append({'name': filename, 'path': str(path), 'size': str(size)})
                    except OSError:
                        continue
                    if len(matches) >= limit:
                        return matches
        except OSError:
            continue
    return matches


def _format_system_snapshot() -> str:
    data = snapshot()
    gpu = data['gpu']
    lines = [
        f"OS: {data['platform']}",
        f"CPU: {data['processor']} ({data['cpu']}% utilization)",
        f"Memory: {data['ram_used']} / {data['ram_total']} GB ({data['ram_pct']}%)",
        f"Disk: {data['disk_used']} / {data['disk_total']} GB ({data['disk_pct']}%)",
        f"Uptime: {data['uptime_hours']} hours",
    ]
    lines.append(f"GPU: {gpu['name']} ({gpu['util']}%, {gpu['temp']} °C)" if gpu else 'GPU: unavailable')
    if data['games']:
        lines.append('Active game/launcher-related processes: ' + ', '.join(item['name'] for item in data['games']))
    return '\n'.join(lines)


def context_for_request(request: str) -> str:
    """Return only the live local facts relevant to a user request."""
    query = request.casefold()
    sections = []
    if any(word in query for word in ('game', 'steam', 'epic', 'gog', 'ubisoft', 'ea app', 'battle.net')):
        games = installed_games()
        lines = [f"Installed games found: {len(games)}"]
        lines.extend(f"- {game['name']} [{game['source']}]" + (f" — {game['path']}" if game['path'] else '') for game in games[:100])
        if len(games) > 100:
            lines.append(f"- … {len(games) - 100} more not shown")
        sections.append('[LIVE LOCAL GAME INVENTORY]\n' + '\n'.join(lines))
        try:
            nvidia = nvidia_games()
            nvidia_lines = [f"NVIDIA App recognized games: {len(nvidia)}"]
            for game in nvidia:
                profiles = game.get('optimizationProfiles') or {}
                ac_state = (profiles.get('ac') or {}).get('currentState', 'UNKNOWN')
                presets = ', '.join((profiles.get('ac') or {}).get('availablePresets') or [])
                nvidia_lines.append(f"- {game.get('displayName') or game.get('game')} — AC optimization: {ac_state}; presets: {presets or 'none'}")
            sections.append('[NVIDIA APP GAME DATA]\n' + '\n'.join(nvidia_lines))
        except NvidiaAppError as exc:
            sections.append(f'[NVIDIA APP GAME DATA]\nUnavailable: {exc}')
    if any(word in query for word in ('cpu', 'gpu', 'ram', 'memory', 'storage', 'disk', 'system', 'temperature', 'telemetry', 'spec')):
        sections.append('[LIVE SYSTEM SNAPSHOT]\n' + _format_system_snapshot())
    if any(word in query for word in ('file', 'folder', 'document', 'download', 'desktop')):
        files = search_user_files(request)
        lines = ['Filename search scope: Desktop, Documents, and Downloads. File contents were not read.']
        lines.extend(f"- {item['name']} — {item['path']} ({int(item['size']) / 1024:.1f} KB)" for item in files)
        if not files:
            lines.append('- No matching filenames found. Attach a file in Knowledge Lab when you want NEXUS to read its contents.')
        sections.append('[LOCAL FILE SEARCH]\n' + '\n'.join(lines))
    if any(word in query for word in ('internet', 'online', 'web connection', 'network connection')):
        status = check_internet()
        sections.append(f"[LIVE INTERNET STATUS]\n{'Online' if status.online else 'Offline'}: {status.detail}")
    return '\n\n'.join(sections)

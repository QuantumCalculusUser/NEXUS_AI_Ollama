"""Small, explicit client for Ollama's local HTTP API. No cloud API keys are used."""
from __future__ import annotations
import json
from typing import Any, Callable, Iterable
import requests

DEFAULT_HOST = "http://127.0.0.1:11434"

class OllamaError(RuntimeError):
    pass

class OllamaClient:
    def __init__(self, host: str = DEFAULT_HOST, timeout: int = 8):
        self.host = host.rstrip("/")
        self.timeout = timeout

    def health(self) -> tuple[bool, str]:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=self.timeout)
            response.raise_for_status()
            return True, "Ollama is reachable"
        except requests.RequestException as exc:
            return False, str(exc)

    def list_models(self) -> list[dict[str, Any]]:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("models", [])
        except requests.RequestException as exc:
            raise OllamaError(f"Cannot reach Ollama at {self.host}. Start Ollama and try again. Details: {exc}") from exc

    def pull_model(self, name: str, on_progress: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Pull a model while reporting the streaming progress events."""
        try:
            with requests.post(f"{self.host}/api/pull", json={"name": name, "stream": True},
                               stream=True, timeout=(10, 1800)) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    event = json.loads(line)
                    if on_progress:
                        on_progress(event)
                    if event.get("error"):
                        raise OllamaError(event["error"])
        except requests.RequestException as exc:
            raise OllamaError(f"Model download failed: {exc}") from exc

    def chat_stream(self, model: str, messages: list[dict[str, Any]],
                    on_token: Callable[[str], None], options: dict[str, Any] | None = None,
                    stop_event=None) -> str:
        payload = {"model": model, "messages": messages, "stream": True,
                   "options": options or {"temperature": 0.65, "num_ctx": 16384}}
        pieces: list[str] = []
        try:
            with requests.post(f"{self.host}/api/chat", json=payload, stream=True,
                               timeout=(10, 900)) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if stop_event is not None and stop_event.is_set():
                        break
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise OllamaError(event["error"])
                    token = event.get("message", {}).get("content", "")
                    if token:
                        pieces.append(token)
                        on_token(token)
                    if event.get("done"):
                        break
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama chat request failed: {exc}") from exc
        return "".join(pieces)

# NEXUS AI Desktop — Ollama Edition

NEXUS is a local-first Windows desktop assistant. Its chat inference uses **Ollama on your own machine**. There is no Nebius API, OpenAI API, hosted chat endpoint, or API key in this project.

The repository is a multi-module Python desktop application, not a tiny one-file demo. The bundled 4K command-banner themes are included as real UI assets. The Ollama model itself is downloaded separately and is several gigabytes; it is not embedded in the ZIP.

## Features in this build

- Dark gaming / sci-fi desktop interface with three 4K banner themes.
- Local Ollama chat through `http://127.0.0.1:11434/api/chat`, streamed token-by-token.
- Model discovery and model pull progress from Ollama's local API.
- Persistent local conversations and reminders in SQLite (`~/.nexus_ai/nexus.sqlite3`).
- File context for text, source code, PDF, DOCX, and common image formats. PDF/DOCX/text extraction runs locally. Image attachments are passed to a compatible vision model. Chat can also search filenames (not file contents) in Desktop, Documents, and Downloads when asked.
- Local Windows text-to-speech and optional offline Vosk speech recognition.
- Explicit online research in chat: saying “search online”, “look up”, or “browse” automatically gathers DuckDuckGo result titles, snippets, and links for the local model. The app does not open result pages automatically.
- CPU/RAM/disk telemetry, best-effort NVIDIA GPU utilization/temperature/clock/VRAM readings, installed-game inventory from Steam/Epic/EA/Ubisoft/GOG/standard game folders, NVIDIA App's supported local game/optimization inventory via its bundled MCP bridge, and heuristic active-game detection.
- A scan-first temporary-file cleaner. It shows individual candidates and asks for confirmation before deleting selected files inside approved temp/cache folders.
- Separate internet-connectivity and local-Ollama status indicators.

## Recommended model

Install the **latest stable Ollama release for Windows** from <https://ollama.com/download>.

For a strong all-purpose local assistant with image understanding, start with:

```powershell
ollama pull qwen3.5:9b
```

This model is large (several GB). With an RTX 5070 laptop GPU and 32 GB system RAM, it is a reasonable quality-first starting point, but actual speed and GPU offload depend on your specific VRAM, context length, and other running applications. If it is too slow or memory-constrained, use:

```powershell
ollama pull qwen3.5:4b
```

The application defaults to `qwen3.5:9b` but lets you select any model installed in Ollama. A vision-capable model is needed for image attachments. Model tags and sizes can change, so check the official library: <https://ollama.com/library/qwen3.5>.

## Windows setup

1. Install the latest stable Ollama app from <https://ollama.com/download> and leave it running.
2. Open PowerShell in the extracted project folder.
3. Create a virtual environment and install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Pull the model:

```powershell
ollama pull qwen3.5:9b
```

5. Launch the desktop application:

```powershell
python main.py
```

Or double-click `launch_windows.bat`, which creates the virtual environment, installs dependencies, and starts NEXUS.

If PowerShell blocks activation, you can skip activation and use `.venv\Scripts\python.exe -m pip install -r requirements.txt`, followed by `.venv\Scripts\python.exe main.py`.

## Optional offline voice input

Voice output uses `pyttsx3` and runs locally where a system voice is available. Voice input uses NumPy, Vosk, and `sounddevice`; download a Vosk English model and extract it to:

`models/vosk-model-small-en-us-0.15/`

Vosk model downloads: <https://alphacephei.com/vosk/models>. The app validates the model files and default microphone before recording. Windows microphone permission must be enabled. If an existing virtual environment predates this release, update it with `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

## Hardware telemetry

NVIDIA readings use `nvidia-ml-py` where possible, with GPUtil as a fallback. Keep current NVIDIA drivers installed. Some laptop/driver combinations do not expose all sensors; unavailable readings are shown as `N/A`, not fabricated. Game detection is a process-name heuristic, not a complete game-history tracker, and this version does not yet read NVIDIA App history or per-game recommended settings.

## Safe cleanup

The cleanup tool only scans files inside known temporary/cache locations. It does not automatically delete anything. You select individual files, then confirm deletion. Do not remove files belonging to running applications. This is not a registry cleaner or an aggressive system optimizer.

## Privacy and connectivity

- Chat content is sent to the Ollama service configured in Settings. By default, that is the local machine at `127.0.0.1`.
- Files are parsed locally. Their text/image content is included only in requests sent to the configured Ollama host. If you change the host to a remote machine, content leaves your PC and goes to that host.
- The internet indicator verifies both DNS and HTTPS against small public connectivity endpoints, with a fallback rather than depending on one host. It distinguishes a missing connection, a captive-portal sign-in, DNS failure, and certificate errors. It does not send chat content.
- Web access is opt-in: use **Knowledge Lab → Web Research → Search web**, or explicitly request an online search in chat. Search results are passed to Ollama as untrusted references.
- Local game, telemetry, and filename context is passed to chat only when the configured Ollama host is `localhost`/`127.0.0.1`/`::1`; it is never silently sent to a remote Ollama host.
- NVIDIA App data is read through its installed, read-only MCP bridge. It reports games it recognizes and their optimization state/presets; it does not expose an authoritative play-time history.
- Conversation history and reminders are stored in the local SQLite database noted above.
- The current app does not send emails, messages, or calls. Reminders are local records only. These integrations require separate, explicit connectors and permission prompts.

## Build a Windows executable

From Windows, after installing the dependencies:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name NEXUS-AI --add-data "assets;assets" main.py
```

The executable and bundled Qt runtime will be much larger than 5–6 MB. That is normal for a Python + Qt desktop app. Ollama and the model weights remain separate installations.

## Project structure

```text
main.py                       Application entry point
nexus/ui.py                   Full desktop UI and navigation
nexus/ollama_client.py        Local Ollama HTTP API and streaming
nexus/workers.py              Background chat and model-download workers
nexus/file_context.py         Local file extraction and image attachment
nexus/system_monitor.py       Hardware/process telemetry and safe cleanup
nexus/voice.py                Local TTS and optional Vosk input
nexus/storage.py              SQLite conversations, settings, reminders
assets/*_4k.jpg               High-resolution sci-fi banner themes
launch_windows.bat            One-command Windows launcher
install_ollama_model.bat      Pull the recommended model
```

## Tests and limitations

Run the basic file extraction tests with:

```powershell
python -m unittest discover -s tests -v
```

The project has not been verified against every Windows driver, microphone, Ollama version, launcher layout, or model. It is a substantial local desktop MVP, not yet a finished autonomous agent. It does not yet implement full web-page reading, image generation, automatic email/SMS/calls, persistent game-history analytics, or a full offline local model manager. Ollama itself must be installed and running for chat.

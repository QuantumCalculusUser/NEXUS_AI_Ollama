"""Local text-to-speech and offline Vosk speech recognition."""
from __future__ import annotations
import base64
import json
import os
import subprocess
import threading
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15"


def voice_diagnostics(model_path: str | Path = DEFAULT_MODEL_PATH) -> str:
    """Validate the voice setup without recording from the microphone."""
    model_dir = Path(model_path).expanduser().resolve()
    missing = [str(model_dir / item) for item in ("am/final.mdl", "conf/model.conf", "graph/HCLr.fst") if not (model_dir / item).is_file()]
    if missing:
        raise RuntimeError(
            "Vosk model is incomplete or in the wrong folder. Expected files under "
            f"{model_dir}. Missing: {', '.join(missing)}"
        )
    try:
        import numpy  # noqa: F401  # SoundDevice requires NumPy at runtime.
        import sounddevice as sd
        from vosk import Model
    except ImportError as exc:
        raise RuntimeError(
            "Voice packages are incomplete. Install them in NEXUS's Python environment with: "
            ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        ) from exc
    try:
        device = sd.query_devices(kind="input")
        sd.check_input_settings(device=device["name"], channels=1, samplerate=16000, dtype="int16")
    except Exception as exc:
        raise RuntimeError(
            "No usable microphone is available at 16 kHz. Check the Windows microphone privacy permission, "
            "choose a default input device, then try again. Details: " + str(exc)
        ) from exc
    try:
        Model(str(model_dir))
    except Exception as exc:
        raise RuntimeError(f"Vosk could not open the model at {model_dir}: {exc}") from exc
    return f"Voice setup is ready. Microphone: {device['name']}"

class VoiceOutput:
    """Speech output with a reliable native Windows backend and a portable fallback."""
    def __init__(self):
        self._engine=None
        self._process=None
        self._lock=threading.Lock()

    @staticmethod
    def _windows_command(text: str) -> list[str]:
        """Build a fixed PowerShell command; spoken text is base64, never code."""
        encoded = base64.b64encode(text.encode("utf-16-le")).decode("ascii")
        script = (
            "$ErrorActionPreference='Stop'; "
            "Add-Type -AssemblyName System.Speech; "
            f"$text=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('{encoded}')); "
            "$speaker=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$voice=$speaker.GetInstalledVoices() | Select-Object -First 1; "
            "if ($null -eq $voice) { throw 'No Windows text-to-speech voice is installed.' }; "
            "$speaker.SelectVoice($voice.VoiceInfo.Name); $speaker.Speak($text);"
        )
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Sta", "-Command", script]

    def _speak_windows(self, text: str) -> None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            self._windows_command(text),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )
        with self._lock:
            self._process = process
        try:
            _, stderr = process.communicate()
            if process.returncode:
                detail = stderr.decode("utf-8", "replace").strip() or f"exit code {process.returncode}"
                raise RuntimeError(detail)
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None

    def speak(self,text):
        text = " ".join(str(text).split())
        if not text:
            return
        try:
            if os.name == "nt":
                self._speak_windows(text)
                return
            import pyttsx3
            engine=pyttsx3.init()
            with self._lock: self._engine=engine
            engine.setProperty('rate',185); engine.say(text); engine.runAndWait()
        except Exception as exc: raise RuntimeError(f"Text-to-speech failed: {exc}") from exc
        finally:
            with self._lock: self._engine=None
    def stop(self):
        # Do not hold the lock while stopping: speech executes on the speaker thread.
        with self._lock:
            engine=self._engine
            process=self._process
        if engine:
            try: engine.stop()
            except Exception: pass
        if process and process.poll() is None:
            try: process.terminate()
            except Exception: pass

class OfflineRecognizer:
    def __init__(self,model_path: str | Path = DEFAULT_MODEL_PATH):
        self.model_path=Path(model_path).expanduser().resolve()
    def listen_once(self, seconds=8):
        try:
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer
            voice_diagnostics(self.model_path)
            model=Model(str(self.model_path)); recognizer=KaldiRecognizer(model,16000)
            audio=sd.rec(int(seconds*16000),samplerate=16000,channels=1,dtype='int16'); sd.wait()
            recognizer.AcceptWaveform(audio.tobytes())
            return json.loads(recognizer.FinalResult()).get('text','')
        except Exception as exc:
            raise RuntimeError(f"Offline voice input unavailable. {exc}") from exc

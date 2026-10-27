@echo off
echo Make sure Ollama for Windows is installed and running.
echo Recommended primary model: qwen3.5:9b (large; allow several GB of disk and memory).
echo Lighter option: qwen3.5:4b.
echo.
ollama pull qwen3.5:9b
if errorlevel 1 (
  echo Pull failed. Try: ollama pull qwen3.5:4b
  pause
  exit /b 1
)
echo Model is ready. Start NEXUS with launch_windows.bat
pause

@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run setup.bat first.
  pause
  exit /b 1
)
set "GRADIO_ANALYTICS_ENABLED=False"
set "HF_HUB_OFFLINE=1"
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause

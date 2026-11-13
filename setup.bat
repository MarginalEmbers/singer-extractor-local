@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo Please install uv first: https://docs.astral.sh/uv/getting-started/installation/
  pause
  exit /b 1
)
if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%CD%\.cache\uv"
set "UV_PYTHON_INSTALL_DIR=%CD%\runtime\python"
if not exist ".venv\Scripts\python.exe" (
  uv venv .venv --python 3.11
  if errorlevel 1 goto :failed
)
uv pip install --python .venv\Scripts\python.exe torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :failed
uv pip install --python .venv\Scripts\python.exe -r requirements-windows.lock
if errorlevel 1 goto :failed
uv pip install --python .venv\Scripts\python.exe -e . --no-deps
if errorlevel 1 goto :failed
echo Setup complete. Next: run download_models.bat, then start.bat.
pause
exit /b 0
:failed
echo Setup failed. Please copy the error above.
pause
exit /b 1

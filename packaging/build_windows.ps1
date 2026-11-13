param([string]$BuildRoot = "")
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $BuildRoot) { $BuildRoot = Join-Path $projectRoot ".build" }
$BuildRoot = [System.IO.Path]::GetFullPath($BuildRoot)
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
$uvExe = (Get-Command uv -ErrorAction Stop).Source
$buildPython = Join-Path $BuildRoot "venv\Scripts\python.exe"
$env:UV_CACHE_DIR = Join-Path $BuildRoot "uv-cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $BuildRoot "python"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $BuildRoot "pyinstaller-cache"
function Confirm-ExitCode { if ($LASTEXITCODE -ne 0) { throw "Build command failed: $LASTEXITCODE" } }
& $uvExe venv (Join-Path $BuildRoot "venv") --python 3.11
Confirm-ExitCode
& $uvExe pip install --python $buildPython torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128
Confirm-ExitCode
& $uvExe pip install --python $buildPython -r (Join-Path $projectRoot "requirements-desktop.lock")
Confirm-ExitCode
& $uvExe pip install --python $buildPython -e $projectRoot --no-deps
Confirm-ExitCode
$priorPath = $env:PATH
try {
    # Avoid collecting same-named DLLs from unrelated software on the developer PATH.
    $env:PATH = "$(Split-Path $buildPython);$env:SystemRoot\System32;$env:SystemRoot"
    & $buildPython (Join-Path $PSScriptRoot "build_icon.py")
    Confirm-ExitCode
    & $buildPython -m PyInstaller --noconfirm --distpath (Join-Path $BuildRoot "dist") --workpath (Join-Path $BuildRoot "pyinstaller") (Join-Path $PSScriptRoot "desktop.spec")
    Confirm-ExitCode
    & $buildPython (Join-Path $PSScriptRoot "collect_notices.py") (Join-Path $BuildRoot "dist\JinjinAudio")
    Confirm-ExitCode
} finally {
    $env:PATH = $priorPath
}
Write-Output "Portable folder: $(Join-Path $BuildRoot 'dist\JinjinAudio')"

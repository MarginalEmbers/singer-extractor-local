# Windows desktop build

## v0.5 online package

Build on Windows with Python 3.11, PySide6 (to generate the icon), and official
[uv 0.12.7](https://github.com/astral-sh/uv/releases/tag/0.12.7).
The Windows .NET Framework C# compiler builds the small graphical launcher;
Python and GPU runtime libraries are installed on first use, not shipped.

From the repository root in Windows PowerShell:

```powershell
python packaging/build_icon.py
python packaging/build_online.py .build/online --uv C:\path\to\uv.exe
```

Use a new destination for each build. The script compiles the launcher, packages
the source/UI and model manifest, includes uv's original license texts, and creates
a SHA-256 inventory. Both EXEs verify this inventory before executing packaged
code; rebuild it using this script after intentional source modifications.
`app`, `tools`, the lock files and `package-files.json` must stay beside the EXEs.
Do not distribute the test-created `data` directory or downloaded runtimes.

The installer pins Python 3.11.16, PyTorch 2.7.1+cu128 from the official CUDA 12.8
index, and all UI/runtime requirements from PyPI. Build-only dependencies such as
PyInstaller are excluded. It uses a dedicated managed Python and environment
under `%LOCALAPPDATA%\JinjinAudio\runtime-cu128-py311-v1`, without registry/PATH
changes or system Python modification. Libraries remain separately replaceable;
modify the pinned requirements and rebuild for alternative library versions.

For automated testing, the launcher supports `--runtime-root PATH`, `--data-dir PATH`,
`--check-only REPORT.json`, `--install-only`, `--settings`, and `--self-test REPORT.json`
with optional `--offline`. Overrides apply only to that process, not global settings.
Use `Start-Process -Wait -PassThru` when scripting the windowed EXE and inspect its
exit code. Check-only returns 2 if the Python/runtime is missing or broken; GPU
unavailability is a separate JSON flag and permits an explicit CPU launch in the UI.
The check imports Qt, audio and Torch libraries and actually executes CUDA FFT
and a cuDNN LSTM. Model absence is actionable but does not block opening the app
for its automatic model download. Errors and installation steps are in `data/logs`.

First installation needs about 3–4 GB of downloads, plus about 919 MB of model downloads. The 12 GiB
free-space guard includes installation/cache headroom and is not a promise about
total song storage. Retries reuse verified package caches where available. Repair
reinstalls pinned packages, preserving user audio and exports.

The C# launcher uses Windows' .NET Framework 4.x / Windows Forms. Test the native
UI at the host DPI: table rows have explicit positions so hiding the progress bar
cannot collapse the buttons into the progress bar's short row.

## v0.3 full portable package

Run from the repository root in **Windows PowerShell**. End users should download
the release instead; these are developer-only instructions.

Prerequisite: official [uv](https://docs.astral.sh/uv/getting-started/installation/).
The script creates its own Python 3.11 environment, installs pinned dependencies,
generates the icon, builds a console-free folder distribution and collects licenses.

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1
```

`ExecutionPolicy Bypass` applies only to this explicitly invoked build-script process.
Alternatively, run the script according to your organization's existing script policy.
Build output: `.build/dist/JinjinAudio/`. Keep the EXE and `_internal` together.
The script does not download or redistribute model checkpoints.
The user-facing `data/` folder is created on launch; exclude it from releases.

The generated icon comes from `packaging/build_icon.py`; no external artwork is required.
The runtime lock is `requirements-desktop.lock`; Torch is separately pinned to
`2.7.1+cu128` from the official PyTorch CUDA 12.8 index. CUDA Toolkit is not needed.
PyInstaller 6.22.3 uses `packaging/desktop.spec`; Qt QML collection is deliberately
limited to the shared libraries used by the QWidget-based WebEngine view.

To test a built EXE without opening a window:

```powershell
& '.\.build\dist\JinjinAudio\哦，金金的音道分离.exe' --self-test "$PWD\.build\check.json" --data-dir "$PWD\.build\test-data"
```

The command is asynchronous in some terminals because the EXE is windowed.
Wait for `check.json`, inspect `ok`, and check the process exit code when automating.
It imports the bundled Qt engine, starts the local API, processes a synthetic signal
using actual weights, exports audio and checks lengths and the residual identity.
It makes no assertion about voice separation quality. Add `--offline` to prohibit
model downloads once the test-data directory already contains validated weights.

Third-party shared libraries remain replaceable; maintain compatible Python/Qt ABIs.
Rebuild the application when changing ABI versions. Original library source locations
and licenses are listed in `LICENSES/LIBRARY_SOURCES.md` and the release notice folder.

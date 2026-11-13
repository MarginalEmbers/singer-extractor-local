# Windows desktop build

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

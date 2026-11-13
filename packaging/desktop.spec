# Build from a clean environment with the pinned [desktop,build] extras.
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parent
metadata = []
for name in ("torch", "numpy", "scipy", "soundfile", "fastapi", "uvicorn", "gdown"):
    metadata += copy_metadata(name)

a = Analysis(
    [str(root / "desktop_app.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "singer_extractor" / "web"), "singer_extractor/web"),
        (str(root / "models" / "manifest.json"), "models"),
        *metadata,
    ],
    hiddenimports=[
        "uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan.on", "anyio._backends._asyncio",
    ],
    hookspath=[str(root / "packaging" / "hooks")],
    excludes=["pytest", "IPython", "notebook", "jupyter", "matplotlib", "tkinter", "PyQt5", "PyQt6"],
    noarchive=False,
)
# Qt uses Windows' own ICU. Never ship an unrelated ICU found on a developer PATH.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {"icuuc.dll", "icuin.dll", "icudt.dll"}
              and not any(unused in entry[0].lower() for unused in ("virtualkeyboard", "quick3d"))]
for destination, source, kind in a.binaries:
    if "codexprimaryruntime" in source.lower():
        raise RuntimeError(f"Unexpected host dependency: {destination}")
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="哦，金金的音道分离", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    icon=str(root / "singer_extractor" / "web" / "app.ico"),
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="JinjinAudio",
)

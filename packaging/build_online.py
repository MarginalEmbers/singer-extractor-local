"""Build the small Windows bootstrap package without bundling Python or PyTorch."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def make_archive(destination):
    files = json.loads((destination / "package-files.json").read_text(encoding="utf8"))
    archive = destination.parent / (destination.name + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name in sorted(
            [*files, "package-files.json", "哦，金金的音道分离.exe", "检查运行环境.exe"]
        ):
            # Never include runtime-generated caches, logs, songs or model downloads.
            package.write(destination / name, destination.name + "/" + name)
    print(archive)


def build(destination, uv):
    if os.name != "nt":
        raise RuntimeError("Build the Windows launcher on Windows.")
    if destination.exists():
        raise FileExistsError("Use a new empty build destination: " + str(destination))
    if "uv 0.12.7 " not in subprocess.check_output([uv, "--version"], text=True):
        raise RuntimeError("This release pins uv 0.12.7.")
    destination.mkdir(parents=True)
    app = destination / "app"
    app.mkdir()
    shutil.copytree(
        ROOT / "singer_extractor",
        app / "singer_extractor",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (app / "models").mkdir()
    shutil.copy2(ROOT / "models/manifest.json", app / "models/manifest.json")
    shutil.copy2(ROOT / "desktop_app.py", app / "desktop_app.py")
    for name in ("requirements-runtime.lock", "requirements-ui.lock"):
        shutil.copy2(ROOT / name, destination / name)
    (destination / "tools").mkdir()
    shutil.copy2(uv, destination / "tools/uv.exe")
    shutil.copytree(ROOT / "LICENSES", destination / "LICENSES")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, destination / name)
    shutil.copy2(ROOT / "packaging/online-readme.txt", destination / "先读我.txt")
    files = {
        str(path.relative_to(destination)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }
    manifest = json.dumps(files, ensure_ascii=False, indent=2).encode("utf8")
    (destination / "package-files.json").write_bytes(manifest)
    with tempfile.TemporaryDirectory(prefix="jinjin-build-") as temporary:
        compile_launcher(destination, manifest, Path(temporary) / "BuildInfo.cs")
    make_archive(destination)
    print(destination)


def compile_launcher(destination, manifest, info):
    info.write_text(
        'internal static class BuildInfo { internal const string ManifestHash = "'
        + hashlib.sha256(manifest).hexdigest()
        + '"; }',
        encoding="utf8",
    )
    compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    exe = destination / "哦，金金的音道分离.exe"
    subprocess.run(
        [
            str(compiler),
            "/nologo",
            "/target:winexe",
            "/platform:x64",
            "/optimize+",
            "/reference:System.Windows.Forms.dll",
            "/reference:System.Drawing.dll",
            "/reference:System.Web.Extensions.dll",
            "/out:" + str(exe),
            "/win32manifest:" + str(ROOT / "packaging/launcher.manifest"),
            "/win32icon:" + str(ROOT / "singer_extractor/web/app.ico"),
            str(ROOT / "packaging/Launcher.cs"),
            str(info),
        ],
        check=True,
    )
    shutil.copy2(exe, destination / "检查运行环境.exe")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--uv", type=Path)
    parser.add_argument("--archive-only", action="store_true")
    args = parser.parse_args()
    if args.archive_only:
        make_archive(args.destination.resolve())
    else:
        if not args.uv:
            parser.error("--uv is required when building")
        build(args.destination.resolve(), args.uv.resolve())

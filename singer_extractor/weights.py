"""Fetch only the two pinned public checkpoints; inference never downloads files."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "models" / "manifest.json"


def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_weights(directory):
    directory = Path(directory)
    for item in manifest()["files"]:
        path = directory / item["name"]
        if not path.is_file():
            raise ValueError(f"缺少模型 {item['name']}。请先运行 download_models.bat。")
        if sha256(path) != item["sha256"]:
            raise ValueError(f"模型 {item['name']} 校验失败，请重新下载官方权重。")


def download_weights(directory=None):
    import gdown

    directory = Path(directory or ROOT / "models")
    directory.mkdir(parents=True, exist_ok=True)
    for item in manifest()["files"]:
        target = directory / item["name"]
        if target.exists() and sha256(target) == item["sha256"]:
            print(f"Verified: {target.name}", flush=True)
            continue
        temporary = target.with_suffix(".download")
        try:
            result = gdown.download(
                id=item["drive_id"], output=str(temporary), use_cookies=False, quiet=False
            )
            if not result or sha256(temporary) != item["sha256"]:
                raise RuntimeError(f"下载内容校验失败：{target.name}。未替换已有文件。")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    verify_weights(directory)

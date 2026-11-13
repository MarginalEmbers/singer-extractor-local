"""Pinned author downloads. No third-party model implementation ships in the app."""

import hashlib
import json
import zipfile
from pathlib import Path

from .weights import ROOT, sha256


def model_manifest():
    return json.loads((Path(__file__).with_name("two_stage_manifest.json")).read_text("utf8"))


def verify_assets(directory):
    directory = Path(directory)
    for item in model_manifest()["downloads"]:
        path = directory / item["file"]
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            raise ValueError(f"双阶段模型缺失或校验失败：{item['file']}")


def prepare_assets(directory=None, progress=lambda value, text: None, download=True):
    """Validate archives before extracting an explicit allowlist of inference files."""
    directory = Path(directory or ROOT / "models/two-stage")
    directory.mkdir(parents=True, exist_ok=True)
    config = model_manifest()
    total = sum(item["bytes"] for item in config["downloads"])
    completed = 0
    for item in config["downloads"]:
        path = directory / item["file"]
        progress(completed / total, f"正在校验模型：{path.name}")
        valid = (
            path.is_file()
            and path.stat().st_size == item["bytes"]
            and sha256(path) == item["sha256"]
        )
        if not valid:
            if not download:
                raise ValueError(f"双阶段模型缺失或校验失败：{path.name}")
            import requests

            temporary = path.with_suffix(path.suffix + ".part")
            try:
                received = 0
                digest = hashlib.sha256()
                with requests.get(item["url"], stream=True, timeout=(20, 120)) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as output:
                        for block in response.iter_content(1024 * 1024):
                            if not block:
                                continue
                            received += len(block)
                            if received > item["bytes"]:
                                raise ValueError("模型下载大小不符，没有安装。")
                            output.write(block)
                            digest.update(block)
                            progress(
                                (completed + received) / total,
                                f"下载 {path.name}：{received / 1e6:.1f} / {item['bytes'] / 1e6:.1f} MB",
                            )
                if received != item["bytes"] or digest.hexdigest() != item["sha256"]:
                    raise ValueError(f"模型下载校验失败：{path.name}，请重试。")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        completed += item["bytes"]
        # Do not extract arbitrary paths, training code, demos or user data.
        if "members" in item:
            with zipfile.ZipFile(path) as archive:
                for member, relative in item["members"].items():
                    data = archive.read(item["prefix"] + "/" + member)
                    target = directory / relative
                    if not target.resolve().is_relative_to(directory.resolve()):
                        raise ValueError("模型路径无效。")
                    if not target.is_file() or target.read_bytes() != data:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        temporary = target.with_suffix(target.suffix + ".part")
                        temporary.write_bytes(data)
                        temporary.replace(target)
    progress(1, "双阶段模型与代码校验通过")
    return directory

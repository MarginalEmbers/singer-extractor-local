"""Startup checks that work before importing any optional runtime dependency."""

import argparse
import importlib
import importlib.metadata
import json
import sys
import tempfile
from pathlib import Path


def dependency_problems(lock, version=importlib.metadata.version):
    problems = []
    for line in Path(lock).read_text(encoding="utf8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==", 1)
        try:
            actual = version(name)
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"缺少 {name} {expected}")
        else:
            if actual != expected:
                problems.append(f"{name} 需要 {expected}，当前为 {actual}")
    return problems


def startup_advice(error):
    message = str(error)
    lower = message.lower()
    if isinstance(error, PermissionError) or "permission denied" in lower:
        return "无法写入文件。请把软件完整解压到有写入权限的文件夹，再重试。"
    if "no space" in lower or "磁盘空间" in message or "disk full" in lower:
        return "磁盘空间不足。请清理运行环境所在盘和软件所在盘的空间，再重试。"
    if "dll" in lower or isinstance(error, (ImportError, ModuleNotFoundError)):
        return (
            "运行库缺失或损坏。请打开“检查运行环境.exe”，点击“修复运行环境”。"
            "若仍提示 DLL 错误，请通过“VC++ 运行库”入口安装微软 x64 运行库。"
        )
    if "cuda" in lower or "nvidia" in lower:
        return "GPU 未能工作。请更新 NVIDIA 驱动并重启电脑，再检查环境；也可选择 CPU。"
    if "模型" in message or any(word in lower for word in ("download", "connection", "ssl")):
        return "模型尚未准备成功。请检查联网和作者下载地址的可访问性，再点击重试。"
    return "请查看“帮助 → 打开日志文件夹”中的详细错误，再重试。"


def diagnose(data_dir, lock):
    report = {"runtime_ok": False, "cuda_ok": False, "models_ok": False, "checks": []}

    def add(name, ok, detail, action=""):
        report["checks"].append(dict(name=name, ok=ok, detail=detail, action=action))

    python_ok = sys.version_info[:2] == (3, 11) and sys.maxsize > 2**32
    add("Python", python_ok, sys.version.split()[0], "需要 Python 3.11 x64；点击安装或修复。")
    directory = Path(data_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=directory):
            pass
        writable = True
        add("数据目录", True, str(directory))
    except OSError as exc:
        writable = False
        add("数据目录", False, str(exc), startup_advice(exc))
    problems = dependency_problems(lock)
    report["dependency_problems"] = problems
    add(
        "运行库版本",
        not problems,
        f"缺少或版本不符的依赖共 {len(problems)} 项，详情见 environment.json。"
        if problems
        else "固定版本检查通过",
        "点击安装或修复运行环境。",
    )
    if not python_ok or problems:
        return report
    try:
        for module in (
            "numpy",
            "scipy.signal",
            "soundfile",
            "fastapi",
            "uvicorn",
            "gdown",
            "PySide6.QtWidgets",
            "PySide6.QtWebEngineWidgets",
            "torch",
        ):
            importlib.import_module(module)
        import torch

        add("运行库加载", True, "音频、桌面界面和 PyTorch 均可加载")
        report["runtime_ok"] = writable
    except Exception as exc:
        add("运行库加载", False, str(exc), startup_advice(exc))
        return report
    try:
        if torch.version.cuda != "12.8":
            raise RuntimeError("需要 PyTorch CUDA 12.8 构建，请修复运行环境。")
        if not torch.cuda.is_available():
            raise RuntimeError("未检测到可用 NVIDIA GPU，或驱动不可用。")
        # Exercise both CUDA FFT and cuDNN RNN, which are used by the actual model.
        with torch.inference_mode():
            wave = torch.ones(1024, device="cuda")
            torch.fft.rfft(wave)
            recurrent = torch.nn.LSTM(8, 8, 2).eval().cuda()
            output, _ = recurrent(torch.ones(8, 1, 8, device="cuda"))
            if not torch.isfinite(output).all().item():
                raise RuntimeError("CUDA 计算返回非有限数值。")
            torch.cuda.synchronize()
        report["cuda_ok"] = True
        report["cuda_architectures"] = torch.cuda.get_arch_list()
        add("GPU 加速", True, torch.cuda.get_device_name(0) + " · CUDA / FFT / cuDNN 检查通过")
    except Exception as exc:
        add(
            "GPU 加速",
            False,
            str(exc),
            "更新 NVIDIA 驱动并重启；运行库错误可修复，也可用 CPU 继续。",
        )
    from .weights import verify_weights

    try:
        verify_weights(directory / "models")
        report["models_ok"] = True
        add("模型文件", True, "作者模型 SHA-256 校验通过")
    except ValueError as exc:
        add("模型文件", False, str(exc), "进入软件后自动下载或重新下载约 29 MB 模型，请保持联网。")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose(args.data_dir, args.lock)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    return 0 if report["runtime_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

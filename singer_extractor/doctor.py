import platform

import torch

from .weights import ROOT, verify_weights
from .two_stage_assets import verify_assets


def diagnose():
    result = {
        "python": platform.python_version(),
        "system": platform.system(),
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
    }
    if result["cuda_available"]:
        result["gpu"] = torch.cuda.get_device_name(0)
        try:
            sample = torch.ones((32, 32), device="cuda")
            result["gpu_compute_ok"] = float((sample @ sample).mean()) == 32.0
        except RuntimeError as exc:
            result["gpu_compute_ok"] = False
            result["gpu_error"] = str(exc)
    try:
        verify_weights(ROOT / "models")
        result["weights"] = "verified"
    except ValueError as exc:
        result["weights"] = str(exc)
    try:
        verify_assets(ROOT / "models/two-stage")
        result["two_stage_weights"] = "verified"
    except ValueError as exc:
        result["two_stage_weights"] = str(exc)
    return result

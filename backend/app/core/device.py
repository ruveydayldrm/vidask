"""Hardware detection: use the GPU only when it is actually big enough."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class DeviceInfo:
    device: str  # "cuda" | "cpu"
    reason: str
    gpu_name: str | None = None
    vram_gb: float | None = None


@lru_cache
def detect_device(preference: str = "auto", min_vram_gb: float = 4.0) -> DeviceInfo:
    if preference == "cpu":
        return DeviceInfo("cpu", "forced by DEVICE=cpu")
    try:
        import torch
    except ImportError:  # pragma: no cover - torch is a transitive dependency
        return DeviceInfo("cpu", "torch not installed")

    if not torch.cuda.is_available():
        info = DeviceInfo("cpu", "CUDA not available to torch")
    else:
        props = torch.cuda.get_device_properties(0)
        vram = props.total_memory / 1024**3
        if preference == "cuda" or vram >= min_vram_gb:
            info = DeviceInfo("cuda", "CUDA GPU detected", props.name, round(vram, 1))
        else:
            info = DeviceInfo(
                "cpu",
                f"GPU has {vram:.1f} GB VRAM (< {min_vram_gb} GB required)",
                props.name,
                round(vram, 1),
            )
    log.info("device.detected", device=info.device, reason=info.reason, gpu=info.gpu_name)
    return info


def whisper_compute_type(device: str, configured: str) -> str:
    if configured != "auto":
        return configured
    return "float16" if device == "cuda" else "int8"

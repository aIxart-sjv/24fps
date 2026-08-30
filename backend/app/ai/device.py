"""
Inference device selection (task Phase 13 scope: "The system must work on
the development laptop even without CUDA... If GPU acceleration is
available, allow inference to use it without making the architecture
GPU-dependent... Report which device was actually used for the job.").

`torch` is an optional runtime dependency here in the same sense FFmpeg is
in `app.media.ffmpeg`: if it cannot be imported, CPU-only operation is
still reported cleanly rather than crashing.
"""

from __future__ import annotations

__all__ = ["is_cuda_available", "select_device"]


def is_cuda_available() -> bool:
    """Whether a CUDA-capable GPU is usable by `torch` in this process.

    Returns:
        `True` only if `torch` imports and reports an available CUDA
        device. Any import or runtime failure is treated as "no GPU",
        never propagated as an exception.
    """
    try:
        import torch
    except ImportError:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def select_device(*, prefer_gpu: bool = True) -> str:
    """Choose the inference device to use.

    Args:
        prefer_gpu: When `True` (the default), use CUDA if available.
            When `False`, always select CPU even if a GPU is present
            (e.g. an explicit job parameter requesting CPU-only
            execution).

    Returns:
        `"cuda:0"` if a GPU is selected, else `"cpu"`. This exact string
        is recorded as the job's `worker` field for reproducibility.
    """
    if prefer_gpu and is_cuda_available():
        return "cuda:0"
    return "cpu"

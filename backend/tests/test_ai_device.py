"""Tests for app/ai/device.py (Phase 13)."""

from __future__ import annotations

from app.ai.device import is_cuda_available, select_device


def test_select_device_returns_cpu_when_gpu_not_preferred() -> None:
    assert select_device(prefer_gpu=False) == "cpu"


def test_select_device_matches_cuda_availability() -> None:
    device = select_device(prefer_gpu=True)
    if is_cuda_available():
        assert device == "cuda:0"
    else:
        assert device == "cpu"


def test_is_cuda_available_never_raises() -> None:
    # This environment has a real CUDA-capable GPU (verified in this
    # session), so this should report True -- but the important contract
    # this test protects is "never raises", not a specific hardware fact.
    assert isinstance(is_cuda_available(), bool)

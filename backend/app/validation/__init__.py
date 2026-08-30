"""
Validation / ground-truth layer (Phase 14, Master Specification Section
36 "Validation Engine").

Pure, DB-free, HTTP-free package: measures whether the forensic/AI
pipeline's actual output matches an independently-known ground truth,
using explicit, documented metrics (never model confidence, never
identity). `app.core.validation_manager` is the DB-aware orchestration
layer built on top of this package, mirroring every prior phase's
pure-engine/DB-manager split (Phase 9-13).
"""

from __future__ import annotations

from app.validation.benchmark import MetricRecord, ValidationRunResult, ValidationType
from app.validation.metrics import ClassificationCounts, f1, precision, recall

__all__ = [
    "ClassificationCounts",
    "MetricRecord",
    "ValidationRunResult",
    "ValidationType",
    "f1",
    "precision",
    "recall",
]

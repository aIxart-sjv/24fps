"""
Deterministic visual-attribute search (Phase 23, "Natural-Language Video
Search").

============================================================================
WHY THIS APPROACH, NOT A VISION-LANGUAGE MODEL
============================================================================
Task Phase 23 scope, "Required Feature — Natural-Language Video Search"
explicitly requires investigating whether a heavier approach (a
vision-language model such as a 3B-parameter LocateAnything-class model)
is actually appropriate before building it, listing hardware, licensing,
offline availability, and latency as things to check first.

This sandbox/deployment has no confirmed GPU, no confirmed internet
access to pull a multi-gigabyte model weight file, and no evidence any
such model is already vendored in this repository (`app/ai/model_registry.py`
downloads only the existing YOLO object/face detection weights on first
use). Introducing a VLM dependency here would be exactly the "do NOT
introduce it blindly" the task itself warns against.

Instead, this module builds the smallest deterministic capability that
concretely serves the documented use case: `docs/SIH_NTRO_REQUIREMENTS.md`'s
own "Re-identification" section (`Level 3`/`Level 4` appearance
correlation) names *clothing color* as the primary practical Re-ID
signal, and explicitly warns "there could be 20 people wearing red
shirts" / "appearance similarity is evidence, not identity proof" --
this module's own docstrings and every result it produces repeat that
warning verbatim in spirit. It requires no model weights, no GPU, no
network access, and no license beyond OpenCV (already a project
dependency): it buckets the already-computed, already-persisted Phase 13
`AIResult.class_name == "person"` detections' upper-body region into a
small set of named colors using HSV thresholds, and matches that against
a color keyword parsed out of the officer's query.

This is NOT semantic/open-vocabulary search. It cannot answer "a man
carrying a suitcase near the entrance" -- only a closed vocabulary of
(color, object class) pairs. That limitation is deliberate and reported
honestly (`SUPPORTED_COLORS`/`SUPPORTED_CLASSES` are returned to the
caller so the frontend can show exactly what is and is not supported)
rather than silently failing or fabricating a match.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

__all__ = [
    "ATTRIBUTE_SEARCH_METHOD",
    "ATTRIBUTE_SEARCH_VERSION",
    "SUPPORTED_CLASSES",
    "SUPPORTED_COLORS",
    "QueryAttributes",
    "classify_dominant_color",
    "parse_query",
]

#: Recorded on every search result for traceability (task Phase 23 scope,
#: "Search Traceability": "Store search parameters and model information").
#: Not a machine-learned model -- a versioned deterministic algorithm, so
#: "model_version" here means "this classifier's own logic version".
ATTRIBUTE_SEARCH_METHOD = "deterministic_hsv_color_attribute_match"
ATTRIBUTE_SEARCH_VERSION = "1.0"

#: HSV hue ranges (OpenCV's 0-179 hue scale) for each named color, checked
#: only when a pixel's saturation/value are not already classified as
#: black/white/gray below. Order matters: red wraps around 0/179.
_HUE_RANGES: tuple[tuple[str, int, int], ...] = (
    ("red", 0, 9),
    ("orange", 10, 22),
    ("yellow", 23, 35),
    ("green", 36, 78),
    ("cyan", 79, 100),
    ("blue", 101, 130),
    ("purple", 131, 155),
    ("pink", 156, 169),
    ("red", 170, 179),
)

#: Colors this module can ever report -- a closed, documented vocabulary
#: (task Phase 23 scope: never claim generalized accuracy). Black/white/
#: gray are saturation/value buckets, not hue buckets.
SUPPORTED_COLORS: tuple[str, ...] = (
    "red",
    "orange",
    "yellow",
    "green",
    "cyan",
    "blue",
    "purple",
    "pink",
    "black",
    "white",
    "gray",
)

#: Object classes this module accepts in a query, mapped to the exact
#: `AIResult.class_name` values `app.ai.object_detection` (COCO-trained
#: YOLO) can produce. A query naming anything else is honestly reported
#: as unsupported rather than silently defaulting to "person".
SUPPORTED_CLASSES: dict[str, str] = {
    "person": "person",
    "man": "person",
    "woman": "person",
    "guy": "person",
    "individual": "person",
    "people": "person",
    "car": "car",
    "vehicle": "car",
    "truck": "truck",
    "bus": "bus",
    "motorcycle": "motorcycle",
    "bike": "bicycle",
    "bicycle": "bicycle",
    "backpack": "backpack",
    "bag": "handbag",
    "handbag": "handbag",
    "suitcase": "suitcase",
}

_LOW_SATURATION_GRAYSCALE_THRESHOLD = 40
_BLACK_VALUE_THRESHOLD = 50
_WHITE_VALUE_THRESHOLD = 200


@dataclass(frozen=True)
class QueryAttributes:
    """What could be deterministically parsed out of a free-text query.

    `color`/`object_class` are `None` when the query names nothing this
    module's closed vocabulary recognizes -- never guessed.
    """

    raw_query: str
    color: str | None
    object_class: str | None
    recognized_words: list[str] = field(default_factory=list)


def parse_query(query: str) -> QueryAttributes:
    """Extract a known color and object class from free text.

    Pure string matching against `SUPPORTED_COLORS`/`SUPPORTED_CLASSES` --
    no NLP model, no network call, fully deterministic and offline.
    """
    words = [w.strip(".,!?").lower() for w in query.split()]
    color = next((w for w in words if w in SUPPORTED_COLORS or w == "grey"), None)
    if color == "grey":
        color = "gray"
    object_class = next((SUPPORTED_CLASSES[w] for w in words if w in SUPPORTED_CLASSES), None)
    recognized = [
        w for w in words if w in SUPPORTED_COLORS or w in SUPPORTED_CLASSES or w == "grey"
    ]
    return QueryAttributes(
        raw_query=query, color=color, object_class=object_class, recognized_words=recognized
    )


def classify_dominant_color(bgr_region: np.ndarray) -> tuple[str | None, float]:
    """Classify a cropped BGR image region's dominant color.

    Args:
        bgr_region: A cropped region (e.g. the upper-body portion of a
            person detection's bounding box), in OpenCV's default BGR
            pixel order.

    Returns:
        `(color_name, match_fraction)` -- `color_name` is one of
        `SUPPORTED_COLORS`, or `None` if the region is empty/degenerate.
        `match_fraction` is the fraction of the region's pixels that fell
        into the winning bucket (0.0-1.0) -- used as this classifier's own
        confidence signal, never a detection-model confidence score.
    """
    if bgr_region.size == 0 or bgr_region.shape[0] == 0 or bgr_region.shape[1] == 0:
        return None, 0.0

    hsv = cv2.cvtColor(bgr_region, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(np.int32)
    sat = hsv[:, :, 1].astype(np.int32)
    val = hsv[:, :, 2].astype(np.int32)

    total = hue.size
    buckets: dict[str, int] = {name: 0 for name in SUPPORTED_COLORS}

    grayscale_mask = sat < _LOW_SATURATION_GRAYSCALE_THRESHOLD
    buckets["black"] += int(
        np.count_nonzero(np.logical_and(grayscale_mask, val < _BLACK_VALUE_THRESHOLD))
    )
    buckets["white"] += int(
        np.count_nonzero(np.logical_and(grayscale_mask, val >= _WHITE_VALUE_THRESHOLD))
    )
    buckets["gray"] += int(
        np.count_nonzero(
            np.logical_and(
                grayscale_mask,
                np.logical_and(val >= _BLACK_VALUE_THRESHOLD, val < _WHITE_VALUE_THRESHOLD),
            )
        )
    )

    chromatic_mask = np.logical_not(grayscale_mask)
    for name, lo, hi in _HUE_RANGES:
        in_range = np.logical_and(hue >= lo, hue <= hi)
        buckets[name] += int(np.count_nonzero(np.logical_and(chromatic_mask, in_range)))

    winner = max(buckets, key=lambda name: buckets[name])
    if buckets[winner] == 0:
        return None, 0.0
    return winner, buckets[winner] / total

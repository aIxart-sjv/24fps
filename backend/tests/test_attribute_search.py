"""Tests for app/ai/attribute_search.py (Phase 23) -- pure, no DB/HTTP."""

from __future__ import annotations

import numpy as np

from app.ai.attribute_search import classify_dominant_color, parse_query


def test_parse_query_recognizes_color_and_defaults_object_class() -> None:
    attrs = parse_query("red shirt guy")
    assert attrs.color == "red"
    assert attrs.object_class == "person"


def test_parse_query_recognizes_grey_as_gray() -> None:
    attrs = parse_query("person wearing a grey jacket")
    assert attrs.color == "gray"


def test_parse_query_recognizes_vehicle_class() -> None:
    attrs = parse_query("blue car near the entrance")
    assert attrs.color == "blue"
    assert attrs.object_class == "car"


def test_parse_query_with_no_recognized_color_returns_none() -> None:
    attrs = parse_query("someone suspicious near the door")
    assert attrs.color is None


def _solid_color_bgr(bgr: tuple[int, int, int], size: int = 40) -> np.ndarray:
    region = np.zeros((size, size, 3), dtype=np.uint8)
    region[:, :] = bgr
    return region


def test_classify_dominant_color_detects_pure_red() -> None:
    # OpenCV BGR order: pure red is (0, 0, 255).
    region = _solid_color_bgr((0, 0, 255))
    color, confidence = classify_dominant_color(region)
    assert color == "red"
    assert confidence > 0.9


def test_classify_dominant_color_detects_pure_blue() -> None:
    region = _solid_color_bgr((255, 0, 0))
    color, confidence = classify_dominant_color(region)
    assert color == "blue"
    assert confidence > 0.9


def test_classify_dominant_color_detects_black() -> None:
    region = _solid_color_bgr((0, 0, 0))
    color, _confidence = classify_dominant_color(region)
    assert color == "black"


def test_classify_dominant_color_detects_white() -> None:
    region = _solid_color_bgr((255, 255, 255))
    color, _confidence = classify_dominant_color(region)
    assert color == "white"


def test_classify_dominant_color_empty_region_returns_none() -> None:
    region = np.zeros((0, 0, 3), dtype=np.uint8)
    color, confidence = classify_dominant_color(region)
    assert color is None
    assert confidence == 0.0

"""Tests for scan crop helpers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.routers.stories import _enhance_scan_image, _normalize_crop_box, _scan_cache_key


def test_normalize_crop_box_accepts_valid_normalized_values() -> None:
    box = _normalize_crop_box(0.1, 0.2, 0.5, 0.6)

    assert box == {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6}


def test_normalize_crop_box_rejects_out_of_range_values() -> None:
    assert _normalize_crop_box(-0.1, 0.2, 0.5, 0.5) is None
    assert _normalize_crop_box(0.1, 0.2, 1.2, 0.5) is None
    assert _normalize_crop_box(0.8, 0.8, 0.4, 0.4) is None
    assert _normalize_crop_box(0.1, 0.2, 0.01, 0.5) is None


def test_enhance_scan_image_creates_output_file(tmp_path: Path) -> None:
    source = tmp_path / "page.jpg"
    Image.new("RGB", (120, 180), color=(180, 175, 160)).save(source)

    enhanced = _enhance_scan_image(source)

    assert enhanced.exists()
    assert enhanced != source
    enhanced.unlink(missing_ok=True)


def test_scan_cache_key_changes_with_crop_box() -> None:
    image_bytes = b"demo-image"
    key1 = _scan_cache_key(image_bytes, None, "温柔", "3-6", "fast", {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.6})
    key2 = _scan_cache_key(image_bytes, None, "温柔", "3-6", "fast", {"x": 0.2, "y": 0.1, "width": 0.5, "height": 0.6})

    assert key1 != key2

"""Tests for scan crop helpers."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.live_scan_runtime_service import enhance_scan_image, normalize_crop_box, scan_cache_key


def test_normalize_crop_box_accepts_valid_normalized_values() -> None:
    box = normalize_crop_box(0.1, 0.2, 0.5, 0.6)

    assert box == {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6}


def test_normalize_crop_box_rejects_out_of_range_values() -> None:
    assert normalize_crop_box(-0.1, 0.2, 0.5, 0.5) is None
    assert normalize_crop_box(0.1, 0.2, 1.2, 0.5) is None
    assert normalize_crop_box(0.8, 0.8, 0.4, 0.4) is None
    assert normalize_crop_box(0.1, 0.2, 0.01, 0.5) is None


def test_enhance_scan_image_creates_output_file(tmp_path: Path) -> None:
    source = tmp_path / "page.jpg"
    Image.new("RGB", (120, 180), color=(180, 175, 160)).save(source)

    enhanced = enhance_scan_image(source)

    assert enhanced.exists()
    assert enhanced != source
    enhanced.unlink(missing_ok=True)


def test_scan_cache_key_changes_with_crop_box() -> None:
    image_bytes = b"demo-image"
    key1 = scan_cache_key(
        image_bytes,
        None,
        "温柔",
        "3-6",
        "fast",
        crop_box={"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.6},
    )
    key2 = scan_cache_key(
        image_bytes,
        None,
        "温柔",
        "3-6",
        "fast",
        crop_box={"x": 0.2, "y": 0.1, "width": 0.5, "height": 0.6},
    )

    assert key1 != key2

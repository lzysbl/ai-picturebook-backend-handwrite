"""Tests for the live scan storytelling tone."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.live_story_service import build_contextual_live_scan_story


def test_live_scan_story_reads_like_storytelling() -> None:
    story = build_contextual_live_scan_story(
        recent_pages=[],
        current_page={
            "roles": ["小兔子"],
            "actions": ["望着远处"],
            "objects": ["一盏小灯"],
            "texts": ["回家"],
            "scene": "森林小路",
            "mood": "安静",
        },
        narration_style="温柔",
        audience_age="3-6",
        extra_prompt="突出回家的感觉",
    )

    assert "故事从森林小路慢慢开始" in story
    assert "小兔子望着远处" in story
    assert "一盏小灯" in story
    assert "回家" in story
    assert "突出回家的感觉" in story
    assert "识别结果" not in story
    assert "图像中" not in story

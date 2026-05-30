"""AI 服务兼容入口测试。

覆盖范围：
- 验证 `ai_service.py` 暴露的图像分析入口能返回页面结构信息。
- 验证规则型故事质量评价能计算页面覆盖和可读性指标。

关联模块：
- `app/services/ai_service.py`
- `app/services/vision_analysis_service.py`
- `app/services/story_quality_service.py`

运行方式：
- `pytest tests/test_ai_service.py`
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.services.ai_service import analyze_images, evaluate_story_quality


def test_analyze_images_mock_returns_expected_page_metadata(tmp_path: Path) -> None:
    """Mock analysis should preserve page order and expose image metadata."""

    image_path = tmp_path / "page1.png"
    Image.new("RGB", (32, 24), color=(255, 240, 200)).save(image_path)

    original_provider = settings.ai_provider
    settings.ai_provider = "mock"
    try:
        result = asyncio.run(analyze_images([str(image_path)]))
    finally:
        settings.ai_provider = original_provider

    assert len(result) == 1
    page = result[0]
    assert page["page"] == 1
    assert page["image_path"] == str(image_path)
    assert page["width"] == 32
    assert page["height"] == 24
    assert page["mode"] == "RGB"
    assert "brightness" in page


def test_evaluate_story_quality_scores_page_coverage_and_readability() -> None:
    """Quality scoring should reflect page coverage and return evidence fields."""

    analysis_result = [{"page": 1}, {"page": 2}, {"page": 3}]
    story_content = "第1页：小熊出门。第2页：它看见了花。"

    quality = evaluate_story_quality(analysis_result, story_content)

    assert quality["scores"]["coherence"] == 67
    assert quality["scores"]["overall"] >= 60
    assert quality["evidence"]["expected_pages"] == [1, 2, 3]
    assert quality["evidence"]["referenced_pages"] == [1, 2]
    assert quality["evidence"]["page_hit_count"] == 2

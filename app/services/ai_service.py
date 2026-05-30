"""AI 兼容入口服务。

职责：
- 给旧代码和测试用例提供统一导入入口，避免调用方直接关心具体服务文件。
- 目前转发图像分析能力和规则型故事质量评价能力。

前端关联：
- 无直接页面调用。
- 实际页面入口在 `/ui/generate`、`/ui/camera`、`/ui/history`，分别通过
  `vision_analysis_service`、`story_generation_service`、`story_quality_service`
  等具体服务完成业务。
"""

from __future__ import annotations

from app.services.story_quality_service import evaluate_story_quality
from app.services.vision_analysis_service import ProgressCallback, analyze_images

__all__ = ["ProgressCallback", "analyze_images", "evaluate_story_quality"]

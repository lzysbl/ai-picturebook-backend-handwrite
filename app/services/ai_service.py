"""Compatibility facade for AI-related analysis and rule-based scoring."""

from __future__ import annotations

from app.services.story_quality_service import evaluate_story_quality
from app.services.vision_analysis_service import ProgressCallback, analyze_images

__all__ = ["ProgressCallback", "analyze_images", "evaluate_story_quality"]

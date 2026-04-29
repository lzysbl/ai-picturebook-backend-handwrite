"""Tests for full story quality evaluation and thesis-facing metrics."""

from __future__ import annotations

import asyncio

from app.services.eval_service import evaluate_story_full


def test_evaluate_story_full_includes_paper_metrics() -> None:
    """The aggregated quality payload should expose paper-facing metrics."""

    analysis_result = [
        {"page": 1, "角色": ["小熊"], "关键物体": ["花"]},
        {"page": 2, "角色": ["小熊"], "关键物体": ["树"]},
        {"page": 3, "角色": ["小熊"], "关键物体": ["月亮"]},
    ]
    story_content = "第1页：小熊出门。第2页：小熊看见花。第4页：小狐狸来了。"

    quality = asyncio.run(
        evaluate_story_full(
            analysis_result=analysis_result,
            story_content=story_content,
            include_judge=False,
            judge_samples=None,
        )
    )

    paper = quality["paper_metrics"]
    assert paper["page_hit_count"] == 2
    assert paper["page_coverage_ratio"] == 0.6667
    assert paper["expected_pages"] == [1, 2, 3]
    assert paper["referenced_pages"] == [1, 2, 4]
    assert paper["hallucination_count"] >= 0
    assert "repeat_3gram_ratio" in paper
    assert "distinct_2" in paper

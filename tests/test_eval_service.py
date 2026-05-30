"""故事质量评价服务测试。

覆盖范围：
- 验证完整质量评价结果包含论文实验可用的指标字段。
- 覆盖规则指标和可选评审输出的组装逻辑。

关联模块：
- `app/services/eval_service.py`
- `app/services/story_quality_service.py`
- `/ui/history` 故事质量评价面板。

运行方式：
- `pytest tests/test_eval_service.py`
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

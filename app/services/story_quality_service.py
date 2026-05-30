"""规则型故事质量评价服务。

职责：
- 不依赖大模型，使用规则指标评估故事质量。
- 检查页面覆盖、内容重复、语言可读性、儿童适龄性等。
- 为论文实验章节生成可解释的质量指标。

前端关联：
- `/ui/history`：故事质量评价面板中的基础指标。
- `/ui/generate`、`/ui/camera`：故事生成或保存后可用于快速质量反馈。

主要路由：
- `app/routers/stories.py`：质量评价相关接口通过 `eval_service` 间接调用。
"""

from __future__ import annotations

import re
from typing import Any


def _extract_page_mentions(story_content: str) -> set[int]:
    text = story_content or ""
    pattern = re.compile(r"(?:\u7b2c\s*)?(\d{1,3})\s*\u9875")
    page_numbers: set[int] = set()
    for match in pattern.finditer(text):
        try:
            page_numbers.add(int(match.group(1)))
        except (TypeError, ValueError):
            continue
    return page_numbers


def _build_readability_units(story_content: str) -> list[str]:
    text = (story_content or "").strip()
    if not text:
        return []

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("《") and line.endswith("》"):
            continue
        if line.startswith("文：") or line.startswith("文:"):
            continue
        line = re.sub(r"^\s*第\s*\d+\s*页\s*[：:]\s*", "", line)
        if line:
            cleaned_lines.append(line)

    merged = "\n".join(cleaned_lines)
    if not merged.strip():
        return []

    sentence_parts = re.split(r"[。！？!?]+", merged)
    units: list[str] = []
    for part in sentence_parts:
        part = part.strip()
        if not part:
            continue
        clauses = re.split(r"[，、；：:]+", part)
        for clause in clauses:
            clause = re.sub(r"\s+", "", clause.strip())
            if clause:
                units.append(clause)
    return units


def _age_score_from_readability(story_content: str) -> tuple[int, dict[str, Any]]:
    lines = [line.strip() for line in (story_content or "").splitlines() if line.strip()]
    avg_line_len = sum(len(line) for line in lines) / len(lines) if lines else 0.0

    units = _build_readability_units(story_content)
    if not units:
        return 60, {
            "avg_line_length": round(avg_line_len, 2),
            "avg_unit_length": 0.0,
            "unit_count": 0,
            "long_unit_ratio": 1.0,
            "very_long_unit_ratio": 1.0,
        }

    lengths = [len(unit) for unit in units]
    unit_count = len(lengths)
    avg_unit_len = sum(lengths) / unit_count
    long_unit_ratio = sum(1 for n in lengths if n > 26) / unit_count
    very_long_unit_ratio = sum(1 for n in lengths if n > 40) / unit_count

    score = 95.0
    if avg_unit_len > 18:
        score -= (avg_unit_len - 18) * 1.3
    if long_unit_ratio > 0.35:
        score -= (long_unit_ratio - 0.35) * 45
    if very_long_unit_ratio > 0.10:
        score -= (very_long_unit_ratio - 0.10) * 90

    merged_len = len(re.sub(r"\s+", "", story_content or ""))
    if merged_len > 180 and unit_count < 8:
        score -= 8

    age_score = max(60, min(98, round(score)))
    evidence = {
        "avg_line_length": round(avg_line_len, 2),
        "avg_unit_length": round(avg_unit_len, 2),
        "unit_count": unit_count,
        "long_unit_ratio": round(long_unit_ratio, 3),
        "very_long_unit_ratio": round(very_long_unit_ratio, 3),
    }
    return age_score, evidence


def evaluate_story_quality(analysis_result: list[dict[str, Any]], story_content: str) -> dict[str, Any]:
    page_count = len(analysis_result)
    referenced_pages = _extract_page_mentions(story_content)

    expected_pages: set[int] = set()
    for index, item in enumerate(analysis_result, start=1):
        page_no = item.get("page", index)
        if isinstance(page_no, int):
            expected_pages.add(page_no)
        else:
            try:
                expected_pages.add(int(page_no))
            except (TypeError, ValueError):
                expected_pages.add(index)

    if not expected_pages:
        hit_count = 0
        coherence = 0
        page_coverage_ratio = 0.0
        missing_pages: list[int] = []
    else:
        hit_count = len(expected_pages.intersection(referenced_pages))
        coherence = round((hit_count / len(expected_pages)) * 100)
        page_coverage_ratio = round(hit_count / len(expected_pages), 4)
        missing_pages = sorted(expected_pages.difference(referenced_pages))

    age_score, age_evidence = _age_score_from_readability(story_content)
    overall = round(coherence * 0.6 + age_score * 0.4)

    return {
        "scores": {
            "coherence": coherence,
            "age_appropriateness": age_score,
            "overall": overall,
        },
        "evidence": {
            "page_count": page_count,
            "expected_pages": sorted(expected_pages),
            "referenced_pages": sorted(referenced_pages),
            "page_hit_count": hit_count,
            "page_coverage_ratio": page_coverage_ratio,
            "missing_pages": missing_pages,
            **age_evidence,
        },
    }


def build_paper_metrics(
    automatic_quality: dict[str, Any] | None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    automatic_quality = automatic_quality or {}
    metrics = metrics or {}
    scores = automatic_quality.get("scores", {})
    evidence = automatic_quality.get("evidence", {})
    return {
        "overall": scores.get("overall"),
        "coherence": scores.get("coherence"),
        "age_appropriateness": scores.get("age_appropriateness"),
        "page_hit_count": evidence.get("page_hit_count"),
        "page_coverage_ratio": evidence.get("page_coverage_ratio"),
        "expected_pages": evidence.get("expected_pages", []),
        "referenced_pages": evidence.get("referenced_pages", []),
        "missing_pages": evidence.get("missing_pages", []),
        "hallucination_count": metrics.get("hallucination_count"),
        "hallucinated_entities": metrics.get("hallucinated_entities", []),
        "repeat_3gram_ratio": metrics.get("repeat_3gram_ratio"),
        "distinct_2": metrics.get("distinct_2"),
    }


__all__ = ["build_paper_metrics", "evaluate_story_quality"]

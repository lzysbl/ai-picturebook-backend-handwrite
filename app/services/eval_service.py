"""故事质量评估服务：自动指标 + 可选 LLM 评审。"""

from __future__ import annotations

import json
import re
from statistics import mean
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.ai_service import evaluate_story_quality

ROLE_ENTITY_MARKERS = ["熊", "兔", "狐狸", "狼", "虎", "狮", "猴", "象", "猫", "狗", "龙"]
_judge_client: AsyncOpenAI | None = None


def _get_judge_client() -> AsyncOpenAI:
    global _judge_client
    if _judge_client is None:
        _judge_client = AsyncOpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url)
    return _judge_client


def _extract_allowed_entities(analysis_result: list[dict[str, Any]]) -> set[str]:
    allowed: set[str] = {"老鼠", "小老鼠"}
    for item in analysis_result:
        for key in ("角色", "关键物体"):
            values = item.get(key, [])
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                for value in values:
                    text = str(value).strip()
                    if text:
                        allowed.add(text)
    return allowed


def _detect_hallucinated_entities(story_content: str, allowed_entities: set[str]) -> list[str]:
    candidates: set[str] = set()
    pattern = r"[\u4e00-\u9fa5]{1,6}(?:熊|兔|狐狸|狼|虎|狮|猴|象|猫|狗|龙)"
    for match in re.finditer(pattern, story_content):
        token = match.group(0).strip()
        if token:
            candidates.add(token)
    prefix_pattern = r"(?:熊|兔|狐狸|狼|虎|狮|猴|象|猫|狗|龙)[\u4e00-\u9fa5]{1,6}"
    for match in re.finditer(prefix_pattern, story_content):
        token = match.group(0).strip()
        if token:
            candidates.add(token)

    unknown: list[str] = []
    for token in sorted(candidates):
        if token in allowed_entities:
            continue
        if any(allowed and allowed in token for allowed in allowed_entities):
            continue
        if any(marker in token and any(marker in allowed for allowed in allowed_entities) for marker in ROLE_ENTITY_MARKERS):
            continue
        unknown.append(token)
    return unknown


def _repeat_3gram_ratio(story_content: str) -> float:
    text = re.sub(r"\s+", "", story_content)
    if len(text) < 9:
        return 0.0
    grams = [text[i : i + 3] for i in range(len(text) - 2)]
    total = len(grams)
    uniq = len(set(grams))
    if total == 0:
        return 0.0
    return round(max(0.0, (total - uniq) / total), 4)


def _distinct_2(story_content: str) -> float:
    text = re.sub(r"\s+", "", story_content)
    if len(text) < 6:
        return 1.0
    grams = [text[i : i + 2] for i in range(len(text) - 1)]
    total = len(grams)
    uniq = len(set(grams))
    if total == 0:
        return 1.0
    return round(uniq / total, 4)


def _safe_load_analysis(image_analysis: str | list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    if image_analysis is None:
        return []
    if isinstance(image_analysis, list):
        return [item for item in image_analysis if isinstance(item, dict)]
    if isinstance(image_analysis, dict):
        return [image_analysis]
    if isinstance(image_analysis, str):
        try:
            parsed = json.loads(image_analysis)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            return []
    return []


async def _judge_once(analysis_result: list[dict[str, Any]], story_content: str) -> dict[str, Any]:
    if not settings.qwen_api_key:
        raise ValueError("未配置 QWEN_API_KEY，无法进行 LLM 评审")

    payload = {
        "analysis_result": [
            {
                "page": item.get("page"),
                "角色": item.get("角色", []),
                "场景": item.get("场景"),
                "动作": item.get("动作", []),
                "情绪": item.get("情绪"),
                "关键物体": item.get("关键物体", []),
                "画面文字": item.get("画面文字", []),
            }
            for item in analysis_result
        ],
        "story_content": story_content,
    }
    prompt = (
        "你是绘本故事质量评审员。请基于输入的图片分析结果和故事文本打分。\n"
        "请严格输出 JSON，不要输出其它文字，格式如下：\n"
        '{"scores":{"grounding":1,"coherence":1,"readability":1,"age_appropriateness":1,"interestingness":1},"comment":"..."}\n'
        "评分范围均为 1-5 的整数。\n"
        f"输入：{json.dumps(payload, ensure_ascii=False)}"
    )
    client = _get_judge_client()
    completion = await client.chat.completions.create(
        model=settings.judge_model,
        temperature=0.2,
        timeout=90,
        messages=[
            {"role": "system", "content": "你是严谨的故事质量评审助手。"},
            {"role": "user", "content": prompt},
        ],
    )
    text = (completion.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    usage = getattr(completion, "usage", None)
    usage_data = {
        "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
    }
    parsed["usage"] = usage_data
    return parsed


def _estimate_cost_cny(model: str, input_tokens: int, output_tokens: int) -> float:
    # 当前仅估算你项目已用的两个主模型价位（中国内地常见区间）
    # qwen3.6-plus: in 2 / out 12 元 / 百万 token
    # qwen3.6-flash: in 1.2 / out 7.2 元 / 百万 token
    model_lower = model.lower()
    if "plus" in model_lower:
        in_price, out_price = 2.0, 12.0
    else:
        in_price, out_price = 1.2, 7.2
    return round((input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price, 6)


async def evaluate_story_full(
    *,
    analysis_result: list[dict[str, Any]] | None = None,
    image_analysis: str | list[dict[str, Any]] | dict[str, Any] | None = None,
    story_content: str,
    include_judge: bool = False,
    judge_samples: int | None = None,
) -> dict[str, Any]:
    """统一质量评估入口。"""

    if analysis_result is None:
        analysis_result = _safe_load_analysis(image_analysis)

    base_quality = evaluate_story_quality(analysis_result, story_content)

    allowed_entities = _extract_allowed_entities(analysis_result)
    hallucinated_entities = _detect_hallucinated_entities(story_content, allowed_entities)
    repeat_ratio = _repeat_3gram_ratio(story_content)
    distinct2 = _distinct_2(story_content)

    metrics = {
        "repeat_3gram_ratio": repeat_ratio,
        "distinct_2": distinct2,
        "hallucinated_entities": hallucinated_entities,
        "hallucination_count": len(hallucinated_entities),
    }

    response: dict[str, Any] = {
        "automatic": base_quality,
        "metrics": metrics,
    }

    if not include_judge or not settings.judge_enabled:
        response["judge"] = {
            "enabled": False,
            "reason": "未开启 LLM 评审（include_judge=false 或 JUDGE_ENABLED=false）",
        }
        return response

    sample_n = judge_samples or settings.judge_samples
    sample_n = max(1, min(sample_n, 5))
    judge_results: list[dict[str, Any]] = []
    try:
        for _ in range(sample_n):
            judge_results.append(await _judge_once(analysis_result, story_content))
    except Exception as exc:  # noqa: BLE001
        response["judge"] = {
            "enabled": True,
            "model": settings.judge_model,
            "samples": sample_n,
            "error": str(exc),
        }
        return response

    dim_keys = ["grounding", "coherence", "readability", "age_appropriateness", "interestingness"]
    avg_scores: dict[str, float] = {}
    for key in dim_keys:
        vals = [float(item.get("scores", {}).get(key, 0)) for item in judge_results]
        avg_scores[key] = round(mean(vals), 3) if vals else 0.0

    input_tokens = sum(int(item.get("usage", {}).get("input_tokens", 0)) for item in judge_results)
    output_tokens = sum(int(item.get("usage", {}).get("output_tokens", 0)) for item in judge_results)
    response["judge"] = {
        "enabled": True,
        "model": settings.judge_model,
        "samples": sample_n,
        "average_scores": avg_scores,
        "raw_results": judge_results,
        "token_usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_cny": _estimate_cost_cny(settings.judge_model, input_tokens, output_tokens),
        },
    }
    return response

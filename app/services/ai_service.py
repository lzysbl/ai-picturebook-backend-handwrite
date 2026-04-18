"""AI 服务层（第一阶段 Mock 版本，后续可替换真实模型 API）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


def analyze_images(image_paths: list[str]) -> list[dict[str, Any]]:
    """分析图片基础信息（尺寸、模式、亮度）。"""

    result: list[dict[str, Any]] = []
    for idx, image_path in enumerate(image_paths, start=1):
        try:
            with Image.open(Path(image_path)) as img:
                brightness = float(ImageStat.Stat(img.convert("L")).mean[0])
                result.append(
                    {
                        "page": idx,
                        "image_path": image_path,
                        "width": img.width,
                        "height": img.height,
                        "mode": img.mode,
                        "brightness": round(brightness, 2),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            result.append({"page": idx, "image_path": image_path, "error": str(exc)})
    return result


def generate_story(
    analysis_result: list[dict[str, Any]],
    extra_prompt: str | None = None,
    narration_style: str | None = None,
    audience_age: str | None = None,
    story_length: str | None = None,
    character_name: str | None = None,
) -> str:
    """根据分析结果生成可读故事文本。"""

    hero = character_name or "小主角"
    style = narration_style or "温柔"
    age = audience_age or "3-6"

    lines: list[str] = [
        f"{style}讲述：{hero}开始了一段绘本冒险。",
        f"目标年龄段：{age}。",
    ]

    limit = len(analysis_result)
    if (story_length or "medium") == "short":
        limit = min(3, limit)
    elif (story_length or "medium") == "medium":
        limit = min(6, limit)

    for item in analysis_result[:limit]:
        if "error" in item:
            lines.append(f"第{item['page']}页图片读取失败，系统已跳过。")
            continue
        lines.append(
            f"第{item['page']}页尺寸为 {item['width']}x{item['height']}，"
            f"亮度约 {item['brightness']}，故事继续推进。"
        )

    if extra_prompt:
        lines.append(f"额外要求：{extra_prompt}。")

    lines.append(f"最后，{hero}学会了勇敢和分享。")
    return "\n".join(lines)


def evaluate_story_quality(
    analysis_result: list[dict[str, Any]],
    story_content: str,
) -> dict[str, Any]:
    """对故事做可解释的简单评分。"""

    page_count = len(analysis_result)
    hit_count = sum(1 for i in range(1, page_count + 1) if f"第{i}页" in story_content)
    coherence = round((hit_count / max(page_count, 1)) * 100)

    avg_line_len = 0.0
    lines = [line for line in story_content.split("\n") if line.strip()]
    if lines:
        avg_line_len = sum(len(line) for line in lines) / len(lines)
    age_score = 90 if avg_line_len <= 30 else max(60, round(120 - avg_line_len))

    overall = round(coherence * 0.6 + age_score * 0.4)
    return {
        "scores": {
            "coherence": coherence,
            "age_appropriateness": age_score,
            "overall": overall,
        },
        "evidence": {
            "page_count": page_count,
            "page_hit_count": hit_count,
            "avg_line_length": round(avg_line_len, 2),
        },
    }

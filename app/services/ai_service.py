"""AI 服务层：支持 mock / Qwen 图片识别与故事生成。"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from openai import AsyncOpenAI
from PIL import Image, ImageStat

from app.core.config import settings

ProgressCallback = Callable[[int, int, str], Awaitable[None] | None]
MAX_CONCURRENCY = 8
logger = logging.getLogger(__name__)

# 常见角色后缀，用于识别“白名单之外的角色名”
ROLE_ENTITY_MARKERS = [
    "熊",
    "兔",
    "狐狸",
    "狼",
    "老虎",
    "狮子",
    "猴",
    "大象",
    "长颈鹿",
    "河马",
    "恐龙",
]

_qwen_client: AsyncOpenAI | None = None


def _get_qwen_client() -> AsyncOpenAI:
    global _qwen_client
    if _qwen_client is None:
        _qwen_client = AsyncOpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url)
    return _qwen_client


async def analyze_images(
    image_paths: list[str],
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    """统一入口：根据配置选择 mock 或 Qwen。"""

    if not image_paths:
        return []

    provider = (settings.ai_provider or "mock").strip().lower()
    logger.info("ai.analyze_images provider=%s image_count=%s", provider, len(image_paths))
    if provider == "qwen":
        return await _analyze_images_qwen(image_paths, progress_callback=progress_callback)
    return _analyze_images_mock(image_paths)


def _analyze_images_mock(image_paths: list[str]) -> list[dict[str, Any]]:
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
                        "角色": ["小主角"],
                        "场景": "绘本场景",
                        "动作": ["观察", "交流"],
                        "情绪": "温暖",
                        "关键物体": ["道具A", "道具B"],
                        "画面文字": [],
                    }
                )
        except Exception as exc:  # noqa: BLE001
            result.append({"page": idx, "image_path": image_path, "error": str(exc)})
    return result


async def _analyze_images_qwen(
    image_paths: list[str],
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    """Qwen 识别：最多并发 8 张，每张完成更新进度。"""

    if not settings.qwen_api_key:
        logger.warning("ai.analyze_images qwen_api_key_missing fallback=mock")
        return _analyze_images_mock(image_paths)

    total = len(image_paths)
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    done_count = 0
    results: dict[int, dict[str, Any]] = {}

    async def update_progress(page_no: int) -> None:
        nonlocal done_count
        done_count += 1
        if not progress_callback:
            return
        maybe = progress_callback(done_count, total, f"已识别第 {page_no} 页（{done_count}/{total}）")
        if maybe is not None:
            await maybe

    async def worker(page_no: int, image_path: str) -> None:
        async with semaphore:
            try:
                parsed = await _call_qwen_vl_for_one_image(image_path=image_path, page_no=page_no)
                item = _normalize_vision_json(parsed)
                item.update({"page": page_no, "image_path": image_path})
                results[page_no] = item
            except Exception as exc:  # noqa: BLE001
                logger.warning("ai.analyze_page_failed page=%s error=%s", page_no, exc)
                results[page_no] = {
                    "page": page_no,
                    "image_path": image_path,
                    "error": f"qwen分析失败: {exc}",
                }
            finally:
                await update_progress(page_no)

    tasks = [
        asyncio.create_task(worker(page_no=idx, image_path=path))
        for idx, path in enumerate(image_paths, start=1)
    ]
    await asyncio.gather(*tasks)

    ordered: list[dict[str, Any]] = []
    for idx, path in enumerate(image_paths, start=1):
        ordered.append(
            results.get(
                idx,
                {"page": idx, "image_path": path, "error": "识别结果缺失"},
            )
        )
    return ordered


async def _call_qwen_vl_for_one_image(image_path: str, page_no: int) -> dict[str, Any]:
    client = _get_qwen_client()
    completion = await client.chat.completions.create(
        model=settings.qwen_model,
        temperature=0.2,
        timeout=120,
        messages=[
            {"role": "system", "content": "你是儿童绘本图像分析助手，只输出 JSON。"},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _image_path_to_data_url(image_path)}},
                    {
                        "type": "text",
                        "text": (
                            f"分析第{page_no}页并返回 JSON："
                            '{"page":1,"角色":[],"场景":"","动作":[],"情绪":"","关键物体":[],"画面文字":[]}'
                            "要求：尽量提取可见文字（标题、对话、拟声词、标语等）。"
                        ),
                    },
                ],
            },
        ],
    )
    parsed = _extract_json(completion.choices[0].message.content or "")
    if not isinstance(parsed, dict):
        raise ValueError("模型未返回 JSON 对象")
    return parsed


async def generate_story(
    analysis_result: list[dict[str, Any]],
    extra_prompt: str | None = None,
    narration_style: str | None = None,
    audience_age: str | None = None,
    story_length: str | None = None,
    character_name: str | None = None,
) -> str:
    """生成故事：优先 Qwen 润色，失败则回退模板。"""

    book_title = _extract_book_title(analysis_result)
    provider = (settings.ai_provider or "mock").strip().lower()
    logger.info(
        "ai.generate_story provider=%s page_count=%s has_prompt=%s",
        provider,
        len(analysis_result),
        bool(extra_prompt),
    )
    if provider == "qwen" and settings.qwen_api_key:
        try:
            return await _generate_story_qwen(
                analysis_result=analysis_result,
                extra_prompt=extra_prompt,
                narration_style=narration_style,
                audience_age=audience_age,
                story_length=story_length,
                character_name=character_name,
                book_title=book_title,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai.generate_story_qwen_failed fallback=template error=%s", exc)

    return _generate_story_template(
        analysis_result=analysis_result,
        extra_prompt=extra_prompt,
        narration_style=narration_style,
        audience_age=audience_age,
        story_length=story_length,
        character_name=character_name,
        book_title=book_title,
    )


async def _generate_story_qwen(
    analysis_result: list[dict[str, Any]],
    extra_prompt: str | None = None,
    narration_style: str | None = None,
    audience_age: str | None = None,
    story_length: str | None = None,
    character_name: str | None = None,
    book_title: str | None = None,
) -> str:
    """Qwen 二段式生成：先写故事，再做违规词重写。"""

    hero = (character_name or "").strip()
    style = narration_style or "温柔"
    age = audience_age or "3-6"
    length = story_length or "medium"
    allowed_characters = _build_allowed_characters(analysis_result, hero)
    allowed_text = "、".join(allowed_characters)

    clean_pages: list[dict[str, Any]] = []
    for item in analysis_result:
        clean_pages.append(
            {
                "page": item.get("page"),
                "角色": item.get("角色", []),
                "场景": item.get("场景"),
                "动作": item.get("动作", []),
                "情绪": item.get("情绪"),
                "关键物体": item.get("关键物体", []),
                "画面文字": item.get("画面文字", []),
                "error": item.get("error"),
            }
        )

    prompt = (
        "请根据以下绘本页面分析结果，写一篇自然、连贯、适合儿童的故事。\n"
        "要求：\n"
        "1. 不要逐字段罗列，不要机械重复“第X页里……”。\n"
        "2. 要有起承转合，语言温和生动。\n"
        "3. 要合理融入页面文字内容（标题、对话、拟声词）。\n"
        "4. 有失败页面时轻描淡写跳过，不破坏整体叙事。\n"
        f"5. 叙事风格：{style}；目标年龄：{age}；篇幅偏好：{length}。\n"
        f"6. 额外要求：{extra_prompt or '无'}。\n"
        f"7. 角色约束：只允许出现这些角色称呼：{allowed_text}。"
        "禁止新增其他物种角色（例如熊、兔、狐狸、狼、老虎等）。\n\n"
        f"结构化输入：{json.dumps(clean_pages, ensure_ascii=False)}"
    )
    if book_title:
        prompt += (
            f"\n8. 已识别到本绘本标题候选：{book_title}。"
            "请自然融入正文或开头，格式建议《标题》，不要杜撰新标题。"
        )
    if hero:
        prompt += f"\n9. 如需突出某个主角，请优先突出：{hero}。"

    client = _get_qwen_client()
    completion = await client.chat.completions.create(
        model=settings.qwen_model,
        temperature=0.7,
        timeout=120,
        messages=[
            {"role": "system", "content": "你是擅长儿童文学创作的故事作者。"},
            {"role": "user", "content": prompt},
        ],
    )
    story = (completion.choices[0].message.content or "").strip()
    if not story:
        raise ValueError("模型未返回故事文本")

    unknown_roles = _find_nonexistent_roles(story, allowed_characters)
    if unknown_roles:
        story = await _rewrite_story_with_constraints(
            story_text=story,
            allowed_characters=allowed_characters,
            unknown_roles=unknown_roles,
        )

    if book_title and book_title not in story and f"《{book_title}》" not in story:
        story = f"《{book_title}》\n\n{story}"

    return story


def _build_allowed_characters(analysis_result: list[dict[str, Any]], hero: str) -> list[str]:
    """从识别结果构造角色白名单。"""

    candidates: list[str] = ["老鼠", "小老鼠"]
    if hero:
        candidates.append(hero)
    for item in analysis_result:
        roles = item.get("角色", [])
        if isinstance(roles, list):
            for role in roles:
                role_text = str(role).strip()
                if role_text:
                    candidates.append(role_text)

    # 去重并保持顺序
    dedup: list[str] = []
    seen: set[str] = set()
    for name in candidates:
        if name not in seen:
            seen.add(name)
            dedup.append(name)
    return dedup


def _extract_book_title(analysis_result: list[dict[str, Any]]) -> str | None:
    """从前几页 OCR 文本里提取绘本标题候选。"""

    raw_lines: list[str] = []
    for item in analysis_result[:3]:
        if "error" in item:
            continue
        page_texts = item.get("画面文字", [])
        if isinstance(page_texts, str):
            page_texts = [page_texts]
        if not isinstance(page_texts, list):
            continue
        for line in page_texts:
            text = str(line).strip()
            if text:
                raw_lines.append(text)

    if not raw_lines:
        return None

    stop_words = {
        "出版社",
        "出版单位",
        "作者",
        "著",
        "译",
        "isbn",
        "copyright",
        "全国百佳",
    }
    title_hints = {"绘本", "故事", "只老鼠", "早餐", "晚安", "冒险"}

    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for raw in raw_lines:
        for part in re.split(r"[，,。！？!?:：;；|/]+", raw):
            text = re.sub(r"\s+", "", part).strip("《》“”\"'[]()（）")
            if not text:
                continue
            lower_text = text.lower()
            if any(word in lower_text for word in stop_words):
                continue
            if len(text) < 2 or len(text) > 20:
                continue
            if text in seen:
                continue
            seen.add(text)

            score = 0
            if any(hint in text for hint in title_hints):
                score += 5
            if "第" in text and "页" in text:
                score -= 2
            if re.search(r"[0-9]{4,}", text):
                score -= 2
            if re.fullmatch(r"[一二三四五六七八九十0-9]+", text):
                score -= 2
            score += max(0, 8 - abs(len(text) - 8))
            candidates.append((score, text))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _find_nonexistent_roles(story_text: str, allowed_characters: list[str]) -> list[str]:
    """检测故事中不在角色白名单的“疑似角色名”。

    示例：白名单没有“爷爷熊”，就会识别为不存在角色。
    """

    allowed_set = {name.strip() for name in allowed_characters if name.strip()}
    candidates: set[str] = set()

    # 抓取常见“XX熊/XX兔/熊XX”这种角色词
    pattern = r"[\u4e00-\u9fa5]{1,6}(?:熊|兔|狐狸|狼|虎|狮|猴|象)"
    for match in re.finditer(pattern, story_text):
        token = match.group(0).strip()
        if token:
            candidates.add(token)

    # 兼容“熊爷爷/兔奶奶”这种前缀式写法
    prefix_pattern = r"(?:熊|兔|狐狸|狼|虎|狮|猴|象)[\u4e00-\u9fa5]{1,6}"
    for match in re.finditer(prefix_pattern, story_text):
        token = match.group(0).strip()
        if token:
            candidates.add(token)

    unknown: list[str] = []
    for token in sorted(candidates):
        # 完全在白名单就通过
        if token in allowed_set:
            continue
        # 若 token 包含某个白名单角色全称，也放过（避免误杀）
        if any(allowed and allowed in token for allowed in allowed_set):
            continue
        # 若白名单中有相同后缀物种（例如小鸟），也放过
        if any(marker in token and any(marker in allowed for allowed in allowed_set) for marker in ROLE_ENTITY_MARKERS):
            continue
        unknown.append(token)
    return unknown


async def _rewrite_story_with_constraints(
    story_text: str,
    allowed_characters: list[str],
    unknown_roles: list[str],
) -> str:
    """存在“白名单外角色”时进行一次自动重写。"""

    client = _get_qwen_client()
    allowed_text = "、".join(allowed_characters)
    bad_text = "、".join(unknown_roles)
    prompt = (
        "请在不改变剧情主线和段落结构的前提下，重写下面故事。\n"
        f"允许角色：{allowed_text}。\n"
        f"不存在的角色：{bad_text}（以及同类新增角色）。\n"
        "规则：任何不在允许角色名单中的角色名都不能出现。\n"
        "要求：语言自然、连续、口语化；不要解释改写过程，只输出最终故事。\n\n"
        f"原故事：\n{story_text}"
    )

    completion = await client.chat.completions.create(
        model=settings.qwen_model,
        temperature=0.4,
        timeout=90,
        messages=[
            {"role": "system", "content": "你是严谨的儿童故事改写助手。"},
            {"role": "user", "content": prompt},
        ],
    )
    rewritten = (completion.choices[0].message.content or "").strip()
    if rewritten:
        return rewritten
    return story_text


def _generate_story_template(
    analysis_result: list[dict[str, Any]],
    extra_prompt: str | None = None,
    narration_style: str | None = None,
    audience_age: str | None = None,
    story_length: str | None = None,
    character_name: str | None = None,
    book_title: str | None = None,
) -> str:
    hero = (character_name or "").strip()
    style = narration_style or "温柔"
    age = audience_age or "3-6"

    if hero:
        lines: list[str] = [
            f"{style}讲述：{hero}开始了一段绘本冒险。",
            f"目标年龄段：{age}。",
        ]
    else:
        lines = [
            f"{style}讲述：新的一天开始了。",
            f"目标年龄段：{age}。",
        ]

    if book_title:
        lines.insert(0, f"绘本标题：《{book_title}》。")

    limit = len(analysis_result)
    if (story_length or "medium") == "short":
        limit = min(3, limit)
    elif (story_length or "medium") == "medium":
        limit = min(6, limit)

    for item in analysis_result[:limit]:
        page = item.get("page", "?")
        if "error" in item:
            lines.append(f"第{page}页分析失败，系统已跳过该页。")
            continue

        roles = "、".join(item.get("角色", [])) or "角色不明确"
        scene = item.get("场景", "未知场景")
        actions = "、".join(item.get("动作", [])) or "没有明显动作"
        emotion = item.get("情绪", "中性")
        objects = "、".join(item.get("关键物体", [])) or "无关键物体"
        page_texts = item.get("画面文字", []) or []
        text_desc = "、".join(page_texts[:6]) if page_texts else "无明显文字"

        lines.append(
            f"第{page}页里，{roles}出现在{scene}，正在{actions}，整体情绪是{emotion}，"
            f"画面中出现了{objects}，可见文字有：{text_desc}。"
        )

    if extra_prompt:
        lines.append(f"额外要求：{extra_prompt}。")
    if hero:
        lines.append(f"最后，{hero}在这次旅程中学会了勇敢和分享。")
    else:
        lines.append("最后，大家在这次旅程中学会了勇敢和分享。")
    return "\n".join(lines)


def _extract_json(text: str) -> dict[str, Any] | list[Any]:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except Exception:  # noqa: BLE001
        pass

    arr_match = re.search(r"\[.*\]", stripped, flags=re.DOTALL)
    obj_match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    match = arr_match if arr_match else obj_match
    if not match:
        raise ValueError("模型输出中未找到 JSON")
    return json.loads(match.group(0))


def _normalize_vision_json(data: dict[str, Any]) -> dict[str, Any]:
    def to_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = re.split(r"[，,；;、\n]", value)
            return [p.strip() for p in parts if p.strip()]
        return [str(value)]

    def to_str(value: Any, default: str) -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    text_items = to_list(data.get("画面文字") or data.get("文字") or data.get("文本"))
    return {
        "角色": to_list(data.get("角色")),
        "场景": to_str(data.get("场景"), "未知场景"),
        "动作": to_list(data.get("动作")),
        "情绪": to_str(data.get("情绪"), "中性"),
        "关键物体": to_list(data.get("关键物体")),
        "画面文字": text_items,
    }


def _image_path_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(ext, "image/jpeg")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _evaluate_story_quality_legacy(analysis_result: list[dict[str, Any]], story_content: str) -> dict[str, Any]:
    page_count = len(analysis_result)
    hit_count = sum(1 for i in range(1, page_count + 1) if f"第{i}页" in story_content)
    coherence = round((hit_count / max(page_count, 1)) * 100)

    lines = [line for line in story_content.split("\n") if line.strip()]
    avg_line_len = sum(len(line) for line in lines) / len(lines) if lines else 0.0
    age_score = 90 if avg_line_len <= 35 else max(60, round(125 - avg_line_len))
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


def _extract_page_mentions(story_content: str) -> set[int]:
    """从故事文本提取页码，兼容“第1页 / 1页 / 第 1 页”写法。"""

    text = story_content or ""
    # \u7b2c=第, \u9875=页。使用 unicode 转义可规避源码编码问题。
    pattern = re.compile(r"(?:\u7b2c\s*)?(\d{1,3})\s*\u9875")
    page_numbers: set[int] = set()
    for match in pattern.finditer(text):
        try:
            page_numbers.add(int(match.group(1)))
        except (TypeError, ValueError):
            continue
    return page_numbers


def evaluate_story_quality(analysis_result: list[dict[str, Any]], story_content: str) -> dict[str, Any]:
    """基础规则评分：连贯性 + 年龄适配。"""

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
    else:
        hit_count = len(expected_pages.intersection(referenced_pages))
        coherence = round((hit_count / len(expected_pages)) * 100)

    lines = [line.strip() for line in (story_content or "").splitlines() if line.strip()]
    avg_line_len = sum(len(line) for line in lines) / len(lines) if lines else 0.0
    age_score = 90 if avg_line_len <= 35 else max(60, round(125 - avg_line_len))
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
            "avg_line_length": round(avg_line_len, 2),
        },
    }

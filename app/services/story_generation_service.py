"""故事生成服务：负责把页面分析结果组装成最终故事文本。

输出规则（强制）：
1. 第一行：`《标题》`
2. 第二行：`文／作者`
3. 后续每页单独一段：`第X页：...`
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings

_client: AsyncOpenAI | None = None
DEFAULT_NARRATION_CONSTRAINT = "减少背景复述，重点写人物动作和情节推进。"

# 兼容“正常中文 key”和历史编码异常 key。
ROLE_KEYS = ("角色", "characters", "瑙掕壊")
SCENE_KEYS = ("场景", "scene", "鍦烘櫙")
ACTION_KEYS = ("动作", "actions", "鍔ㄤ綔")
MOOD_KEYS = ("情绪", "mood", "鎯呯华")
OBJECT_KEYS = ("关键物体", "objects", "鍏抽敭鐗╀綋")
OCR_KEYS = ("画面文字", "文字", "文本", "ocr_texts", "鐢婚潰鏂囧瓧")


def _normalize_title_for_match(title: str | None) -> str:
    """Normalize title so title-specific rules can match reliably."""
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", title or "")


def _character_consistency_constraint(title: str | None) -> str:
    """Return title-specific character constraints for books with clear casts."""
    normalized = _normalize_title_for_match(title)
    if "爸爸我要月亮" in normalized:
        return (
            "角色一致性要求：本书核心角色只有爸爸、小茉莉、月亮和猫。"
            "禁止出现小男孩、男孩、成年女性、蓝衣人物等新增人物；"
            "如果画面识别中出现这些称呼，请按上下文改写为爸爸或小茉莉。"
        )
    return ""


def _apply_known_story_character_fix(story_text: str, title: str | None) -> str:
    """Clean obvious hallucinated roles for books with known fixed casts."""
    if "爸爸我要月亮" not in _normalize_title_for_match(title):
        return story_text

    replacements = {
        "成年女性": "爸爸",
        "蓝衣人物": "爸爸",
        "小男孩": "爸爸",
        "男孩": "爸爸",
        "一个人": "爸爸",
        "小女孩": "小茉莉",
        "女孩": "小茉莉",
    }
    fixed = story_text
    for old, new in replacements.items():
        fixed = fixed.replace(old, new)
    fixed = re.sub(r"爸爸和爸爸", "爸爸", fixed)
    fixed = re.sub(r"爸爸、爸爸", "爸爸", fixed)
    return fixed


def _get_client() -> AsyncOpenAI:
    """懒加载 Qwen/OpenAI 兼容客户端。"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url)
    return _client


def _pick(item: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """从多个候选 key 里取第一个存在且非空的值。"""
    for key in keys:
        if key in item and item.get(key) not in (None, ""):
            return item.get(key)
    return default


def _to_list(value: Any) -> list[str]:
    """把字符串/列表统一转换为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        return [part.strip() for part in re.split(r"[，,、|/\n；;]", text) if part.strip()]
    return [str(value).strip()]


def _join_list(value: Any, default: str) -> str:
    """把列表字段拼接为中文顿号文本。"""
    values = _to_list(value)
    return "、".join(values) if values else default


def _is_metadata_segment(segment: str) -> bool:
    """判断 OCR 片段是否属于封面元信息（著译、出版社、编号等）。"""
    text = segment.strip()
    if not text:
        return True
    if re.search(r"(出版社|出版单位|ISBN)", text):
        return True
    if re.search(r"^(文[／/]?|作者)[:：/\s]*", text):
        return True
    if re.search(r"^(?:\[.+?\])?.{1,24}\s*(著|译)$", text):
        return True
    if re.search(r"^老[一二三四五六七八九十]{1,2}\s*\d+$", text):
        return True
    return False


def _clean_ocr_for_story(value: Any) -> list[str]:
    """清理 OCR，移除不适合写进故事正文的元信息。"""
    cleaned: list[str] = []
    for raw in _to_list(value):
        # 先切分成片段，便于过滤“著/译/出版社/编号”。
        segments = [seg.strip() for seg in re.split(r"[、，,；;]", raw) if seg.strip()]
        kept = [seg for seg in segments if not _is_metadata_segment(seg)]
        if not kept:
            continue
        text = "、".join(kept).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _story_ocr_text(item: dict[str, Any]) -> str:
    """返回适合进入故事正文/提纲的 OCR 文本。"""
    raw_flag = _pick(item, "is_title_page", "是否标题页", default=False)
    is_title_page = str(raw_flag).strip().lower() in {"true", "1", "yes", "y", "是"} if isinstance(raw_flag, str) else bool(raw_flag)
    raw_ocr_list = _to_list(_pick(item, *OCR_KEYS, default=[]))
    raw_ocr_text = " ".join(raw_ocr_list)
    # 标题页或明显封面信息页：不把 OCR 文本塞进故事正文。
    if is_title_page:
        return ""
    if re.search(r"(出版社|出版单位|ISBN)", raw_ocr_text):
        return ""
    if re.search(r"(?:\[.+?\])?.{1,24}\s*(著|译)", raw_ocr_text):
        return ""
    if re.search(r"老[一二三四五六七八九十]{1,2}\s*\d+", raw_ocr_text):
        return ""

    cleaned = _clean_ocr_for_story(raw_ocr_list)
    return "；".join(cleaned[:2]) if cleaned else ""


def _select_page_limit(story_length: str | None, total_pages: int) -> int:
    """根据篇幅限制参与叙事的页数。"""
    mode = (story_length or "long").lower()
    if mode == "short":
        return min(4, total_pages)
    if mode == "long":
        return total_pages
    return min(8, total_pages)


def _sorted_pages(analysis_result: list[dict[str, Any]], story_length: str | None) -> list[dict[str, Any]]:
    """按页码排序并按篇幅截断。"""
    pages = sorted(analysis_result, key=lambda x: int(x.get("page", 0) or 0))
    return pages[: _select_page_limit(story_length, len(pages))]


def _collect_ocr_lines(analysis_result: list[dict[str, Any]], page_limit: int = 4) -> list[str]:
    """收集前几页 OCR 文本用于标题/作者识别。"""
    lines: list[str] = []
    for item in analysis_result[:page_limit]:
        texts = _pick(item, *OCR_KEYS, default=[])
        if isinstance(texts, str):
            text = texts.strip()
            if text:
                lines.append(text)
            continue
        if isinstance(texts, list):
            for t in texts:
                text = str(t).strip()
                if text:
                    lines.append(text)
    return lines


def _extract_book_title(analysis_result: list[dict[str, Any]]) -> str:
    """提取绘本标题，优先 `book_title`，其次 OCR《书名》格式。"""
    for item in analysis_result[:3]:
        title = _pick(item, "book_title", "title", default=None)
        if isinstance(title, str) and title.strip():
            return title.strip()

    lines = _collect_ocr_lines(analysis_result)
    for line in lines:
        match = re.search(r"《([^》]{2,40})》", line)
        if match:
            return match.group(1).strip()

    stop_tokens = ("出版社", "出版", "作者", "著", "译", "ISBN", "文/")
    for line in lines:
        compact = re.sub(r"\s+", "", line)
        if any(token in compact for token in stop_tokens):
            continue
        if 2 <= len(compact) <= 26:
            return compact
    return "未命名绘本"


def _extract_title_author_from_title_pages(
    analysis_result: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    """从每页检测结果中提取标题页信息（优先级最高）。"""
    for item in analysis_result:
        raw_flag = _pick(item, "is_title_page", "是否标题页", default=False)
        if isinstance(raw_flag, str):
            is_title_page = raw_flag.strip().lower() in {"true", "1", "yes", "y", "是"}
        else:
            is_title_page = bool(raw_flag)
        if not is_title_page:
            continue

        title = _pick(item, "detected_title", "识别标题", default=None)
        author = _pick(item, "detected_author", "识别作者", default=None)
        title_text = str(title).strip() if isinstance(title, str) else None
        author_text = str(author).strip() if isinstance(author, str) else None

        if not title_text:
            # 标题页兜底：仍可从该页 OCR 中抓《标题》
            ocr = _join_list(_pick(item, *OCR_KEYS, default=[]), "")
            match = re.search(r"《([^》]{2,40})》", ocr)
            if match:
                title_text = match.group(1).strip()
        if title_text or author_text:
            return title_text, author_text

    return None, None


def _is_clear_recognized_title(title: str | None) -> bool:
    """判断识别标题是否足够可信，可直接使用。"""
    text = (title or "").strip()
    if not text or text == "未命名绘本":
        return False
    if len(text) < 2 or len(text) > 40:
        return False
    bad_tokens = ("出版社", "ISBN", "作者", "文/", "文／", "译")
    if any(token in text for token in bad_tokens):
        return False
    return True


def _extract_book_author(analysis_result: list[dict[str, Any]]) -> str:
    """提取作者，兼容：文/xx、文／xx、作者：xx、xx 著 等格式。"""
    lines = _collect_ocr_lines(analysis_result)
    if not lines:
        return "未识别作者"

    patterns = [
        r"(?:^|[，。；\s])文[/:：／\s]*([^\s，。；]{2,40})",
        r"(?:^|[，。；\s])作者[/:：／\s]*([^\s，。；]{2,40})",
        r"(?:^|[，。；\s])([^\s，。；]{2,40})\s*著(?:$|[，。；\s])",
        r"(?:^|[，。；\s])([^\s，。；]{2,40})\s*绘(?:$|[，。；\s])",
    ]

    for line in lines:
        text = line.strip()
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                author = match.group(1).strip(" /：:，。；")
                if author:
                    return author
    return "未识别作者"


def _sanitize_story_output(text: str) -> str:
    """统一清洗模型输出，移除 markdown 标记。"""
    content = (text or "").strip()
    if not content:
        return content
    content = content.replace("**", "").replace("__", "")
    content = re.sub(r"^\s*#{1,6}\s*", "", content, flags=re.MULTILINE)
    content = re.sub(r"^\s*[-*]\s+", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return "\n".join(line.rstrip() for line in content.splitlines() if line.strip())


_PAGE_LINE_PATTERN = re.compile(r"^(第\s*\d+\s*页[：:])\s*(.+)$")


def _opening_signature(content: str) -> str:
    """Build compact opening signature for cross-page repetition detection."""
    if not content:
        return ""
    first_span = re.split(r"[，,。！？；;]", content, maxsplit=1)[0].strip()
    normalized = re.sub(
        r"(深蓝色|夜晚|白色|绿色|红色|户外|草地|背景|星空|天空|房子|树|星星|月亮|旁边|周围|上方|下方|的|有|在|一座|一只|一棵|一个|正在|静静|轻轻|微风|仿佛|里|中|外)",
        "",
        first_span,
    )
    normalized = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", normalized)
    return normalized[:18]


def _remove_leading_sentence_or_clause(content: str) -> str:
    """Remove first sentence/clause if it is repetitive background setup."""
    text = (content or "").strip()
    if not text:
        return text

    full_sentence = re.match(r"^[^。！？!?]*[。！？!?]\s*(.*)$", text)
    if full_sentence:
        tail = (full_sentence.group(1) or "").strip()
        if len(tail) >= 10:
            return tail

    first_clause = re.match(r"^[^，,；;]*[，,；;]\s*(.*)$", text)
    if first_clause:
        tail = (first_clause.group(1) or "").strip()
        if len(tail) >= 10:
            return tail
    return text


def _dedupe_background_repetition(story_text: str) -> str:
    """Reduce cross-page repeated opening backgrounds but keep page events."""
    lines = [line.strip() for line in (story_text or "").splitlines() if line.strip()]
    if not lines:
        return story_text

    deduped_lines: list[str] = []
    recent_signatures: list[str] = []

    for line in lines:
        matched = _PAGE_LINE_PATTERN.match(line)
        if not matched:
            deduped_lines.append(line)
            continue

        page_prefix = matched.group(1)
        content = matched.group(2).strip()
        signature = _opening_signature(content)

        is_repetitive = False
        if signature and len(signature) >= 6:
            for prev in recent_signatures:
                if signature == prev or signature in prev or prev in signature:
                    is_repetitive = True
                    break

        if is_repetitive:
            content = _remove_leading_sentence_or_clause(content)

        deduped_lines.append(f"{page_prefix}{content}")

        if signature:
            recent_signatures.append(signature)
            if len(recent_signatures) > 3:
                recent_signatures.pop(0)

    return "\n".join(deduped_lines)


def _ensure_header(story: str, title: str, author: str) -> str:
    """确保最终文本前两行固定是标题和作者。"""
    title_line = f"《{(title or '未命名绘本').strip()}》"
    author_line = f"文／{(author or '未识别作者').strip()}"

    lines = [line.strip() for line in (story or "").splitlines() if line.strip()]
    body = lines

    if body and body[0].startswith("《") and body[0].endswith("》"):
        body = body[1:]
    if body and body[0].startswith("文/"):
        body = [f"文／{body[0][2:].strip()}"] + body[1:]
    if body and body[0].startswith("文／"):
        body = body[1:]

    return "\n".join([title_line, author_line, *body]).strip()


def _build_outline(pages: list[dict[str, Any]]) -> str:
    """把结构化分析结果转为模型可读提纲。"""
    lines: list[str] = []
    for index, item in enumerate(pages, start=1):
        page_no = item.get("page", index)
        if "error" in item:
            lines.append(f"第{page_no}页：识别失败。")
            continue

        roles = _join_list(_pick(item, *ROLE_KEYS, default=[]), "人物未识别")
        scene = str(_pick(item, *SCENE_KEYS, default="场景未识别") or "场景未识别")
        actions = _join_list(_pick(item, *ACTION_KEYS, default=[]), "动作未识别")
        mood = str(_pick(item, *MOOD_KEYS, default="情绪未识别") or "情绪未识别")
        objects = _join_list(_pick(item, *OBJECT_KEYS, default=[]), "关键物体未识别")
        ocr = _story_ocr_text(item) or "无"

        lines.append(
            f"第{page_no}页：角色[{roles}]；场景[{scene}]；动作[{actions}]；"
            f"情绪[{mood}]；物体[{objects}]；可见文字[{ocr}]。"
        )
    return "\n".join(lines)


def _build_template_story(
    pages: list[dict[str, Any]],
    title: str,
    author: str,
    narration_style: str | None,
    audience_age: str | None,
    extra_prompt: str | None,
) -> str:
    """无模型或模型失败时的稳定兜底文本。"""
    style = (narration_style or "温柔").strip()
    age = (audience_age or "3-6").strip()

    lines: list[str] = []
    for index, item in enumerate(pages, start=1):
        page_no = item.get("page", index)
        if "error" in item:
            lines.append(f"第{page_no}页：这一页识别信息不完整，故事平滑过渡到下一页。")
            continue

        roles = _join_list(_pick(item, *ROLE_KEYS, default=[]), "小伙伴们")
        scene = str(_pick(item, *SCENE_KEYS, default="一个场景") or "一个场景")
        actions = _join_list(_pick(item, *ACTION_KEYS, default=[]), "活动着")
        mood = str(_pick(item, *MOOD_KEYS, default="温和") or "温和")
        ocr = _story_ocr_text(item)

        sentence = (
            f"第{page_no}页：在{scene}里，{roles}正在{actions}，"
            f"整体气氛{mood}，叙述风格偏{style}，适合{age}岁阅读。"
        )
        if ocr:
            sentence += f" 画面可见文字：{ocr}。"
        lines.append(sentence)

    if extra_prompt:
        lines.append(f"补充要求：{extra_prompt}。")

    body = _sanitize_story_output("\n".join(lines))
    body = _dedupe_background_repetition(body)
    body = _apply_known_story_character_fix(body, title)
    return _ensure_header(body, title, author)


def _guess_image_mime(image_path: str) -> str:
    """Guess MIME type for local picturebook page image."""
    suffix = Path(image_path).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/jpeg"


def _image_to_data_url(image_path: str) -> str:
    """Convert local image path to a data URL for OpenAI-compatible vision APIs."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"图片文件不存在：{image_path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_guess_image_mime(image_path)};base64,{encoded}"


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output, including fenced JSON blocks."""
    content = (text or "").strip()
    if not content:
        raise ValueError("模型未返回 JSON 内容")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.S)
    if fenced:
        content = fenced.group(1)
    else:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start : end + 1]

    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("模型返回内容不是 JSON 对象")
    return parsed


def _normalize_whole_book_pages(raw_pages: Any, expected_count: int) -> list[dict[str, Any]]:
    """Normalize whole-book model page analysis into the existing analysis_result shape."""
    pages = raw_pages if isinstance(raw_pages, list) else []
    normalized: list[dict[str, Any]] = []

    for index, raw_item in enumerate(pages, start=1):
        item = raw_item if isinstance(raw_item, dict) else {}
        page_no = item.get("page") or item.get("page_no") or item.get("页码") or index
        try:
            page_no = int(page_no)
        except (TypeError, ValueError):
            page_no = index

        visible_text = item.get("visible_text") or item.get("text") or item.get("ocr_texts") or item.get("画面文字") or ""
        summary = str(item.get("summary") or item.get("content") or item.get("内容") or "").strip()
        normalized.append(
            {
                "page": page_no,
                "角色": _to_list(item.get("characters") or item.get("角色")),
                "场景": str(item.get("scene") or item.get("场景") or ""),
                "动作": _to_list(item.get("actions") or item.get("动作")),
                "情绪": str(item.get("mood") or item.get("情绪") or ""),
                "关键物体": _to_list(item.get("objects") or item.get("关键物体")),
                "画面文字": _to_list(visible_text),
                "summary": summary,
                "is_title_page": bool(item.get("is_title_page") or item.get("是否标题页") or False),
                "detected_title": str(item.get("detected_title") or item.get("识别标题") or "").strip(),
                "detected_author": str(item.get("detected_author") or item.get("识别作者") or "").strip(),
                "generation_mode": "whole_book",
            }
        )

    existing_pages = {int(item.get("page", 0) or 0) for item in normalized}
    for page_no in range(1, expected_count + 1):
        if page_no not in existing_pages:
            normalized.append(
                {
                    "page": page_no,
                    "角色": [],
                    "场景": "",
                    "动作": [],
                    "情绪": "",
                    "关键物体": [],
                    "画面文字": [],
                    "summary": "模型未返回该页的结构化分析。",
                    "generation_mode": "whole_book",
                }
            )

    return sorted(normalized, key=lambda item: int(item.get("page", 0) or 0))


async def generate_story_from_images(
    image_paths: list[str],
    extra_prompt: str | None = None,
    narration_style: str | None = None,
    audience_age: str | None = None,
    story_length: str | None = None,
    character_name: str | None = None,
    fallback_title: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Submit the whole picturebook to a multimodal model and return analysis + story."""
    if not image_paths:
        raise ValueError("没有可用于生成故事的图片")

    provider = (settings.ai_provider or "mock").strip().lower()
    if provider != "qwen" or not settings.qwen_api_key:
        raise RuntimeError("整本图片生成需要配置 AI_PROVIDER=qwen 和 QWEN_API_KEY")

    style = (narration_style or "温柔").strip()
    age = (audience_age or "3-6").strip()
    hero = (character_name or "").strip()
    length = (story_length or "long").strip()
    extra = (
        f"{extra_prompt} {DEFAULT_NARRATION_CONSTRAINT}".strip()
        if extra_prompt
        else DEFAULT_NARRATION_CONSTRAINT
    )
    fallback = (fallback_title or "").strip()

    instruction = f"""
你将收到一本儿童绘本的全部页面图片，图片顺序就是绘本页序。
请先整体理解全书，再完成两件事：
1. 输出每页的结构化识别结果，用于系统落库和质量评估。
2. 输出一版适合儿童听的“讲述版故事”，不是原文摘抄，也不是图片说明。
最终只能输出一个严格 JSON 对象，不要输出 markdown，不要输出 JSON 之外的任何文字。

必须输出的 JSON 结构：
{{
  "title": "从封面/标题页/OCR中明确识别到的书名；如果无法明确识别则填空字符串",
  "author": "从封面/标题页/OCR中明确识别到的作者；如果无法明确识别则填空字符串",
  "pages": [
    {{
      "page": 1,
      "is_title_page": true,
      "detected_title": "",
      "detected_author": "",
      "characters": [],
      "scene": "",
      "actions": [],
      "mood": "",
      "objects": [],
      "visible_text": "",
      "summary": ""
    }}
  ],
  "story": "最终讲述版故事正文"
}}

全局规则：
1. 必须覆盖全部 {len(image_paths)} 页，pages 数组和 story 正文都要按页输出。
2. story 第一行必须是《标题》，第二行必须是“文／作者”，后面每页单独一段，以“第X页：”开头。
3. 如果图片能明确识别标题，优先使用识别标题；否则使用数据库标题：{fallback or "未命名绘本"}。
4. 先建立全书角色表，再写故事；同一个角色跨页必须保持同一称呼。
5. 不要新增图片和文字中不存在的角色；无法确定性别或身份时，用“孩子、人物、动物、家人”等中性称呼。
6. 如果 OCR 文字和视觉判断冲突，优先相信绘本原文/OCR。
7. 可以保留绘本原文里的关键短句，但不要整页逐句照抄；要用讲故事的语气串联动作、心理和因果。
8. 不要使用“封面展示、图片中、画面上、白色背景下、连续动作场景里”这类说明性表达。
9. 封面页/标题页只用于识别标题作者；如果该页没有真实剧情，story 中要写成自然开场，不要写成“封面介绍”。
10. 不要把出版社、译者、角色编号、版权信息整段写进故事正文。
11. 减少背景复述，重点写人物动作和情节推进；连续页面在同一场景时，只写新的动作和变化。
12. 每一页正文建议 1-3 句，句子要适合 {age} 岁儿童听读，避免过长复句。
13. 语言要有讲述感：可以加入轻微的情绪、期待、惊喜、疑问，但不能改变原故事事件。
14. 年龄段：{age}；叙述风格：{style}；篇幅：{length}；指定主角：{hero or "无"}。
15. 附加要求：{extra}。
"""

    content: list[dict[str, Any]] = [{"type": "text", "text": instruction.strip()}]
    for index, image_path in enumerate(image_paths, start=1):
        content.append({"type": "text", "text": f"第{index}页图片："})
        content.append({"type": "image_url", "image_url": {"url": _image_to_data_url(image_path)}})

    completion = await _get_client().chat.completions.create(
        model=settings.qwen_model,
        temperature=0.25,
        timeout=240,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是儿童绘本多模态理解与故事讲述助手。"
                    "你必须严格依据图片和可见文字写作，既不能胡编角色，也不能只机械复述原文。"
                ),
            },
            {"role": "user", "content": content},
        ],
    )
    raw_content = (completion.choices[0].message.content or "").strip()
    result = _extract_json_object(raw_content)

    analysis_result = _normalize_whole_book_pages(result.get("pages"), len(image_paths))
    detected_title = str(result.get("title") or "").strip()
    detected_author = str(result.get("author") or "").strip()
    if detected_title:
        for item in analysis_result:
            item["book_title"] = detected_title
            item["detected_title"] = item.get("detected_title") or detected_title
    if detected_author:
        for item in analysis_result:
            item["detected_author"] = item.get("detected_author") or detected_author

    title = detected_title if _is_clear_recognized_title(detected_title) else (fallback or "未命名绘本")
    author = detected_author or _extract_book_author(analysis_result)
    story = _sanitize_story_output(str(result.get("story") or "").strip())
    if not story:
        raise ValueError("模型未返回 story 字段")
    story = _dedupe_background_repetition(story)
    story = _apply_known_story_character_fix(story, title)
    story = _ensure_header(story, title, author)
    return analysis_result, story


async def _generate_with_qwen(
    pages: list[dict[str, Any]],
    title: str,
    author: str,
    extra_prompt: str | None,
    narration_style: str | None,
    audience_age: str | None,
    character_name: str | None,
) -> str:
    """调用 Qwen 生成故事，并在返回后再补一层头部校验。"""
    style = (narration_style or "温柔").strip()
    age = (audience_age or "3-6").strip()
    hero = (character_name or "").strip()
    character_constraint = _character_consistency_constraint(title)
    merged_extra_prompt = (
        f"{extra_prompt} {DEFAULT_NARRATION_CONSTRAINT}".strip()
        if extra_prompt
        else DEFAULT_NARRATION_CONSTRAINT
    )
    page_tags = [f"第{int(item.get('page', idx))}页" for idx, item in enumerate(pages, start=1)]

    prompt = (
        "请根据输入生成儿童绘本故事。\n"
        "硬性规则：\n"
        "1. 第一行必须是《标题》，且使用给定标题。\n"
        "2. 第二行必须是 文／作者，且使用给定作者。\n"
        "3. 从第三行开始，每页单独一段，必须以“第X页：”开头。\n"
        "4. 不要输出 markdown 符号（如 **、#、-）。\n"
        f"5. 必须按顺序覆盖：{'、'.join(page_tags)}。\n"
        "6. 不要新增输入中不存在的角色。\n"
        "7. 不要把封面元信息原样写进正文（如 出版社、著译信息、角色编号名单）。\n"
        "8. 不要在相邻页面重复同一类背景开场句（例如“深蓝色的夜空、星星闪烁”）。\n"
        "9. 如果场景延续但没有换场，请用简短承接语，不要每页都完整重写背景。\n"
        f"{'10. ' + character_constraint + chr(10) if character_constraint else ''}"
        f"风格：{style}；年龄段：{age}；主角偏好：{hero or '无'}；附加要求：{merged_extra_prompt}。\n"
        f"固定标题：{title}\n"
        f"固定作者：{author}\n\n"
        f"页面信息：\n{_build_outline(pages)}\n"
    )

    completion = await _get_client().chat.completions.create(
        model=settings.qwen_model,
        temperature=0.4,
        timeout=120,
        messages=[
            {"role": "system", "content": "你是儿童绘本故事创作助手。"},
            {"role": "user", "content": prompt},
        ],
    )
    content = (completion.choices[0].message.content or "").strip()
    if not content:
        raise ValueError("模型未返回故事内容")
    body = _sanitize_story_output(content)
    body = _dedupe_background_repetition(body)
    body = _apply_known_story_character_fix(body, title)
    return _ensure_header(body, title, author)


async def generate_story(
    analysis_result: list[dict[str, Any]],
    extra_prompt: str | None = None,
    narration_style: str | None = None,
    audience_age: str | None = None,
    story_length: str | None = None,
    character_name: str | None = None,
    fallback_title: str | None = None,
) -> str:
    """故事生成统一入口。"""
    pages = _sorted_pages(analysis_result, story_length)
    title_from_page, author_from_page = _extract_title_author_from_title_pages(analysis_result)
    recognized_title = title_from_page or _extract_book_title(analysis_result)
    if _is_clear_recognized_title(recognized_title):
        title = recognized_title
    else:
        title = (fallback_title or "").strip() or recognized_title or "未命名绘本"
    author = (author_from_page or "").strip() or _extract_book_author(analysis_result)

    provider = (settings.ai_provider or "mock").strip().lower()
    if provider == "qwen" and settings.qwen_api_key:
        try:
            return await _generate_with_qwen(
                pages=pages,
                title=title,
                author=author,
                extra_prompt=extra_prompt,
                narration_style=narration_style,
                audience_age=audience_age,
                character_name=character_name,
            )
        except Exception:
            # 出错回退到模板，保证功能可用。
            pass

    return _build_template_story(
        pages=pages,
        title=title,
        author=author,
        narration_style=narration_style,
        audience_age=audience_age,
        extra_prompt=extra_prompt,
    )

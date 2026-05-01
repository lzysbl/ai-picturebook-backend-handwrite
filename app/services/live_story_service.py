"""Helpers for turning page analysis into child-friendly live storytelling."""

from __future__ import annotations

from typing import Any

ROLE_CN = "\u89d2\u8272"
ACTION_CN = "\u52a8\u4f5c"
OBJECT_CN = "\u5173\u952e\u7269\u4f53"
TEXT_CN = "\u753b\u9762\u6587\u5b57"
SCENE_CN = "\u573a\u666f"
MOOD_CN = "\u60c5\u7eea"
SEP_CN = "\u3001"
UNKNOWN_MARKERS = ("\u672a\u77e5", "\u672a\u8bc6\u522b", "\u65e0")
FALLBACK_SCENE = "\u6545\u4e8b\u7684\u5c0f\u89d2\u843d"
FALLBACK_MOOD = "\u6e29\u6696"


def _first_present(data: dict[str, Any], keys: list[str], default: Any) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _as_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _is_unknown_text(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return any(marker in text for marker in UNKNOWN_MARKERS)


def _clean_story_tokens(values: list[str], limit: int) -> list[str]:
    cleaned: list[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        if _is_unknown_text(text):
            continue
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def summarize_page_for_live_story(analysis_result: list[dict[str, Any]]) -> dict[str, Any]:
    first = analysis_result[0] if analysis_result else {}

    roles = _as_list(_first_present(first, [ROLE_CN, "roles"], []), 4)
    actions = _as_list(_first_present(first, [ACTION_CN, "actions"], []), 3)
    objects = _as_list(_first_present(first, [OBJECT_CN, "objects"], []), 3)
    texts = _as_list(_first_present(first, [TEXT_CN, "texts"], []), 3)

    scene = str(_first_present(first, [SCENE_CN, "scene"], "\u7ed8\u672c\u573a\u666f")).strip() or "\u7ed8\u672c\u573a\u666f"
    mood = str(_first_present(first, [MOOD_CN, "mood"], "\u6e29\u548c")).strip() or "\u6e29\u548c"

    return {
        "page": int(first.get("page", 1) or 1),
        "roles": roles,
        "actions": actions,
        "objects": objects,
        "texts": texts,
        "scene": scene,
        "mood": mood,
    }


def build_character_registry(recent_pages: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for page in recent_pages:
        for role in page.get("roles", []):
            if role and role not in seen:
                seen.append(role)
    return seen


def same_page_summary(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("scene") == right.get("scene")
        and left.get("roles", []) == right.get("roles", [])
        and left.get("texts", []) == right.get("texts", [])
    )


def merge_scan_session_pages(
    existing_pages: list[dict[str, Any]],
    current_page: dict[str, Any],
    max_pages: int = 3,
) -> list[dict[str, Any]]:
    if existing_pages and same_page_summary(existing_pages[-1], current_page):
        existing_pages[-1] = current_page
        return existing_pages[-max_pages:]
    return [*existing_pages[-(max_pages - 1) :], current_page]


def context_pages_to_generation_input(
    recent_pages: list[dict[str, Any]],
    current_page: dict[str, Any],
) -> list[dict[str, Any]]:
    combined = [*recent_pages, current_page]
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(combined, start=1):
        pages.append(
            {
                "page": index,
                ROLE_CN: page.get("roles", []),
                SCENE_CN: page.get("scene", ""),
                ACTION_CN: page.get("actions", []),
                MOOD_CN: page.get("mood", ""),
                OBJECT_CN: page.get("objects", []),
                TEXT_CN: page.get("texts", []),
            }
        )
    return pages


def build_contextual_live_scan_story(
    recent_pages: list[dict[str, Any]],
    current_page: dict[str, Any],
    narration_style: str | None,
    audience_age: str | None,
    extra_prompt: str | None,
) -> str:
    role_list = _clean_story_tokens([str(r) for r in current_page.get("roles", [])], 3)
    action_list = _clean_story_tokens([str(a) for a in current_page.get("actions", [])], 3)
    object_list = _clean_story_tokens([str(o) for o in current_page.get("objects", [])], 4)
    text_list = _clean_story_tokens([str(t) for t in current_page.get("texts", [])], 3)

    raw_scene = str(current_page.get("scene") or "").strip()
    raw_mood = str(current_page.get("mood") or "").strip()
    scene = raw_scene if not _is_unknown_text(raw_scene) else FALLBACK_SCENE
    mood = raw_mood if (raw_mood and not _is_unknown_text(raw_mood) and raw_mood != "\u4e2d\u6027") else FALLBACK_MOOD

    joined_roles = SEP_CN.join(role_list[:2])
    subject = joined_roles if joined_roles else "\u5c0f\u4e3b\u89d2"
    action_phrase = SEP_CN.join(action_list[:2]) if action_list else "\u6b63\u5728\u8f7b\u8f7b\u5730\u89c2\u5bdf\u5468\u56f4"
    object_phrase = SEP_CN.join(object_list[:3])
    text_phrase = SEP_CN.join(text_list[:2])

    joined_tokens = " ".join([raw_scene, raw_mood, object_phrase, text_phrase]).upper()
    factual_mode = any(k in joined_tokens for k in ["PASSPORT", "ID", "\u8eab\u4efd\u8bc1", "\u62a4\u7167", "\u8bc1\u4ef6"])
    weak_signal = not role_list and not action_list and not object_list and scene == FALLBACK_SCENE

    lines: list[str] = []

    if weak_signal:
        lines.append("\u8fd9\u4e00\u9875\u7684\u753b\u9762\u8fd8\u5728\u6162\u6162\u6e05\u6670\uff0c\u6545\u4e8b\u5148\u8f7b\u8f7b\u505c\u4e00\u4e0b\u3002")
        lines.append("\u8bf7\u628a\u7ed8\u672c\u518d\u9760\u8fd1\u955c\u5934\u4e00\u70b9\uff0c\u6211\u4eec\u9a6c\u4e0a\u7ee7\u7eed\u5f80\u4e0b\u8bb2\u3002")
        return "\n".join(lines)

    if recent_pages:
        previous = recent_pages[-1]
        previous_scene = str(previous.get("scene") or "").strip()
        if previous_scene and previous_scene == scene and scene != FALLBACK_SCENE:
            lines.append(f"\u6545\u4e8b\u63a5\u7740\u4e0a\u4e00\u9875\u7ee7\u7eed\uff0c{scene}\u91cc\u53c8\u6709\u4e86\u65b0\u7684\u53d8\u5316\u3002")
        else:
            lines.append(f"\u7ffb\u5230\u8fd9\u4e00\u9875\uff0c\u6545\u4e8b\u6765\u5230\u4e86{scene}\u3002")
    else:
        lines.append(f"\u6545\u4e8b\u4ece{scene}\u6162\u6162\u5f00\u59cb\u3002")

    if factual_mode:
        lines.append(f"\u8fd9\u4e00\u9875\u50cf\u4e00\u5f20\u7ebf\u7d22\u5361\uff1a{subject}{action_phrase}\u3002")
    else:
        lines.append(f"\u8fd9\u65f6\uff0c{subject}{action_phrase}\uff0c\u7a7a\u6c14\u91cc\u6709\u4e00\u70b9{mood}\u7684\u5473\u9053\u3002")

    if object_phrase:
        lines.append(f"\u8eab\u8fb9\u7684{object_phrase}\uff0c\u50cf\u5728\u6084\u6084\u63d0\u793a\u63a5\u4e0b\u6765\u7684\u60c5\u8282\u3002")
    if text_phrase:
        lines.append(f"\u9875\u9762\u4e0a\u8fd8\u6709\u201c{text_phrase}\u201d\u8fd9\u6837\u7684\u5c0f\u7ebf\u7d22\u3002")

    registry = build_character_registry([*recent_pages, current_page])
    if len(registry) >= 2 and not factual_mode:
        joined_registry = SEP_CN.join(registry[:4])
        lines.append(f"\u76ee\u524d\u4e3a\u6b62\uff0c\u6545\u4e8b\u91cc\u51fa\u73b0\u8fc7\uff1a{joined_registry}\u3002")

    if extra_prompt:
        lines.append(f"\u8fd9\u4e00\u9875\u53ef\u4ee5\u7279\u522b\u5173\u6ce8\uff1a{extra_prompt}\u3002")

    if not factual_mode:
        lines.append("\u4f60\u89c9\u5f97\uff0c\u4e0b\u4e00\u9875\u4f1a\u53d1\u751f\u4ec0\u4e48\u5462\uff1f")

    return "\n".join(lines)


__all__ = [
    "build_character_registry",
    "build_contextual_live_scan_story",
    "context_pages_to_generation_input",
    "merge_scan_session_pages",
    "same_page_summary",
    "summarize_page_for_live_story",
]

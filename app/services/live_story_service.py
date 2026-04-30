"""Helpers for turning page analysis into child-friendly live storytelling."""

from __future__ import annotations

from typing import Any

ROLE_CN = "\u89d2\u8272"
ACTION_CN = "\u52a8\u4f5c"
OBJECT_CN = "\u5173\u952e\u7269\u4f53"
TEXT_CN = "\u753b\u9762\u6587\u5b57"
SCENE_CN = "\u573a\u666f"
MOOD_CN = "\u60c5\u7eea"


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
    role_list = [str(r).strip() for r in current_page.get("roles", []) if str(r).strip()]
    action_list = [str(a).strip() for a in current_page.get("actions", []) if str(a).strip()]
    object_list = [str(o).strip() for o in current_page.get("objects", []) if str(o).strip()]
    text_list = [str(t).strip() for t in current_page.get("texts", []) if str(t).strip()]

    subject = f"\u753b\u9762\u91cc\u7684{'\u3001'.join(role_list[:3])}" if role_list else "\u753b\u9762\u91cc\u7684\u5c0f\u4e3b\u89d2"
    action_phrase = "\u3001".join(action_list[:2]) if action_list else "\u6b63\u5728\u5b89\u9759\u5730\u89c2\u5bdf\u5468\u56f4"
    object_phrase = "\u3001".join(object_list[:3])
    text_phrase = "\u3001".join(text_list[:3])

    scene = str(current_page.get("scene") or "\u4e00\u4e2a\u5b89\u9759\u7684\u5730\u65b9")
    mood = str(current_page.get("mood") or "\u6e29\u548c")

    joined_tokens = " ".join([scene, subject, object_phrase, text_phrase]).upper()
    factual_mode = any(k in joined_tokens for k in ["PASSPORT", "ID", "\u8eab\u4efd\u8bc1", "\u62a4\u7167", "\u8bc1\u4ef6"])

    lines: list[str] = []

    if recent_pages:
        previous = recent_pages[-1]
        if previous.get("scene") == scene:
            lines.append(f"\u6545\u4e8b\u8fd8\u5728\u7ee7\u7eed\uff0c\u6211\u4eec\u8fd8\u5728{scene}\u3002")
        else:
            lines.append(f"\u7ffb\u5230\u8fd9\u4e00\u9875\uff0c\u753b\u9762\u6765\u5230\u4e86{scene}\u3002")

    if factual_mode:
        lines.append(f"\u753b\u9762\u4e2d\u53ef\u4ee5\u770b\u5230{subject}{action_phrase}\u3002")
    else:
        lines.append(f"{subject}{action_phrase}\uff0c\u753b\u9762\u6574\u4f53\u662f{mood}\u7684\u611f\u89c9\u3002")

    if object_phrase:
        lines.append(f"\u8fd8\u80fd\u770b\u5230{object_phrase}\u3002")
    if text_phrase:
        lines.append(f"\u9875\u9762\u4e0a\u8fd8\u80fd\u770b\u5230\uff1a{text_phrase}\u3002")

    registry = build_character_registry([*recent_pages, current_page])
    if len(registry) >= 2 and not factual_mode:
        lines.append(f"\u5230\u76ee\u524d\u4e3a\u6b62\uff0c\u6545\u4e8b\u91cc\u51fa\u73b0\u8fc7\uff1a{'\u3001'.join(registry[:4])}\u3002")

    if extra_prompt:
        lines.append(f"\u8fd9\u4e00\u9875\u8fd8\u53ef\u4ee5\u7279\u522b\u5173\u6ce8\uff1a{extra_prompt}\u3002")

    return "\n".join(lines)


__all__ = [
    "build_character_registry",
    "build_contextual_live_scan_story",
    "context_pages_to_generation_input",
    "merge_scan_session_pages",
    "same_page_summary",
    "summarize_page_for_live_story",
]

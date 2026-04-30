"""Helpers for turning page analysis into child-friendly live storytelling."""

from __future__ import annotations

from typing import Any


def summarize_page_for_live_story(analysis_result: list[dict[str, Any]]) -> dict[str, Any]:
    first = analysis_result[0] if analysis_result else {}
    roles = first.get("角色", []) if isinstance(first.get("角色"), list) else []
    actions = first.get("动作", []) if isinstance(first.get("动作"), list) else []
    objects = first.get("关键物体", []) if isinstance(first.get("关键物体"), list) else []
    texts = first.get("画面文字", []) if isinstance(first.get("画面文字"), list) else []
    return {
        "page": int(first.get("page", 1) or 1),
        "roles": [str(x).strip() for x in roles if str(x).strip()][:4],
        "actions": [str(x).strip() for x in actions if str(x).strip()][:3],
        "objects": [str(x).strip() for x in objects if str(x).strip()][:3],
        "texts": [str(x).strip() for x in texts if str(x).strip()][:3],
        "scene": str(first.get("场景") or "绘本场景"),
        "mood": str(first.get("情绪") or "温暖"),
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
                "角色": page.get("roles", []),
                "场景": page.get("scene", ""),
                "动作": page.get("actions", []),
                "情绪": page.get("mood", ""),
                "关键物体": page.get("objects", []),
                "画面文字": page.get("texts", []),
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

    if role_list:
        subject = f"????{'?'.join(role_list[:3])}"
    else:
        subject = "???????"

    action_phrase = "?".join(action_list[:2]) if action_list else "?????????"
    object_phrase = "?".join(object_list[:3])
    text_phrase = "?".join(text_list[:3])

    scene = str(current_page.get("scene") or "???????")
    mood = str(current_page.get("mood") or "??")

    joined_tokens = " ".join([scene, subject, object_phrase, text_phrase]).upper()
    factual_mode = any(k in joined_tokens for k in ["PASSPORT", "ID", "???", "??", "??"])

    lines: list[str] = []

    if recent_pages:
        previous = recent_pages[-1]
        if previous.get("scene") == scene:
            lines.append(f"???????????{scene}?")
        else:
            lines.append(f"???????????{scene}?")

    if factual_mode:
        lines.append(f"???????{subject}{action_phrase}?")
    else:
        lines.append(f"{subject}{action_phrase}??????{mood}????")

    if object_phrase:
        lines.append(f"????{object_phrase}?")
    if text_phrase:
        lines.append(f"????????{text_phrase}?")

    registry = build_character_registry([*recent_pages, current_page])
    if len(registry) >= 2 and not factual_mode:
        lines.append(f"?????????????{'?'.join(registry[:4])}?")

    if extra_prompt:
        lines.append(f"?????????????{extra_prompt}?")

    return "\n".join(lines)


__all__ = [
    "build_character_registry",
    "build_contextual_live_scan_story",
    "context_pages_to_generation_input",
    "merge_scan_session_pages",
    "same_page_summary",
    "summarize_page_for_live_story",
]

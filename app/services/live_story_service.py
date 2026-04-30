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
    style = (narration_style or "温柔").strip()
    age = (audience_age or "3-6").strip()
    roles = "、".join(current_page.get("roles", [])) or "小主角"
    actions = "、".join(current_page.get("actions", [])) or "在轻轻看着周围"
    objects = "、".join(current_page.get("objects", []))
    texts = "；".join(current_page.get("texts", []))
    scene = current_page.get("scene") or "一个安静的地方"
    mood = current_page.get("mood") or "温暖"

    lines = [f"下面我用更适合{age}岁孩子的{style}语气，讲一讲这一页的小故事。"]
    if recent_pages:
        previous = recent_pages[-1]
        if previous.get("scene") == scene:
            lines.append(f"故事还在继续，画面里的小伙伴们还停留在{scene}。")
        else:
            lines.append(f"翻到这一页，故事来到了{scene}。")

    lines.append(f"这时候，{roles}正在{actions}，整个画面看起来有一点{mood}。")

    if objects:
        lines.append(f"他们身边还能看到{objects}，这些小细节像是在悄悄提醒我们，接下来会发生新的事情。")
    if texts:
        lines.append(f"如果仔细看，页面上还有这些线索：{texts}。")

    registry = build_character_registry([*recent_pages, current_page])
    if len(registry) >= 2:
        lines.append(f"到目前为止，故事里已经出现了{'、'.join(registry[:4])}这些角色。")

    if extra_prompt:
        lines.append(f"如果特别留意的话，可以把重点放在：{extra_prompt}。")

    return "\n".join(lines)


__all__ = [
    "build_character_registry",
    "build_contextual_live_scan_story",
    "context_pages_to_generation_input",
    "merge_scan_session_pages",
    "same_page_summary",
    "summarize_page_for_live_story",
]

"""故事记录业务服务。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.story import Story


async def create_story_record(
    db: AsyncSession,
    user_id: int,
    book_id: int,
    prompt: str | None,
    image_analysis: dict[str, Any] | list[dict[str, Any]] | str | None,
    story_content: str,
) -> Story:
    """创建故事记录。"""
    if isinstance(image_analysis, (dict, list)):
        image_analysis_text = json.dumps(image_analysis, ensure_ascii=False)
    else:
        image_analysis_text = image_analysis

    story = Story(
        user_id=user_id,
        book_id=book_id,
        prompt=prompt or "",
        image_analysis=image_analysis_text,
        story_content=story_content,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


async def list_stories_by_user(db: AsyncSession, user_id: int) -> list[Story]:
    """查询用户故事历史。"""
    stmt = select(Story).where(Story.user_id == user_id).order_by(Story.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_story_by_id_and_user(db: AsyncSession, story_id: int, user_id: int) -> Story | None:
    """按 id + user 查询故事详情。"""
    stmt = select(Story).where(Story.id == story_id, Story.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

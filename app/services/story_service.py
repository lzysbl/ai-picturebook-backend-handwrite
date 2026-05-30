"""故事记录服务。

职责：
- 管理已经生成或保存的故事记录。
- 创建故事历史，保存用户提示词、图片分析结果和最终故事文本。
- 查询用户历史故事、查看故事详情、删除故事记录。

前端关联：
- `/ui/history`：故事历史列表、故事详情、删除历史记录。
- `/ui/generate`：完整故事生成成功后写入故事记录。
- `/ui/camera`：实时识别保存为故事时写入故事记录。
- `/ui/dashboard`：旧版仪表盘的最近故事展示。

主要路由：
- `app/routers/stories.py`：`/api/stories`
- `app/routers/stories.py`：`/api/stories/{story_id}`
- `app/routers/stories.py`：生成、保存故事时内部调用。
"""

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
    """创建故事记录并写入数据库。"""

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
    """查询用户的故事历史记录。"""

    stmt = select(Story).where(Story.user_id == user_id).order_by(Story.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_story_by_id_and_user(db: AsyncSession, story_id: int, user_id: int) -> Story | None:
    """按 story_id + user_id 查询故事详情。"""

    stmt = select(Story).where(Story.id == story_id, Story.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_story_by_id_and_user(db: AsyncSession, story_id: int, user_id: int) -> bool:
    """按 story_id + user_id 删除故事记录。"""

    story = await get_story_by_id_and_user(db, story_id, user_id)
    if not story:
        return False
    await db.delete(story)
    await db.commit()
    return True

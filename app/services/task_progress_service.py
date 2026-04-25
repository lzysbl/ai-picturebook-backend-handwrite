"""故事生成任务状态服务：优先 Redis，失败时降级为内存。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.core.redis_client import get_redis

TASK_KEY_PREFIX = "story_task:"
_local_tasks: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


async def _set_task(task: dict[str, Any]) -> None:
    serialized_task = jsonable_encoder(task)
    redis = await get_redis()
    if redis is not None:
        await redis.set(
            _task_key(task["task_id"]),
            json.dumps(serialized_task, ensure_ascii=False),
            ex=settings.story_cache_ttl_seconds,
        )
        return
    _local_tasks[task["task_id"]] = serialized_task


async def create_story_task(task_id: str, user_id: int) -> dict[str, Any]:
    """创建任务初始状态。"""

    now_iso = _now_iso()
    task = {
        "task_id": task_id,
        "status": "queued",
        "progress": 0,
        "current_step": "等待执行",
        "error": None,
        "result": None,
        "user_id": user_id,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await _set_task(task)
    return task


async def get_story_task(task_id: str) -> dict[str, Any] | None:
    """按 task_id 获取任务状态。"""

    redis = await get_redis()
    if redis is not None:
        raw = await redis.get(_task_key(task_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return _local_tasks.get(task_id)


async def update_story_task(task_id: str, **kwargs: Any) -> dict[str, Any] | None:
    """更新任务状态并刷新 TTL。"""

    task = await get_story_task(task_id)
    if not task:
        return None
    task.update(kwargs)
    task["updated_at"] = _now_iso()
    await _set_task(task)
    return task


def task_public_view(task: dict[str, Any]) -> dict[str, Any]:
    """对外返回的任务字段。"""

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "current_step": task["current_step"],
        "error": task.get("error"),
        "result": task.get("result"),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }

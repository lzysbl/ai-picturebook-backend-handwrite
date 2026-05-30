"""故事质量评价缓存服务。

职责：
- 按故事 ID 和评价模式缓存质量评价结果，避免重复调用规则评价或大模型评审。
- 支持读取、写入和清除缓存；Redis 不可用时降级为本地内存缓存。
- 刷新评价时才重新计算，普通页面切换优先复用缓存。

前端关联：
- `/ui/history`：故事详情页打开质量评价、切换评价模式、刷新评价。

主要路由：
- `app/routers/stories.py`：`/api/stories/{story_id}/quality`
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.core.redis_client import get_redis

QUALITY_KEY_PREFIX = "story_quality:"
_local_quality_cache: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mode_key(include_judge: bool, judge_samples: int | None) -> str:
    if not include_judge:
        return "basic"
    sample = judge_samples or settings.judge_samples
    sample = max(1, min(sample, 5))
    model_tag = settings.judge_model.replace(":", "_").replace("/", "_")
    return f"deep:s{sample}:m{model_tag}"


def _cache_key(story_id: int, include_judge: bool, judge_samples: int | None) -> str:
    return f"{QUALITY_KEY_PREFIX}{story_id}:{_mode_key(include_judge, judge_samples)}"


async def get_story_quality_cache(
    *,
    story_id: int,
    include_judge: bool,
    judge_samples: int | None,
) -> dict[str, Any] | None:
    """Read cached quality payload."""

    key = _cache_key(story_id, include_judge, judge_samples)
    redis = await get_redis()
    if redis is not None:
        raw = await redis.get(key)
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None
    return _local_quality_cache.get(key)


async def set_story_quality_cache(
    *,
    story_id: int,
    include_judge: bool,
    judge_samples: int | None,
    quality: dict[str, Any],
) -> None:
    """Save cached quality payload."""

    key = _cache_key(story_id, include_judge, judge_samples)
    payload = {
        "story_id": story_id,
        "include_judge": include_judge,
        "judge_samples": judge_samples,
        "saved_at": _now_iso(),
        "quality": jsonable_encoder(quality),
    }
    redis = await get_redis()
    if redis is not None:
        await redis.set(
            key,
            json.dumps(payload, ensure_ascii=False),
            ex=settings.quality_cache_ttl_seconds,
        )
        return
    _local_quality_cache[key] = payload


async def clear_story_quality_cache(story_id: int) -> None:
    """Delete all cached quality entries for one story."""

    prefix = f"{QUALITY_KEY_PREFIX}{story_id}:"
    redis = await get_redis()
    if redis is not None:
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=f"{prefix}*")
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
        return

    for key in list(_local_quality_cache.keys()):
        if key.startswith(prefix):
            _local_quality_cache.pop(key, None)

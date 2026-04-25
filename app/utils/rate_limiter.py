"""基于 Redis 的简单限流工具（不可用时降级内存）。"""

from __future__ import annotations

import asyncio
import time
from collections import deque

from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.redis_client import get_redis

_local_hits: dict[str, deque[float]] = {}
_local_lock = asyncio.Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_key(action: str, request: Request, user_id: int | None = None) -> str:
    if user_id is not None:
        return f"rate_limit:{action}:user:{user_id}"
    return f"rate_limit:{action}:ip:{_client_ip(request)}"


def _too_many_requests(wait_seconds: int) -> HTTPException:
    msg = f"请求太频繁，请 {max(wait_seconds, 1)} 秒后再试"
    return HTTPException(status_code=429, detail=msg)


async def enforce_rate_limit(
    request: Request,
    action: str,
    limit: int,
    window_seconds: int,
    user_id: int | None = None,
) -> None:
    """检查限流，超限抛出 429。"""

    if not settings.rate_limit_enabled:
        return
    if limit <= 0 or window_seconds <= 0:
        return

    key = _rate_key(action=action, request=request, user_id=user_id)
    redis = await get_redis()

    if redis is not None:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count > limit:
            ttl = await redis.ttl(key)
            raise _too_many_requests(int(ttl if ttl and ttl > 0 else window_seconds))
        return

    # Redis 不可用时的内存降级限流
    now = time.time()
    window_start = now - window_seconds
    async with _local_lock:
        bucket = _local_hits.setdefault(key, deque())
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            wait_seconds = int(bucket[0] + window_seconds - now)
            raise _too_many_requests(wait_seconds)
        bucket.append(now)

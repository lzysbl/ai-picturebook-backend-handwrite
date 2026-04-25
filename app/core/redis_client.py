"""Redis 客户端管理：统一初始化、获取与关闭。"""

from __future__ import annotations

import logging

from redis.asyncio import Redis, from_url

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None
_redis_unavailable: bool = False


async def init_redis() -> None:
    """应用启动时初始化 Redis。连接失败时降级为本地内存模式。"""

    global _redis_client, _redis_unavailable

    if not settings.redis_enabled:
        _redis_client = None
        _redis_unavailable = True
        return

    try:
        client = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await client.ping()
        _redis_client = client
        _redis_unavailable = False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 初始化失败，将使用内存降级模式：%s", exc)
        _redis_client = None
        _redis_unavailable = True


async def get_redis() -> Redis | None:
    """获取 Redis 客户端，不可用时返回 None。"""

    global _redis_client, _redis_unavailable

    if not settings.redis_enabled:
        return None
    if _redis_client is not None:
        return _redis_client
    if _redis_unavailable:
        return None

    await init_redis()
    return _redis_client


async def close_redis() -> None:
    """应用关闭时释放 Redis 连接。"""

    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None

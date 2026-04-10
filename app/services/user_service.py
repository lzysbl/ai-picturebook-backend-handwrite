"""用户业务服务。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.security import hash_password, verify_password


def _pick_value(obj: Any, key: str) -> Any:
    """兼容 pydantic 对象 / dict 取值。"""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """按用户名查询用户。"""
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: Any) -> User:
    """创建用户（自动密码哈希 + 重名检查）。"""
    username = _pick_value(user_in, "username")
    password = _pick_value(user_in, "password")
    if not username or not password:
        raise ValueError("用户名和密码不能为空")

    exists = await get_user_by_username(db, username)
    if exists:
        raise ValueError("用户名已存在")

    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """校验用户名和密码。"""
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

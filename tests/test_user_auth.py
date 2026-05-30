"""用户认证与密码重置测试。

覆盖范围：
- 验证注册表单密码一致性和邮箱格式校验。
- 验证密码重置 token 生成、重置和邮箱登录流程。

关联模块：
- `app/schemas/user.py`
- `app/services/user_service.py`
- `/ui/login`、`/ui/register`、`/ui/forgot-password`、`/ui/reset-password`

运行方式：
- `pytest tests/test_user_auth.py`
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app.models.user import User
from app.schemas.user import UserRegisterRequest
from app.services.user_service import (
    authenticate_user,
    create_user,
    issue_password_reset_token,
    reset_password_with_token,
)


class _FakeResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []

    def add(self, user: User) -> None:
        user.id = len(self.users) + 1
        self.users.append(user)

    async def commit(self) -> None:
        return None

    async def refresh(self, _user: User) -> None:
        return None

    async def execute(self, stmt):
        compiled = stmt.compile()
        params = compiled.params

        if "username_1" in params:
            target = params["username_1"]
            item = next((user for user in self.users if user.username == target), None)
            return _FakeResult(item)
        if "email_1" in params:
            target = params["email_1"]
            item = next((user for user in self.users if user.email == target), None)
            return _FakeResult(item)
        if "reset_password_token_hash_1" in params:
            target = params["reset_password_token_hash_1"]
            item = next((user for user in self.users if user.reset_password_token_hash == target), None)
            return _FakeResult(item)
        if "id_1" in params:
            target = params["id_1"]
            item = next((user for user in self.users if user.id == target), None)
            return _FakeResult(item)
        return _FakeResult(None)


def test_user_register_requires_matching_passwords() -> None:
    with pytest.raises(ValidationError):
        UserRegisterRequest(
            username="tester",
            email="tester@example.com",
            password="password123",
            confirm_password="password456",
        )


def test_user_register_validates_email() -> None:
    with pytest.raises(ValidationError):
        UserRegisterRequest(
            username="tester",
            email="not-an-email",
            password="password123",
            confirm_password="password123",
        )


def test_password_reset_flow_supports_email_login() -> None:
    async def runner() -> None:
        db = _FakeSession()
        await create_user(
            db,
            {
                "username": "tester",
                "email": "tester@example.com",
                "password": "password123",
            },
        )

        token = await issue_password_reset_token(db, "tester@example.com", 30)
        assert token

        reset_ok = await reset_password_with_token(db, token, "newpassword123")
        assert reset_ok is True

        by_email = await authenticate_user(db, "tester@example.com", "newpassword123")
        assert by_email is not None
        assert by_email.email == "tester@example.com"

        old_password_user = await authenticate_user(db, "tester", "password123")
        assert old_password_user is None

    asyncio.run(runner())

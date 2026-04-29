"""User-related request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("密码过长：最大 72 字节（英文约 72 个字符，中文约 24 个字符）")
    return value


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValueError("邮箱格式不正确")
    return email


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    email: str = Field(..., min_length=6, max_length=255, description="邮箱")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    confirm_password: str = Field(..., min_length=6, max_length=64, description="确认密码")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("password", "confirm_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_password_bytes(value)

    @model_validator(mode="after")
    def validate_password_match(self) -> "UserRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=255, description="用户名或邮箱")
    password: str = Field(..., min_length=6, max_length=64, description="密码")

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_password_bytes(value)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=6, max_length=255, description="注册邮箱")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _normalize_email(value)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=12, max_length=255, description="重置令牌")
    password: str = Field(..., min_length=6, max_length=64, description="新密码")
    confirm_password: str = Field(..., min_length=6, max_length=64, description="确认新密码")

    @field_validator("password", "confirm_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_password_bytes(value)

    @model_validator(mode="after")
    def validate_password_match(self) -> "ResetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=64, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码")
    confirm_new_password: str = Field(..., min_length=6, max_length=64, description="确认新密码")

    @field_validator("old_password", "new_password", "confirm_new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_password_bytes(value)

    @model_validator(mode="after")
    def validate_password_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("两次输入的新密码不一致")
        if self.old_password == self.new_password:
            raise ValueError("新密码不能与旧密码相同")
        return self


class UserInfo(BaseModel):
    id: int
    username: str
    email: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponseData(BaseModel):
    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: UserInfo

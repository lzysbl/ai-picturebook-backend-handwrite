"""用户模块的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserRegisterRequest(BaseModel):
    """用户注册请求体。"""

    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """bcrypt 明文密码上限 72 字节，这里提前给出中文提示。"""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码过长：最多 72 字节（英文约 72 个字符，中文约 24 个字符）")
        return value


class UserLoginRequest(BaseModel):
    """用户登录请求体。"""

    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """登录时同样限制密码字节数，避免底层库直接抛英文错误。"""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码过长：最多 72 字节（英文约 72 个字符，中文约 24 个字符）")
        return value


class UserInfo(BaseModel):
    """用户基础信息（对外返回）。"""

    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponseData(BaseModel):
    """登录成功后的 data 字段。"""

    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: UserInfo

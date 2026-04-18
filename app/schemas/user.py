"""用户模块的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    """用户注册请求体。"""

    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


class UserLoginRequest(BaseModel):
    """用户登录请求体。"""

    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


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

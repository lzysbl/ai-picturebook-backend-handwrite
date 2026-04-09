"""用户相关 Schema（请求体 + 响应体）。

你要在这里定义 4 个模型：
1. UserRegisterRequest（注册请求）
2. UserLoginRequest（登录请求）
3. UserInfo（用户信息响应）
4. LoginResponseData（登录返回 data）
"""

# TODO: 导入 datetime、BaseModel、Field
# 示例：from datetime import datetime
# 示例：from pydantic import BaseModel, Field


class UserRegisterRequest:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段：
    - username: str（可加最小长度约束）
    - password: str（可加最小长度约束）
    """


class UserLoginRequest:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段：
    - username: str
    - password: str
    """


class UserInfo:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段：
    - id: int
    - username: str
    - created_at: datetime
    """


class LoginResponseData:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段：
    - access_token: str
    - token_type: str = "bearer"
    - user: UserInfo
    """

"""用户相关请求响应模型。

建议你手写：
- UserRegisterRequest
- UserLoginRequest
- UserInfo
- LoginResponseData（包含 token）
"""
from pydantic import BaseModel
# TODO: 定义用户 schemas
class UserRegisterRequest(BaseModel):# 用户注册请求模型
    username: str# 用户名
    password: str# 密码
    email: str# 邮箱地址


class UserLoginRequest(BaseModel):# 用户登录请求模型
    username: str# 用户名
    password: str# 密码


class UserInfo(BaseModel):# 用户信息模型
    id: int# 用户 ID
    username: str# 用户名
    created_at: str# 创建时间，字符串格式
    
class LoginResponseData(BaseModel):# 登录响应数据模型，包含 token
    access_token: str# 访问令牌
    token_type: str = "bearer"# 令牌类型，默认为 "bearer"
    

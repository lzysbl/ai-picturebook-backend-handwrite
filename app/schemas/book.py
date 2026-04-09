"""绘本相关请求响应模型。

建议你手写：
- BookCreateRequest
- BookInfo
"""
from pydantic import BaseModel

# TODO: 定义绘本 schemas

class BookCreateRequest(BaseModel):# 绘本创建请求模型
    title: str# 绘本标题
    cover_image: str# 绘本封面图片路径
    
class BookInfo(BaseModel):# 绘本信息模型
    id: int# 绘本 ID
    user_id: int# 创建者用户 ID
    title: str# 绘本标题
    cover_image: str# 绘本封面图片路径
    created_at: str# 创建时间，字符串格式


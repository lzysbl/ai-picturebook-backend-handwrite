"""绘本图片相关模型。

建议你手写：
- BookImageInfo
"""
from pydantic import BaseModel

# TODO: 定义图片 schemas

class BookImageInfo(BaseModel):# 绘本图片信息模型
    id: int# 图片 ID
    book_id: int# 关联的书籍 ID
    image_path: str# 图片路径
    image_order: int# 图片顺序
    created_at: str# 创建时间，字符串格式
    

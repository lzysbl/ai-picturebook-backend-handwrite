"""故事相关模型。

建议你手写：
- StoryGenerateRequest
- StoryEvaluateRequest
- StoryInfo
"""
from pydantic import BaseModel

# TODO: 定义故事 schemas
class StoryGenerateRequest(BaseModel):# 故事生成请求模型
    title: str# 故事标题
    genre: str# 故事类型
    length: int# 故事长度，单位为字数
    
class StoryEvaluateRequest(BaseModel):# 故事评价请求模型
    story_id: int# 故事 ID
    rating: int# 评分，1-5
    comment: str# 评价内容
    
class StoryInfo(BaseModel):# 故事信息模型
    id: int# 故事 ID
    book_id: int# 关联的书籍 ID
    user_id: int# 创建者用户 ID
    prompt: str# 生成故事的提示语
    image_analysis: str# 图片分析结果
    story_content: str# 故事内容
    created_at: str# 创建时间，字符串格式

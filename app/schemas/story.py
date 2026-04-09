"""故事相关模型。

建议你手写：
- StoryGenerateRequest
- StoryEvaluateRequest
- StoryInfo
"""


# TODO: 定义故事 schemas
from datetime import datetime
from pydantic import BaseModel, Field


class StoryGenerateRequest(BaseModel):# 故事生成请求模型
    user_id: int = Field(..., gt=0, description="用户ID")# 用户 ID，必须大于 0
    book_id: int = Field(..., gt=0, description="绘本ID")# 绘本 ID，必须大于 0
    prompt: str | None = Field(default=None, description="附加提示词")# 生成故事的附加提示词
    narration_style: str | None = Field(default="温柔", description="温柔/活泼/睡前")# 叙述风格，默认为 "温柔"
    audience_age: str | None = Field(default="3-6", description="目标年龄段")# 目标年龄段，默认为 "3-6"
    story_length: str | None = Field(default="medium", description="short/medium/long")# 故事长度，默认为 "medium"
    character_name: str | None = Field(default=None, description="主角名字")# 主角名字，默认为 None


class StoryEvaluateRequest(StoryGenerateRequest):# 故事评估请求模型，继承生成请求模型
    story_content: str | None = Field(
        default=None,# 故事内容，评估时必填，如果不传则先生成再评估
        description="要评估的故事文本，不传则先生成再评估",# 评估时必填，如果不传则先生成再评估
    )


class StoryInfo(BaseModel):# 故事信息模型
    id: int# 故事 ID
    book_id: int# 关联的书籍 ID
    user_id: int# 关联的用户 ID
    prompt: str | None# 生成故事的附加提示词
    image_analysis: str | None# 图片分析结果
    story_content: str# 故事内容
    created_at: datetime# 创建时间


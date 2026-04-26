"""故事模块请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StoryGenerateRequest(BaseModel):
    """生成故事请求体。"""

    book_id: int = Field(..., description="绘本 ID")
    prompt: str | None = Field(default=None, description="额外提示词")
    narration_style: str | None = Field(default="温柔", description="叙述风格")
    audience_age: str | None = Field(default="3-6", description="目标年龄")
    story_length: str | None = Field(default="long", description="故事长度")
    character_name: str | None = Field(default=None, description="主角名称")
    generation_mode: str | None = Field(
        default="whole_book",
        description="生成模式：whole_book=整本图片一次提交，pipeline=逐页识别后生成",
    )
    include_judge: bool = Field(default=False, description="是否在生成后启用 LLM 深度评估")
    judge_samples: int | None = Field(default=None, description="LLM 评审采样次数（1~5）")


class StoryEvaluateRequest(BaseModel):
    """单独评估故事质量请求体。"""

    book_id: int = Field(..., description="绘本 ID")
    story_content: str = Field(..., min_length=1, description="待评估故事文本")
    include_judge: bool = Field(default=False, description="是否启用 LLM 评审")
    judge_samples: int | None = Field(default=None, description="LLM 评审采样次数（1~5）")


class StoryInfo(BaseModel):
    """故事记录信息。"""

    id: int
    book_id: int
    user_id: int
    prompt: str | None
    image_analysis: str | None
    story_content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryGenerateData(BaseModel):
    """生成故事接口的 data 字段。"""

    analysis_result: list[dict[str, Any]]
    story_content: str
    quality: dict[str, Any]
    story: StoryInfo


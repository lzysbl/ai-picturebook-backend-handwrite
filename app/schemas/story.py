"""故事相关 Schema。"""

# TODO: 导入 datetime、BaseModel、Field
# 示例：from datetime import datetime
# 示例：from pydantic import BaseModel, Field


class StoryGenerateRequest:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段（贴合你的项目）：
    - user_id: int
    - book_id: int
    - prompt: str | None = None
    - narration_style: str | None = "温柔"
    - audience_age: str | None = "3-6"
    - story_length: str | None = "medium"
    - character_name: str | None = None
    """


class StoryEvaluateRequest:
    """
    TODO: 改成 BaseModel，并建议继承 StoryGenerateRequest。

    额外字段建议：
    - story_content: str | None = None
    说明：不传时，可由系统先生成再评估。
    """


class StoryInfo:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段：
    - id: int
    - book_id: int
    - user_id: int
    - prompt: str | None
    - image_analysis: str | None
    - story_content: str
    - created_at: datetime
    """

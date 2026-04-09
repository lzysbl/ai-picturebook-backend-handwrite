"""通用响应模型（所有接口共享）。

你在这个文件只做一件事：
1. 定义统一响应结构 ApiResponse。

统一结构建议：
{
  "success": true,
  "message": "xxx",
  "data": {...}
}
"""

# TODO: 导入 Any / Optional / BaseModel
# 示例：from typing import Any, Optional
# 示例：from pydantic import BaseModel


class ApiResponse:
    """
    TODO: 改成 BaseModel 并补字段。

    需要字段：
    1. success: bool
    2. message: str
    3. data: Optional[Any] = None
    """
    pass

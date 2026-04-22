"""最小化 AI 连通性测试脚本（读取项目 .env 配置）。"""

from __future__ import annotations

import sys
from pathlib import Path

from openai import OpenAI

# 允许从 tests 目录直接运行：把项目根目录加入导入路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings


def main() -> None:
    """测试 Qwen 文本能力是否可调用。"""

    if not settings.qwen_api_key:
        raise RuntimeError("未读取到 QWEN_API_KEY，请检查 .env")

    client = OpenAI(
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_base_url,
    )

    completion = client.chat.completions.create(
        model=settings.qwen_model or "qwen3.6-flash",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "你是谁？"},
        ],
        timeout=60,
    )
    print("模型回复：", completion.choices[0].message.content)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"错误信息：{exc}")
        print("请参考文档：https://help.aliyun.com/model-studio/developer-reference/error-code")

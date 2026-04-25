"""请求上下文：用于在日志中关联 request_id。"""

from __future__ import annotations

from contextvars import ContextVar

_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> None:
    """写入当前协程上下文的 request_id。"""

    _request_id_ctx_var.set(request_id)


def get_request_id() -> str:
    """读取当前协程上下文的 request_id。"""

    return _request_id_ctx_var.get()


"""日志初始化：控制台 + 滚动文件，附带 request_id 字段。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings
from app.core.request_context import get_request_id


class RequestIdFilter(logging.Filter):
    """给每条日志注入 request_id。"""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = get_request_id()
        return True


def setup_logging() -> None:
    """初始化全局日志配置。"""

    log_dir = Path(settings.log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / settings.log_file

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    request_id_filter = RequestIdFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(request_id_filter)

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_id_filter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 避免第三方 logger 级别过低刷屏，可按需再调优
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


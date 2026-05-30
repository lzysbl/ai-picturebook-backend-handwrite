"""绘本服务测试。

覆盖范围：
- 验证删除绘本时，本地上传目录会被清理。

关联模块：
- `app/services/book_service.py`
- `/ui/books` 删除绘本功能间接依赖该逻辑。

运行方式：
- `pytest tests/test_book_service.py`
"""

from __future__ import annotations

from pathlib import Path

from app.services.book_service import _remove_book_upload_dir


def test_remove_book_upload_dir_deletes_book_folder(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    book_dir = upload_dir / "books" / "12"
    book_dir.mkdir(parents=True)
    (book_dir / "page1.png").write_text("demo", encoding="utf-8")

    _remove_book_upload_dir(str(upload_dir), 12)

    assert not book_dir.exists()

"""Tests for book-service helpers."""

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

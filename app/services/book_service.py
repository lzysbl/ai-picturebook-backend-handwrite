"""绘本信息服务。

职责：
- 管理绘本主体数据，包括创建、查询、按标题复用、删除和封面更新。
- 删除绘本时同步清理本地上传目录，避免数据库记录和文件残留不一致。
- 查询绘本时自动用第一页图片补齐缺失封面。

前端关联：
- `/ui/books`：绘本列表、新建绘本、删除绘本。
- `/ui/upload`：上传图片前选择或创建绘本。
- `/ui/generate`：生成故事前选择绘本。
- `/ui/history`：按绘本查看历史故事和图片。

主要路由：
- `app/routers/books.py`：`/api/books`
- `app/routers/images.py`：上传图片后更新封面。
- `app/routers/stories.py`：生成故事或保存实时识别结果时关联绘本。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book
from app.models.book_image import BookImage


async def create_book(
    db: AsyncSession,
    user_id: int,
    title: str,
    cover_image: str | None = None,
) -> Book:
    book = Book(user_id=user_id, title=title, cover_image=cover_image)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def list_books_by_user(db: AsyncSession, user_id: int) -> list[Book]:
    stmt = select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())
    result = await db.execute(stmt)
    books = list(result.scalars().all())

    changed = False
    for book in books:
        if await _fill_missing_cover_with_first_page(db, book):
            changed = True

    if changed:
        await db.commit()

    return books


async def get_book_by_id_and_user(db: AsyncSession, book_id: int, user_id: int) -> Book | None:
    stmt = select(Book).where(Book.id == book_id, Book.user_id == user_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if not book:
        return None

    if await _fill_missing_cover_with_first_page(db, book):
        await db.commit()

    return book


async def get_or_create_book_by_title(
    db: AsyncSession,
    user_id: int,
    title: str,
) -> Book:
    stmt = select(Book).where(Book.user_id == user_id, Book.title == title).order_by(Book.id.asc()).limit(1)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if book:
        return book
    return await create_book(db=db, user_id=user_id, title=title)


async def delete_book(db: AsyncSession, book_id: int, user_id: int) -> Book | None:
    book = await get_book_by_id_and_user(db, book_id, user_id)
    if not book:
        return None

    upload_dir = settings.upload_dir
    await db.delete(book)
    await db.commit()
    _remove_book_upload_dir(upload_dir, book_id)
    return book


async def update_book_cover_image(
    db: AsyncSession,
    book: Book,
    cover_image: str,
) -> Book:
    book.cover_image = cover_image
    await db.commit()
    await db.refresh(book)
    return book


async def _fill_missing_cover_with_first_page(db: AsyncSession, book: Book) -> bool:
    if book.cover_image:
        return False

    stmt = (
        select(BookImage.image_path)
        .where(BookImage.book_id == book.id)
        .order_by(BookImage.image_order.asc(), BookImage.id.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    first_image_path = result.scalar_one_or_none()
    if not first_image_path:
        return False

    book.cover_image = first_image_path
    return True


def _remove_book_upload_dir(upload_dir: str, book_id: int) -> None:
    """Remove local upload directory for a deleted book."""

    book_dir = Path(upload_dir) / "books" / str(book_id)
    if book_dir.exists():
        shutil.rmtree(book_dir, ignore_errors=True)

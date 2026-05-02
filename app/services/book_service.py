"""Book service layer."""

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

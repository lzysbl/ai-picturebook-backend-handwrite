"""绘本业务服务层。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.book_image import BookImage


async def create_book(
    db: AsyncSession,
    user_id: int,
    title: str,
    cover_image: str | None = None,
) -> Book:
    """创建一本绘本。"""

    book = Book(user_id=user_id, title=title, cover_image=cover_image)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def list_books_by_user(db: AsyncSession, user_id: int) -> list[Book]:
    """查询用户绘本列表，并自动补全缺失封面。"""

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
    """按 book_id + user_id 查询单本绘本，并自动补全缺失封面。"""

    stmt = select(Book).where(Book.id == book_id, Book.user_id == user_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if not book:
        return None

    if await _fill_missing_cover_with_first_page(db, book):
        await db.commit()

    return book


async def delete_book(db: AsyncSession, book_id: int, user_id: int) -> Book | None:
    """删除指定绘本，返回删除前对象。"""

    book = await get_book_by_id_and_user(db, book_id, user_id)
    if not book:
        return None
    await db.delete(book)
    await db.commit()
    return book


async def update_book_cover_image(
    db: AsyncSession,
    book: Book,
    cover_image: str,
) -> Book:
    """更新绘本封面图片。"""

    book.cover_image = cover_image
    await db.commit()
    await db.refresh(book)
    return book


async def _fill_missing_cover_with_first_page(db: AsyncSession, book: Book) -> bool:
    """若封面为空，自动使用第一页图片作为封面。"""

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

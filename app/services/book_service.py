"""绘本业务服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book


async def create_book(
    db: AsyncSession,
    user_id: int,
    title: str,
    cover_image: str | None = None,
) -> Book:
    """创建绘本记录。"""
    book = Book(user_id=user_id, title=title, cover_image=cover_image)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def list_books_by_user(db: AsyncSession, user_id: int) -> list[Book]:
    """查询用户的绘本列表。"""
    stmt = select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())#按创建时间倒序排列，最新的在前面
    result = await db.execute(stmt)#执行查询
    return list(result.scalars().all())#返回查询结果的列表


async def get_book_by_id_and_user(db: AsyncSession, book_id: int, user_id: int) -> Book | None:
    """按 book_id + user_id 查询单本绘本。"""
    stmt = select(Book).where(Book.id == book_id, Book.user_id == user_id)#查询条件：id 和 user_id 都要匹配
    result = await db.execute(stmt)#执行查询
    return result.scalar_one_or_none()#返回单个结果，如果没有或有多个则返回 None


async def delete_book(db: AsyncSession, book_id: int, user_id: int) -> Book | None:
    """删除绘本。存在则返回删除前对象，不存在返回 None。"""
    book = await get_book_by_id_and_user(db, book_id, user_id)
    if not book:
        return None
    await db.delete(book)        
    await db.commit()
    return book

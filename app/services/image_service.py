"""图片业务服务。"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book_image import BookImage


async def save_upload_file(file: UploadFile, upload_dir: str, book_id: int) -> str:
    """保存上传文件，返回保存路径。"""
    book_dir = Path(upload_dir) / "books" / str(book_id)
    book_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"
    save_path = book_dir / filename

    content = await file.read()
    save_path.write_bytes(content)
    return str(save_path.as_posix())


async def create_book_image_record(
    db: AsyncSession,
    book_id: int,
    image_path: str,
    image_order: int,
) -> BookImage:
    """创建图片记录。"""
    record = BookImage(book_id=book_id, image_path=image_path, image_order=image_order)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_book_images(db: AsyncSession, book_id: int) -> list[BookImage]:
    """按顺序查询绘本图片。"""
    stmt = select(BookImage).where(BookImage.book_id == book_id).order_by(BookImage.image_order.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())

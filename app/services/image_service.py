"""绘本图片服务。

职责：
- 保存用户上传的图片文件，并生成本地存储路径。
- 把已有图片复制到指定绘本目录，用于实时识别保存为绘本页。
- 创建和查询 `BookImage` 数据库记录，维护绘本页顺序。

前端关联：
- `/ui/upload`：上传绘本图片。
- `/ui/books`：查看某本绘本的图片页。
- `/ui/history`：查看历史故事关联的绘本图片。
- `/ui/camera`：保存实时识别结果时，把实拍图片沉淀为绘本图片。

主要路由：
- `app/routers/images.py`：`/api/books/{book_id}/images/upload`
- `app/routers/images.py`：`/api/books/{book_id}/images`
- `app/routers/stories.py`：实时识别保存接口内部调用。
"""

from __future__ import annotations

import uuid
import shutil
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book_image import BookImage


async def save_upload_file(file: UploadFile, upload_dir: str, book_id: int) -> str:
    """保存上传图片到本地目录并返回路径。"""

    book_dir = Path(upload_dir) / "books" / str(book_id)
    book_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"
    save_path = book_dir / filename

    content = await file.read()
    save_path.write_bytes(content)
    return str(save_path.as_posix())


async def save_existing_image_file(source_path: str | Path, upload_dir: str, book_id: int) -> str:
    """复制已有图片到绘本目录并返回新路径。"""

    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"图片文件不存在：{source_path}")

    book_dir = Path(upload_dir) / "books" / str(book_id)
    book_dir.mkdir(parents=True, exist_ok=True)

    suffix = source.suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"
    save_path = book_dir / filename
    shutil.copyfile(source, save_path)
    return str(save_path.as_posix())


async def create_book_image_record(
    db: AsyncSession,
    book_id: int,
    image_path: str,
    image_order: int,
) -> BookImage:
    """创建图片数据库记录。"""

    record = BookImage(book_id=book_id, image_path=image_path, image_order=image_order)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_book_images(db: AsyncSession, book_id: int) -> list[BookImage]:
    """查询某本绘本的所有图片（按页码顺序）。"""

    stmt = select(BookImage).where(BookImage.book_id == book_id).order_by(BookImage.image_order.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())

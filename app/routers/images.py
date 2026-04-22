"""图片路由：上传与列表查询。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.routers.users import get_current_user
from app.schemas.book_image import BookImageInfo
from app.schemas.common import ApiResponse
from app.services.book_service import get_book_by_id_and_user, update_book_cover_image
from app.services.image_service import create_book_image_record, list_book_images, save_upload_file

router = APIRouter(prefix="/api/books", tags=["Images"])


@router.post("/{book_id}/images/upload", response_model=ApiResponse)
async def upload_images_api(
    book_id: int,
    files: list[UploadFile] = File(..., description="可一次上传一张或多张图片"),
    start_order: int = Form(default=1, description="起始页码"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """上传绘本图片并写入图片记录。"""

    book = await get_book_by_id_and_user(db, book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")

    order = start_order
    saved_records: list[dict] = []
    first_saved_path: str | None = None

    for file in files:
        saved_path = await save_upload_file(file=file, upload_dir=settings.upload_dir, book_id=book_id)
        if first_saved_path is None:
            first_saved_path = saved_path

        record = await create_book_image_record(
            db=db,
            book_id=book_id,
            image_path=saved_path,
            image_order=order,
        )
        saved_records.append(BookImageInfo.model_validate(record).model_dump())
        order += 1

    # 自动封面策略：
    # 1) 该绘本当前没有封面 -> 用本次上传的第一页
    # 2) 本次从第 1 页开始上传 -> 覆盖为本次第一页
    if first_saved_path and (not book.cover_image or start_order == 1):
        await update_book_cover_image(db=db, book=book, cover_image=first_saved_path)

    return ApiResponse(success=True, message="上传成功", data=saved_records)


@router.get("/{book_id}/images", response_model=ApiResponse)
async def list_images_api(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """查询某本绘本的图片列表。"""

    book = await get_book_by_id_and_user(db, book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, book_id)
    data = [BookImageInfo.model_validate(item).model_dump() for item in images]
    return ApiResponse(success=True, message="查询成功", data=data)

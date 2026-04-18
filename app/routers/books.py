"""绘本路由：增删查。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.book import BookCreateRequest, BookInfo
from app.schemas.common import ApiResponse
from app.services.book_service import create_book, delete_book, get_book_by_id_and_user, list_books_by_user
from app.routers.users import get_current_user

router = APIRouter(prefix="/api/books", tags=["Books"])


@router.post("", response_model=ApiResponse)
async def create_book_api(
    payload: BookCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """创建绘本。"""

    book = await create_book(
        db=db,
        user_id=current_user.id,
        title=payload.title,
        cover_image=payload.cover_image,
    )
    return ApiResponse(success=True, message="创建绘本成功", data=BookInfo.model_validate(book).model_dump())


@router.get("", response_model=ApiResponse)
async def list_books_api(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """查询当前用户绘本列表。"""

    books = await list_books_by_user(db, current_user.id)
    data = [BookInfo.model_validate(item).model_dump() for item in books]
    return ApiResponse(success=True, message="查询成功", data=data)


@router.get("/{book_id}", response_model=ApiResponse)
async def get_book_api(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """查询单本绘本。"""

    book = await get_book_by_id_and_user(db, book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")
    return ApiResponse(success=True, message="查询成功", data=BookInfo.model_validate(book).model_dump())


@router.delete("/{book_id}", response_model=ApiResponse)
async def delete_book_api(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """删除单本绘本。"""

    book = await delete_book(db, book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")
    return ApiResponse(success=True, message="删除成功", data={"book_id": book_id})

"""故事路由：生成、评估、历史查询。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.routers.users import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.story import StoryEvaluateRequest, StoryGenerateData, StoryGenerateRequest, StoryInfo
from app.services.ai_service import analyze_images, evaluate_story_quality, generate_story
from app.services.book_service import get_book_by_id_and_user
from app.services.image_service import list_book_images
from app.services.story_service import create_story_record, get_story_by_id_and_user, list_stories_by_user

router = APIRouter(prefix="/api/stories", tags=["Stories"])


@router.post("/generate", response_model=ApiResponse)
async def generate_story_api(
    payload: StoryGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """根据绘本图片生成故事并保存记录。"""

    book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, payload.book_id)
    if not images:
        raise HTTPException(status_code=400, detail="该绘本还没有上传图片")

    image_paths = [img.image_path for img in images]
    analysis_result = analyze_images(image_paths)
    story_content = generate_story(
        analysis_result=analysis_result,
        extra_prompt=payload.prompt,
        narration_style=payload.narration_style,
        audience_age=payload.audience_age,
        story_length=payload.story_length,
        character_name=payload.character_name,
    )
    quality = evaluate_story_quality(analysis_result, story_content)

    story_record = await create_story_record(
        db=db,
        user_id=current_user.id,
        book_id=payload.book_id,
        prompt=payload.prompt,
        image_analysis=analysis_result,
        story_content=story_content,
    )
    response_data = StoryGenerateData(
        analysis_result=analysis_result,
        story_content=story_content,
        quality=quality,
        story=StoryInfo.model_validate(story_record),
    )
    return ApiResponse(success=True, message="故事生成成功", data=response_data.model_dump())


@router.post("/evaluate", response_model=ApiResponse)
async def evaluate_story_api(
    payload: StoryEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """对输入故事文本进行质量评估。"""

    book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, payload.book_id)
    if not images:
        raise HTTPException(status_code=400, detail="该绘本还没有上传图片")

    analysis_result = analyze_images([img.image_path for img in images])
    quality = evaluate_story_quality(analysis_result, payload.story_content)
    return ApiResponse(success=True, message="评估完成", data=quality)


@router.get("", response_model=ApiResponse)
async def list_stories_api(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """查询当前用户的故事历史。"""

    stories = await list_stories_by_user(db, current_user.id)
    data = [StoryInfo.model_validate(item).model_dump() for item in stories]
    return ApiResponse(success=True, message="查询成功", data=data)


@router.get("/{story_id}", response_model=ApiResponse)
async def get_story_api(
    story_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """查询单条故事详情。"""

    story = await get_story_by_id_and_user(db, story_id, current_user.id)
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")
    return ApiResponse(success=True, message="查询成功", data=StoryInfo.model_validate(story).model_dump())

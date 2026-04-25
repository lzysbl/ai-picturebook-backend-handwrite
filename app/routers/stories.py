"""故事路由：同步生成、异步任务、质量评估、历史查询。"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.routers.users import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.story import StoryEvaluateRequest, StoryGenerateData, StoryGenerateRequest, StoryInfo
from app.services.ai_service import analyze_images, generate_story
from app.services.book_service import get_book_by_id_and_user
from app.services.eval_service import evaluate_story_full
from app.services.image_service import list_book_images
from app.services.story_service import create_story_record, get_story_by_id_and_user, list_stories_by_user
from app.services.task_progress_service import (
    create_story_task,
    get_story_task,
    task_public_view,
    update_story_task,
)
from app.utils.rate_limiter import enforce_rate_limit

router = APIRouter(prefix="/api/stories", tags=["Stories"])


async def _run_generate_task(
    task_id: str,
    user_id: int,
    payload: StoryGenerateRequest,
    image_paths: list[str],
) -> None:
    """后台异步任务：识别 -> 生成 -> 评价 -> 入库。"""

    total = len(image_paths)

    async def on_batch_progress(done_count: int, total_count: int, _: str) -> None:
        progress = 5 + int((done_count / max(total_count, 1)) * 65)
        await update_story_task(
            task_id,
            status="running",
            progress=min(progress, 70),
            current_step=f"第一阶段，正在识别图片（{done_count}/{total_count}）",
        )

    try:
        await update_story_task(
            task_id,
            status="running",
            progress=5,
            current_step=f"第一阶段，正在识别图片（0/{total}）",
        )
        analysis_result = await analyze_images(image_paths, progress_callback=on_batch_progress)

        await update_story_task(task_id, progress=75, current_step="第二阶段，正在生成故事")
        story_content = await generate_story(
            analysis_result=analysis_result,
            extra_prompt=payload.prompt,
            narration_style=payload.narration_style,
            audience_age=payload.audience_age,
            story_length=payload.story_length,
            character_name=payload.character_name,
        )

        await update_story_task(task_id, progress=85, current_step="第二阶段，正在评估故事质量")
        quality = await evaluate_story_full(
            analysis_result=analysis_result,
            story_content=story_content,
            include_judge=payload.include_judge,
            judge_samples=payload.judge_samples,
        )

        await update_story_task(task_id, progress=92, current_step="第三阶段，正在入库")
        async with SessionLocal() as task_db:
            story_record = await create_story_record(
                db=task_db,
                user_id=user_id,
                book_id=payload.book_id,
                prompt=payload.prompt,
                image_analysis=analysis_result,
                story_content=story_content,
            )

        result = StoryGenerateData(
            analysis_result=analysis_result,
            story_content=story_content,
            quality=quality,
            story=StoryInfo.model_validate(story_record),
        ).model_dump(mode="json")
        await update_story_task(
            task_id,
            status="completed",
            progress=100,
            current_step="第三阶段，生成完成并入库",
            result=result,
        )
    except Exception as exc:  # noqa: BLE001
        await update_story_task(
            task_id,
            status="failed",
            current_step="执行失败",
            error=str(exc),
        )


@router.post("/generate", response_model=ApiResponse)
async def generate_story_api(
    payload: StoryGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """同步生成故事（请求会等待直到故事完成）。"""

    await enforce_rate_limit(
        request=request,
        action="stories:generate_sync",
        limit=settings.rate_limit_story_submit_limit,
        window_seconds=settings.rate_limit_story_submit_window_seconds,
        user_id=current_user.id,
    )

    book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, payload.book_id)
    if not images:
        raise HTTPException(status_code=400, detail="该绘本还没有上传图片")

    image_paths = [img.image_path for img in images]
    analysis_result = await analyze_images(image_paths)
    story_content = await generate_story(
        analysis_result=analysis_result,
        extra_prompt=payload.prompt,
        narration_style=payload.narration_style,
        audience_age=payload.audience_age,
        story_length=payload.story_length,
        character_name=payload.character_name,
    )
    quality = await evaluate_story_full(
        analysis_result=analysis_result,
        story_content=story_content,
        include_judge=payload.include_judge,
        judge_samples=payload.judge_samples,
    )

    story_record = await create_story_record(
        db=db,
        user_id=current_user.id,
        book_id=payload.book_id,
        prompt=payload.prompt,
        image_analysis=analysis_result,
        story_content=story_content,
    )

    data = StoryGenerateData(
        analysis_result=analysis_result,
        story_content=story_content,
        quality=quality,
        story=StoryInfo.model_validate(story_record),
    ).model_dump(mode="json")
    return ApiResponse(success=True, message="故事生成成功", data=data)


@router.post("/generate/submit", response_model=ApiResponse)
async def submit_generate_task_api(
    payload: StoryGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """提交异步生成任务。"""

    await enforce_rate_limit(
        request=request,
        action="stories:generate_submit",
        limit=settings.rate_limit_story_submit_limit,
        window_seconds=settings.rate_limit_story_submit_window_seconds,
        user_id=current_user.id,
    )

    book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, payload.book_id)
    if not images:
        raise HTTPException(status_code=400, detail="该绘本还没有上传图片")

    task_id = str(uuid.uuid4())
    await create_story_task(task_id=task_id, user_id=current_user.id)

    image_paths = [img.image_path for img in images]
    asyncio.create_task(_run_generate_task(task_id, current_user.id, payload, image_paths))
    return ApiResponse(success=True, message="任务已提交", data={"task_id": task_id})


@router.get("/tasks/{task_id}", response_model=ApiResponse)
async def get_generate_task_api(task_id: str, current_user=Depends(get_current_user)) -> ApiResponse:
    """查询异步任务进度。"""

    task = await get_story_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return ApiResponse(success=True, message="查询成功", data=task_public_view(task))


@router.post("/evaluate", response_model=ApiResponse)
async def evaluate_story_api(
    payload: StoryEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """对输入故事文本做质量评估。"""

    book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, payload.book_id)
    if not images:
        raise HTTPException(status_code=400, detail="该绘本还没有上传图片")

    analysis_result = await analyze_images([img.image_path for img in images])
    quality = await evaluate_story_full(
        analysis_result=analysis_result,
        story_content=payload.story_content,
        include_judge=payload.include_judge,
        judge_samples=payload.judge_samples,
    )
    return ApiResponse(success=True, message="评估完成", data=quality)


@router.get("/{story_id}/quality", response_model=ApiResponse)
async def get_story_quality_api(
    story_id: int,
    include_judge: bool = False,
    judge_samples: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """按故事记录评估质量。"""

    story = await get_story_by_id_and_user(db, story_id, current_user.id)
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")

    quality = await evaluate_story_full(
        image_analysis=story.image_analysis,
        story_content=story.story_content,
        include_judge=include_judge,
        judge_samples=judge_samples,
    )
    return ApiResponse(success=True, message="评估完成", data=quality)


@router.get("", response_model=ApiResponse)
async def list_stories_api(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """查询当前用户故事历史。"""

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


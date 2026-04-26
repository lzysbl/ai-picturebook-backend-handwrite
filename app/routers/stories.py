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
from app.services.ai_service import analyze_images
from app.services.book_service import get_book_by_id_and_user
from app.services.eval_service import evaluate_story_full
from app.services.image_service import list_book_images
from app.services.story_generation_service import generate_story, generate_story_from_images
from app.services.story_quality_cache_service import clear_story_quality_cache, get_story_quality_cache, set_story_quality_cache
from app.services.story_service import (
    create_story_record,
    delete_story_by_id_and_user,
    get_story_by_id_and_user,
    list_stories_by_user,
)
from app.services.task_progress_service import (
    create_story_task,
    get_story_task,
    task_public_view,
    update_story_task,
)
from app.utils.rate_limiter import enforce_rate_limit

router = APIRouter(prefix="/api/stories", tags=["Stories"])


def _normalize_judge_samples(include_judge: bool, judge_samples: int | None) -> int | None:
    """Normalize judge samples for cache key and scoring behavior."""

    if not include_judge:
        return None
    sample = judge_samples or settings.judge_samples
    return max(1, min(sample, 5))


def _use_whole_book_mode(payload: StoryGenerateRequest) -> bool:
    """Return whether the request should use the whole-book multimodal flow."""
    mode = (payload.generation_mode or "whole_book").strip().lower()
    return mode in {"whole_book", "whole-book", "all_images", "all-images"}


async def _generate_with_pipeline(
    payload: StoryGenerateRequest,
    image_paths: list[str],
    book_title: str | None,
    progress_callback=None,
) -> tuple[list[dict], str]:
    """Old stable flow: analyze page images first, then generate story from page analysis."""
    analysis_result = await analyze_images(image_paths, progress_callback=progress_callback)
    story_content = await generate_story(
        analysis_result=analysis_result,
        extra_prompt=payload.prompt,
        narration_style=payload.narration_style,
        audience_age=payload.audience_age,
        story_length=payload.story_length,
        character_name=payload.character_name,
        fallback_title=book_title,
    )
    return analysis_result, story_content


async def _generate_with_selected_mode(
    payload: StoryGenerateRequest,
    image_paths: list[str],
    book_title: str | None,
    progress_callback=None,
) -> tuple[list[dict], str]:
    """Prefer whole-book generation, and fall back to the old pipeline if it fails."""
    if _use_whole_book_mode(payload):
        try:
            return await generate_story_from_images(
                image_paths=image_paths,
                extra_prompt=payload.prompt,
                narration_style=payload.narration_style,
                audience_age=payload.audience_age,
                story_length=payload.story_length,
                character_name=payload.character_name,
                fallback_title=book_title,
            )
        except Exception:
            # Whole-book multimodal calls may fail because of image count, model config, or API limits.
            # Falling back keeps the product usable instead of blocking the user.
            pass

    return await _generate_with_pipeline(
        payload=payload,
        image_paths=image_paths,
        book_title=book_title,
        progress_callback=progress_callback,
    )


async def _run_generate_task(
    task_id: str,
    user_id: int,
    payload: StoryGenerateRequest,
    image_paths: list[str],
    book_title: str | None = None,
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
            progress=8,
            current_step=(
                f"第一阶段，正在整本理解绘本（共{total}页）"
                if _use_whole_book_mode(payload)
                else f"第一阶段，正在识别图片（0/{total}）"
            ),
        )
        analysis_result, story_content = await _generate_with_selected_mode(
            payload=payload,
            image_paths=image_paths,
            book_title=book_title,
            progress_callback=on_batch_progress,
        )

        await update_story_task(task_id, progress=80, current_step="第二阶段，故事已生成，正在评估")
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
            normalized_samples = _normalize_judge_samples(payload.include_judge, payload.judge_samples)
            await set_story_quality_cache(
                story_id=story_record.id,
                include_judge=payload.include_judge,
                judge_samples=normalized_samples,
                quality=quality,
            )
            # Keep a basic score cache for list and fallback display.
            if payload.include_judge:
                basic_quality = await evaluate_story_full(
                    analysis_result=analysis_result,
                    story_content=story_content,
                    include_judge=False,
                    judge_samples=None,
                )
                await set_story_quality_cache(
                    story_id=story_record.id,
                    include_judge=False,
                    judge_samples=None,
                    quality=basic_quality,
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
    analysis_result, story_content = await _generate_with_selected_mode(
        payload=payload,
        image_paths=image_paths,
        book_title=book.title,
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
    normalized_samples = _normalize_judge_samples(payload.include_judge, payload.judge_samples)
    await set_story_quality_cache(
        story_id=story_record.id,
        include_judge=payload.include_judge,
        judge_samples=normalized_samples,
        quality=quality,
    )
    # Keep a basic score cache for list and fallback display.
    if payload.include_judge:
        basic_quality = await evaluate_story_full(
            analysis_result=analysis_result,
            story_content=story_content,
            include_judge=False,
            judge_samples=None,
        )
        await set_story_quality_cache(
            story_id=story_record.id,
            include_judge=False,
            judge_samples=None,
            quality=basic_quality,
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
    asyncio.create_task(_run_generate_task(task_id, current_user.id, payload, image_paths, book.title))
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
    refresh: bool = False,
    cached_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """按故事记录评估质量。"""

    story = await get_story_by_id_and_user(db, story_id, current_user.id)
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")

    normalized_samples = _normalize_judge_samples(include_judge, judge_samples)
    if not refresh:
        cached_payload = await get_story_quality_cache(
            story_id=story.id,
            include_judge=include_judge,
            judge_samples=normalized_samples,
        )
        if cached_payload and isinstance(cached_payload.get("quality"), dict):
            return ApiResponse(success=True, message="读取历史评分成功", data=cached_payload["quality"])
        if cached_only:
            return ApiResponse(success=True, message="暂无已保存评分", data=None)

    quality = await evaluate_story_full(
        image_analysis=story.image_analysis,
        story_content=story.story_content,
        include_judge=include_judge,
        judge_samples=normalized_samples,
    )
    await set_story_quality_cache(
        story_id=story.id,
        include_judge=include_judge,
        judge_samples=normalized_samples,
        quality=quality,
    )
    if refresh:
        return ApiResponse(success=True, message="评分已刷新", data=quality)
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


@router.delete("/{story_id}", response_model=ApiResponse)
async def delete_story_api(
    story_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """Delete one story history record of current user."""

    deleted = await delete_story_by_id_and_user(db, story_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="故事不存在")

    await clear_story_quality_cache(story_id)
    return ApiResponse(success=True, message="删除成功", data={"story_id": story_id})


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

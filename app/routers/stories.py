"""故事路由：同步生成、异步任务、评估、历史查询。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal, get_db
from app.routers.users import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.story import StoryEvaluateRequest, StoryGenerateData, StoryGenerateRequest, StoryInfo
from app.services.ai_service import analyze_images, evaluate_story_quality, generate_story
from app.services.book_service import get_book_by_id_and_user
from app.services.image_service import list_book_images
from app.services.story_service import create_story_record, get_story_by_id_and_user, list_stories_by_user

router = APIRouter(prefix="/api/stories", tags=["Stories"])
_story_tasks: dict[str, dict[str, Any]] = {}


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "current_step": task["current_step"],
        "error": task.get("error"),
        "result": task.get("result"),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


def _update_task(task_id: str, **kwargs: Any) -> None:
    task = _story_tasks.get(task_id)
    if not task:
        return
    task.update(kwargs)
    task["updated_at"] = datetime.utcnow().isoformat()


async def _run_generate_task(
    task_id: str,
    user_id: int,
    payload: StoryGenerateRequest,
    image_paths: list[str],
) -> None:
    total = len(image_paths)

    async def on_batch_progress(done_count: int, total_count: int, step_text: str) -> None:
        # 识别阶段占用 5%~70%
        progress = 5 + int((done_count / max(total_count, 1)) * 65)
        _update_task(
            task_id,
            status="running",
            progress=min(progress, 70),
            current_step=f"第一阶段，正在识别图片（{done_count}/{total_count}）",
        )

    try:
        _update_task(task_id, status="running", progress=5, current_step=f"第一阶段，正在识别图片（0/{total}）")
        analysis_result = await analyze_images(image_paths, progress_callback=on_batch_progress)
        _update_task(task_id, progress=75, current_step="第二阶段，正在生成故事")

        story_content = await generate_story(
            analysis_result=analysis_result,
            extra_prompt=payload.prompt,
            narration_style=payload.narration_style,
            audience_age=payload.audience_age,
            story_length=payload.story_length,
            character_name=payload.character_name,
        )
        quality = evaluate_story_quality(analysis_result, story_content)
        _update_task(task_id, progress=90, current_step="第三阶段，正在入库")

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
        ).model_dump()
        _update_task(task_id, status="completed", progress=100, current_step="第三阶段，生成完成并入库", result=result)
    except Exception as exc:  # noqa: BLE001
        _update_task(task_id, status="failed", current_step="执行失败", error=str(exc))


@router.post("/generate", response_model=ApiResponse)
async def generate_story_api(
    payload: StoryGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
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
    quality = evaluate_story_quality(analysis_result, story_content)
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
    )
    return ApiResponse(success=True, message="故事生成成功", data=data.model_dump())


@router.post("/generate/submit", response_model=ApiResponse)
async def submit_generate_task_api(
    payload: StoryGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, payload.book_id)
    if not images:
        raise HTTPException(status_code=400, detail="该绘本还没有上传图片")

    task_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat()
    _story_tasks[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "progress": 0,
        "current_step": "等待执行",
        "error": None,
        "result": None,
        "user_id": current_user.id,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    image_paths = [img.image_path for img in images]
    asyncio.create_task(_run_generate_task(task_id, current_user.id, payload, image_paths))
    return ApiResponse(success=True, message="任务已提交", data={"task_id": task_id})


@router.get("/tasks/{task_id}", response_model=ApiResponse)
async def get_generate_task_api(task_id: str, current_user=Depends(get_current_user)) -> ApiResponse:
    task = _story_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return ApiResponse(success=True, message="查询成功", data=_task_view(task))


@router.post("/evaluate", response_model=ApiResponse)
async def evaluate_story_api(
    payload: StoryEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    images = await list_book_images(db, payload.book_id)
    if not images:
        raise HTTPException(status_code=400, detail="该绘本还没有上传图片")

    analysis_result = await analyze_images([img.image_path for img in images])
    quality = evaluate_story_quality(analysis_result, payload.story_content)
    return ApiResponse(success=True, message="评估完成", data=quality)


@router.get("", response_model=ApiResponse)
async def list_stories_api(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    stories = await list_stories_by_user(db, current_user.id)
    data = [StoryInfo.model_validate(item).model_dump() for item in stories]
    return ApiResponse(success=True, message="查询成功", data=data)


@router.get("/{story_id}", response_model=ApiResponse)
async def get_story_api(
    story_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    story = await get_story_by_id_and_user(db, story_id, current_user.id)
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")
    return ApiResponse(success=True, message="查询成功", data=StoryInfo.model_validate(story).model_dump())

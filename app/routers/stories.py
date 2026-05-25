"""Story routes: generation, scan, evaluation, tasks, and history."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from time import time
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.routers.users import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.story import (
    LiveScanStorySaveRequest,
    StoryEvaluateRequest,
    StoryGenerateData,
    StoryGenerateRequest,
    StoryInfo,
    StoryTTSRequest,
)
from app.services.book_service import create_book, get_book_by_id_and_user, update_book_cover_image
from app.services.eval_service import evaluate_story_full
from app.services.image_service import create_book_image_record, list_book_images, save_existing_image_file
from app.services.live_story_service import (
    build_character_registry as live_build_character_registry,
    build_contextual_live_scan_story as live_build_contextual_live_scan_story,
    context_pages_to_generation_input as live_context_pages_to_generation_input,
    merge_scan_session_pages as live_merge_scan_session_pages,
    summarize_page_for_live_story as live_summarize_page_for_live_story,
)
from app.services import live_scan_runtime_service as live_scan_runtime
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
from app.services.tts_service import synthesize_text_to_speech
from app.services.vision_analysis_service import analyze_image_with_direct_story, analyze_images, stream_image_direct_story
from app.utils.rate_limiter import enforce_rate_limit

router = APIRouter(prefix="/api/stories", tags=["Stories"])
logger = logging.getLogger(__name__)


def _normalize_judge_samples(include_judge: bool, judge_samples: int | None) -> int | None:
    if not include_judge:
        return None
    sample = judge_samples or settings.judge_samples
    return max(1, min(sample, 5))


def _use_whole_book_mode(payload: StoryGenerateRequest) -> bool:
    mode = (payload.generation_mode or "whole_book").strip().lower()
    return mode in {"whole_book", "whole-book", "all_images", "all-images"}


def _normalize_optional_text(value: str | None, default: str | None = None) -> str | None:
    text = (value or "").strip()
    return text if text else default


# Rebind runtime helpers to the dedicated service so the router only owns API flow.
_elapsed_ms = live_scan_runtime.elapsed_ms
_resolve_user_live_scan_path = live_scan_runtime.resolve_user_live_scan_path
_collect_live_scan_paths = live_scan_runtime.collect_live_scan_paths
_scan_cache_key = live_scan_runtime.scan_cache_key
_normalize_crop_box = live_scan_runtime.normalize_crop_box
_sse_event = live_scan_runtime.sse_event
_clean_live_scan_stream_text = live_scan_runtime.clean_live_scan_stream_text
_detect_page_box_with_opencv = live_scan_runtime.detect_page_box_with_opencv
_crop_image_to_temp = live_scan_runtime.crop_image_to_temp
_enhance_scan_image = live_scan_runtime.enhance_scan_image
_get_scan_cache = live_scan_runtime.get_scan_cache
_set_scan_cache = live_scan_runtime.set_scan_cache
_scan_session_key = live_scan_runtime.scan_session_key
_get_scan_session = live_scan_runtime.get_scan_session
_set_scan_session = live_scan_runtime.set_scan_session


async def _generate_with_pipeline(
    payload: StoryGenerateRequest,
    image_paths: list[str],
    book_title: str | None,
    progress_callback=None,
) -> tuple[list[dict[str, Any]], str]:
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
) -> tuple[list[dict[str, Any]], str]:
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


@router.post("/scan", response_model=ApiResponse)
async def scan_story_page_api(
    request: Request,
    image: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    narration_style: str | None = Form(default="温柔"),
    audience_age: str | None = Form(default="3-6"),
    response_mode: str | None = Form(default="fast"),
    crop_source: str | None = Form(default=None),
    crop_x: float | None = Form(default=None),
    crop_y: float | None = Form(default=None),
    crop_width: float | None = Form(default=None),
    crop_height: float | None = Form(default=None),
    replace_last_page: bool = Form(default=False),
    include_judge: bool = Form(default=False),
    judge_samples: int | None = Form(default=None),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    total_started_at = time()
    image_bytes = await image.read()
    read_ms = _elapsed_ms(total_started_at)
    suffix = Path(image.filename or "frame.jpg").suffix or ".jpg"
    normalized_session_id = (session_id or "").strip()
    normalized_prompt = _normalize_optional_text(prompt)
    normalized_style = _normalize_optional_text(narration_style, "温柔")
    normalized_age = _normalize_optional_text(audience_age, "3-6")
    normalized_mode = (response_mode or "fast").strip().lower()
    normalized_crop_source = (crop_source or "").strip().lower()
    normalized_crop_box = _normalize_crop_box(crop_x, crop_y, crop_width, crop_height)
    live_ai_provider = _normalize_optional_text(settings.live_ai_provider, settings.ai_provider)
    if normalized_mode not in {"fast", "full", "direct"}:
        normalized_mode = "fast"

    cache_key = _scan_cache_key(
        image_bytes=image_bytes,
        prompt=normalized_prompt,
        narration_style=normalized_style,
        audience_age=normalized_age,
        response_mode=normalized_mode,
        provider=live_ai_provider,
        crop_box=normalized_crop_box,
    )
    cached = await _get_scan_cache(cache_key) if not normalized_session_id else None
    if cached is not None:
        cached_timing = dict(cached.get("timing") or {})
        cached_timing.update(
            {
                "cache_hit": True,
                "cache_lookup_ms": _elapsed_ms(total_started_at),
                "total_ms": _elapsed_ms(total_started_at),
            }
        )
        cached_payload = {**cached, "timing": cached_timing}
        logger.info(
            "scan.timing mode=%s cache_hit=true crop_mode=%s total_ms=%s user_id=%s session=%s provider=%s",
            cached_payload.get("response_mode", normalized_mode),
            cached_payload.get("crop_mode", "-"),
            cached_timing["total_ms"],
            current_user.id,
            normalized_session_id or "-",
            cached_payload.get("provider", live_ai_provider),
        )
        return ApiResponse(success=True, message="实时识别完成（缓存）", data=cached_payload)

    tmp_path: Path | None = None
    scan_path: Path | None = None
    prepared_path: Path | None = None
    crop_mode = "full_frame"
    effective_crop_box = normalized_crop_box
    temp_write_ms = 0
    page_detect_ms = 0
    crop_ms = 0
    enhance_ms = 0
    persisted_scan_path: Path | None = None
    analysis_ms = 0
    page_summary_ms = 0
    session_load_ms = 0
    story_ms = 0
    session_save_ms = 0
    quality_ms = 0
    try:
        stage_started_at = time()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)
        temp_write_ms = _elapsed_ms(stage_started_at)

        stage_started_at = time()
        if normalized_crop_source == "guide" and normalized_crop_box is not None:
            effective_crop_box = normalized_crop_box
            crop_mode = "guide_crop"
        elif normalized_crop_source == "detected":
            crop_mode = "frontend_crop"
        else:
            opencv_crop_box = _detect_page_box_with_opencv(tmp_path)
            if opencv_crop_box is not None:
                effective_crop_box = opencv_crop_box
                crop_mode = "model_crop"
            elif normalized_crop_box is not None:
                crop_mode = "guide_crop"
        page_detect_ms = _elapsed_ms(stage_started_at)

        stage_started_at = time()
        scan_path, crop_result_mode = _crop_image_to_temp(tmp_path, effective_crop_box)
        if crop_result_mode == "full_frame":
            crop_mode = "full_frame"
        crop_ms = _elapsed_ms(stage_started_at)
        stage_started_at = time()
        prepared_path = _enhance_scan_image(scan_path)
        enhance_ms = _elapsed_ms(stage_started_at)
        persisted_dir = Path(settings.upload_dir) / "live_scans" / str(current_user.id)
        persisted_dir.mkdir(parents=True, exist_ok=True)
        persisted_scan_path = persisted_dir / f"{uuid.uuid4().hex}.jpg"
        with Image.open(prepared_path) as persisted_img:
            persisted_img.convert("RGB").save(persisted_scan_path, format="JPEG", quality=88)
        recent_pages: list[dict[str, Any]] = []
        context_pages: list[dict[str, Any]] = []
        character_registry: list[str] = []
        session_page_count = 1
        session_key = ""

        if normalized_session_id:
            stage_started_at = time()
            session_key = _scan_session_key(current_user.id, normalized_session_id)
            session_payload = await _get_scan_session(session_key) or {}
            recent_pages = (
                session_payload.get("recent_pages", [])
                if isinstance(session_payload.get("recent_pages", []), list)
                else []
            )
            session_load_ms = _elapsed_ms(stage_started_at)
        context_pages = recent_pages[:-1] if replace_last_page and recent_pages else recent_pages
        current_page_no = len(context_pages) + 1

        if normalized_mode == "direct":
            stage_started_at = time()
            direct_result = await analyze_image_with_direct_story(
                str(prepared_path),
                provider_override=live_ai_provider,
                page_no=current_page_no,
                narration_style=normalized_style,
                audience_age=normalized_age,
                extra_prompt=normalized_prompt,
                recent_pages=context_pages,
            )
            analysis_result = [dict(direct_result.get("analysis") or {})]
            analysis_result[0].update(
                {
                    "page": current_page_no,
                    "image_path": str(persisted_scan_path.as_posix()) if persisted_scan_path else str(prepared_path),
                }
            )
            story_content = str(direct_result.get("story") or "").strip()
            analysis_ms = _elapsed_ms(stage_started_at)

            stage_started_at = time()
            current_page = live_summarize_page_for_live_story(analysis_result)
            if persisted_scan_path is not None:
                current_page["image_path"] = str(persisted_scan_path.as_posix())
            page_summary_ms = _elapsed_ms(stage_started_at)
            character_registry = current_page.get("roles", [])
            story_ms = 0
        else:
            stage_started_at = time()
            analysis_result = await analyze_images(
                [str(prepared_path)],
                provider_override=live_ai_provider,
                compact=normalized_mode == "fast",
            )
            if persisted_scan_path and analysis_result:
                analysis_result[0]["image_path"] = str(persisted_scan_path.as_posix())
            analysis_ms = _elapsed_ms(stage_started_at)
            stage_started_at = time()
            current_page = live_summarize_page_for_live_story(analysis_result)
            if persisted_scan_path is not None:
                current_page["image_path"] = str(persisted_scan_path.as_posix())
            page_summary_ms = _elapsed_ms(stage_started_at)
            character_registry = current_page.get("roles", [])

        stage_started_at = time()
        if normalized_mode == "full":
            generation_input = (
                live_context_pages_to_generation_input(context_pages, current_page)
                if context_pages
                else analysis_result
            )
            story_content = await generate_story(
                analysis_result=generation_input,
                extra_prompt=normalized_prompt,
                narration_style=normalized_style,
                audience_age=normalized_age,
                story_length="short",
                character_name=None,
                fallback_title="实时扫描绘本",
            )
        elif normalized_mode == "fast":
            story_content = live_build_contextual_live_scan_story(
                recent_pages=context_pages,
                current_page=current_page,
                narration_style=normalized_style,
                audience_age=normalized_age,
                extra_prompt=normalized_prompt,
            )
        if normalized_mode != "direct":
            story_ms = _elapsed_ms(stage_started_at)

        if normalized_session_id:
            stage_started_at = time()
            if replace_last_page and recent_pages:
                merged_pages = [*recent_pages[:-1], current_page][-3:]
            else:
                merged_pages = live_merge_scan_session_pages(recent_pages, current_page)
            character_registry = live_build_character_registry(merged_pages)
            session_page_count = len(merged_pages)
            await _set_scan_session(
                session_key,
                {
                    "recent_pages": merged_pages,
                    "character_registry": character_registry,
                },
            )
            session_save_ms = _elapsed_ms(stage_started_at)
        else:
            character_registry = live_build_character_registry([current_page])

        stage_started_at = time()
        quality = await evaluate_story_full(
            analysis_result=analysis_result,
            story_content=story_content,
            include_judge=include_judge,
            judge_samples=judge_samples,
        )
        quality_ms = _elapsed_ms(stage_started_at)
    finally:
        if prepared_path and prepared_path.exists():
            prepared_path.unlink(missing_ok=True)
        if scan_path and tmp_path and scan_path != tmp_path and scan_path.exists():
            scan_path.unlink(missing_ok=True)
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    total_ms = _elapsed_ms(total_started_at)
    timing = {
        "cache_hit": False,
        "response_mode": normalized_mode,
        "crop_mode": crop_mode,
        "provider": live_ai_provider,
        "replace_last_page": replace_last_page,
        "read_ms": read_ms,
        "temp_write_ms": temp_write_ms,
        "page_detect_ms": page_detect_ms,
        "crop_ms": crop_ms,
        "enhance_ms": enhance_ms,
        "analysis_ms": analysis_ms,
        "page_summary_ms": page_summary_ms,
        "session_load_ms": session_load_ms,
        "story_ms": story_ms,
        "session_save_ms": session_save_ms,
        "quality_ms": quality_ms,
        "total_ms": total_ms,
    }
    logger.info(
        (
            "scan.timing mode=%s cache_hit=false crop_mode=%s total_ms=%s "
            "analysis_ms=%s story_ms=%s quality_ms=%s page_detect_ms=%s crop_ms=%s "
            "enhance_ms=%s session_load_ms=%s session_save_ms=%s user_id=%s session=%s provider=%s"
        ),
        normalized_mode,
        crop_mode,
        total_ms,
        analysis_ms,
        story_ms,
        quality_ms,
        page_detect_ms,
        crop_ms,
        enhance_ms,
        session_load_ms,
        session_save_ms,
        current_user.id,
        normalized_session_id or "-",
        live_ai_provider,
    )

    payload = {
        "analysis_result": analysis_result,
        "story_content": story_content,
        "quality": quality,
        "response_mode": normalized_mode,
        "provider": live_ai_provider,
        "crop_mode": crop_mode,
        "crop_box": effective_crop_box,
        "scan_image_path": str(persisted_scan_path.as_posix()) if persisted_scan_path else None,
        "timing": timing,
        "replace_last_page": replace_last_page,
        "context": {
            "session_id": normalized_session_id or None,
            "recent_page_count": session_page_count,
            "character_registry": character_registry,
        },
    }
    if not normalized_session_id:
        await _set_scan_cache(cache_key, payload)
    return ApiResponse(success=True, message="实时识别完成", data=payload)


@router.post("/scan/stream")
async def stream_scan_story_page_api(
    request: Request,
    image: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    narration_style: str | None = Form(default="温柔"),
    audience_age: str | None = Form(default="3-6"),
    crop_source: str | None = Form(default=None),
    crop_x: float | None = Form(default=None),
    crop_y: float | None = Form(default=None),
    crop_width: float | None = Form(default=None),
    crop_height: float | None = Form(default=None),
    response_mode: str | None = Form(default="direct"),
    replace_last_page: bool = Form(default=False),
    include_judge: bool = Form(default=False),
    judge_samples: int | None = Form(default=None),
    current_user=Depends(get_current_user),
) -> StreamingResponse:
    total_started_at = time()
    image_bytes = await image.read()
    read_ms = _elapsed_ms(total_started_at)
    suffix = Path(image.filename or "frame.jpg").suffix or ".jpg"
    normalized_session_id = (session_id or "").strip()
    normalized_prompt = _normalize_optional_text(prompt)
    normalized_style = _normalize_optional_text(narration_style, "温柔")
    normalized_age = _normalize_optional_text(audience_age, "3-6")
    normalized_crop_source = (crop_source or "").strip().lower()
    normalized_crop_box = _normalize_crop_box(crop_x, crop_y, crop_width, crop_height)
    live_ai_provider = _normalize_optional_text(settings.live_ai_provider, settings.ai_provider)
    normalized_mode = (response_mode or "direct").strip().lower()
    stream_mode = "fast_stream" if normalized_mode == "fast" else "direct_stream"

    async def event_generator():
        tmp_path: Path | None = None
        scan_path: Path | None = None
        prepared_path: Path | None = None
        persisted_scan_path: Path | None = None
        crop_mode = "full_frame"
        effective_crop_box = normalized_crop_box
        temp_write_ms = 0
        page_detect_ms = 0
        crop_ms = 0
        enhance_ms = 0
        session_load_ms = 0
        session_save_ms = 0
        analysis_ms = 0
        quality_ms = 0
        first_delta_ms: int | None = None
        story_chunks: list[str] = []
        analysis_result: list[dict[str, Any]] = []
        current_page: dict[str, Any] = {}
        context_pages: list[dict[str, Any]] = []
        recent_pages: list[dict[str, Any]] = []
        character_registry: list[str] = []
        session_page_count = 1
        session_key = ""

        try:
            stage_started_at = time()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(image_bytes)
                tmp_path = Path(tmp.name)
            temp_write_ms = _elapsed_ms(stage_started_at)

            stage_started_at = time()
            if normalized_crop_source == "guide" and normalized_crop_box is not None:
                effective_crop_box = normalized_crop_box
                crop_mode = "guide_crop"
            elif normalized_crop_source == "detected":
                crop_mode = "frontend_crop"
            else:
                opencv_crop_box = _detect_page_box_with_opencv(tmp_path)
                if opencv_crop_box is not None:
                    effective_crop_box = opencv_crop_box
                    crop_mode = "model_crop"
                elif normalized_crop_box is not None:
                    crop_mode = "guide_crop"
            page_detect_ms = _elapsed_ms(stage_started_at)

            stage_started_at = time()
            scan_path, crop_result_mode = _crop_image_to_temp(tmp_path, effective_crop_box)
            if crop_result_mode == "full_frame":
                crop_mode = "full_frame"
            crop_ms = _elapsed_ms(stage_started_at)

            stage_started_at = time()
            prepared_path = _enhance_scan_image(scan_path)
            enhance_ms = _elapsed_ms(stage_started_at)

            persisted_dir = Path(settings.upload_dir) / "live_scans" / str(current_user.id)
            persisted_dir.mkdir(parents=True, exist_ok=True)
            persisted_scan_path = persisted_dir / f"{uuid.uuid4().hex}.jpg"
            with Image.open(prepared_path) as persisted_img:
                persisted_img.convert("RGB").save(persisted_scan_path, format="JPEG", quality=88)

            if normalized_session_id:
                stage_started_at = time()
                session_key = _scan_session_key(current_user.id, normalized_session_id)
                session_payload = await _get_scan_session(session_key) or {}
                recent_pages = (
                    session_payload.get("recent_pages", [])
                    if isinstance(session_payload.get("recent_pages", []), list)
                    else []
                )
                session_load_ms = _elapsed_ms(stage_started_at)
            context_pages = recent_pages[:-1] if replace_last_page and recent_pages else recent_pages
            current_page_no = len(context_pages) + 1

            yield _sse_event(
                "meta",
                {
                    "response_mode": stream_mode,
                    "provider": live_ai_provider,
                    "crop_mode": crop_mode,
                    "crop_box": effective_crop_box,
                    "scan_image_path": str(persisted_scan_path.as_posix()),
                    "replace_last_page": replace_last_page,
                    "context": {
                        "session_id": normalized_session_id or None,
                        "recent_page_count": current_page_no,
                    },
                },
            )

            stage_started_at = time()
            async for delta in stream_image_direct_story(
                str(prepared_path),
                provider_override=live_ai_provider,
                page_no=current_page_no,
                narration_style=normalized_style,
                audience_age=normalized_age,
                extra_prompt=normalized_prompt,
                recent_pages=context_pages,
            ):
                if first_delta_ms is None:
                    first_delta_ms = _elapsed_ms(stage_started_at)
                story_chunks.append(delta)
                yield _sse_event("delta", {"text": delta})
            analysis_ms = _elapsed_ms(stage_started_at)

            story_content = _clean_live_scan_stream_text("".join(story_chunks))
            analysis_result = [
                {
                    "page": current_page_no,
                    "image_path": str(persisted_scan_path.as_posix()),
                    "角色": [],
                    "场景": "实时扫描绘本",
                    "动作": [],
                    "情绪": "温暖",
                    "关键物体": [],
                    "画面文字": [],
                    "is_picturebook_page": not story_content.startswith("请将绘本页放入引导框"),
                    "page_confidence": 0.6 if story_content else 0.0,
                }
            ]
            current_page = live_summarize_page_for_live_story(analysis_result)
            current_page["story"] = story_content
            current_page["image_path"] = str(persisted_scan_path.as_posix())

            if normalized_session_id:
                stage_started_at = time()
                if replace_last_page and recent_pages:
                    merged_pages = [*recent_pages[:-1], current_page][-3:]
                else:
                    # Stream mode has intentionally lightweight analysis, so do not
                    # collapse pages by summary similarity here.
                    merged_pages = [*recent_pages, current_page][-3:]
                character_registry = live_build_character_registry(merged_pages)
                session_page_count = len(merged_pages)
                await _set_scan_session(
                    session_key,
                    {
                        "recent_pages": merged_pages,
                        "character_registry": character_registry,
                    },
                )
                session_save_ms = _elapsed_ms(stage_started_at)
            else:
                character_registry = live_build_character_registry([current_page])

            stage_started_at = time()
            quality = await evaluate_story_full(
                analysis_result=analysis_result,
                story_content=story_content,
                include_judge=include_judge,
                judge_samples=judge_samples,
            )
            quality_ms = _elapsed_ms(stage_started_at)

            total_ms = _elapsed_ms(total_started_at)
            timing = {
                "cache_hit": False,
                "response_mode": stream_mode,
                "crop_mode": crop_mode,
                "provider": live_ai_provider,
                "replace_last_page": replace_last_page,
                "read_ms": read_ms,
                "temp_write_ms": temp_write_ms,
                "page_detect_ms": page_detect_ms,
                "crop_ms": crop_ms,
                "enhance_ms": enhance_ms,
                "analysis_ms": analysis_ms,
                "first_delta_ms": first_delta_ms,
                "story_ms": 0,
                "session_load_ms": session_load_ms,
                "session_save_ms": session_save_ms,
                "quality_ms": quality_ms,
                "total_ms": total_ms,
            }
            payload = {
                "analysis_result": analysis_result,
                "story_content": story_content,
                "quality": quality,
                "response_mode": "direct_stream",
                "provider": live_ai_provider,
                "crop_mode": crop_mode,
                "crop_box": effective_crop_box,
                "scan_image_path": str(persisted_scan_path.as_posix()),
                "timing": timing,
                "replace_last_page": replace_last_page,
                "context": {
                    "session_id": normalized_session_id or None,
                    "recent_page_count": session_page_count,
                    "character_registry": character_registry,
                },
            }
            logger.info(
                (
                    "scan.stream_timing mode=%s crop_mode=%s total_ms=%s "
                    "first_delta_ms=%s analysis_ms=%s quality_ms=%s session_load_ms=%s "
                    "session_save_ms=%s user_id=%s session=%s provider=%s"
                ),
                stream_mode,
                crop_mode,
                total_ms,
                first_delta_ms,
                analysis_ms,
                quality_ms,
                session_load_ms,
                session_save_ms,
                current_user.id,
                normalized_session_id or "-",
                live_ai_provider,
            )
            yield _sse_event("done", payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scan.stream_failed user_id=%s", current_user.id)
            yield _sse_event("error", {"message": str(exc) or "stream scan failed"})
        finally:
            if prepared_path and prepared_path.exists():
                prepared_path.unlink(missing_ok=True)
            if scan_path and tmp_path and scan_path != tmp_path and scan_path.exists():
                scan_path.unlink(missing_ok=True)
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/tts", response_model=ApiResponse)
async def story_tts_api(
    payload: StoryTTSRequest,
    request: Request,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    total_started_at = time()
    await enforce_rate_limit(
        request=request,
        action="stories:tts",
        limit=settings.rate_limit_story_submit_limit,
        window_seconds=settings.rate_limit_story_submit_window_seconds,
        user_id=current_user.id,
    )
    try:
        result = await synthesize_text_to_speech(
            text=payload.text,
            voice_preset=payload.voice_preset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    total_ms = _elapsed_ms(total_started_at)
    logger.info(
        "tts.timing provider=%s total_ms=%s text_chars=%s original_text_chars=%s segment_count=%s truncated=%s voice=%s user_id=%s",
        result.provider,
        total_ms,
        result.text_chars,
        result.original_text_chars,
        result.segment_count,
        result.truncated,
        result.voice_preset or "-",
        current_user.id,
    )
    return ApiResponse(
        success=True,
        message="朗读音频生成成功",
        data={
            "audio_url": result.file_url,
            "provider": result.provider,
            "sample_rate": result.sample_rate,
            "duration_seconds": result.duration_seconds,
            "text_chars": result.text_chars,
            "original_text_chars": result.original_text_chars,
            "truncated": result.truncated,
            "segment_count": result.segment_count,
            "voice_preset": result.voice_preset,
            "timing": {
                "provider": result.provider,
                "total_ms": total_ms,
            },
        },
    )


@router.post("/scan/save", response_model=ApiResponse)
async def save_scan_story_api(
    payload: LiveScanStorySaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    story_text = payload.story_content.strip()
    if not story_text:
        raise HTTPException(status_code=400, detail="故事内容不能为空")

    if payload.book_id:
        book = await get_book_by_id_and_user(db, payload.book_id, current_user.id)
        if not book:
            raise HTTPException(status_code=404, detail="归档绘本不存在")
    else:
        title = f"实时扫描绘本 {datetime.now():%Y%m%d %H%M%S}"
        book = await create_book(db=db, user_id=current_user.id, title=title)

    source_scan_paths = _collect_live_scan_paths(payload, current_user.id)
    existing_images = await list_book_images(db, book.id)
    next_order = (max((item.image_order for item in existing_images), default=0) + 1) if existing_images else 1
    saved_image_paths: list[str] = []
    for index, source_path in enumerate(source_scan_paths, start=next_order):
        saved_path = await save_existing_image_file(source_path, settings.upload_dir, book.id)
        await create_book_image_record(
            db=db,
            book_id=book.id,
            image_path=saved_path,
            image_order=index,
        )
        saved_image_paths.append(saved_path)

    if saved_image_paths and not book.cover_image:
        await update_book_cover_image(db=db, book=book, cover_image=saved_image_paths[0])

    image_analysis = {
        "source": "live_scan",
        "session_id": payload.session_id,
        "response_mode": payload.response_mode,
        "narration_style": payload.narration_style,
        "audience_age": payload.audience_age,
        "page_stories": payload.page_stories,
        "last_analysis_result": payload.analysis_result,
        "saved_image_paths": saved_image_paths,
    }
    story = await create_story_record(
        db=db,
        user_id=current_user.id,
        book_id=book.id,
        prompt=payload.prompt or "实时扫描连续讲述",
        image_analysis=image_analysis,
        story_content=story_text,
    )
    evaluation_analysis = payload.analysis_result or [
        {
            "场景": "实时扫描绘本",
            "角色": [],
            "关键物体": [],
            "page_stories": payload.page_stories,
        }
    ]
    quality = await evaluate_story_full(
        analysis_result=evaluation_analysis,
        story_content=story_text,
        include_judge=False,
        judge_samples=None,
    )
    await set_story_quality_cache(
        story_id=story.id,
        include_judge=False,
        judge_samples=None,
        quality=quality,
    )
    return ApiResponse(
        success=True,
        message="实时故事已保存",
        data={
            "story": StoryInfo.model_validate(story).model_dump(mode="json"),
            "quality": quality,
            "book_id": book.id,
            "image_paths": saved_image_paths,
        },
    )


@router.post("/generate/submit", response_model=ApiResponse)
async def submit_generate_task_api(
    payload: StoryGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
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
    stories = await list_stories_by_user(db, current_user.id)
    data = [StoryInfo.model_validate(item).model_dump() for item in stories]
    return ApiResponse(success=True, message="查询成功", data=data)


@router.delete("/{story_id}", response_model=ApiResponse)
async def delete_story_api(
    story_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
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
    story = await get_story_by_id_and_user(db, story_id, current_user.id)
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")
    return ApiResponse(success=True, message="查询成功", data=StoryInfo.model_validate(story).model_dump())

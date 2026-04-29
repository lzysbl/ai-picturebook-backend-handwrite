"""Story routes: generation, scan, evaluation, tasks, and history."""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import uuid
from pathlib import Path
from time import time
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis
from app.db.session import SessionLocal, get_db
from app.routers.users import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.story import StoryEvaluateRequest, StoryGenerateData, StoryGenerateRequest, StoryInfo
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
from app.services.vision_analysis_service import analyze_images
from app.utils.rate_limiter import enforce_rate_limit

router = APIRouter(prefix="/api/stories", tags=["Stories"])

SCAN_CACHE_TTL_SECONDS = 120
SCAN_SESSION_TTL_SECONDS = 900
_local_scan_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_local_scan_sessions: dict[str, tuple[float, dict[str, Any]]] = {}
try:
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None


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


def _page_summary_from_analysis(analysis_result: list[dict[str, Any]]) -> dict[str, Any]:
    first = analysis_result[0] if analysis_result else {}
    roles = first.get("角色", []) if isinstance(first.get("角色"), list) else []
    actions = first.get("动作", []) if isinstance(first.get("动作"), list) else []
    objects = first.get("关键物体", []) if isinstance(first.get("关键物体"), list) else []
    texts = first.get("画面文字", []) if isinstance(first.get("画面文字"), list) else []
    return {
        "page": int(first.get("page", 1) or 1),
        "roles": [str(x).strip() for x in roles if str(x).strip()][:4],
        "actions": [str(x).strip() for x in actions if str(x).strip()][:3],
        "objects": [str(x).strip() for x in objects if str(x).strip()][:3],
        "texts": [str(x).strip() for x in texts if str(x).strip()][:3],
        "scene": str(first.get("场景") or "绘本场景"),
        "mood": str(first.get("情绪") or "温暖"),
    }


def _build_character_registry(recent_pages: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for page in recent_pages:
        for role in page.get("roles", []):
            if role and role not in seen:
                seen.append(role)
    return seen


def _same_page_summary(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("scene") == right.get("scene")
        and left.get("roles", []) == right.get("roles", [])
        and left.get("texts", []) == right.get("texts", [])
    )


def _merge_scan_session_pages(
    existing_pages: list[dict[str, Any]],
    current_page: dict[str, Any],
    max_pages: int = 3,
) -> list[dict[str, Any]]:
    if existing_pages and _same_page_summary(existing_pages[-1], current_page):
        existing_pages[-1] = current_page
        return existing_pages[-max_pages:]
    return [*existing_pages[-(max_pages - 1) :], current_page]


def _build_live_scan_story(
    analysis_result: list[dict[str, Any]],
    narration_style: str | None,
    audience_age: str | None,
    extra_prompt: str | None,
) -> str:
    page = _page_summary_from_analysis(analysis_result)
    return _build_contextual_live_scan_story([], page, narration_style, audience_age, extra_prompt)


def _build_contextual_live_scan_story(
    recent_pages: list[dict[str, Any]],
    current_page: dict[str, Any],
    narration_style: str | None,
    audience_age: str | None,
    extra_prompt: str | None,
) -> str:
    style = _normalize_optional_text(narration_style, "温柔")
    age = _normalize_optional_text(audience_age, "3-6")
    roles = "、".join(current_page.get("roles", [])) or "小主角"
    actions = "、".join(current_page.get("actions", [])) or "正在观察周围"
    objects = "、".join(current_page.get("objects", []))
    texts = "；".join(current_page.get("texts", []))
    scene = current_page.get("scene") or "绘本场景"
    mood = current_page.get("mood") or "温暖"

    lines = [f"这是一个适合{age}岁儿童的{style}风格讲述。"]
    if recent_pages:
        previous = recent_pages[-1]
        previous_roles = "、".join(previous.get("roles", [])) or "前一页的角色们"
        if previous.get("scene") == scene:
            lines.append(f"延续前一页的场景，{previous_roles}这次仍然在{scene}里。")
        else:
            lines.append(f"和前一页相比，现在画面转到了{scene}。")

    lines.append(f"当前画面中，{roles}正在{actions}，整体氛围偏{mood}。")
    registry = _build_character_registry([*recent_pages, current_page])
    if registry:
        lines.append(f"到目前为止，故事中已经出现的主要角色有：{'、'.join(registry)}。")
    if objects:
        lines.append(f"这一页还出现了这些关键元素：{objects}。")
    if texts:
        lines.append(f"页面上可以看到的文字或线索有：{texts}。")
    if extra_prompt:
        lines.append(f"补充提示：{extra_prompt}。")
    return "\n".join(lines)


def _context_pages_to_generation_input(
    recent_pages: list[dict[str, Any]],
    current_page: dict[str, Any],
) -> list[dict[str, Any]]:
    combined = [*recent_pages, current_page]
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(combined, start=1):
        pages.append(
            {
                "page": index,
                "角色": page.get("roles", []),
                "场景": page.get("scene", ""),
                "动作": page.get("actions", []),
                "情绪": page.get("mood", ""),
                "关键物体": page.get("objects", []),
                "画面文字": page.get("texts", []),
            }
        )
    return pages


def _scan_cache_key(
    image_bytes: bytes,
    prompt: str | None,
    narration_style: str | None,
    audience_age: str | None,
    response_mode: str,
    crop_box: dict[str, float] | None = None,
) -> str:
    digest = hashlib.sha256(image_bytes).hexdigest()
    raw = json.dumps(
        {
            "digest": digest,
            "prompt": prompt or "",
            "style": narration_style or "",
            "age": audience_age or "",
            "mode": response_mode,
            "crop_box": crop_box or {},
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "story_scan:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_crop_box(
    crop_x: float | None,
    crop_y: float | None,
    crop_width: float | None,
    crop_height: float | None,
) -> dict[str, float] | None:
    values = (crop_x, crop_y, crop_width, crop_height)
    if any(value is None for value in values):
        return None
    try:
        x = float(crop_x)
        y = float(crop_y)
        width = float(crop_width)
        height = float(crop_height)
    except (TypeError, ValueError):
        return None

    if width <= 0.05 or height <= 0.05:
        return None
    if x < 0 or y < 0 or width > 1 or height > 1:
        return None
    if x + width > 1 or y + height > 1:
        return None
    return {
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(width, 6),
        "height": round(height, 6),
    }


def _detect_page_box_with_opencv(image_path: Path) -> dict[str, float] | None:
    if cv2 is None:
        return None

    image = cv2.imread(str(image_path))
    if image is None:
        return None

    original_height, original_width = image.shape[:2]
    max_side = 960
    scale = min(1.0, max_side / max(original_width, original_height))
    if scale < 1.0:
        resized = cv2.resize(image, (int(original_width * scale), int(original_height * scale)))
    else:
        resized = image

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 60, 160)
    kernel = np.ones((5, 5), np.uint8)
    edged = cv2.dilate(edged, kernel, iterations=1)
    edged = cv2.erode(edged, kernel, iterations=1)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    resized_height, resized_width = resized.shape[:2]
    image_area = resized_width * resized_height
    best_box: tuple[int, int, int, int] | None = None
    best_score = -1.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.12:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        x, y, w, h = cv2.boundingRect(approx if len(approx) >= 4 else contour)
        if w <= 0 or h <= 0:
            continue

        area_ratio = (w * h) / image_area
        aspect_ratio = w / max(1, h)
        center_x = (x + w / 2) / resized_width
        center_y = (y + h / 2) / resized_height
        if area_ratio < 0.15 or area_ratio > 0.95:
            continue
        if aspect_ratio < 0.45 or aspect_ratio > 1.9:
            continue
        if abs(center_x - 0.5) > 0.38 or abs(center_y - 0.5) > 0.38:
            continue

        score = area_ratio - abs(center_x - 0.5) * 0.4 - abs(center_y - 0.5) * 0.4
        if score > best_score:
            best_score = score
            best_box = (x, y, w, h)

    if not best_box:
        return None

    x, y, w, h = best_box
    x = x / scale
    y = y / scale
    w = w / scale
    h = h / scale
    padding = 0.02
    return {
        "x": round(max(0.0, x / original_width - padding), 6),
        "y": round(max(0.0, y / original_height - padding), 6),
        "width": round(min(1.0, w / original_width + padding * 2), 6),
        "height": round(min(1.0, h / original_height + padding * 2), 6),
    }


def _crop_image_to_temp(
    image_path: Path,
    crop_box: dict[str, float] | None,
) -> tuple[Path, str]:
    if not crop_box:
        return image_path, "full_frame"

    with Image.open(image_path) as img:
        width, height = img.size
        left = max(0, min(width - 1, int(crop_box["x"] * width)))
        top = max(0, min(height - 1, int(crop_box["y"] * height)))
        right = max(left + 1, min(width, int((crop_box["x"] + crop_box["width"]) * width)))
        bottom = max(top + 1, min(height, int((crop_box["y"] + crop_box["height"]) * height)))

        if right - left < max(80, width // 8) or bottom - top < max(80, height // 8):
            return image_path, "full_frame"

        cropped = img.crop((left, top, right, bottom))
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=image_path.suffix or ".jpg")
        tmp_path = Path(tmp.name)
        tmp.close()
        cropped.save(tmp_path)
        return tmp_path, "cropped"


def _enhance_scan_image(image_path: Path) -> Path:
    """Apply lightweight enhancement to improve page readability before analysis."""

    with Image.open(image_path) as img:
        prepared = ImageOps.exif_transpose(img).convert("RGB")
        prepared = ImageOps.autocontrast(prepared, cutoff=1)
        prepared = ImageEnhance.Color(prepared).enhance(0.92)
        prepared = ImageEnhance.Contrast(prepared).enhance(1.15)
        prepared = ImageEnhance.Sharpness(prepared).enhance(1.18)
        prepared = prepared.filter(ImageFilter.MedianFilter(size=3))

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=image_path.suffix or ".jpg")
        tmp_path = Path(tmp.name)
        tmp.close()
        prepared.save(tmp_path, quality=92)
        return tmp_path


async def _get_scan_cache(cache_key: str) -> dict[str, Any] | None:
    redis = await get_redis()
    if redis is not None:
        cached = await redis.get(cache_key)
        if not cached:
            return None
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return None

    item = _local_scan_cache.get(cache_key)
    if not item:
        return None
    expires_at, payload = item
    if expires_at < time():
        _local_scan_cache.pop(cache_key, None)
        return None
    return payload


async def _set_scan_cache(cache_key: str, payload: dict[str, Any]) -> None:
    redis = await get_redis()
    if redis is not None:
        await redis.set(cache_key, json.dumps(payload, ensure_ascii=False), ex=SCAN_CACHE_TTL_SECONDS)
        return
    _local_scan_cache[cache_key] = (time() + SCAN_CACHE_TTL_SECONDS, payload)


def _scan_session_key(user_id: int, session_id: str) -> str:
    return f"story_scan_session:{user_id}:{session_id}"


async def _get_scan_session(cache_key: str) -> dict[str, Any] | None:
    redis = await get_redis()
    if redis is not None:
        cached = await redis.get(cache_key)
        if not cached:
            return None
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return None

    item = _local_scan_sessions.get(cache_key)
    if not item:
        return None
    expires_at, payload = item
    if expires_at < time():
        _local_scan_sessions.pop(cache_key, None)
        return None
    return payload


async def _set_scan_session(cache_key: str, payload: dict[str, Any]) -> None:
    redis = await get_redis()
    if redis is not None:
        await redis.set(cache_key, json.dumps(payload, ensure_ascii=False), ex=SCAN_SESSION_TTL_SECONDS)
        return
    _local_scan_sessions[cache_key] = (time() + SCAN_SESSION_TTL_SECONDS, payload)


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
    include_judge: bool = Form(default=False),
    judge_samples: int | None = Form(default=None),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    image_bytes = await image.read()
    suffix = Path(image.filename or "frame.jpg").suffix or ".jpg"
    normalized_session_id = (session_id or "").strip()
    normalized_prompt = _normalize_optional_text(prompt)
    normalized_style = _normalize_optional_text(narration_style, "温柔")
    normalized_age = _normalize_optional_text(audience_age, "3-6")
    normalized_mode = (response_mode or "fast").strip().lower()
    normalized_crop_source = (crop_source or "").strip().lower()
    normalized_crop_box = _normalize_crop_box(crop_x, crop_y, crop_width, crop_height)
    if normalized_mode not in {"fast", "full"}:
        normalized_mode = "fast"

    cache_key = _scan_cache_key(
        image_bytes=image_bytes,
        prompt=normalized_prompt,
        narration_style=normalized_style,
        audience_age=normalized_age,
        response_mode=normalized_mode,
        crop_box=normalized_crop_box,
    )
    cached = await _get_scan_cache(cache_key)
    if cached is not None:
        return ApiResponse(success=True, message="实时识别完成（缓存）", data=cached)

    tmp_path: Path | None = None
    scan_path: Path | None = None
    prepared_path: Path | None = None
    crop_mode = "full_frame"
    effective_crop_box = normalized_crop_box
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)

        if normalized_crop_source != "detected":
            opencv_crop_box = _detect_page_box_with_opencv(tmp_path)
            if opencv_crop_box is not None:
                effective_crop_box = opencv_crop_box
                crop_mode = "model_crop"
            elif normalized_crop_box is not None:
                crop_mode = "guide_crop"
        else:
            crop_mode = "frontend_crop"

        scan_path, crop_result_mode = _crop_image_to_temp(tmp_path, effective_crop_box)
        if crop_result_mode == "full_frame":
            crop_mode = "full_frame"
        prepared_path = _enhance_scan_image(scan_path)
        analysis_result = await analyze_images([str(prepared_path)])
        current_page = _page_summary_from_analysis(analysis_result)
        recent_pages: list[dict[str, Any]] = []
        character_registry = current_page.get("roles", [])
        session_page_count = 1
        session_key = ""

        if normalized_session_id:
            session_key = _scan_session_key(current_user.id, normalized_session_id)
            session_payload = await _get_scan_session(session_key) or {}
            recent_pages = (
                session_payload.get("recent_pages", [])
                if isinstance(session_payload.get("recent_pages", []), list)
                else []
            )

        if normalized_mode == "full":
            generation_input = (
                _context_pages_to_generation_input(recent_pages, current_page)
                if recent_pages
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
        else:
            story_content = _build_contextual_live_scan_story(
                recent_pages=recent_pages,
                current_page=current_page,
                narration_style=normalized_style,
                audience_age=normalized_age,
                extra_prompt=normalized_prompt,
            )

        if normalized_session_id:
            merged_pages = _merge_scan_session_pages(recent_pages, current_page)
            character_registry = _build_character_registry(merged_pages)
            session_page_count = len(merged_pages)
            await _set_scan_session(
                session_key,
                {
                    "recent_pages": merged_pages,
                    "character_registry": character_registry,
                },
            )
        else:
            character_registry = _build_character_registry([current_page])

        quality = await evaluate_story_full(
            analysis_result=analysis_result,
            story_content=story_content,
            include_judge=include_judge,
            judge_samples=judge_samples,
        )
    finally:
        if prepared_path and prepared_path.exists():
            prepared_path.unlink(missing_ok=True)
        if scan_path and tmp_path and scan_path != tmp_path and scan_path.exists():
            scan_path.unlink(missing_ok=True)
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    payload = {
        "analysis_result": analysis_result,
        "story_content": story_content,
        "quality": quality,
        "response_mode": normalized_mode,
        "crop_mode": crop_mode,
        "crop_box": effective_crop_box,
        "context": {
            "session_id": normalized_session_id or None,
            "recent_page_count": session_page_count,
            "character_registry": character_registry,
        },
    }
    await _set_scan_cache(cache_key, payload)
    return ApiResponse(success=True, message="实时识别完成", data=payload)


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

"""实时识别运行时服务。

职责：
- 支撑摄像头实时识别流程中的运行时能力，而不是直接生成故事。
- 处理实拍图片路径校验、扫描缓存 key、连续识别 session、SSE 事件格式。
- 对图片做页面区域检测、裁剪和增强，提升实时识别稳定性。
- 在 Redis 不可用时使用本地内存缓存降级。

前端关联：
- `/ui/camera`：实时识别主页面。
- 前端 `camera.js` 通过 `/api/stories/scan`、`/api/stories/scan/stream`、
  `/api/stories/scan/save` 间接使用本服务。

主要路由：
- `app/routers/stories.py`：实时识别、流式识别、保存实时识别结果。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from time import time
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.core.config import settings
from app.core.redis_client import get_redis
from app.schemas.story import LiveScanStorySaveRequest

SCAN_CACHE_TTL_SECONDS = 120
SCAN_SESSION_TTL_SECONDS = 900
_local_scan_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_local_scan_sessions: dict[str, tuple[float, dict[str, Any]]] = {}

try:
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None


def elapsed_ms(started_at: float) -> int:
    return max(0, int((time() - started_at) * 1000))


def resolve_user_live_scan_path(path_text: str, user_id: int) -> Path | None:
    """Only allow saving images from the current user's live-scan directory."""

    raw = str(path_text or "").strip().replace("\\", "/")
    if not raw:
        return None

    upload_root = Path(settings.upload_dir).resolve()
    if raw.startswith("/uploads/"):
        candidate = upload_root / raw.removeprefix("/uploads/")
    elif raw.startswith("uploads/"):
        candidate = Path(raw).resolve()
    else:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = candidate.resolve()

    live_scan_root = (upload_root / "live_scans" / str(user_id)).resolve()
    candidate = candidate.resolve()
    try:
        candidate.relative_to(live_scan_root)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def collect_live_scan_paths(payload: LiveScanStorySaveRequest, user_id: int) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()

    raw_paths: list[Any] = list(payload.image_paths)
    for page in payload.page_stories:
        if isinstance(page, dict):
            raw_paths.append(page.get("image_path"))

    for raw_path in raw_paths:
        resolved = resolve_user_live_scan_path(str(raw_path or ""), user_id)
        if resolved is None:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        paths.append(resolved)
    return paths


def scan_cache_key(
    image_bytes: bytes,
    prompt: str | None,
    narration_style: str | None,
    audience_age: str | None,
    response_mode: str,
    provider: str | None = None,
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
            "provider": provider or "",
            "crop_box": crop_box or {},
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "story_scan:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_crop_box(
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


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def clean_live_scan_stream_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.removeprefix("```").removesuffix("```").strip()
    for prefix in ("讲述：", "故事：", "当前页：", "直接讲述："):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned


def detect_page_box_with_opencv(image_path: Path) -> dict[str, float] | None:
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


def crop_image_to_temp(
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


def enhance_scan_image(image_path: Path) -> Path:
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


async def get_scan_cache(cache_key: str) -> dict[str, Any] | None:
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


async def set_scan_cache(cache_key: str, payload: dict[str, Any]) -> None:
    redis = await get_redis()
    if redis is not None:
        await redis.set(cache_key, json.dumps(payload, ensure_ascii=False), ex=SCAN_CACHE_TTL_SECONDS)
        return
    _local_scan_cache[cache_key] = (time() + SCAN_CACHE_TTL_SECONDS, payload)


def scan_session_key(user_id: int, session_id: str) -> str:
    return f"story_scan_session:{user_id}:{session_id}"


async def get_scan_session(cache_key: str) -> dict[str, Any] | None:
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


async def set_scan_session(cache_key: str, payload: dict[str, Any]) -> None:
    redis = await get_redis()
    if redis is not None:
        await redis.set(cache_key, json.dumps(payload, ensure_ascii=False), ex=SCAN_SESSION_TTL_SECONDS)
        return
    _local_scan_sessions[cache_key] = (time() + SCAN_SESSION_TTL_SECONDS, payload)


__all__ = [
    "clean_live_scan_stream_text",
    "collect_live_scan_paths",
    "crop_image_to_temp",
    "detect_page_box_with_opencv",
    "elapsed_ms",
    "enhance_scan_image",
    "get_scan_cache",
    "get_scan_session",
    "normalize_crop_box",
    "scan_cache_key",
    "scan_session_key",
    "set_scan_cache",
    "set_scan_session",
    "sse_event",
]

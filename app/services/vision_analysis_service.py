"""Image analysis service for mock and Qwen-backed picture understanding."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from openai import AsyncOpenAI
from PIL import Image, ImageStat

from app.core.config import settings

ProgressCallback = Callable[[int, int, str], Awaitable[None] | None]
MAX_CONCURRENCY = 8
logger = logging.getLogger(__name__)

_qwen_client: AsyncOpenAI | None = None
_doubao_client: AsyncOpenAI | None = None


def _get_qwen_client() -> AsyncOpenAI:
    global _qwen_client
    if _qwen_client is None:
        _qwen_client = AsyncOpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url)
    return _qwen_client


def _get_doubao_client() -> AsyncOpenAI:
    global _doubao_client
    if _doubao_client is None:
        _doubao_client = AsyncOpenAI(api_key=settings.doubao_api_key, base_url=settings.doubao_base_url)
    return _doubao_client


async def analyze_images(
    image_paths: list[str],
    progress_callback: ProgressCallback | None = None,
    provider_override: str | None = None,
) -> list[dict[str, Any]]:
    """Analyze uploaded picture-book pages with either mock or Qwen provider."""

    if not image_paths:
        return []

    provider = (provider_override or settings.ai_provider or "mock").strip().lower()
    logger.info("ai.analyze_images provider=%s image_count=%s", provider, len(image_paths))
    if provider == "qwen":
        return await _analyze_images_qwen(image_paths, progress_callback=progress_callback)
    if provider == "doubao":
        return await _analyze_images_doubao(image_paths, progress_callback=progress_callback)
    return _analyze_images_mock(image_paths)


def _analyze_images_mock(image_paths: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for idx, image_path in enumerate(image_paths, start=1):
        try:
            with Image.open(Path(image_path)) as img:
                brightness = float(ImageStat.Stat(img.convert("L")).mean[0])
                result.append(
                    {
                        "page": idx,
                        "image_path": image_path,
                        "width": img.width,
                        "height": img.height,
                        "mode": img.mode,
                        "brightness": round(brightness, 2),
                        "角色": ["小主角"],
                        "场景": "绘本场景",
                        "动作": ["观察", "交流"],
                        "情绪": "温暖",
                        "关键物体": ["道具A", "道具B"],
                        "画面文字": [],
                    }
                )
        except Exception as exc:  # noqa: BLE001
            result.append({"page": idx, "image_path": image_path, "error": str(exc)})
    return result


async def _analyze_images_qwen(
    image_paths: list[str],
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    if not settings.qwen_api_key:
        logger.warning("ai.analyze_images qwen_api_key_missing fallback=mock")
        return _analyze_images_mock(image_paths)

    total = len(image_paths)
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    done_count = 0
    results: dict[int, dict[str, Any]] = {}

    async def update_progress(page_no: int) -> None:
        nonlocal done_count
        done_count += 1
        if not progress_callback:
            return
        maybe = progress_callback(done_count, total, f"已识别第 {page_no} 页（{done_count}/{total}）")
        if maybe is not None:
            await maybe

    async def worker(page_no: int, image_path: str) -> None:
        async with semaphore:
            try:
                parsed = await _call_qwen_vl_for_one_image(image_path=image_path, page_no=page_no)
                item = _normalize_vision_json(parsed)
                item.update({"page": page_no, "image_path": image_path})
                results[page_no] = item
            except Exception as exc:  # noqa: BLE001
                logger.warning("ai.analyze_page_failed page=%s error=%s", page_no, exc)
                results[page_no] = {
                    "page": page_no,
                    "image_path": image_path,
                    "error": f"qwen分析失败: {exc}",
                }
            finally:
                await update_progress(page_no)

    tasks = [
        asyncio.create_task(worker(page_no=idx, image_path=path))
        for idx, path in enumerate(image_paths, start=1)
    ]
    await asyncio.gather(*tasks)

    ordered: list[dict[str, Any]] = []
    for idx, path in enumerate(image_paths, start=1):
        ordered.append(
            results.get(
                idx,
                {"page": idx, "image_path": path, "error": "识别结果缺失"},
            )
        )
    return ordered


async def _analyze_images_doubao(
    image_paths: list[str],
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    if not settings.doubao_api_key:
        logger.warning("ai.analyze_images doubao_api_key_missing fallback=mock")
        return _analyze_images_mock(image_paths)

    total = len(image_paths)
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    done_count = 0
    results: dict[int, dict[str, Any]] = {}

    async def update_progress(page_no: int) -> None:
        nonlocal done_count
        done_count += 1
        if not progress_callback:
            return
        maybe = progress_callback(done_count, total, f"recognized page {page_no} ({done_count}/{total})")
        if maybe is not None:
            await maybe

    async def worker(page_no: int, image_path: str) -> None:
        async with semaphore:
            try:
                parsed = await _call_doubao_vl_for_one_image(image_path=image_path, page_no=page_no)
                item = _normalize_vision_json(parsed)
                item.update({"page": page_no, "image_path": image_path})
                results[page_no] = item
            except Exception as exc:  # noqa: BLE001
                logger.warning("ai.analyze_page_failed provider=doubao page=%s error=%s", page_no, exc)
                results[page_no] = {
                    "page": page_no,
                    "image_path": image_path,
                    "error": f"doubao analysis failed: {exc}",
                }
            finally:
                await update_progress(page_no)

    tasks = [
        asyncio.create_task(worker(page_no=idx, image_path=path))
        for idx, path in enumerate(image_paths, start=1)
    ]
    await asyncio.gather(*tasks)

    ordered: list[dict[str, Any]] = []
    for idx, path in enumerate(image_paths, start=1):
        ordered.append(
            results.get(
                idx,
                {"page": idx, "image_path": path, "error": "missing recognition result"},
            )
        )
    return ordered


async def _call_qwen_vl_for_one_image(image_path: str, page_no: int) -> dict[str, Any]:
    client = _get_qwen_client()
    json_schema = (
        '{"page":1,"角色":[],"场景":"","动作":[],"情绪":"","关键物体":[],"画面文字":[],'
        '"is_title_page":false,"detected_title":"","detected_author":""}'
    )
    if page_no == 1:
        user_prompt = (
            f"这是第{page_no}页，请优先判断是否包含绘本标题信息，并返回 JSON："
            f"{json_schema}"
            "规则："
            "1) 如果识别到明确书名，写入 detected_title；"
            "2) 如果识别到作者，写入 detected_author；"
            "3) 如果没有明确标题，detected_title 必须返回空字符串，不要猜测；"
            "4) 即使没有标题，也要正常提取页面内容（角色、场景、动作、情绪、关键物体、画面文字）；"
            "5) 仅输出 JSON。"
        )
    else:
        user_prompt = (
            f"分析第{page_no}页并返回 JSON："
            f"{json_schema}"
            "要求：尽量提取可见文字（标题、对话、拟声词、标语等）；"
            "并判断该页是否是标题页/扉页（如仅有书名、作者、出版信息）。"
        )

    completion = await client.chat.completions.create(
        model=settings.qwen_model,
        temperature=0.2,
        timeout=120,
        messages=[
            {"role": "system", "content": "你是儿童绘本图像分析助手，只输出 JSON。"},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _image_path_to_data_url(image_path)}},
                    {"type": "text", "text": user_prompt},
                ],
            },
        ],
    )
    parsed = _extract_json(completion.choices[0].message.content or "")
    if not isinstance(parsed, dict):
        raise ValueError("模型未返回 JSON 对象")
    return parsed


async def _call_doubao_vl_for_one_image(image_path: str, page_no: int) -> dict[str, Any]:
    client = _get_doubao_client()
    completion = await client.chat.completions.create(
        model=settings.doubao_model,
        temperature=0.2,
        timeout=120,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a picture-book page vision parser. "
                    "Return only one JSON object, with no markdown or extra explanation."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _image_path_to_data_url(image_path)}},
                    {"type": "text", "text": _build_vision_prompt(page_no)},
                ],
            },
        ],
    )
    parsed = _extract_json(completion.choices[0].message.content or "")
    if not isinstance(parsed, dict):
        raise ValueError("model did not return a JSON object")
    return parsed


def _build_vision_prompt(page_no: int) -> str:
    schema = (
        '{"page":1,"角色":[],"场景":"","动作":[],"情绪":"","关键物体":[],"画面文字":[],'
        '"is_title_page":false,"detected_title":"","detected_author":""}'
    )
    return (
        f"请分析第 {page_no} 页绘本画面，并严格返回符合以下结构的 JSON：{schema}\n"
        "要求：\n"
        "1. 只提取画面中有依据的信息，不要猜测看不见的内容。\n"
        "2. 角色、动作、关键物体、画面文字必须是数组。\n"
        "3. 场景和情绪用简短中文短语。\n"
        "4. 如果能看到书名或作者，写入 detected_title / detected_author；否则返回空字符串。\n"
        "5. 如果是封面、扉页或标题页，将 is_title_page 设为 true。\n"
        "6. 不要输出 markdown，不要解释，只输出 JSON。"
    )


def _extract_json(text: str) -> dict[str, Any] | list[Any]:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except Exception:  # noqa: BLE001
        pass

    arr_match = re.search(r"\[.*\]", stripped, flags=re.DOTALL)
    obj_match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    match = arr_match if arr_match else obj_match
    if not match:
        raise ValueError("模型输出中未找到 JSON")
    return json.loads(match.group(0))


def _normalize_vision_json(data: dict[str, Any]) -> dict[str, Any]:
    def to_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = re.split(r"[，、\n]", value)
            return [p.strip() for p in parts if p.strip()]
        return [str(value)]

    def to_str(value: Any, default: str) -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    text_items = to_list(data.get("画面文字") or data.get("文字") or data.get("文本"))
    raw_is_title = data.get("is_title_page", data.get("是否标题页", False))
    if isinstance(raw_is_title, str):
        is_title_page = raw_is_title.strip().lower() in {"true", "1", "yes", "y", "是"}
    else:
        is_title_page = bool(raw_is_title)

    detected_title = to_str(data.get("detected_title") or data.get("识别标题"), "").strip()
    detected_author = to_str(data.get("detected_author") or data.get("识别作者"), "").strip()

    return {
        "角色": to_list(data.get("角色")),
        "场景": to_str(data.get("场景"), "未知场景"),
        "动作": to_list(data.get("动作")),
        "情绪": to_str(data.get("情绪"), "中性"),
        "关键物体": to_list(data.get("关键物体")),
        "画面文字": text_items,
        "is_title_page": is_title_page,
        "detected_title": detected_title,
        "detected_author": detected_author,
    }


def _image_path_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(ext, "image/jpeg")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


__all__ = ["ProgressCallback", "analyze_images"]

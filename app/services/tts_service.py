"""Optional text-to-speech service with Bark provider."""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TTSResult:
    file_url: str
    file_path: str
    provider: str
    sample_rate: int
    duration_seconds: float
    text_chars: int
    voice_preset: str | None


def _normalize_audio(audio: Any) -> np.ndarray:
    arr = np.asarray(audio)
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    if arr.size == 0:
        raise ValueError("TTS 音频为空")
    if np.issubdtype(arr.dtype, np.floating):
        arr = np.clip(arr, -1.0, 1.0)
        arr = (arr * 32767.0).astype(np.int16)
    elif arr.dtype != np.int16:
        arr = np.clip(arr, -32768, 32767).astype(np.int16)
    return arr


def _write_wav_bytes(audio_int16: np.ndarray, sample_rate: int) -> bytes:
    with io.BytesIO() as buf:
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()


def _resolve_tts_output_dir() -> Path:
    upload_dir = Path(settings.upload_dir).resolve()
    out_dir = upload_dir / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _save_audio_file(content: bytes) -> tuple[str, str]:
    out_dir = _resolve_tts_output_dir()
    filename = f"{uuid4().hex}.wav"
    output_path = out_dir / filename
    output_path.write_bytes(content)
    file_url = f"/uploads/tts/{filename}"
    return str(output_path), file_url


def _synthesize_with_bark(text: str, voice_preset: str | None) -> tuple[np.ndarray, int, str]:
    if not settings.bark_enabled:
        raise RuntimeError("Bark 未启用，请先设置 BARK_ENABLED=true")

    try:
        from bark import SAMPLE_RATE, generate_audio  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Bark 依赖未安装，请先安装 bark 与 torch") from exc

    if settings.bark_seed is not None:
        try:
            import torch  # type: ignore

            torch.manual_seed(settings.bark_seed)
        except Exception:  # noqa: BLE001
            logger.warning("bark.seed_failed")

    preset = (voice_preset or settings.bark_voice_preset or "").strip() or None
    kwargs: dict[str, Any] = {}
    if preset:
        kwargs["history_prompt"] = preset

    logger.info("tts.bark_generate chars=%s preset=%s", len(text), preset or "-")
    audio = generate_audio(text, **kwargs)
    audio_int16 = _normalize_audio(audio)
    return audio_int16, int(SAMPLE_RATE), preset or ""


async def synthesize_text_to_speech(
    *,
    text: str,
    voice_preset: str | None = None,
) -> TTSResult:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("朗读文本不能为空")
    if len(clean_text) > settings.tts_max_chars:
        raise ValueError(f"朗读文本过长，请控制在 {settings.tts_max_chars} 字以内")

    provider = (settings.tts_provider or "none").strip().lower()
    if provider != "bark":
        raise RuntimeError("当前未启用 TTS，设置 TTS_PROVIDER=bark 后可用")

    audio_int16, sample_rate, preset = await asyncio.to_thread(_synthesize_with_bark, clean_text, voice_preset)
    wav_bytes = _write_wav_bytes(audio_int16, sample_rate)
    file_path, file_url = _save_audio_file(wav_bytes)
    duration_seconds = round(len(audio_int16) / float(sample_rate), 2)
    return TTSResult(
        file_url=file_url,
        file_path=file_path,
        provider="bark",
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        text_chars=len(clean_text),
        voice_preset=preset or None,
    )

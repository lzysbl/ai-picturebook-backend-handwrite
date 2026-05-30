"""文字转语音服务。

职责：
- 把生成好的故事文本转换为可播放音频。
- 支持 Edge TTS 和 Piper 两种语音后端。
- 对长文本进行清洗、分段、合成和音频合并，并把生成文件保存到上传目录。

前端关联：
- `/ui/camera`：实时识别后朗读当前页讲述或总故事。

主要路由：
- `app/routers/stories.py`：`/api/stories/tts`
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

_SENTENCE_END_RE = re.compile(r"([\u3002\uff01\uff1f!?；;])")
_COMMA_RE = re.compile(r"([\uff0c\u3001,])")


@dataclass(slots=True)
class TTSResult:
    file_url: str
    file_path: str
    provider: str
    sample_rate: int
    duration_seconds: float
    text_chars: int
    original_text_chars: int
    truncated: bool
    segment_count: int
    voice_preset: str | None


def _resolve_tts_output_dir() -> Path:
    upload_dir = Path(settings.upload_dir).resolve()
    out_dir = upload_dir / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _save_audio_file(content: bytes, suffix: str = ".wav") -> tuple[str, str]:
    out_dir = _resolve_tts_output_dir()
    filename = f"{uuid4().hex}{suffix}"
    output_path = out_dir / filename
    output_path.write_bytes(content)
    file_url = f"/uploads/tts/{filename}"
    return str(output_path), file_url


def _resolve_provider() -> str:
    provider = (settings.tts_provider or "none").strip().lower()
    if provider in {"none", ""}:
        raise RuntimeError("TTS is disabled, set TTS_PROVIDER=edge or piper")
    if provider not in {"edge", "piper"}:
        raise RuntimeError("Unsupported TTS provider, set TTS_PROVIDER=edge or piper")
    return provider


def _sanitize_tts_text(text: str) -> str:
    cleaned_chars: list[str] = []
    for char in text:
        codepoint = ord(char)
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        if char in {"\r", "\u2028", "\u2029"}:
            cleaned_chars.append("\n")
            continue
        if char == "\n":
            cleaned_chars.append(char)
            continue
        if codepoint < 32 or codepoint == 127 or codepoint == 0xFFFD:
            cleaned_chars.append(" ")
            continue
        cleaned_chars.append(char)

    text = "".join(cleaned_chars)
    text = text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")

    lines = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if line:
            lines.append(line)
    return "\n".join(lines)


def _split_long_sentence(sentence: str, max_chars: int = 24) -> list[str]:
    sentence = sentence.strip()
    if len(sentence) <= max_chars:
        return [sentence] if sentence else []

    parts: list[str] = []
    buffer = ""
    chunks = _COMMA_RE.split(sentence)
    for chunk in chunks:
        if not chunk:
            continue
        if len(buffer) + len(chunk) <= max_chars:
            buffer += chunk
            continue
        if buffer:
            parts.append(buffer.strip())
        buffer = chunk.lstrip("，、,").strip()
    if buffer:
        parts.append(buffer.strip())

    fallback: list[str] = []
    for part in parts or [sentence]:
        if len(part) <= max_chars:
            fallback.append(part)
        else:
            fallback.extend(part[i : i + max_chars] for i in range(0, len(part), max_chars))
    return [item for item in fallback if item]


def _prepare_story_reading_text(text: str) -> str:
    sanitized = _sanitize_tts_text(text)
    if not sanitized:
        return ""
    if sanitized.count("?") / max(len(sanitized), 1) > 0.35:
        return ""

    sentences: list[str] = []
    for raw_line in sanitized.splitlines():
        pieces = _SENTENCE_END_RE.split(raw_line)
        current = ""
        for piece in pieces:
            if not piece:
                continue
            current += piece
            if _SENTENCE_END_RE.fullmatch(piece):
                sentences.extend(_split_long_sentence(current))
                current = ""
        if current.strip():
            sentences.extend(_split_long_sentence(current))

    # Repeating short lines gives Piper clearer paragraph boundaries and more natural pauses.
    return "\n".join(sentence.strip() for sentence in sentences if sentence.strip())


def _split_tts_segments(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if max_chars <= 0:
        return [text]

    segments: list[str] = []
    current: list[str] = []
    total = 0
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if len(candidate) > max_chars:
            if current:
                segments.append("\n".join(current))
                current = []
                total = 0
            for index in range(0, len(candidate), max_chars):
                segments.append(candidate[index : index + max_chars])
            continue

        next_total = total + len(candidate) + (1 if current else 0)
        if next_total <= max_chars:
            current.append(candidate)
            total = next_total
            continue
        if current:
            segments.append("\n".join(current))
        current = [candidate]
        total = len(candidate)

    if current:
        segments.append("\n".join(current))
    return [segment.strip() for segment in segments if segment.strip()]


def _resolve_wav_stats(path: Path) -> tuple[int, int]:
    with wave.open(str(path), "rb") as wf:
        return int(wf.getframerate()), int(wf.getnframes())


def _resolve_wav_stats_from_bytes(content: bytes) -> tuple[int, int]:
    with io.BytesIO(content) as buf:
        with wave.open(buf, "rb") as wf:
            return int(wf.getframerate()), int(wf.getnframes())


async def _synthesize_edge_segment(text: str, voice: str) -> bytes:
    try:
        import edge_tts  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("edge-tts is not installed, run: pip install edge-tts") from exc

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=settings.edge_tts_rate,
        volume=settings.edge_tts_volume,
    )
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])

    if not audio:
        raise RuntimeError("Edge TTS produced empty audio")

    return bytes(audio)


async def _synthesize_with_edge_segments(segments: list[str], voice_preset: str | None) -> tuple[bytes, int, float, str | None]:
    voice = (voice_preset or settings.edge_tts_voice or "zh-CN-XiaoxiaoNeural").strip()
    audio_parts: list[bytes] = []
    for index, segment in enumerate(segments, start=1):
        logger.info("tts.edge_generate segment=%s/%s chars=%s voice=%s", index, len(segments), len(segment), voice)
        audio_parts.append(await _synthesize_edge_segment(segment, voice))
    return b"".join(audio_parts), 24000, 0.0, voice


def _synthesize_with_piper(text: str, voice_preset: str | None) -> tuple[bytes, int, float, str | None]:
    text = _prepare_story_reading_text(text)
    binary = (settings.piper_binary or "piper").strip() or "piper"
    if shutil.which(binary) is None:
        if binary == "piper":
            cmd = [sys.executable, "-m", "piper"]
        else:
            raise RuntimeError(f"Piper binary not found: {binary}")
    else:
        cmd = [binary]

    model_path = (settings.piper_model_path or "").strip()
    if not model_path:
        raise RuntimeError("PIPER_MODEL_PATH is required when TTS_PROVIDER=piper")
    model = Path(model_path)
    if not model.exists():
        raise RuntimeError(f"Piper model not found: {model}")

    output_dir = _resolve_tts_output_dir()
    output_path = output_dir / f"{uuid4().hex}.wav"
    input_path = output_dir / f"{uuid4().hex}.txt"

    cmd.extend(
        [
            "--model",
            str(model),
            "--output_file",
            str(output_path),
            "--input_file",
            str(input_path),
        ]
    )

    config_path = (settings.piper_config_path or "").strip()
    if config_path:
        config = Path(config_path)
        if not config.exists():
            raise RuntimeError(f"Piper config not found: {config}")
        cmd.extend(["--config", str(config)])

    if settings.piper_speaker is not None:
        cmd.extend(["--speaker", str(settings.piper_speaker)])
    if settings.piper_length_scale is not None:
        cmd.extend(["--length_scale", str(settings.piper_length_scale)])
    if settings.piper_noise_scale is not None:
        cmd.extend(["--noise_scale", str(settings.piper_noise_scale)])
    if settings.piper_noise_w is not None:
        cmd.extend(["--noise_w", str(settings.piper_noise_w)])
    if settings.piper_sentence_silence is not None:
        cmd.extend(["--sentence_silence", str(settings.piper_sentence_silence)])
    if settings.piper_use_cuda:
        cmd.append("--cuda")

    input_path.write_text(text, encoding="utf-8")
    logger.info("tts.piper_generate chars=%s model=%s", len(text), model.name)
    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
        )
    finally:
        input_path.unlink(missing_ok=True)

    if process.returncode != 0:
        output_path.unlink(missing_ok=True)
        stderr = (process.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = (process.stdout or b"").decode("utf-8", errors="replace").strip()
        message = stderr or stdout or f"exit_code={process.returncode}"
        if "surrogates not allowed" in message or "UnicodeEncodeError" in message:
            raise RuntimeError("Piper synthesis failed: text contains invalid characters") from None
        raise RuntimeError(f"Piper synthesis failed: {message}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Piper synthesis produced empty audio file")

    wav_bytes = output_path.read_bytes()
    sample_rate, frame_count = _resolve_wav_stats(output_path)
    duration = round((frame_count / float(sample_rate)) if sample_rate > 0 else 0.0, 2)
    output_path.unlink(missing_ok=True)
    return wav_bytes, sample_rate, duration, voice_preset


def _merge_wav_bytes(parts: list[bytes]) -> tuple[bytes, int, float]:
    if not parts:
        raise RuntimeError("No WAV audio segments to merge")

    params = None
    frames: list[bytes] = []
    frame_count = 0
    sample_rate = 0
    for content in parts:
        with io.BytesIO(content) as buf:
            with wave.open(buf, "rb") as wf:
                current_params = wf.getparams()
                if params is None:
                    params = current_params
                    sample_rate = int(wf.getframerate())
                elif current_params[:3] != params[:3]:
                    raise RuntimeError("Piper generated incompatible WAV segments")
                data = wf.readframes(wf.getnframes())
                frames.append(data)
                frame_count += int(wf.getnframes())

    with io.BytesIO() as out:
        with wave.open(out, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(b"".join(frames))
        merged = out.getvalue()
    duration = round((frame_count / float(sample_rate)) if sample_rate > 0 else 0.0, 2)
    return merged, sample_rate, duration


def _synthesize_with_piper_segments(segments: list[str], voice_preset: str | None) -> tuple[bytes, int, float, str | None]:
    wav_parts: list[bytes] = []
    selected_voice: str | None = voice_preset
    for index, segment in enumerate(segments, start=1):
        logger.info("tts.piper_segment segment=%s/%s chars=%s", index, len(segments), len(segment))
        wav_bytes, _, _, selected_voice = _synthesize_with_piper(segment, voice_preset)
        wav_parts.append(wav_bytes)
    merged, sample_rate, duration = _merge_wav_bytes(wav_parts)
    return merged, sample_rate, duration, selected_voice


async def synthesize_text_to_speech(
    *,
    text: str,
    voice_preset: str | None = None,
) -> TTSResult:
    clean_text = _prepare_story_reading_text(text)
    if not clean_text:
        raise ValueError("Text cannot be empty")
    original_text_chars = len(clean_text)
    segments = _split_tts_segments(clean_text, settings.tts_max_chars)
    if not segments:
        raise ValueError("Text cannot be empty")

    provider = _resolve_provider()
    if provider == "edge":
        audio_bytes, sample_rate, duration_seconds, selected_voice = await _synthesize_with_edge_segments(
            segments,
            voice_preset,
        )
        file_path, file_url = _save_audio_file(audio_bytes, suffix=".mp3")
    else:
        wav_bytes, sample_rate, duration_seconds, selected_voice = await asyncio.to_thread(
            _synthesize_with_piper_segments,
            segments,
            voice_preset,
        )

        file_path, file_url = _save_audio_file(wav_bytes, suffix=".wav")
        sample_rate_from_bytes, frame_count = _resolve_wav_stats_from_bytes(wav_bytes)
        if sample_rate_from_bytes > 0:
            sample_rate = sample_rate_from_bytes
            duration_seconds = round(frame_count / float(sample_rate_from_bytes), 2)
    return TTSResult(
        file_url=file_url,
        file_path=file_path,
        provider=provider,
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        text_chars=sum(len(segment) for segment in segments),
        original_text_chars=original_text_chars,
        truncated=False,
        segment_count=len(segments),
        voice_preset=selected_voice,
    )

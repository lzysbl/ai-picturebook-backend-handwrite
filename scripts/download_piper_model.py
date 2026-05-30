"""Piper 中文语音模型下载脚本。

用途：
- 下载本地 Piper TTS 所需的中文语音模型和配置文件。
- 当 `.env` 中 `TTS_PROVIDER=piper` 时，后端 `tts_service.py` 会使用这些模型。

关联页面/模块：
- `/ui/camera`：实时识别后的朗读功能。
- `app/services/tts_service.py`：Piper 语音合成后端。

默认输出：
- `models/piper/zh_CN-huayan-x_low.onnx`
- `models/piper/zh_CN-huayan-x_low.onnx.json`
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_VOICE = "zh_CN-huayan-x_low"
DEFAULT_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
VOICE_PATHS = {
    "zh_CN-huayan-x_low": "zh/zh_CN/huayan/x_low",
    "zh_CN-huayan-medium": "zh/zh_CN/huayan/medium",
}


def _download_file(url: str, output_path: Path, force: bool = False) -> None:
    if output_path.exists() and output_path.stat().st_size > 0 and not force:
        print(f"skip existing: {output_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    request = Request(url, headers={"User-Agent": "ai-picturebook-piper-downloader/1.0"})

    print(f"download: {url}")
    try:
        with urlopen(request, timeout=60) as response, tmp_path.open("wb") as file:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                file.write(chunk)
    except URLError as exc:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"download failed: {url}") from exc

    tmp_path.replace(output_path)
    print(f"saved: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")


def download_piper_voice(
    *,
    voice: str,
    output_dir: Path,
    base_url: str,
    force: bool,
) -> None:
    voice_path = VOICE_PATHS.get(voice)
    if not voice_path:
        available = ", ".join(sorted(VOICE_PATHS))
        raise ValueError(f"unknown voice: {voice}; available: {available}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in (".onnx", ".onnx.json"):
        filename = f"{voice}{suffix}"
        url = f"{base_url.rstrip('/')}/{voice_path}/{filename}"
        _download_file(url, output_dir / filename, force=force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Piper voice model files.")
    parser.add_argument("--voice", default=DEFAULT_VOICE, choices=sorted(VOICE_PATHS))
    parser.add_argument("--output-dir", default="models/piper")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()

    download_piper_voice(
        voice=args.voice,
        output_dir=Path(args.output_dir),
        base_url=args.base_url,
        force=args.force,
    )
    print("done")


if __name__ == "__main__":
    main()

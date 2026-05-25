"""Benchmark realtime scan APIs with a directory of local images.

Usage example:
    python scripts/benchmark_scan_images.py --image-dir demo_book --username yjl --password xxx --mode direct --stream --tts
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class BenchmarkConfig:
    base_url: str
    token: str
    image_dir: Path
    out_dir: Path
    mode: str
    stream: bool
    repeat: int
    limit: int | None
    recursive: bool
    per_dir_limit: int | None
    exclude_dirs: tuple[str, ...]
    narration_style: str
    audience_age: str
    prompt: str | None
    tts: bool
    timeout: float
    sleep_seconds: float


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def summarize(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "avg": 0, "p50": 0, "p90": 0, "max": 0}
    return {
        "count": len(values),
        "avg": round(statistics.mean(values)),
        "p50": percentile(values, 0.5),
        "p90": percentile(values, 0.9),
        "max": max(values),
    }


def discover_images(
    image_dir: Path,
    *,
    recursive: bool = False,
    per_dir_limit: int | None = None,
    exclude_dirs: tuple[str, ...] = (),
) -> list[Path]:
    if not image_dir.exists():
        raise FileNotFoundError(f"Image directory does not exist: {image_dir}")
    if not image_dir.is_dir():
        raise NotADirectoryError(f"Image path is not a directory: {image_dir}")

    excluded = {name.lower() for name in exclude_dirs}
    iterator = image_dir.rglob("*") if recursive else image_dir.iterdir()
    images = sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and not any(part.lower() in excluded for part in path.relative_to(image_dir).parts[:-1])
    )
    if per_dir_limit is None:
        return images

    grouped: dict[Path, list[Path]] = {}
    for path in images:
        grouped.setdefault(path.parent, []).append(path)
    limited: list[Path] = []
    for directory in sorted(grouped):
        limited.extend(grouped[directory][:per_dir_limit])
    return limited


def elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def make_form_data(config: BenchmarkConfig) -> dict[str, str]:
    data = {
        "response_mode": config.mode,
        "narration_style": config.narration_style,
        "audience_age": config.audience_age,
        "crop_source": "full",
        "include_judge": "false",
    }
    if config.prompt:
        data["prompt"] = config.prompt
    return data


def parse_api_response(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("success", False):
        raise RuntimeError(str(payload.get("message") or payload))
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("API response data is not an object")
    return data


def login(base_url: str, username: str, password: str, timeout: float) -> str:
    import httpx

    response = httpx.post(
        f"{base_url.rstrip('/')}/api/users/login",
        json={"username": username, "password": password},
        timeout=timeout,
    )
    response.raise_for_status()
    data = parse_api_response(response.json())
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError("Login succeeded but access_token is missing")
    return token


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def scan_image(client: Any, config: BenchmarkConfig, image_path: Path) -> dict[str, Any]:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    started_at = time.perf_counter()
    with image_path.open("rb") as handle:
        response = client.post(
            f"{config.base_url.rstrip('/')}/api/stories/scan",
            headers=auth_headers(config.token),
            data=make_form_data(config),
            files={"image": (image_path.name, handle, mime_type)},
        )
    client_total_ms = elapsed_ms(started_at)
    response.raise_for_status()
    data = parse_api_response(response.json())
    data["client_total_ms"] = client_total_ms
    data["client_first_delta_ms"] = None
    return data


def stream_scan_image(client: Any, config: BenchmarkConfig, image_path: Path) -> dict[str, Any]:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    started_at = time.perf_counter()
    first_delta_ms: int | None = None
    done_payload: dict[str, Any] | None = None
    story_chunks: list[str] = []

    with image_path.open("rb") as handle:
        with client.stream(
            "POST",
            f"{config.base_url.rstrip('/')}/api/stories/scan/stream",
            headers=auth_headers(config.token),
            data=make_form_data(config),
            files={"image": (image_path.name, handle, mime_type)},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                event = json.loads(line.removeprefix("data:").strip())
                event_type = event.get("type")
                if event_type == "delta":
                    text = str(event.get("text") or "")
                    if text and first_delta_ms is None:
                        first_delta_ms = elapsed_ms(started_at)
                    story_chunks.append(text)
                elif event_type == "done":
                    done_payload = event
                elif event_type == "error":
                    raise RuntimeError(str(event.get("message") or "stream scan failed"))

    if done_payload is None:
        raise RuntimeError("Stream finished without a done event")
    done_payload["client_total_ms"] = elapsed_ms(started_at)
    done_payload["client_first_delta_ms"] = first_delta_ms
    if not done_payload.get("story_content") and story_chunks:
        done_payload["story_content"] = "".join(story_chunks).strip()
    return done_payload


def synthesize_tts(client: Any, config: BenchmarkConfig, text: str) -> dict[str, Any]:
    started_at = time.perf_counter()
    response = client.post(
        f"{config.base_url.rstrip('/')}/api/stories/tts",
        headers={**auth_headers(config.token), "Content-Type": "application/json"},
        json={"text": text},
    )
    client_total_ms = elapsed_ms(started_at)
    response.raise_for_status()
    data = parse_api_response(response.json())
    timing = data.get("timing") if isinstance(data.get("timing"), dict) else {}
    return {
        "tts_client_ms": client_total_ms,
        "tts_server_ms": timing.get("total_ms"),
        "tts_provider": data.get("provider"),
        "tts_segment_count": data.get("segment_count"),
        "audio_url": data.get("audio_url"),
    }


def row_from_result(
    image_path: Path,
    run_index: int,
    config: BenchmarkConfig,
    result: dict[str, Any],
    tts_result: dict[str, Any] | None = None,
    error: str | None = None,
    tts_error: str | None = None,
) -> dict[str, Any]:
    timing = result.get("timing") if isinstance(result.get("timing"), dict) else {}
    story = str(result.get("story_content") or result.get("text") or "")
    analysis = result.get("analysis_result") if isinstance(result.get("analysis_result"), list) else []
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    tts_result = tts_result or {}
    return {
        "book": image_path.parent.name,
        "image": image_path.name,
        "relative_path": str(image_path),
        "run": run_index,
        "mode": config.mode,
        "stream": config.stream,
        "status": "error" if error else "ok",
        "client_total_ms": result.get("client_total_ms"),
        "client_first_delta_ms": result.get("client_first_delta_ms"),
        "server_total_ms": timing.get("total_ms"),
        "server_first_delta_ms": timing.get("first_delta_ms"),
        "analysis_ms": timing.get("analysis_ms"),
        "story_ms": timing.get("story_ms"),
        "quality_ms": timing.get("quality_ms"),
        "crop_mode": result.get("crop_mode") or timing.get("crop_mode"),
        "response_mode": result.get("response_mode"),
        "provider": result.get("provider"),
        "recent_page_count": meta.get("recent_page_count"),
        "story_chars": len(story),
        "analysis_items": len(analysis),
        "tts_client_ms": tts_result.get("tts_client_ms"),
        "tts_server_ms": tts_result.get("tts_server_ms"),
        "tts_provider": tts_result.get("tts_provider"),
        "tts_segment_count": tts_result.get("tts_segment_count"),
        "error": error or "",
        "tts_error": tts_error or "",
        "story_preview": story.replace("\n", " ")[:120],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "book",
        "image",
        "relative_path",
        "run",
        "mode",
        "stream",
        "status",
        "client_total_ms",
        "client_first_delta_ms",
        "server_total_ms",
        "server_first_delta_ms",
        "analysis_ms",
        "story_ms",
        "quality_ms",
        "crop_mode",
        "response_mode",
        "provider",
        "recent_page_count",
        "story_chars",
        "analysis_items",
        "tts_client_ms",
        "tts_server_ms",
        "tts_provider",
        "tts_segment_count",
        "error",
        "tts_error",
        "story_preview",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_values(rows: list[dict[str, Any]], key: str) -> list[int]:
    values: list[int] = []
    for row in rows:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            values.append(int(value))
        except (TypeError, ValueError):
            continue
    return values


def build_markdown(rows: list[dict[str, Any]], config: BenchmarkConfig) -> str:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    lines = [
        "# Image Scan Benchmark",
        "",
        f"- Base URL: `{config.base_url}`",
        f"- Image directory: `{config.image_dir}`",
        f"- Mode: `{config.mode}`",
        f"- Stream: `{config.stream}`",
        f"- Repeat: `{config.repeat}`",
        f"- Limit: `{getattr(config, 'limit', None)}`",
        f"- Recursive: `{getattr(config, 'recursive', False)}`",
        f"- Per-dir limit: `{getattr(config, 'per_dir_limit', None)}`",
        f"- Exclude dirs: `{', '.join(getattr(config, 'exclude_dirs', ())) or '-'}`",
        f"- TTS: `{config.tts}`",
        f"- Success: `{len(ok_rows)}/{len(rows)}`",
        "",
        "## Timing Summary",
        "",
        "| Metric | Count | Avg | P50 | P90 | Max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for metric in (
        "client_total_ms",
        "client_first_delta_ms",
        "server_total_ms",
        "server_first_delta_ms",
        "analysis_ms",
        "story_ms",
        "quality_ms",
        "tts_client_ms",
        "tts_server_ms",
    ):
        summary = summarize(int_values(ok_rows, metric))
        lines.append(
            f"| {metric} | {summary['count']} | {summary['avg']} | "
            f"{summary['p50']} | {summary['p90']} | {summary['max']} |"
        )

    if any(row.get("status") == "error" for row in rows):
        lines.extend(["", "## Errors", ""])
        for row in rows:
            if row.get("status") == "error":
                lines.append(f"- {row.get('image')} run {row.get('run')}: {row.get('error')}")

    if any(row.get("tts_error") for row in rows):
        lines.extend(["", "## TTS Errors", ""])
        for row in rows:
            if row.get("tts_error"):
                lines.append(f"- {row.get('image')} run {row.get('run')}: {row.get('tts_error')}")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark realtime scan APIs with local images.")
    parser.add_argument("--image-dir", required=True, help="Directory containing phone-shot picture-book images.")
    parser.add_argument("--base-url", default=os.getenv("BENCHMARK_BASE_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--username", default=os.getenv("BENCHMARK_USERNAME"))
    parser.add_argument("--password", default=os.getenv("BENCHMARK_PASSWORD"))
    parser.add_argument("--token", default=os.getenv("BENCHMARK_ACCESS_TOKEN"))
    parser.add_argument("--mode", choices=["fast", "direct", "full"], default="direct")
    parser.add_argument("--stream", action="store_true", help="Use /api/stories/scan/stream instead of /api/stories/scan.")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None, help="Only benchmark the first N images.")
    parser.add_argument("--recursive", action="store_true", help="Recursively discover images under --image-dir.")
    parser.add_argument("--per-dir-limit", type=int, default=None, help="Use at most N images from each directory.")
    parser.add_argument("--exclude-dir", action="append", default=[], help="Directory name to exclude. Can be passed multiple times.")
    parser.add_argument("--style", default="温柔")
    parser.add_argument("--age", default="3-6")
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--tts", action="store_true", help="Also benchmark /api/stories/tts for each successful story.")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--sleep", type=float, default=0, help="Seconds to sleep between requests.")
    parser.add_argument("--out-dir", default="reports/image_scan_benchmark")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.per_dir_limit is not None and args.per_dir_limit < 1:
        raise SystemExit("--per-dir-limit must be >= 1")
    if args.stream and args.mode == "full":
        raise SystemExit("--stream only supports fast/direct modes.")

    image_dir = Path(args.image_dir)
    images = discover_images(
        image_dir,
        recursive=args.recursive,
        per_dir_limit=args.per_dir_limit,
        exclude_dirs=tuple(args.exclude_dir),
    )
    if args.limit is not None:
        images = images[: args.limit]
    if not images:
        raise SystemExit(f"No images found in {image_dir}. Supported extensions: {sorted(IMAGE_EXTENSIONS)}")

    token = args.token
    if not token:
        if not args.username or not args.password:
            raise SystemExit("Pass --token, or pass both --username and --password.")
        token = login(args.base_url, args.username, args.password, args.timeout)

    config = BenchmarkConfig(
        base_url=args.base_url.rstrip("/"),
        token=token,
        image_dir=image_dir,
        out_dir=Path(args.out_dir),
        mode=args.mode,
        stream=args.stream,
        repeat=args.repeat,
        limit=args.limit,
        recursive=args.recursive,
        per_dir_limit=args.per_dir_limit,
        exclude_dirs=tuple(args.exclude_dir),
        narration_style=args.style,
        audience_age=args.age,
        prompt=args.prompt,
        tts=args.tts,
        timeout=args.timeout,
        sleep_seconds=args.sleep,
    )
    config.out_dir.mkdir(parents=True, exist_ok=True)

    import httpx

    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=config.timeout) as client:
        for run_index in range(1, config.repeat + 1):
            for image_path in images:
                result: dict[str, Any] = {}
                tts_result: dict[str, Any] | None = None
                error: str | None = None
                tts_error: str | None = None
                try:
                    if config.stream:
                        result = stream_scan_image(client, config, image_path)
                    else:
                        result = scan_image(client, config, image_path)
                    story = str(result.get("story_content") or "")
                    if config.tts and story.strip():
                        try:
                            tts_result = synthesize_tts(client, config, story)
                        except Exception as exc:  # noqa: BLE001
                            tts_error = str(exc)
                except Exception as exc:  # noqa: BLE001
                    error = str(exc)
                rows.append(row_from_result(image_path, run_index, config, result, tts_result, error, tts_error))
                status = "ERROR" if error else "OK"
                print(f"[{status}] run={run_index} image={image_path.name}")
                if config.sleep_seconds > 0:
                    time.sleep(config.sleep_seconds)

    csv_path = config.out_dir / "image_scan_benchmark.csv"
    md_path = config.out_dir / "image_scan_benchmark_summary.md"
    write_csv(csv_path, rows)
    md_path.write_text(build_markdown(rows, config), encoding="utf-8")
    print(f"CSV: {csv_path}")
    print(f"Summary: {md_path}")


if __name__ == "__main__":
    main()

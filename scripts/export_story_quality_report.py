"""Export story quality results for thesis tables."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models.story import Story
from app.services.eval_service import evaluate_story_full


def _safe_load_analysis(raw: str | list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    return []


async def _load_story_payload(story_id: int) -> dict[str, Any]:
    async with SessionLocal() as db:
        result = await db.execute(select(Story).where(Story.id == story_id))
        story = result.scalar_one_or_none()
        if story is None:
            raise ValueError(f"Story {story_id} not found")
        return {
            "source": "database",
            "story_id": story.id,
            "book_id": story.book_id,
            "prompt": story.prompt,
            "analysis_result": _safe_load_analysis(story.image_analysis),
            "story_content": story.story_content,
        }


def _load_local_payload(analysis_file: Path, story_file: Path) -> dict[str, Any]:
    return {
        "source": "local_files",
        "story_id": None,
        "book_id": None,
        "prompt": None,
        "analysis_result": _safe_load_analysis(analysis_file.read_text(encoding="utf-8")),
        "story_content": story_file.read_text(encoding="utf-8"),
    }


def _resolve_output_path(output: str | None, export_format: str, story_id: int | None) -> Path:
    if output:
        return Path(output)
    suffix = "csv" if export_format == "csv" else "json"
    return Path(f"story_quality_report_{story_id or 'sample'}.{suffix}")


def _flatten_row(payload: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    paper = quality.get("paper_metrics", {})
    return {
        "source": payload.get("source"),
        "story_id": payload.get("story_id"),
        "book_id": payload.get("book_id"),
        "overall": paper.get("overall"),
        "coherence": paper.get("coherence"),
        "age_appropriateness": paper.get("age_appropriateness"),
        "page_hit_count": paper.get("page_hit_count"),
        "page_coverage_ratio": paper.get("page_coverage_ratio"),
        "expected_pages": "|".join(str(x) for x in paper.get("expected_pages", [])),
        "referenced_pages": "|".join(str(x) for x in paper.get("referenced_pages", [])),
        "missing_pages": "|".join(str(x) for x in paper.get("missing_pages", [])),
        "hallucination_count": paper.get("hallucination_count"),
        "hallucinated_entities": "|".join(str(x) for x in paper.get("hallucinated_entities", [])),
        "repeat_3gram_ratio": paper.get("repeat_3gram_ratio"),
        "distinct_2": paper.get("distinct_2"),
    }


def _write_json(output_path: Path, payload: dict[str, Any], quality: dict[str, Any]) -> None:
    report = {
        "source": payload.get("source"),
        "story_id": payload.get("story_id"),
        "book_id": payload.get("book_id"),
        "prompt": payload.get("prompt"),
        "paper_metrics": quality.get("paper_metrics", {}),
        "quality": quality,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(output_path: Path, payload: dict[str, Any], quality: dict[str, Any]) -> None:
    row = _flatten_row(payload, quality)
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


async def _run(args: argparse.Namespace) -> Path:
    if args.story_id is not None:
        payload = await _load_story_payload(args.story_id)
        story_id = args.story_id
    else:
        payload = _load_local_payload(Path(args.analysis_file), Path(args.story_file))
        story_id = None

    quality = await evaluate_story_full(
        analysis_result=payload["analysis_result"],
        story_content=payload["story_content"],
        include_judge=args.include_judge,
        judge_samples=args.judge_samples,
    )

    output_path = _resolve_output_path(args.output, args.format, story_id)
    if args.format == "csv":
        _write_csv(output_path, payload, quality)
    else:
        _write_json(output_path, payload, quality)
    return output_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export thesis-friendly story quality reports.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--story-id", type=int, help="Existing story record id from the database.")
    source.add_argument("--analysis-file", help="Local analysis-result JSON file.")
    parser.add_argument("--story-file", help="Local story text file. Required with --analysis-file.")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--output", help="Output file path.")
    parser.add_argument("--include-judge", action="store_true")
    parser.add_argument("--judge-samples", type=int, default=None)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.analysis_file and not args.story_file:
        parser.error("--story-file is required when using --analysis-file")
    output_path = asyncio.run(_run(args))
    print(f"Exported report to {output_path}")


if __name__ == "__main__":
    main()

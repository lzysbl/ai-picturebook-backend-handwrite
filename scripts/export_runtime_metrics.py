"""运行日志指标导出脚本。

用途：
- 从 `logs/app.log` 解析识别、流式识别、完整生成和 TTS 的耗时日志。
- 导出 Markdown 汇总和 CSV 原始数据，用于论文第 6 章性能分析。

关联页面/模块：
- `/ui/camera`：实时识别、流式识别、TTS。
- `/ui/generate`：完整故事生成。
- `app/routers/stories.py`：记录 scan、stream、tts timing 日志。

运行方式：
- `python scripts/export_runtime_metrics.py`
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path


SCAN_PATTERN = re.compile(
    r"scan(?:\.stream)?[._]timing mode=(?P<mode>\S+).*?total_ms=(?P<total>\d+)"
    r"(?:.*?first_delta_ms=(?P<first_delta>\d+|None))?"
    r".*?analysis_ms=(?P<analysis>\d+)"
    r".*?quality_ms=(?P<quality>\d+)"
)
TTS_PATTERN = re.compile(
    r"tts\.timing provider=(?P<provider>\S+) total_ms=(?P<total>\d+).*?segment_count=(?P<segments>\d+)"
)


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def summarize(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "avg": 0, "p50": 0, "p90": 0, "max": 0}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values)),
        "p50": percentile(values, 0.5),
        "p90": percentile(values, 0.9),
        "max": max(values),
    }


def parse_log(log_path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    scan_rows: list[dict[str, object]] = []
    tts_rows: list[dict[str, object]] = []

    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        scan_match = SCAN_PATTERN.search(line)
        if scan_match:
            first_delta_raw = scan_match.group("first_delta")
            story_match = re.search(r"\bstory_ms=(\d+)", line)
            scan_rows.append(
                {
                    "mode": scan_match.group("mode"),
                    "total_ms": int(scan_match.group("total")),
                    "analysis_ms": int(scan_match.group("analysis")),
                    "story_ms": int(story_match.group(1)) if story_match else None,
                    "quality_ms": int(scan_match.group("quality")),
                    "first_delta_ms": None if first_delta_raw in (None, "None") else int(first_delta_raw),
                }
            )
            continue

        tts_match = TTS_PATTERN.search(line)
        if tts_match:
            tts_rows.append(
                {
                    "provider": tts_match.group("provider"),
                    "total_ms": int(tts_match.group("total")),
                    "segment_count": int(tts_match.group("segments")),
                }
            )

    return scan_rows, tts_rows


def build_markdown(scan_rows: list[dict[str, object]], tts_rows: list[dict[str, object]]) -> str:
    lines = ["# Runtime Metrics Summary", ""]

    scan_groups: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in scan_rows:
        mode = str(row["mode"])
        scan_groups[mode]["total_ms"].append(int(row["total_ms"]))
        scan_groups[mode]["analysis_ms"].append(int(row["analysis_ms"]))
        story_ms = row.get("story_ms")
        if isinstance(story_ms, int):
            scan_groups[mode]["story_ms"].append(story_ms)
        scan_groups[mode]["quality_ms"].append(int(row["quality_ms"]))
        first_delta = row["first_delta_ms"]
        if isinstance(first_delta, int):
            scan_groups[mode]["first_delta_ms"].append(first_delta)

    lines.extend(
        [
            "## Scan Metrics",
            "",
            "| Mode | Metric | Count | Avg | P50 | P90 | Max |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for mode in sorted(scan_groups):
        for metric in ("total_ms", "analysis_ms", "story_ms", "first_delta_ms", "quality_ms"):
            summary = summarize(scan_groups[mode].get(metric, []))
            lines.append(
                f"| {mode} | {metric} | {summary['count']} | {summary['avg']} | "
                f"{summary['p50']} | {summary['p90']} | {summary['max']} |"
            )

    tts_groups: dict[str, list[int]] = defaultdict(list)
    for row in tts_rows:
        tts_groups[str(row["provider"])].append(int(row["total_ms"]))

    lines.extend(
        [
            "",
            "## TTS Metrics",
            "",
            "| Provider | Count | Avg | P50 | P90 | Max |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for provider in sorted(tts_groups):
        summary = summarize(tts_groups[provider])
        lines.append(
            f"| {provider} | {summary['count']} | {summary['avg']} | {summary['p50']} | "
            f"{summary['p90']} | {summary['max']} |"
        )

    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export runtime metrics from logs/app.log")
    parser.add_argument("--log", default="logs/app.log", help="Path to app log file")
    parser.add_argument("--out-dir", default="reports/runtime_metrics", help="Output directory")
    args = parser.parse_args()

    log_path = Path(args.log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scan_rows, tts_rows = parse_log(log_path)
    markdown = build_markdown(scan_rows, tts_rows)

    (out_dir / "runtime_metrics_summary.md").write_text(markdown, encoding="utf-8")
    write_csv(
        out_dir / "scan_metrics_raw.csv",
        scan_rows,
        ["mode", "total_ms", "analysis_ms", "story_ms", "quality_ms", "first_delta_ms"],
    )
    write_csv(
        out_dir / "tts_metrics_raw.csv",
        tts_rows,
        ["provider", "total_ms", "segment_count"],
    )


if __name__ == "__main__":
    main()

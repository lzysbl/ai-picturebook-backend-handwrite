"""Tests for the thesis report export script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_export_story_quality_report_writes_json(tmp_path: Path) -> None:
    """The export script should generate a thesis-friendly JSON report from local files."""

    analysis_file = tmp_path / "analysis.json"
    story_file = tmp_path / "story.txt"
    output_file = tmp_path / "report.json"

    analysis_file.write_text(
        json.dumps(
            [
                {"page": 1, "角色": ["小熊"], "关键物体": ["花"]},
                {"page": 2, "角色": ["小熊"], "关键物体": ["树"]},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    story_file.write_text("第1页：小熊出门。第2页：小熊看见花。", encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [
            sys.executable,
            "scripts/export_story_quality_report.py",
            "--analysis-file",
            str(analysis_file),
            "--story-file",
            str(story_file),
            "--output",
            str(output_file),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(output_file.read_text(encoding="utf-8"))
    assert report["source"] == "local_files"
    assert "paper_metrics" in report
    assert report["paper_metrics"]["page_hit_count"] == 2
    assert report["paper_metrics"]["page_coverage_ratio"] == 1.0

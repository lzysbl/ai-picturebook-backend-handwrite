"""运行指标导出脚本测试。

覆盖范围：
- 用临时日志文件验证 scan、stream、tts timing 能被正确解析。
- 验证 Markdown 汇总和 CSV 原始数据文件会正常生成。

关联脚本：
- `scripts/export_runtime_metrics.py`
- 论文第 6 章性能统计。

运行方式：
- `pytest tests/test_export_runtime_metrics.py`
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_export_runtime_metrics_writes_markdown_and_csv(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    out_dir = tmp_path / "runtime_metrics"

    log_file.write_text(
        "\n".join(
            [
                "2026-05-02 | INFO | scan.timing mode=fast cache_hit=false crop_mode=guide_crop total_ms=1200 analysis_ms=1100 story_ms=20 quality_ms=5",
                "2026-05-02 | INFO | scan.stream_timing mode=fast_stream crop_mode=guide_crop total_ms=900 first_delta_ms=500 analysis_ms=850 quality_ms=0",
                "2026-05-02 | INFO | tts.timing provider=edge total_ms=650 text_chars=80 original_text_chars=80 segment_count=1 truncated=false voice=zh-CN-XiaoxiaoNeural",
            ]
        ),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [
            sys.executable,
            "scripts/export_runtime_metrics.py",
            "--log",
            str(log_file),
            "--out-dir",
            str(out_dir),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    summary_md = out_dir / "runtime_metrics_summary.md"
    scan_csv = out_dir / "scan_metrics_raw.csv"
    tts_csv = out_dir / "tts_metrics_raw.csv"

    assert summary_md.exists()
    assert scan_csv.exists()
    assert tts_csv.exists()

    summary_text = summary_md.read_text(encoding="utf-8")
    assert "Scan Metrics" in summary_text
    assert "| fast | total_ms | 1 | 1200 | 1200 | 1200 | 1200 |" in summary_text
    assert "| fast | story_ms | 1 | 20 | 20 | 20 | 20 |" in summary_text
    assert "fast_stream" in summary_text
    assert "edge" in summary_text

    scan_text = scan_csv.read_text(encoding="utf-8-sig")
    assert "fast,1200,1100,20,5," in scan_text

"""Tests for image scan benchmark helpers."""

from __future__ import annotations

from pathlib import Path

from scripts.benchmark_scan_images import build_markdown, discover_images, row_from_result, summarize


def test_discover_images_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.PNG").write_bytes(b"x")
    (tmp_path / "c.txt").write_text("x", encoding="utf-8")

    images = discover_images(tmp_path)

    assert [path.name for path in images] == ["a.jpg", "b.PNG"]


def test_discover_images_can_sample_recursively_per_directory(tmp_path: Path) -> None:
    book_a = tmp_path / "book_a"
    book_b = tmp_path / "book_b"
    ignored = tmp_path / "phone_pages"
    book_a.mkdir()
    book_b.mkdir()
    ignored.mkdir()
    for index in range(3):
        (book_a / f"a{index}.jpg").write_bytes(b"x")
        (book_b / f"b{index}.jpg").write_bytes(b"x")
        (ignored / f"p{index}.jpg").write_bytes(b"x")

    images = discover_images(
        tmp_path,
        recursive=True,
        per_dir_limit=2,
        exclude_dirs=("phone_pages",),
    )

    assert [path.name for path in images] == ["a0.jpg", "a1.jpg", "b0.jpg", "b1.jpg"]


def test_summarize_reports_p50_p90_and_max() -> None:
    summary = summarize([100, 200, 300, 400, 500])

    assert summary == {"count": 5, "avg": 300, "p50": 300, "p90": 460, "max": 500}


def test_build_markdown_contains_success_ratio(tmp_path: Path) -> None:
    class Config:
        base_url = "http://127.0.0.1:8001"
        image_dir = tmp_path
        mode = "direct"
        stream = True
        repeat = 1
        tts = False

    markdown = build_markdown(
        [
            {
                "status": "ok",
                "client_total_ms": 1000,
                "server_total_ms": 900,
            }
        ],
        Config(),  # type: ignore[arg-type]
    )

    assert "Success: `1/1`" in markdown
    assert "| client_total_ms | 1 | 1000 | 1000 | 1000 | 1000 |" in markdown


def test_tts_error_does_not_mark_scan_as_failed(tmp_path: Path) -> None:
    class Config:
        mode = "direct"
        stream = False

    row = row_from_result(
        tmp_path / "page.jpg",
        1,
        Config(),  # type: ignore[arg-type]
        {"story_content": "小猫慢慢走到河边。"},
        error=None,
        tts_error="edge-tts is not installed",
    )

    assert row["status"] == "ok"
    assert row["tts_error"] == "edge-tts is not installed"

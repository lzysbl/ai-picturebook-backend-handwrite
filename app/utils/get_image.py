"""绘本图片爬虫（并发下载版）。

功能：
1. 抓取绘本详情页列表。
2. 解析每本绘本标题和分页图片链接。
3. 使用线程池并发下载每本绘本的所有页图。
4. 校验并创建保存目录（默认项目根目录 demo_book）。
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.limaogushi.com"
INDEX_URL = "https://www.limaogushi.com/huiben"

# 当前文件: app/utils/get_image.py
# 项目根目录: ../../
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAVE_ROOT = PROJECT_ROOT / "demo_book"

MAX_WORKERS = 8
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL + "/",
}


def ensure_save_root(save_root: Path) -> Path:
    """校验并创建保存目录，返回绝对路径。"""
    resolved = save_root.resolve()
    if resolved.exists() and not resolved.is_dir():
        raise NotADirectoryError(f"保存路径不是目录: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def safe_name(name: str) -> str:
    """清理文件夹名中的非法字符。"""
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return cleaned or "未命名绘本"


def get_html(url: str) -> str:
    """获取网页 HTML。"""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def get_soup(url: str) -> BeautifulSoup:
    """获取 BeautifulSoup 对象。"""
    return BeautifulSoup(get_html(url), "html.parser")


def extract_detail_urls() -> list[str]:
    """从首页提取所有绘本详情页链接。"""
    soup = get_soup(INDEX_URL)
    detail_urls: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if re.fullmatch(r"/huiben/\d+\.html", href):
            detail_urls.add(urljoin(BASE_URL, href))
        elif re.fullmatch(r"https?://www\.limaogushi\.com/huiben/\d+\.html", href):
            detail_urls.add(href)

    return sorted(detail_urls)


def extract_title(soup: BeautifulSoup) -> str:
    """从详情页提取绘本标题。"""
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if text and text != "狸猫故事":
            return text

    selectors = [
        {"name": "div", "class_": "title"},
        {"name": "div", "class_": "article-title"},
        {"name": "div", "class_": "post-title"},
        {"name": "h2", "class_": "title"},
    ]
    for rule in selectors:
        tag = soup.find(rule["name"], class_=rule["class_"])
        if tag:
            text = tag.get_text(strip=True)
            if text and text != "狸猫故事":
                return text

    if soup.title:
        title_text = soup.title.get_text(strip=True)
        title_text = re.split(r"[-_|]", title_text)[0].strip()
        if title_text:
            return title_text

    return "未命名绘本"


def extract_page_image_links(detail_url: str) -> list[tuple[int, str]]:
    """从详情页提取“第X页图片”链接。"""
    soup = get_soup(detail_url)
    pages: list[tuple[int, str]] = []

    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        href = a_tag["href"].strip()
        match = re.fullmatch(r"第(\d+)页图片", text)
        if match:
            page_no = int(match.group(1))
            img_url = urljoin(detail_url, href)
            pages.append((page_no, img_url))

    dedup: dict[int, str] = {}
    for page_no, img_url in pages:
        dedup[page_no] = img_url
    return sorted(dedup.items(), key=lambda item: item[0])


def extract_book_info(detail_url: str) -> tuple[str, list[tuple[int, str]]]:
    """提取标题和图片链接。"""
    soup = get_soup(detail_url)
    return extract_title(soup), extract_page_image_links(detail_url)


def guess_ext(content_type: str, url: str) -> str:
    """根据响应头或 URL 猜测图片扩展名。"""
    content_type = (content_type or "").lower()
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"

    match = re.search(r"\.(jpg|jpeg|png|webp|gif)(?:\?|$)", url, re.I)
    if match:
        ext = match.group(1).lower()
        return ".jpg" if ext == "jpeg" else "." + ext
    return ".jpg"


def download_file(url: str, save_path_without_ext: Path, referer: str) -> Path:
    """下载单张图片并返回保存路径。"""
    headers = dict(HEADERS)
    headers["Referer"] = referer
    with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT) as resp:
        resp.raise_for_status()
        ext = guess_ext(resp.headers.get("Content-Type"), url)
        save_path = save_path_without_ext.with_suffix(ext)
        with save_path.open("wb") as file_obj:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)
    return save_path


def _download_one_page(book_dir: Path, page_no: int, img_url: str, referer: str) -> tuple[int, bool, str]:
    """线程池任务：下载单页，返回结果状态。"""
    filename_base = book_dir / f"{page_no:03d}"
    try:
        saved_path = download_file(img_url, filename_base, referer=referer)
        return page_no, True, str(saved_path)
    except Exception as exc:  # noqa: BLE001
        return page_no, False, f"{img_url} -> {exc}"


def download_book_pages_concurrent(
    book_dir: Path,
    detail_url: str,
    pages: list[tuple[int, str]],
    max_workers: int = MAX_WORKERS,
) -> None:
    """并发下载某本绘本的所有页图。"""
    if not pages:
        print("没有找到“第X页图片”链接，跳过。")
        return

    workers = max(1, min(max_workers, len(pages)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_download_one_page, book_dir, page_no, img_url, detail_url)
            for page_no, img_url in pages
        ]
        for future in as_completed(futures):
            page_no, ok, msg = future.result()
            if ok:
                print(f"  [OK] 第{page_no}页 -> {msg}")
            else:
                print(f"  [FAIL] 第{page_no}页 -> {msg}")


def main(save_root: Path = DEFAULT_SAVE_ROOT, max_workers: int = MAX_WORKERS) -> None:
    """主流程。"""
    final_save_root = ensure_save_root(save_root)
    print(f"保存目录: {final_save_root}")
    print(f"并发线程数: {max_workers}")

    try:
        detail_urls = extract_detail_urls()
    except Exception as exc:  # noqa: BLE001
        print("抓取首页失败：", exc)
        return

    print("找到绘本数量:", len(detail_urls))
    if not detail_urls:
        print("没有找到任何绘本详情页链接。")
        return

    for idx, detail_url in enumerate(detail_urls, start=1):
        print("=" * 70)
        print(f"[{idx}/{len(detail_urls)}] {detail_url}")

        try:
            title, pages = extract_book_info(detail_url)
        except Exception as exc:  # noqa: BLE001
            print("解析详情页失败：", exc)
            continue

        book_dir = final_save_root / safe_name(title)
        book_dir.mkdir(parents=True, exist_ok=True)

        print("绘本标题:", title)
        print("页数:", len(pages))
        download_book_pages_concurrent(book_dir, detail_url, pages, max_workers=max_workers)

        try:
            source_file = book_dir / "_source.txt"
            source_file.write_text(
                f"title: {title}\n"
                f"detail_url: {detail_url}\n",
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            print("写入来源文件失败：", exc)

    print("=" * 70)
    print("全部下载完成。")


if __name__ == "__main__":
    main()

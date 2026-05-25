from __future__ import annotations

import math
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_DIR = ROOT / "reports" / "software_engineering_figures"
THESIS_DIR = ROOT / "reports" / "thesis_figures"
BACKUP_ROOT = THESIS_DIR / f"backup_before_cn_redraw_{datetime.now():%Y%m%d_%H%M%S}"
FONT_PATH = Path(r"C:\Windows\Fonts\simhei.ttf")

BG = "#f5f8fb"
INK = "#1f3554"
BLUE = "#3f78bf"
LIGHT_BLUE = "#e8f3fb"
GREEN = "#e6f4ea"
ORANGE = "#fff2df"
PINK = "#fdecec"
GRAY = "#eef1f5"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size)


F16 = font(16)
F18 = font(18)
F20 = font(20)
F22 = font(22)
F24 = font(24)
F28 = font(28)
F32 = font(32)


def save_backup(paths: list[Path]) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            target = BACKUP_ROOT / path.name
            shutil.copy2(path, target)


def text_size(draw: ImageDraw.ImageDraw, text: str, ft: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=ft)
    return box[2] - box[0], box[3] - box[1]


def centered_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, ft=F22, fill=INK) -> None:
    x1, y1, x2, y2 = box
    w, h = text_size(draw, text, ft)
    draw.text((x1 + (x2 - x1 - w) / 2, y1 + (y2 - y1 - h) / 2 - 2), text, font=ft, fill=fill)


def multiline_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], lines: list[str], ft=F22, fill=INK, gap=8) -> None:
    x1, y1, x2, y2 = box
    heights = [text_size(draw, line, ft)[1] for line in lines]
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = y1 + (y2 - y1 - total_h) / 2
    for line, h in zip(lines, heights):
        w, _ = text_size(draw, line, ft)
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=ft, fill=fill)
        y += h + gap


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=BLUE, width=3, radius=24) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def ellipse(draw: ImageDraw.ImageDraw, box, text: str, fill=LIGHT_BLUE, outline=BLUE, ft=F22) -> None:
    draw.ellipse(box, fill=fill, outline=outline, width=3)
    centered_text(draw, box, text, ft=ft)


def rect(draw: ImageDraw.ImageDraw, box, text: str | list[str], fill=LIGHT_BLUE, outline=BLUE, ft=F22) -> None:
    rounded(draw, box, fill=fill, outline=outline, width=3, radius=18)
    if isinstance(text, list):
        multiline_center(draw, box, text, ft=ft)
    else:
        centered_text(draw, box, text, ft=ft)


def arrow(draw: ImageDraw.ImageDraw, start, end, fill="#58799f", width=3) -> None:
    draw.line([start, end], fill=fill, width=width)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 12
    p1 = (x2 - size * math.cos(angle - math.pi / 6), y2 - size * math.sin(angle - math.pi / 6))
    p2 = (x2 - size * math.cos(angle + math.pi / 6), y2 - size * math.sin(angle + math.pi / 6))
    draw.polygon([end, p1, p2], fill=fill)


def actor(draw: ImageDraw.ImageDraw, x: int, y: int, label: str) -> None:
    draw.ellipse((x - 24, y, x + 24, y + 48), outline=INK, width=4)
    draw.line((x, y + 48, x, y + 125), fill=INK, width=4)
    draw.line((x - 62, y + 78, x + 62, y + 78), fill=INK, width=4)
    draw.line((x, y + 125, x - 48, y + 190), fill=INK, width=4)
    draw.line((x, y + 125, x + 48, y + 190), fill=INK, width=4)
    w, _ = text_size(draw, label, F22)
    draw.text((x - w / 2, y + 215), label, font=F22, fill=INK)


def title(draw: ImageDraw.ImageDraw, text: str, w: int) -> None:
    tw, _ = text_size(draw, text, F32)
    draw.text(((w - tw) / 2, 28), text, font=F32, fill=INK)


def new_canvas(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (w, h), BG)
    return image, ImageDraw.Draw(image)


def draw_use_case() -> Path:
    path = SOFTWARE_DIR / "figure_3_1_use_case.png"
    image, draw = new_canvas(1800, 1050)
    title(draw, "系统用例图", 1800)
    rounded(draw, (380, 105, 1420, 950), "white", BLUE, 4, 26)
    centered_text(draw, (380, 125, 1420, 170), "AI 绘本讲述系统", F28)

    use_cases = [
        ((430, 205, 690, 300), "注册/登录"),
        ((715, 205, 985, 300), "绘本管理"),
        ((1010, 205, 1280, 300), "图片上传"),
        ((430, 405, 690, 500), "故事生成"),
        ((715, 405, 985, 500), "实时识别"),
        ((1010, 405, 1280, 500), "语音朗读"),
        ((430, 605, 690, 700), "历史查看"),
        ((715, 605, 985, 700), "保存故事"),
        ((1010, 605, 1280, 700), "质量评价"),
        ((715, 795, 985, 890), "日志统计"),
    ]
    for box, label in use_cases:
        ellipse(draw, box, label)

    actor(draw, 150, 250, "用户")
    actor(draw, 150, 610, "教师/家长")
    actor(draw, 1570, 250, "多模态服务")
    actor(draw, 1570, 610, "TTS 服务")

    for box, _ in use_cases[:7]:
        arrow(draw, (260, 470), (box[0], (box[1] + box[3]) // 2), width=2)
    arrow(draw, (260, 830), (715, 650), width=2)
    arrow(draw, (1280, 455), (1485, 470), width=2)
    arrow(draw, (1280, 650), (1485, 470), width=2)
    arrow(draw, (1280, 455), (1485, 830), width=2)
    arrow(draw, (850, 500), (850, 795), width=2)

    image.save(path)
    return path


def draw_architecture() -> Path:
    path = THESIS_DIR / "figure_4_1_system_architecture.png"
    image, draw = new_canvas(1900, 620)
    title(draw, "系统总体架构", 1900)
    layers = [
        ((70, 140, 360, 480), "用户访问层", ["手机浏览器", "电脑浏览器", "摄像头取景"]),
        ((430, 140, 760, 480), "前端展示层", ["HTML/CSS/JS", "实时识别页面", "历史与绘本页面"]),
        ((830, 140, 1160, 480), "后端接口层", ["FastAPI 路由", "鉴权与限流", "SSE 流式输出"]),
        ((1230, 140, 1540, 480), "业务服务层", ["视觉分析", "故事生成", "TTS 合成", "质量约束"]),
        ((1610, 140, 1830, 480), "数据与外部服务", ["SQLite/MySQL", "Redis 缓存", "千问/豆包", "Edge TTS"]),
    ]
    for box, head, lines in layers:
        rect(draw, box, [head, *lines], fill="white", ft=F22)
    for x in [360, 760, 1160, 1540]:
        arrow(draw, (x + 15, 310), (x + 65, 310), width=4)
    image.save(path)
    return path


def draw_er() -> Path:
    path = SOFTWARE_DIR / "figure_4_4_database_er.png"
    image, draw = new_canvas(1900, 1120)
    title(draw, "数据库实体关系图", 1900)
    entities = {
        "users": ((120, 170, 520, 470), ["users", "id 主键", "username 唯一", "email 唯一", "password_hash", "created_at"]),
        "books": ((750, 170, 1150, 470), ["books", "id 主键", "user_id 外键", "title", "cover_image", "created_at"]),
        "book_images": ((1340, 170, 1740, 500), ["book_images", "id 主键", "book_id 外键", "image_path", "image_order", "created_at"]),
        "stories": ((750, 680, 1150, 1010), ["stories", "id 主键", "book_id 外键", "user_id 外键", "prompt", "image_analysis", "story_content"]),
    }
    for box, lines in entities.values():
        rect(draw, box, lines, fill="white", ft=F20)
    arrow(draw, (520, 320), (750, 320), width=4)
    centered_text(draw, (560, 270, 710, 310), "1 对多", F20)
    arrow(draw, (1150, 320), (1340, 320), width=4)
    centered_text(draw, (1180, 270, 1310, 310), "1 对多", F20)
    arrow(draw, (950, 470), (950, 680), width=4)
    centered_text(draw, (980, 540, 1130, 590), "绘本生成故事", F20)
    arrow(draw, (400, 470), (780, 760), width=4)
    centered_text(draw, (410, 600, 680, 650), "用户拥有故事", F20)
    image.save(path)
    return path


def draw_live_pipeline() -> Path:
    path = THESIS_DIR / "figure_4_2_live_scan_pipeline.png"
    image, draw = new_canvas(1900, 620)
    title(draw, "实时绘本识别与讲述流程", 1900)
    steps = [
        "摄像头取景",
        "画面稳定判断",
        "引导框裁剪",
        "图像增强",
        "多模态识别",
        "生成讲述文本",
        "语音朗读/保存",
    ]
    x = 70
    boxes = []
    for i, step in enumerate(steps):
        box = (x + i * 260, 245, x + i * 260 + 210, 365)
        boxes.append(box)
        rect(draw, box, step, fill=LIGHT_BLUE)
    for a, b in zip(boxes, boxes[1:]):
        arrow(draw, (a[2], 305), (b[0], 305), width=4)
    draw.text((120, 440), "说明：实时链路优先返回当前页讲述，完整生成用于保存和归档。", font=F22, fill=INK)
    image.save(path)
    return path


def draw_backend_modules() -> Path:
    path = THESIS_DIR / "figure_4_3_backend_modules.png"
    image, draw = new_canvas(1800, 820)
    title(draw, "后端功能模块划分", 1800)
    modules = [
        ((90, 150, 420, 310), "routers", ["用户接口", "绘本接口", "故事接口", "健康检查"]),
        ((530, 150, 860, 310), "schemas", ["请求参数", "响应模型", "字段校验"]),
        ((970, 150, 1300, 310), "services", ["视觉分析", "故事生成", "TTS", "质量评价"]),
        ((1390, 150, 1710, 310), "core", ["配置管理", "日志", "Redis", "请求上下文"]),
        ((310, 470, 640, 630), "db/models", ["User", "Book", "BookImage", "Story"]),
        ((760, 470, 1090, 630), "utils", ["鉴权", "限流", "安全工具"]),
        ((1210, 470, 1540, 630), "scripts/tests", ["系统测试", "指标导出", "批量 benchmark"]),
    ]
    for box, head, lines in modules:
        rect(draw, box, [head, *lines], fill="white", ft=F20)
    for start, end in [((420, 230), (530, 230)), ((860, 230), (970, 230)), ((1300, 230), (1390, 230)), ((1130, 310), (520, 470)), ((1130, 310), (925, 470)), ((1130, 310), (1375, 470))]:
        arrow(draw, start, end, width=3)
    image.save(path)
    return path


def draw_sequence() -> Path:
    path = SOFTWARE_DIR / "figure_5_3_live_scan_sequence.png"
    image, draw = new_canvas(2100, 1180)
    title(draw, "实时识别与朗读顺序图", 2100)
    lanes = [
        (170, "用户"),
        (470, "前端页面"),
        (800, "扫描接口"),
        (1130, "实时讲述服务"),
        (1460, "多模态模型"),
        (1810, "TTS 服务"),
    ]
    for x, label in lanes:
        centered_text(draw, (x - 110, 120, x + 110, 170), label, F22)
        draw.line((x, 180, x, 1050), fill="#9aa7b5", width=3)
    messages = [
        (170, 470, 250, "启动摄像头"),
        (470, 800, 330, "上传当前帧"),
        (800, 1130, 410, "裁剪与增强"),
        (1130, 1460, 490, "请求图像理解"),
        (1460, 1130, 570, "返回讲述文本"),
        (1130, 800, 650, "组织结果与耗时"),
        (800, 470, 730, "SSE/JSON 返回"),
        (470, 1810, 830, "请求语音朗读"),
        (1810, 470, 930, "返回音频地址"),
        (470, 170, 1010, "展示文本并播放"),
    ]
    for x1, x2, y, label in messages:
        arrow(draw, (x1, y), (x2, y), width=3)
        centered_text(draw, (min(x1, x2) + 20, y - 38, max(x1, x2) - 20, y - 6), label, F18)
    image.save(path)
    return path


def draw_frontend_state() -> Path:
    path = THESIS_DIR / "figure_5_1_frontend_state.png"
    image, draw = new_canvas(1600, 900)
    title(draw, "前端实时识别状态流转", 1600)
    states = [
        ((130, 180, 390, 300), "未启动"),
        ((500, 180, 760, 300), "摄像头预览"),
        ((870, 180, 1130, 300), "识别中"),
        ((1240, 180, 1500, 300), "显示当前页"),
        ((500, 520, 760, 640), "总故事视图"),
        ((870, 520, 1130, 640), "朗读中"),
        ((1240, 520, 1500, 640), "保存成功"),
    ]
    for box, label in states:
        rect(draw, box, label, fill=GREEN if label.endswith("成功") else LIGHT_BLUE)
    arrows = [(390, 240, 500, 240), (760, 240, 870, 240), (1130, 240, 1240, 240), (1370, 300, 630, 520), (760, 580, 870, 580), (1130, 580, 1240, 580)]
    for x1, y1, x2, y2 in arrows:
        arrow(draw, (x1, y1), (x2, y2), width=4)
    draw.text((130, 750), "重新识别只刷新当前页；重置故事书会清空当前扫描会话。", font=F22, fill=INK)
    image.save(path)
    return path


def draw_tts_flow() -> Path:
    path = THESIS_DIR / "figure_5_2_tts_flow.png"
    image, draw = new_canvas(1500, 620)
    title(draw, "语音朗读处理流程", 1500)
    steps = ["讲述文本", "清洗文本", "按句分段", "Edge TTS 合成", "合并音频", "返回 audio_url"]
    boxes = []
    for i, step in enumerate(steps):
        box = (70 + i * 235, 250, 250 + i * 235, 360)
        boxes.append(box)
        rect(draw, box, step, fill=ORANGE)
    for a, b in zip(boxes, boxes[1:]):
        arrow(draw, (a[2], 305), (b[0], 305), width=4)
    image.save(path)
    return path


def draw_bar_chart(path: Path, title_text: str, labels: list[str], values: list[float], unit: str = "ms") -> Path:
    image, draw = new_canvas(1500, 850)
    title(draw, title_text, 1500)
    left, bottom, top = 170, 700, 160
    max_v = max(values) * 1.15
    draw.line((left, top, left, bottom), fill=INK, width=3)
    draw.line((left, bottom, 1420, bottom), fill=INK, width=3)
    bar_w = 115
    gap = 70
    for i, (label, value) in enumerate(zip(labels, values)):
        x1 = left + 55 + i * (bar_w + gap)
        h = int((bottom - top) * value / max_v)
        y1 = bottom - h
        draw.rectangle((x1, y1, x1 + bar_w, bottom), fill=BLUE)
        centered_text(draw, (x1 - 30, bottom + 18, x1 + bar_w + 30, bottom + 70), label, F18)
        centered_text(draw, (x1 - 30, y1 - 42, x1 + bar_w + 30, y1 - 10), f"{value:.0f} {unit}", F18)
    image.save(path)
    return path


def draw_runtime_metrics() -> Path:
    return draw_bar_chart(
        THESIS_DIR / "figure_6_2_runtime_metrics.png",
        "运行日志主要耗时指标",
        ["direct_stream", "fast", "direct", "full", "Edge TTS"],
        [5833, 7340, 14822, 24144, 3052],
    )


def draw_latency() -> Path:
    return draw_bar_chart(
        THESIS_DIR / "figure_6_1_latency_comparison.png",
        "不同识别与讲述方案延迟对比",
        ["标准流式", "手机快速", "手机直接", "手机流式", "完整生成", "流式+TTS"],
        [5672, 17702, 19378, 8394, 45080, 9251],
    )


def draw_dataset() -> Path:
    path = THESIS_DIR / "figure_6_3_dataset_composition.png"
    image, draw = new_canvas(1300, 720)
    title(draw, "测试数据来源构成", 1300)
    data = [("标准绘本页", 55, BLUE), ("手机实拍页", 12, "#f39c3d"), ("人工复核样本", 22, "#4aa96c")]
    total = sum(v for _, v, _ in data)
    cx, cy, r = 430, 380, 210
    start = -90
    for label, value, color in data:
        end = start + 360 * value / total
        draw.pieslice((cx - r, cy - r, cx + r, cy + r), start, end, fill=color, outline="white", width=3)
        start = end
    for i, (label, value, color) in enumerate(data):
        y = 250 + i * 85
        draw.rectangle((780, y, 830, y + 50), fill=color)
        draw.text((850, y + 8), f"{label}: {value} 张", font=F24, fill=INK)
    image.save(path)
    return path


def main() -> None:
    targets = [
        SOFTWARE_DIR / "figure_3_1_use_case.png",
        SOFTWARE_DIR / "figure_4_4_database_er.png",
        SOFTWARE_DIR / "figure_5_3_live_scan_sequence.png",
        THESIS_DIR / "figure_4_1_system_architecture.png",
        THESIS_DIR / "figure_4_2_live_scan_pipeline.png",
        THESIS_DIR / "figure_4_3_backend_modules.png",
        THESIS_DIR / "figure_5_1_frontend_state.png",
        THESIS_DIR / "figure_5_2_tts_flow.png",
        THESIS_DIR / "figure_6_1_latency_comparison.png",
        THESIS_DIR / "figure_6_2_runtime_metrics.png",
        THESIS_DIR / "figure_6_3_dataset_composition.png",
    ]
    save_backup(targets)
    generated = [
        draw_use_case(),
        draw_architecture(),
        draw_er(),
        draw_live_pipeline(),
        draw_backend_modules(),
        draw_sequence(),
        draw_frontend_state(),
        draw_tts_flow(),
        draw_latency(),
        draw_runtime_metrics(),
        draw_dataset(),
    ]
    for path in generated:
        print(path.relative_to(ROOT))
    print(f"backup={BACKUP_ROOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

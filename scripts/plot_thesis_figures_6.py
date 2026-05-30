"""论文第 6 章实验图生成脚本。

用途：
- 使用 Pillow 绘制延迟对比、运行指标和测试数据组成等论文实验图。
- 避免依赖 matplotlib/numpy，减少本机科学计算库版本冲突。

关联数据：
- `reports/image_scan_benchmark`：benchmark 结果。
- `reports/runtime_metrics`：运行日志指标。

输出：
- `reports/thesis_figures_python/figure_6_1_latency_comparison.png`
- `reports/thesis_figures_python/figure_6_2_runtime_metrics.png`
- `reports/thesis_figures_python/figure_6_3_dataset_composition.png`
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "thesis_figures_python"

BLUE = "#2563EB"
LIGHT_BLUE = "#DBEAFE"
GRAY = "#64748B"
GREEN = "#22C55E"
ORANGE = "#F97316"
PURPLE = "#8B5CF6"
TEXT = "#0F172A"
MUTED = "#475569"
GRID = "#CBD5E1"
BG = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for item in candidates:
        path = Path(item)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FONT_TITLE = font(34, True)
FONT_LABEL = font(22)
FONT_LABEL_BOLD = font(22, True)
FONT_SMALL = font(18)
FONT_NOTE = font(17)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def center_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt, fill=TEXT) -> None:
    x, y = xy
    w, h = text_size(draw, text, fnt)
    draw.text((x - w / 2, y - h / 2), text, font=fnt, fill=fill)


def multiline_center(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    top_y: int,
    lines: list[str],
    fnt,
    fill=TEXT,
    line_gap: int = 6,
) -> None:
    y = top_y
    for line in lines:
        w, h = text_size(draw, line, fnt)
        draw.text((center_x - w / 2, y), line, font=fnt, fill=fill)
        y += h + line_gap


def draw_rotated_label(
    img: Image.Image,
    center: tuple[int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill=MUTED,
) -> None:
    w, h = text_size(ImageDraw.Draw(Image.new("RGB", (1, 1))), text, fnt)
    label = Image.new("RGBA", (w + 12, h + 12), (255, 255, 255, 0))
    label_draw = ImageDraw.Draw(label)
    label_draw.text((6, 6), text, font=fnt, fill=fill)
    rotated = label.rotate(90, expand=True)
    x = int(center[0] - rotated.width / 2)
    y = int(center[1] - rotated.height / 2)
    img.paste(rotated, (x, y), rotated)


def draw_axes(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    right: int,
    bottom: int,
    y_max: float,
    y_label: str,
    x_label: str,
    steps: int = 5,
) -> None:
    draw.line((left, top, left, bottom), fill=TEXT, width=2)
    draw.line((left, bottom, right, bottom), fill=TEXT, width=2)
    for i in range(steps + 1):
        value = y_max * i / steps
        y = bottom - (bottom - top) * i / steps
        draw.line((left, y, right, y), fill=GRID, width=1)
        label = f"{value:.0f}"
        w, h = text_size(draw, label, FONT_SMALL)
        draw.text((left - w - 12, y - h / 2), label, font=FONT_SMALL, fill=MUTED)
    draw_rotated_label(img, (left - 105, (top + bottom) // 2), y_label, FONT_SMALL)
    center_text(draw, ((left + right) // 2, bottom + 120), x_label, FONT_LABEL, fill=TEXT)


def save(img: Image.Image, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_DIR / name)


def plot_figure_6_1() -> None:
    labels = [
        "标准抽样\n直接讲述+流式",
        "手机实拍\n快速响应",
        "手机实拍\n直接讲述",
        "手机实拍\n直接讲述+流式",
        "手机实拍\n完整生成",
        "流式讲述\n+TTS",
    ]
    latency = [5.672, 17.702, 19.378, 8.394, 45.080, 9.251]
    success = ["55/55", "12/12", "12/12", "12/12", "3/3", "3/3"]
    colors = [BLUE, "#94A3B8", GRAY, GREEN, ORANGE, PURPLE]

    width, height = 1800, 1050
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    center_text(draw, (width // 2, 70), "不同识别与讲述方案平均端到端延迟对比", FONT_TITLE)

    left, top, right, bottom = 160, 150, 1700, 780
    y_max = 50
    draw_axes(img, draw, left, top, right, bottom, y_max, "纵轴：平均端到端延迟（秒）", "横轴：识别与讲述方案")
    bar_area = right - left
    slot = bar_area / len(labels)
    bar_w = 120

    for idx, (label, value, color, rate) in enumerate(zip(labels, latency, colors, success)):
        x = left + slot * idx + slot / 2
        bar_h = (bottom - top) * value / y_max
        x1, y1 = int(x - bar_w / 2), int(bottom - bar_h)
        x2, y2 = int(x + bar_w / 2), bottom
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, fill=color)
        multiline_center(draw, int(x), y1 - 76, [f"{value:.1f}s", f"成功 {rate}"], FONT_SMALL, fill=TEXT)
        multiline_center(draw, int(x), bottom + 24, label.split("\n"), FONT_SMALL, fill=TEXT)

    center_text(draw, (width // 2, 920), "", FONT_LABEL)
    note = "注：标准抽样覆盖 28 本绘本 55 张页面；手机实拍样本为 12 张连续页面。"
    center_text(draw, (width // 2, 995), note, FONT_NOTE, fill=MUTED)
    save(img, "figure_6_1_latency_comparison.png")


def plot_figure_6_2() -> None:
    modes = ["直接讲述", "直接讲述\n流式", "快速响应", "快速响应\n流式", "完整生成", "语音合成"]
    total = [14.822, 5.833, 7.340, 7.780, 24.144, 3.052]
    analysis = [14.691, 5.706, 7.196, 7.664, 4.583, 0.0]
    story = [0.0, 0.0, 0.0, 0.0, 19.444, 0.0]
    first_delta = [0.0, 5.345, 0.0, 7.537, 0.0, 0.0]

    series = [
        ("总耗时", total, BLUE),
        ("视觉分析", analysis, GRAY),
        ("讲述生成", story, GREEN),
        ("首块返回", first_delta, ORANGE),
    ]

    width, height = 1850, 1100
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    center_text(draw, (width // 2, 70), "运行日志导出的主要耗时指标", FONT_TITLE)

    left, top, right, bottom = 160, 180, 1740, 800
    y_max = 30
    draw_axes(img, draw, left, top, right, bottom, y_max, "纵轴：平均耗时（秒）", "横轴：日志模式")
    slot = (right - left) / len(modes)
    bar_w = 34
    gap = 8

    for i, mode in enumerate(modes):
        group_center = left + slot * i + slot / 2
        start_x = group_center - (len(series) * bar_w + (len(series) - 1) * gap) / 2
        for j, (_, values, color) in enumerate(series):
            value = values[i]
            x1 = int(start_x + j * (bar_w + gap))
            x2 = x1 + bar_w
            bar_h = (bottom - top) * value / y_max
            y1 = int(bottom - bar_h)
            draw.rounded_rectangle((x1, y1, x2, bottom), radius=5, fill=color)
            if value > 0:
                center_text(draw, (x1 + bar_w // 2, y1 - 16), f"{value:.1f}", FONT_SMALL, fill=TEXT)
        mode_lines = mode.split("\n")
        label_top = bottom + 34
        for line_index, line in enumerate(mode_lines):
            line_w, line_h = text_size(draw, line, FONT_SMALL)
            line_x = int(group_center - line_w / 2)
            line_y = label_top + line_index * (line_h + 6)
            draw.text((line_x, line_y), line, font=FONT_SMALL, fill=TEXT)

    legend_x, legend_y = 520, 120
    for idx, (name, _, color) in enumerate(series):
        x = legend_x + idx * 210
        draw.rounded_rectangle((x, legend_y, x + 30, legend_y + 18), radius=4, fill=color)
        draw.text((x + 42, legend_y - 3), name, font=FONT_SMALL, fill=TEXT)

    center_text(draw, (width // 2, 930), "", FONT_LABEL)
    note = "注：数据来自运行日志汇总；语音合成仅统计 Edge TTS 生成耗时。"
    center_text(draw, (width // 2, 1010), note, FONT_NOTE, fill=MUTED)
    save(img, "figure_6_2_runtime_metrics.png")


def plot_figure_6_3() -> None:
    labels = ["标准绘本页面", "手机实拍页面", "TTS端到端抽样"]
    counts = [55, 12, 3]
    details = ["28 本绘本抽样", "《小猫钓鱼》连续页", "流式讲述+朗读"]
    colors = [BLUE, GREEN, ORANGE]

    width, height = 1500, 850
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    center_text(draw, (width // 2, 70), "测试数据来源构成", FONT_TITLE)

    left, top, right, bottom = 260, 170, 1280, 600
    max_count = 60
    draw.line((left, top, left, bottom), fill=TEXT, width=2)
    draw.line((left, bottom, right, bottom), fill=TEXT, width=2)
    for i in range(0, 61, 10):
        x = left + (right - left) * i / max_count
        draw.line((x, top, x, bottom), fill=GRID, width=1)
        center_text(draw, (int(x), bottom + 26), str(i), FONT_SMALL, fill=MUTED)
    draw_rotated_label(img, (left - 150, (top + bottom) // 2), "纵轴：测试数据类型", FONT_SMALL)

    y_positions = [230, 365, 500]
    bar_h = 55
    for y, label, count, detail, color in zip(y_positions, labels, counts, details, colors):
        draw.text((60, y - 16), label, font=FONT_LABEL_BOLD, fill=TEXT)
        bar_w = int((right - left) * count / max_count)
        draw.rounded_rectangle((left, y - bar_h // 2, left + bar_w, y + bar_h // 2), radius=14, fill=color)
        draw.text((left + bar_w + 20, y - 16), f"{count}  {detail}", font=FONT_LABEL, fill=TEXT)

    center_text(draw, (width // 2, 685), "横轴：样本数量（张/次）", FONT_LABEL)
    note = "注：共统计 70 个实验样本或抽样任务，覆盖标准图片、真实拍摄和语音朗读场景。"
    center_text(draw, (width // 2, 785), note, FONT_NOTE, fill=MUTED)
    save(img, "figure_6_3_dataset_composition.png")


def main() -> None:
    plot_figure_6_1()
    plot_figure_6_2()
    plot_figure_6_3()
    print(f"saved figures to: {OUT_DIR}")


if __name__ == "__main__":
    main()

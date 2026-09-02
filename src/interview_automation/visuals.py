from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import PipelineConfig
from .utils import write_json


GOLD = (244, 190, 74)
NAVY = (8, 19, 42)
BLACK = (3, 4, 8)
WHITE = (250, 250, 250)
ANSWER_TEXT = (17, 24, 91)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ["arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int, start: int, minimum: int) -> tuple[ImageFont.ImageFont, list[str]]:
    for size in range(start, minimum - 1, -2):
        fnt = font(size, bold=True)
        lines = wrap_text(draw, text, fnt, max_width)
        line_h = int(size * 1.22)
        if len(lines) * line_h <= max_height:
            return fnt, lines
    fnt = font(minimum, bold=True)
    return fnt, wrap_text(draw, text, fnt, max_width)


def background(config: PipelineConfig) -> Image.Image:
    img = Image.new("RGB", (config.width, config.height), BLACK)
    d = ImageDraw.Draw(img)
    for x in range(0, config.width, 42):
        color = (24, 33, 54) if x % 84 else (74, 58, 25)
        d.line((x, 0, x, config.height), fill=color, width=1)
    for y in range(0, config.height, 54):
        d.line((0, y, config.width, y), fill=(10, 24, 47), width=1)
    for i in range(10):
        x0 = 280 + i * 140
        d.arc((x0, 160, x0 + 360, 840), 210, 330, fill=(29, 88, 110), width=3)
        d.ellipse((x0 + 210, 320, x0 + 270, 380), outline=GOLD, width=4)
    d.rectangle((0, 0, config.width, config.height), outline=(35, 24, 10), width=18)
    return img


def draw_watermark(d: ImageDraw.ImageDraw, config: PipelineConfig) -> None:
    f = font(24, bold=True)
    box = (config.width - 220, config.height - 120, config.width - 35, config.height - 45)
    d.rounded_rectangle(box, radius=6, fill=(235, 235, 235))
    d.text((box[0] + 22, box[1] + 25), config.watermark, fill=(20, 45, 58), font=f)


def opening_slide(script: dict, config: PipelineConfig, path: Path) -> None:
    img = background(config)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 115))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)
    title = script["title"]
    d.text((config.width // 2, 380), "INTERVIEW PREPARATION SERIES", fill=GOLD, font=font(46, True), anchor="mm")
    title_font, lines = fit_font(d, title, 1550, 240, 92, 54)
    y = 515 - (len(lines) - 1) * 55
    for line in lines:
        d.text((config.width // 2, y), line, fill=WHITE, font=title_font, anchor="mm")
        y += int(title_font.size * 1.18)
    draw_watermark(d, config)
    img.save(path)


def question_slide(question: dict, total: int, config: PipelineConfig, path: Path) -> None:
    img = background(config)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, config.width, 240), fill=BLACK)
    d.text((80, 50), f"QUESTION {question['number']} OF {total}", fill=GOLD, font=font(34, True))
    q_font, q_lines = fit_font(d, question["question"], config.width - 160, 140, 56, 36)
    y = 105
    for line in q_lines:
        d.text((80, y), line, fill=WHITE, font=q_font)
        y += int(q_font.size * 1.12)

    card = (48, 300, config.width - 48, config.height - 125)
    d.rounded_rectangle(card, radius=18, fill=WHITE)
    d.text((90, 345), "SAMPLE ANSWER", fill=(184, 135, 12), font=font(36, True))
    d.line((90, 392, 174, 392), fill=GOLD, width=4)

    answer = question["answer"]
    key = "KEY POINTS TO COVER: " + "; ".join(question["key_points"])
    body = answer + "\n\n" + key
    body_font, lines = fit_font(d, body, config.width - 210, 500, 39, 25)
    y = 425
    for raw in body.split("\n"):
        for line in wrap_text(d, raw, body_font, config.width - 210):
            d.text((90, y), line, fill=ANSWER_TEXT, font=body_font)
            y += int(body_font.size * 1.32)
        y += int(body_font.size * 0.7)

    progress_x = 80
    progress_y = config.height - 82
    width = config.width - 160
    d.line((progress_x, progress_y, progress_x + width, progress_y), fill=(120, 120, 120), width=7)
    d.line((progress_x, progress_y, progress_x + int(width * question["number"] / total), progress_y), fill=GOLD, width=7)
    draw_watermark(d, config)
    img.save(path)


def generate_visuals(script: dict, config: PipelineConfig, slides_dir: Path, manifest_path: Path) -> dict:
    slides_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    intro = slides_dir / "slide_000_intro.png"
    if not intro.exists():
        opening_slide(script, config, intro)
    paths.append(str(intro))
    total = len(script["questions"])
    for q in script["questions"]:
        path = slides_dir / f"slide_{q['number']:03d}.png"
        if not path.exists():
            question_slide(q, total, config, path)
        paths.append(str(path))
    outro = slides_dir / "slide_999_outro.png"
    if not outro.exists():
        opening_slide({"title": "Keep Practicing. Keep Building."}, config, outro)
    paths.append(str(outro))
    manifest = {"slides": paths, "width": config.width, "height": config.height}
    write_json(manifest_path, manifest)
    return manifest

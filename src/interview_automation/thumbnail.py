from __future__ import annotations

from pathlib import Path

from PIL import ImageDraw

from .config import PipelineConfig
from .visuals import GOLD, WHITE, background, draw_watermark, fit_font, font


def generate_thumbnail(script: dict, config: PipelineConfig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = background(config)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, config.width, config.height), fill=(0, 0, 0, 120))
    d.text((config.width // 2, 320), "INTERVIEW PREPARATION SERIES", fill=GOLD, font=font(48, True), anchor="mm")
    fnt, lines = fit_font(d, script["thumbnail_text"], 1500, 360, 110, 62)
    y = 500 - (len(lines) - 1) * 70
    for line in lines:
        d.text((config.width // 2, y), line, fill=WHITE, font=fnt, anchor="mm")
        y += int(fnt.size * 1.08)
    d.text((config.width // 2, 770), "with sample answers", fill=GOLD, font=font(58, True), anchor="mm")
    draw_watermark(d, config)
    img.save(path)
    return path

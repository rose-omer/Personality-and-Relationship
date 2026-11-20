"""Paylaşım önizlemesi (Open Graph) için 1200x630 PNG üretir."""

import io
import os
from functools import cache

from PIL import Image, ImageDraw, ImageFont

from models import AXIS_LABELS

WIDTH, HEIGHT = 1200, 630
BG = "#F5F6F8"
INK = "#17171C"
MUTED = "#5A5B66"
TRACK = "#DCDDE3"
ACCENT = "#1F6B52"
COUPLE = "#B8402A"

# Türkçe harfleri (ş, ğ, ı, İ) kapsayan yazı tipleri. İlk bulunan kullanılır.
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans{bold}.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans{bold}.ttf",
    "C:/Windows/Fonts/segoeui{winbold}.ttf",
    "/System/Library/Fonts/Supplemental/Arial{macbold}.ttf",
)


@cache
def _font(size: int, bold: bool = False) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    custom = os.getenv("OG_FONT_PATH")
    candidates = [custom] if custom else []
    candidates += [
        path.format(
            bold="-Bold" if bold else "",
            winbold="b" if bold else "",
            macbold=" Bold" if bold else "",
        )
        for path in FONT_CANDIDATES
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and " ".join(lines) != text:
        lines[-1] = lines[-1].rstrip(".,;") + "…"
    return lines


def _header(draw: ImageDraw.ImageDraw, label: str, color: str) -> None:
    draw.rectangle((0, 0, WIDTH, 12), fill=color)
    draw.text((72, 64), label, font=_font(30), fill=MUTED)


def render_single(result: dict) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    _header(draw, "Kişilik testi sonucu", ACCENT)

    y = 112
    for line in _wrap(draw, result["tip_adi"], _font(72, bold=True), WIDTH - 144, 2):
        draw.text((72, y), line, font=_font(72, bold=True), fill=INK)
        y += 84

    y = max(y + 28, 300)
    axes = result["eksenler"]
    for key, (title, left, right) in AXIS_LABELS.items():
        value = max(0, min(100, int(axes[key])))
        draw.text((72, y), title, font=_font(28, bold=True), fill=INK)
        track_x0, track_x1 = 420, WIDTH - 72
        track_y = y + 18
        draw.rounded_rectangle((track_x0, track_y - 3, track_x1, track_y + 3), 3, fill=TRACK)
        cx = track_x0 + (track_x1 - track_x0) * value / 100
        draw.ellipse((cx - 13, track_y - 13, cx + 13, track_y + 13), fill=ACCENT)
        draw.text((track_x0, y + 36), left, font=_font(20), fill=MUTED)
        draw.text((track_x1, y + 36), right, font=_font(20), fill=MUTED, anchor="ra")
        y += 76

    return _to_png(image)


def render_couple(result: dict) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    _header(draw, "İlişki uyumu sonucu", COUPLE)

    score = max(0, min(100, int(result["uyum_skoru"])))
    box = (72, 150, 432, 510)
    draw.arc(box, 0, 360, fill=TRACK, width=34)
    if score:
        draw.arc(box, -90, -90 + 360 * score / 100, fill=COUPLE, width=34)
    draw.text((252, 318), f"%{score}", font=_font(96, bold=True), fill=INK, anchor="mm")
    draw.text((252, 400), "uyum", font=_font(30), fill=MUTED, anchor="mm")

    y = 170
    for line in _wrap(draw, result["ozet"], _font(40, bold=True), WIDTH - 560, 5):
        draw.text((500, y), line, font=_font(40, bold=True), fill=INK)
        y += 54
    return _to_png(image)


def _to_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()

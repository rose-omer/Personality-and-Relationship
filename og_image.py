"""Paylaşım önizlemesi (Open Graph) için 1200x630 PNG üretir.

Arayüzle aynı risograf dili: açık kâğıt, lacivert yazı, pembe ve mavi mürekkep.
İki mürekkep "multiply" ile basılır; kesişim kendiliğinden koyulaşır.
Görsel 2 kat büyük çizilip küçültülür (kenar yumuşatma).
"""

import io
import math
from functools import cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from models import AXIS_LABELS

WIDTH, HEIGHT = 1200, 630
K = 2  # Çizim ölçeği.

PAPER = "#ECEDE9"
PAPER_DEEP = "#E0E1DC"
INK = "#1E2766"
INK_2 = "#2B3A8C"
PINK = "#FF48B0"
BLUE = "#0078BF"
WHITE = "#FFFFFF"

FONT_DIR = Path(__file__).resolve().parent / "fonts"
# Değişken yazı tipleri (OFL). Türkçe harfleri (ş, ğ, ı, İ) kapsar.
FONTS = {"display": FONT_DIR / "Unbounded.ttf", "body": FONT_DIR / "Rubik.ttf"}


@cache
def _font(family: str, size: int, weight: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    path = FONTS[family]
    if not path.exists():
        return ImageFont.load_default(size * K)
    font = ImageFont.truetype(str(path), size * K)
    font.set_variation_by_axes([weight])
    return font


def _s(*values: float) -> tuple[float, ...]:
    return tuple(v * K for v in values)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width * K:
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


def _halftone(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str, angle: float
) -> None:
    """Daire biçiminde yarım ton nokta deseni; ızgara baskıdaki gibi `angle` derece döner."""
    step, dot = 10, 2.4
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    count = r // step + 1
    for i in range(-count, count + 1):
        for j in range(-count, count + 1):
            u, v = i * step, j * step
            if u * u + v * v > r * r:
                continue
            x, y = cx + u * cos - v * sin, cy + u * sin + v * cos
            draw.ellipse(_s(x - dot, y - dot, x + dot, y + dot), fill=color)


def _circle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, **kwargs) -> None:
    draw.ellipse(_s(cx - r, cy - r, cx + r, cy + r), **kwargs)


def _print(pink_layer: Image.Image, blue_layer: Image.Image) -> Image.Image:
    return ImageChops.multiply(pink_layer, blue_layer)


def _layers() -> tuple[Image.Image, Image.Image]:
    size = (WIDTH * K, HEIGHT * K)
    return Image.new("RGB", size, PAPER), Image.new("RGB", size, WHITE)


def render_single(result: dict) -> bytes:
    pink_layer, blue_layer = _layers()
    pink = ImageDraw.Draw(pink_layer)
    blue = ImageDraw.Draw(blue_layer)

    # Sağ üstte tek mürekkep: pembe disk, kayık mavi çizgi, yarım ton noktalar.
    _circle(pink, 1040, 120, 150, fill=PINK)
    _circle(blue, 1048, 112, 150, outline=BLUE, width=2 * K)
    _halftone(blue, 880, 250, 60, BLUE, -18)

    image = _print(pink_layer, blue_layer)
    draw = ImageDraw.Draw(image)
    draw.text(_s(72, 56), "Kişilik testi sonucu", font=_font("body", 28, 500), fill=INK_2)

    title_font = _font("display", 60, 900)
    y = 104
    for line in _wrap(draw, result["tip_adi"], title_font, 740, 2):
        draw.text(_s(72, y), line, font=title_font, fill=INK)
        y += 70

    y = 300
    axes = result["eksenler"]
    left, right = 72, WIDTH - 72
    for key, (title, _low, _high) in AXIS_LABELS.items():
        value = max(0, min(100, int(axes[key])))
        draw.text(_s(left, y), title, font=_font("body", 24, 700), fill=INK)
        draw.text(_s(right, y), str(value), font=_font("display", 24, 700), fill=INK, anchor="ra")
        top = y + 34
        draw.rectangle(_s(left, top, right, top + 30), fill=PAPER_DEEP)
        end = left + (right - left) * value / 100
        if value:
            draw.rectangle(_s(left, top + 5, end, top + 25), fill=PINK)
        mid = (left + right) / 2
        for dash in range(top, top + 30, 8):
            draw.line(_s(mid, dash, mid, dash + 4), fill=INK, width=2 * K)
        y += 76

    return _to_png(image)


def render_couple(result: dict) -> bytes:
    score = max(0, min(100, int(result["uyum_skoru"])))
    r, cy, center = 180, 330, 340
    # Uyum arttıkça daireler yaklaşır (arayüzdeki çizimle aynı kural).
    distance = r * (1.4 - 0.7 * score / 100)
    cx1, cx2 = center - distance / 2, center + distance / 2

    pink_layer, blue_layer = _layers()
    pink = ImageDraw.Draw(pink_layer)
    blue = ImageDraw.Draw(blue_layer)
    # Arayüzdeki gibi iki yarım ton: sol üstte mavi (-18°), sağ altta pembe (22°).
    _halftone(blue, 92, 92, 60, BLUE, -18)
    _halftone(pink, 1124, 566, 62, PINK, 22)
    _circle(pink, cx1, cy, r, fill=PINK)
    _circle(blue, cx2, cy + 6, r, fill=BLUE)
    _circle(blue, cx1 + 6, cy - 6, r, outline=BLUE, width=2 * K)

    image = _print(pink_layer, blue_layer)
    draw = ImageDraw.Draw(image)

    overlap = 2 * r - distance
    text = f"%{score}"
    size = int(min(64, (overlap - 20) / (len(text) * 0.86)))
    draw.text(_s(center, cy - 4), text, font=_font("display", size, 900), fill=WHITE, anchor="ms")
    draw.text(_s(center, cy + 32), "uyum", font=_font("body", 24, 700), fill=WHITE, anchor="ms")

    x = 700
    title_font = _font("display", 40, 700)
    y = 56
    for line in _wrap(draw, "İlişki uyumu sonucu", title_font, WIDTH - x - 64, 2):
        draw.text(_s(x, y), line, font=title_font, fill=INK)
        y += 52
    body_font = _font("body", 32, 500)
    y += 24
    for line in _wrap(draw, result["ozet"], body_font, WIDTH - x - 64, 7):
        draw.text(_s(x, y), line, font=body_font, fill=INK)
        y += 44
    return _to_png(image)


def _to_png(image: Image.Image) -> bytes:
    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()

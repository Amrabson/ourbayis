"""Generate static/og.png (1200x630) — parchment background, navy OurBayis
wordmark, gold skyline motif, EN + HE tagline. Pure Pillow, no network calls.

Run: python tools/make_og.py
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent / "static"

PAPER = (250, 246, 236)
PAPER_DEEP = (241, 233, 214)
NAVY = (34, 51, 84)
GOLD = (165, 118, 42)
GOLD_BRIGHT = (201, 162, 74)

W, H = 1200, 630


def find_font(names, size, hebrew=False):
    """Try a list of common font file names (Bellefair/Assistant if present
    locally, else a system fallback). Hebrew text needs a font with Hebrew
    glyphs — Windows' Arial/Tahoma cover it; Georgia/Times often don't."""
    candidates = []
    candidates += [str(STATIC / "fonts" / n) for n in names]
    if hebrew:
        candidates += [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\tahoma.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
        ]
    else:
        candidates += [
            r"C:\Windows\Fonts\georgia.ttf",
            r"C:\Windows\Fonts\georgiab.ttf",
            r"C:\Windows\Fonts\times.ttf",
            r"C:\Windows\Fonts\timesbd.ttf",
        ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def skyline(draw, base_y, color):
    """Simple gold skyline motif: wall crenellations + a dome + a tower."""
    x = 70
    # crenellated wall
    for i in range(6):
        draw.rectangle([x, base_y - 30, x + 16, base_y], outline=color, width=3)
        x += 24
    # tower
    draw.rectangle([x + 10, base_y - 80, x + 46, base_y], outline=color, width=3)
    draw.polygon([(x + 6, base_y - 80), (x + 28, base_y - 100), (x + 50, base_y - 80)], outline=color)
    x += 70
    # dome building
    draw.arc([x, base_y - 90, x + 70, base_y - 20], 180, 360, fill=color, width=3)
    draw.line([x, base_y - 55, x, base_y], fill=color, width=3)
    draw.line([x + 70, base_y - 55, x + 70, base_y], fill=color, width=3)


def main():
    img = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)

    # soft radial-ish vignette using overlapping rectangles (no radial gradient in core PIL)
    draw.rectangle([0, 0, W, H], fill=PAPER)
    draw.ellipse([-200, -300, W + 200, 260], fill=PAPER_DEEP)

    # hairline border
    draw.rectangle([24, 24, W - 24, H - 24], outline=GOLD_BRIGHT, width=2)

    # skyline motif, bottom-left
    skyline(draw, H - 70, GOLD)

    # wordmark
    brand_font = find_font(["Bellefair-Regular.ttf", "Bellefair.ttf"], 108)
    tagline_font = find_font(["Assistant-Regular.ttf"], 34)
    he_font = find_font(["Assistant-Regular.ttf"], 32, hebrew=True)

    brand_text = "OurBayis"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    bw = bbox[2] - bbox[0]
    draw.text(((W - bw) / 2, 160), brand_text, font=brand_font, fill=NAVY)

    tagline_en = "Gift registries for a home in Israel"
    bbox = draw.textbbox((0, 0), tagline_en, font=tagline_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, 300), tagline_en, font=tagline_font, fill=GOLD)

    # PIL has no BiDi shaping — Hebrew doesn't change glyph shape by position,
    # only reading order, so reversing the string gives correct visual order.
    tagline_he = "רשימות מתנות לבית בישראל"[::-1]
    bbox = draw.textbbox((0, 0), tagline_he, font=he_font)
    hw = bbox[2] - bbox[0]
    draw.text(((W - hw) / 2, 350), tagline_he, font=he_font, fill=GOLD)

    out = STATIC / "og.png"
    img.save(out, "PNG")
    print("wrote", out)


if __name__ == "__main__":
    main()

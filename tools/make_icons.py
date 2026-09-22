"""Generate the site icons from the same house-and-heart mark as the inline
favicon: static/favicon.svg, static/favicon.ico (16/32/48) and
static/apple-touch-icon.png (180x180, navy tile with the gold house — the
header's brand mark). Dev-time only (Pillow, like make_og.py); the app just
serves the files.

    python tools/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent.parent / "static"
NAVY, NAVY_DEEP, GOLD, PAPER = "#223354", "#18233b", "#c9a24a", "#faf6ec"

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<path d="M16 3 3 14h3v14h20V14h3L16 3z" fill="#223354"/>
<path d="M16 25c-2.8-2.2-5-4-5-6.2 0-1.6 1.2-2.8 2.7-2.8 1 0 1.8.5 2.3 1.3.5-.8 1.3-1.3 2.3-1.3 1.5 0 2.7 1.2 2.7 2.8 0 2.2-2.2 4-5 6.2z" fill="#c9a24a"/>
</svg>
"""


def draw_mark(size, house, heart, bg=None, inset=0.0):
    """Draw the 32-unit mark at `size` px, 4x supersampled for clean edges."""
    ss = size * 4
    img = Image.new("RGBA", (ss, ss), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    scale = ss * (1 - 2 * inset) / 32
    off = ss * inset

    def p(x, y):
        return (off + x * scale, off + y * scale)

    d.polygon([p(16, 3), p(3, 14), p(6, 14), p(6, 28), p(26, 28), p(26, 14), p(29, 14)], fill=house)
    r = 2.75 * scale
    for cx in (13.7, 18.3):
        x, y = p(cx, 18.8)
        d.ellipse([x - r, y - r, x + r, y + r], fill=heart)
    d.polygon([p(11.05, 19.4), p(20.95, 19.4), p(16, 25)], fill=heart)
    return img.resize((size, size), Image.LANCZOS)


def main():
    (STATIC / "favicon.svg").write_text(SVG, encoding="utf-8")
    ico = draw_mark(48, NAVY, GOLD)
    ico.save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # iOS rounds the corners itself and ignores transparency, so a full navy tile
    touch = draw_mark(180, GOLD, NAVY_DEEP, bg=NAVY, inset=0.16)
    touch.convert("RGB").save(STATIC / "apple-touch-icon.png", optimize=True)
    print("wrote favicon.svg, favicon.ico, apple-touch-icon.png")


if __name__ == "__main__":
    main()

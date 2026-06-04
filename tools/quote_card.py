#!/usr/bin/env python3
"""Render a 1080x1350 typographic quote card for Holy Chip promo posts.

Usage:
  python3 quote_card.py <output.jpg> "Line one|Line two|Line three" [--theme light|dark] [--font mono|heavy]

The body uses '|' as a line break (so we can pass it on the command line).
Footer "holy-chip.com" is added automatically in muted colour.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350

THEMES = {
    "light": {"bg": (248, 244, 232), "fg": (42, 42, 40),  "muted": (136, 136, 128), "accent": (176, 138, 32)},
    "dark":  {"bg": (10, 10, 10),    "fg": (255, 255, 255),"muted": (130, 130, 125),"accent": (232, 200, 74)},
}

FONT_MONO    = "/System/Library/Fonts/SFNSMono.ttf"
FONT_SFNS    = "/System/Library/Fonts/SFNS.ttf"          # variable; wght 900 = Black
FONT_PSTART  = os.path.expanduser("~/holy-chip/tools/fonts/PressStart2P-Regular.ttf")  # website headline
FONT_STMONO  = os.path.expanduser("~/holy-chip/tools/fonts/ShareTechMono-Regular.ttf") # website body

def get_font(size, kind="mono"):
    """kind = 'mono' | 'heavy' | 'website' (Press Start 2P) | 'website-body' (Share Tech Mono)"""
    if kind == "heavy":
        f = ImageFont.truetype(FONT_SFNS, size)
        try:
            f.set_variation_by_axes([900])
        except Exception:
            pass
        return f
    if kind == "website":
        return ImageFont.truetype(FONT_PSTART, size)
    if kind == "website-body":
        return ImageFont.truetype(FONT_STMONO, size)
    return ImageFont.truetype(FONT_MONO, size)

def main():
    if len(sys.argv) < 3:
        print("Usage: quote_card.py <output.jpg> \"line1|line2|line3\" [--theme light|dark] [--font mono|heavy]")
        sys.exit(1)
    out = sys.argv[1]
    body = sys.argv[2].split("|")

    theme = "light"
    font_kind = "mono"
    for i, a in enumerate(sys.argv):
        if a == "--theme" and i + 1 < len(sys.argv):
            theme = sys.argv[i + 1]
        if a == "--font" and i + 1 < len(sys.argv):
            font_kind = sys.argv[i + 1]

    t = THEMES[theme]
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)

    # Header dot — small Holy Chip "·"
    d.text((W // 2, 180), "·", fill=t["accent"], font=get_font(80, "mono"), anchor="mm")

    # Body — auto-size so longest line fits with comfortable margins
    PADDING = 60 if font_kind == "website" else 90
    max_line = max(body, key=len)
    if font_kind == "heavy":
        size = 110
    elif font_kind == "website":
        size = 120  # Press Start 2P needs a big start to fill the frame
    else:
        size = 64
    while size > 24:
        f = get_font(size, font_kind)
        bbox = d.textbbox((0, 0), max_line, font=f)
        if bbox[2] - bbox[0] <= W - 2 * PADDING:
            break
        size -= 2
    if font_kind == "heavy":
        line_h = int(size * 1.25)
    elif font_kind == "website":
        line_h = int(size * 1.7)   # Press Start 2P needs breathing room
    else:
        line_h = int(size * 1.5)

    total_h = line_h * len(body)
    y0 = (H - total_h) // 2 - 40
    f_body = get_font(size, font_kind)
    for i, line in enumerate(body):
        d.text((W // 2, y0 + i * line_h), line, fill=t["fg"], font=f_body, anchor="mm")

    # Footer — "holy-chip.com" in website body font, bigger
    footer_font_kind = "website-body" if font_kind == "website" else "mono"
    footer_color = t["accent"] if font_kind == "website" else t["muted"]
    d.text((W // 2, H - 110), "holy-chip.com", fill=footer_color, font=get_font(56, footer_font_kind), anchor="mm")

    img.save(out, "JPEG", quality=92, optimize=True)
    print(f"OK:{out}  {W}x{H}  theme={theme}  font={font_kind}")

if __name__ == "__main__":
    main()

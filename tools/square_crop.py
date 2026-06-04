#!/usr/bin/env python3
"""Generate a 1080x1350 (4:5) JPEG variant of a Holy Chip story image for Instagram.

The story PNG is portrait (896x1200, ratio 0.747), below IG's 4:5 floor (0.8).
We scale-to-fit inside a 1080x1350 white canvas, centered, and save as JPEG
(IG container API requires JPEG, not PNG). 4:5 is IG's tallest allowed ratio
so we waste the least space; the comic fills ~93% of the frame with small
white margins on the sides.

Usage:
  python3 square_crop.py <source.png> [<dest.jpg>]

If dest omitted, writes to <source-stem>.square.jpg next to source.
"""
import os
import sys
from PIL import Image

CANVAS_W = 1080
CANVAS_H = 1350
BG = (255, 255, 255)  # white

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 square_crop.py <source.png> [<dest.jpg>]")
        sys.exit(0)
    src = sys.argv[1]
    if not os.path.exists(src):
        print(f"ERROR: not found: {src}", file=sys.stderr)
        sys.exit(1)
    if len(sys.argv) >= 3:
        dst = sys.argv[2]
    else:
        stem, _ = os.path.splitext(src)
        dst = f"{stem}.square.jpg"

    im = Image.open(src).convert("RGB")
    w, h = im.size
    scale = min(CANVAS_W / w, CANVAS_H / h)
    new_w, new_h = int(w * scale), int(h * scale)
    im = im.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    x = (CANVAS_W - new_w) // 2
    y = (CANVAS_H - new_h) // 2
    canvas.paste(im, (x, y))
    canvas.save(dst, "JPEG", quality=92, optimize=True)
    print(f"OK:{dst}")
    print(f"SIZE:{CANVAS_W}x{CANVAS_H}")

if __name__ == "__main__":
    main()

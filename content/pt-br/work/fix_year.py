#!/usr/bin/env python3
"""Swap the banner year on an approved image without re-rendering (Press Start 2P is monospaced).
    fix_year.py IMAGE OLD NEW        e.g. fix_year.py HC049.en.png 2047 2041
Finds the white text at the right end of the black banner, renders NEW in the same font at
exactly that box size and color, and paints it over OLD."""
import sys
from PIL import Image, ImageDraw, ImageFont
FONT = '/Users/rmello/holy-chip/SGen/public/fonts/PressStart2P-Regular.ttf'
path, old, new = sys.argv[1:4]
im = Image.open(path).convert('RGB'); W, H = im.size; g = im.convert('L')
bh = 0
while bh < H // 4 and g.getpixel((W // 2, bh + 2)) < 60 or bh < 10: bh += 1     # banner height: dark rows from the top
bh = next(y for y in range(5, H // 4) if all(g.getpixel((x, y)) > 150 for x in range(W // 3, W // 3 + 40)))  # first light row = end of banner
x0 = int(W * 0.78); strip = g.crop((x0, 0, W - 2, bh - 2)).point(lambda v: 255 if v > 128 else 0)
bx = strip.getbbox(); L, T, R, B = bx[0] + x0, bx[1], bx[2] + x0, bx[3]
ink = max((im.getpixel((x, y)) for x in range(L, R) for y in range(T, B)), key=sum)
bgc = im.getpixel((L - 6, (T + B) // 2))
# render NEW big, crop to ink, scale to the old box
f = ImageFont.truetype(FONT, 160); t = Image.new('L', (1400, 220), 0)
ImageDraw.Draw(t).text((10, 10), new, font=f, fill=255); t = t.crop(t.getbbox()).resize((R - L, B - T), Image.LANCZOS)
d = ImageDraw.Draw(im); d.rectangle((L - 2, T - 2, R + 2, B + 2), fill=bgc)
im.paste(Image.new('RGB', t.size, ink), (L, T), t)
im.save(path); print(path, 'year box', (L, T, R, B), 'banner', bh)

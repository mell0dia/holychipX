#!/usr/bin/env python3
"""Rebuild panel 3 of a rendered comic from an APPROVED one: same black HOLY CHIP !! bubble,
same bot cut-out, so EN and PT (and re-renders) share one approved panel 3. Borders are found on
the LEFT half only, so a model bot sitting over the divider doesn't confuse it.
    fix_p3.py COMIC.png APPROVED.png BOT_CUTOUT.png
"""
import sys
from PIL import Image, ImageDraw

def bands(im):
    g = im.convert('L'); W, H = im.size; xs = range(10, 600, 3); rows = []
    for y in range(H):
        if sum(1 for x in xs if g.getpixel((x, y)) < 60) > len(xs) * 0.9: rows.append(y)
    out = []
    for y in rows:
        if out and y == out[-1][1] + 1: out[-1][1] = y
        else: out.append([y, y])
    return [b for b in out if b[1] - b[0] >= 3]          # real borders, not text rows

def p3_box(im):
    b = bands(im); H = im.size[1]
    b = [x for x in b if x[0] > H // 2]
    return b[-2], b[-1]                                  # divider above panel 3, footer strip

def main(comic, approved, cutout):
    im = Image.open(comic).convert('RGB'); ap = Image.open(approved).convert('RGB'); W, H = im.size
    (d0, d1), (f0, _) = p3_box(im); (a0, a1), (af0, _) = p3_box(ap)
    bg = im.getpixel((W // 4, d0 - 6)); d = ImageDraw.Draw(im); g = im.convert('L')
    # panel 2: wipe whatever pokes in on the right below the bots' pedestals
    ped = d0 - 1
    while ped > d0 - 120 and not any(g.getpixel((x, ped)) < 60 for x in range(12, W // 2, 2)): ped -= 1
    if ped + 3 <= d0 - 1:
        d.rectangle((W // 2, ped + 3, W - 9, d0 - 1), fill=bg)
    # panel 3: clear, then the approved bubble (left part) centred, the bot bottom-aligned on the right
    d.rectangle((0, d0, W, d1), fill=(0, 0, 0))
    d.rectangle((9, d1 + 1, W - 9, f0 - 1), fill=bg)
    ah = af0 - a1 - 1; bub = ap.crop((9, a1 + 1, 600, af0))
    im.paste(bub, (9, d1 + 1 + max(0, ((f0 - d1 - 1) - ah) // 2)))
    bot = Image.open(cutout).convert('RGBA'); x = W - 9 - bot.width - 4
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); lay.paste(bot, (x, f0 - bot.height), bot)
    base = im.convert('RGBA'); base.alpha_composite(lay); base.convert('RGB').save(comic)
    print(comic, 'panel 3 rows', d1 + 1, f0 - 1)

main(*sys.argv[1:4])

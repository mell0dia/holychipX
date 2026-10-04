"""Replace the reaction bot in a PT short's right frame with a hand-made one
(the original art, only its own features redrawn)."""
import sys
from PIL import Image, ImageDraw

def paste_short_bot(png, art_png, div=962, bot=712):
    im = Image.open(png).convert("RGB"); g = im.convert("L"); W, H = im.size
    cols = range(1080, 1260)
    by = max(y for y in range(120, 420) if any(g.getpixel((x, y)) < 90 for x in cols)
             and all(any(g.getpixel((x, yy)) < 90 for x in cols) for yy in range(y - 3, y)))
    y = by
    while y < 500 and any(g.getpixel((x, y)) < 90 for x in cols): y += 1
    tail = y
    bg = im.getpixel((div + 20, bot - 10))
    ImageDraw.Draw(im).rectangle((div + 4, tail + 4, W - 14, bot), fill=bg)
    a = Image.open(art_png); a = a.crop(a.getchannel("A").getbbox())
    s = (bot - (tail + 14)) / a.height
    a = a.resize((round(a.width * s), round(a.height * s)), Image.LANCZOS)
    im.paste(a, ((div + W - 14) // 2 - a.width // 2, bot - a.height), a)
    im.save(png)

if __name__ == "__main__":
    paste_short_bot(sys.argv[1], sys.argv[2])

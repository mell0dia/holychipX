"""Replace the reaction bot in a PT short's right frame with a hand-made one
(the original art, only its own features redrawn)."""
import sys
from PIL import Image, ImageDraw

def paste_short_bot(png, art_png, div=962, bot=712):
    im = Image.open(png).convert("RGB"); g = im.convert("L"); W, H = im.size
    cols = range(1080, 1260)
    # The punchline bubble is one connected dark outline (with its tail). Flood
    # it from its top edge; its lowest pixel is the tail tip. If the flood leaks
    # into the bot (tail touching it), fall back to a safe line.
    from collections import deque
    top_y = next(y for y in range(100, 300) if g.getpixel((1150, y)) < 90)
    seen = {(1150, top_y)}; q = deque(seen); low = top_y
    while q:
        x, y = q.popleft(); low = max(low, y)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if div < n[0] < W - 10 and 90 < n[1] < 520 and n not in seen and g.getpixel(n) < 128:
                    seen.add(n); q.append(n)
    tail = low if low < 430 else 360
    bg = im.getpixel((div + 20, bot - 10))
    ImageDraw.Draw(im).rectangle((div + 4, tail + 4, W - 14, bot), fill=bg)
    a = Image.open(art_png); a = a.crop(a.getchannel("A").getbbox())
    s = (bot - (tail + 14)) / a.height
    a = a.resize((round(a.width * s), round(a.height * s)), Image.LANCZOS)
    im.paste(a, ((div + W - 14) // 2 - a.width // 2, bot - a.height), a)
    im.save(png)

if __name__ == "__main__":
    paste_short_bot(sys.argv[1], sys.argv[2])

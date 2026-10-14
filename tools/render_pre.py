#!/usr/bin/env python3
"""Render a story's pre image (HC###.pre.png) with the chip's OWN art.

    render_pre.py HC048 "LONG DISTANCE AI" [--bot p2Right|p1Left|...] [--speaker "Right Bot"]

Runs SGen's generatePreComicImage on the dev server (:3000) for the banner,
bubble and layout, then replaces Gemini's redrawn chip with the story's real
bot art (stories/HC###.json slot, default p2Right / the speaker's side), sized
to the free space beside the bubble. Gemini keeps inventing faces (angry brows,
cheeks) - the art is the one thing it must not touch. Writes the PNG and
records preComic / preBot / preImage in the JSON.
"""
import base64, html, io, json, re, subprocess, sys
from collections import deque
from pathlib import Path
from PIL import Image, ImageDraw

HC = Path.home() / "holy-chip"
STORIES = HC / "website" / "holy-chip-site" / "stories"
SGEN = HC / "SGen"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def gemini_pre(script, bot):
    page = SGEN / "zz-render-pre.html"
    page.write_text(f"""<!doctype html><html><head><link rel="stylesheet" href="/src/index.css"></head><body><pre id="out"></pre>
<script type="module">
import {{ generatePreComicImage }} from '/src/services/gemini.ts';
const toData = src => new Promise((r,j) => {{ const i = new Image(); i.onload = () => {{ const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight; c.getContext('2d').drawImage(i,0,0); r(c.toDataURL()); }}; i.onerror=j; i.src = src; }});
try {{
  const tpl = await toData('/images/template.png');
  let bub; try {{ bub = await toData('/images/bubbles.png'); }} catch (e) {{ bub = undefined; }}
  const r = await generatePreComicImage({json.dumps(script, ensure_ascii=False)}, tpl, bub, {json.dumps(bot)});
  document.getElementById('out').textContent = JSON.stringify([r.image]);
}} catch (e) {{ document.getElementById('out').textContent = JSON.stringify(['ERR ' + (e && e.stack || e)]); }}
</script></body></html>""")
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=240000", "--timeout=240000",
                              "--dump-dom", "http://localhost:3000/zz-render-pre.html"], capture_output=True, text=True, timeout=300).stdout
    finally:
        page.unlink(missing_ok=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    v = json.loads(html.unescape(m.group(1))) if m and m.group(1) else ["EMPTY (is SGen running on :3000?)"]
    if not v[0].startswith("data:"):
        sys.exit(v[0][:600])
    return Image.open(io.BytesIO(base64.b64decode(v[0].split(",", 1)[1]))).convert("RGB")


def art_with_alpha(data_url):
    """The bot art with only its OUTSIDE white transparent (the face stays white)."""
    art = Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGB")
    m = Image.new("L", art.size, 255); apx = art.convert("L").load(); mpx = m.load()
    q = deque([(0, 0), (art.width - 1, 0), (0, art.height - 1), (art.width - 1, art.height - 1)]); seen = set(q)
    while q:
        x, y = q.popleft(); mpx[x, y] = 0
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < art.width and 0 <= ny < art.height and (nx, ny) not in seen and apx[nx, ny] > 200:
                seen.add((nx, ny)); q.append((nx, ny))
    art.putalpha(m)
    return art.crop(m.getbbox())


def transplant(im, art, bot_on_right):
    W, H = im.size; g = im.convert("L"); px = g.load()
    # The panel frame: from each edge, skip the light margin (if any), then the
    # frame's dark run; the interior starts after it. Sampled on rows/columns
    # the bot never reaches (just under the banner, far left), so a bot drawn
    # over the frame cannot fool it.
    def inward(seq):
        it = iter(seq); x = next(it)
        while px[x] > 150: x = next(it)        # light margin outside the frame
        while px[x] < 150: x = next(it)        # the frame line
        return x
    top = next(y for y in range(80, 250) if px[W // 4, y] > 150)            # banner bottom
    ys = top + 30
    left = inward((x, ys) for x in range(0, W // 2))[0]
    right = inward((x, ys) for x in range(W - 1, W // 2, -1))[0]
    bottom = inward((left + 30, y) for y in range(H - 1, H // 2, -1))[1]
    thick = right + 1
    while thick < W and px[thick, ys] < 150: thick += 1
    thick -= right + 1                                                      # frame line width
    # the bubble = the connected dark region holding a point near its first letters
    seed = next((x, y) for y in range(top + 40, bottom) for x in range(left + 40, W // 2) if px[x, y] < 60)
    bubble = {seed}; q = deque([seed])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if left < nx < right and top < ny < bottom and (nx, ny) not in bubble and px[nx, ny] < 100:
                bubble.add((nx, ny)); q.append((nx, ny))
    bx = [x for x, y in bubble]; by = [y for x, y in bubble]
    b0, b1, bb = min(bx), max(bx), max(by)
    # Gemini's bot = dark ink outside the bubble's own box (letter counters inside it don't count)
    other = [(x, y) for x in range(left + 2, right - 1) for y in range(top + 2, bottom - 1)
             if px[x, y] < 100 and (x, y) not in bubble and ((x > b1 - 40) if bot_on_right else (x < b0 + 40) or y > bb + 4)]
    bg = im.getpixel((W // 4 if bot_on_right else 3 * W // 4, bottom - 5)); dr = ImageDraw.Draw(im)
    if other:
        ox0 = min(p[0] for p in other); ox1 = max(p[0] for p in other); oy0 = min(p[1] for p in other)
        if bot_on_right: dr.rectangle((ox0 - 10, oy0 - 10, right - 1, bottom - 1), fill=bg)
        else: dr.rectangle((left + 1, oy0 - 10, ox1 + 10, bottom - 1), fill=bg)
        bp = im.load()
        for (x, y) in bubble: bp[x, y] = (0, 0, 0)          # the bubble's tail may cross the cleared box
        dr.rectangle((right + 1, top, right + thick, bottom + thick), fill=(0, 0, 0))     # the frame, repainted
        dr.rectangle((left - thick, bottom + 1, right + thick, bottom + thick), fill=(0, 0, 0))
    if bot_on_right: X0, X1 = b1 + 24, right - 24
    else: X0, X1 = left + 24, b0 - 24
    s = min((X1 - X0) / art.width, (bottom - top - 50) / art.height)
    art = art.resize((round(art.width * s), round(art.height * s)), Image.LANCZOS)
    im.paste(art, ((X0 + X1) // 2 - art.width // 2, bottom - 24 - art.height), art)
    return im


def main():
    a = sys.argv[1:]; sid = a[0].upper(); text = a[1]
    p = STORIES / f"{sid}.json"; d = json.loads(p.read_text())
    speaker = a[a.index("--speaker") + 1] if "--speaker" in a else d["script"].get("preComic", {}).get("bot", "Right Bot")
    slot = a[a.index("--bot") + 1] if "--bot" in a else ("p2Right" if speaker == "Right Bot" else "p2Left")
    bot = d.get(slot) or d.get("p1Right" if speaker == "Right Bot" else "p1Left")
    script = dict(d["script"]); script["preComic"] = {"bot": speaker, "text1": text, "text2": ""}
    im = transplant(gemini_pre(script, bot), art_with_alpha(bot), speaker == "Right Bot")
    out = STORIES / f"{sid}.pre.png"; im.save(out)
    d["script"]["preComic"] = script["preComic"]; d["preBot"] = bot
    d["preImage"] = "data:image/png;base64," + base64.b64encode(out.read_bytes()).decode()
    p.write_text(json.dumps(d, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()

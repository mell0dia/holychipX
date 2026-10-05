#!/usr/bin/env python3
"""The Stories page's index: stories/manifest.json + stories/thumbs/.

The page used to send a HEAD request for every number 0-200 (x3 files) to find
out which stories exist, then draw each card from the full 896x1200 comic plus
the full pre image - 600 requests and ~38 MB for 42 stories. Now one small JSON
lists everything, and each card is a 400px JPEG (~25 KB) made here; the full
comic loads only in the reader.

    stories_manifest.py          # update manifest + any missing/stale thumbs

Run after every release (new story, short, or redone art).
"""
import json
from pathlib import Path
from PIL import Image

SITE = Path.home() / "holy-chip/website/holy-chip-site"
S = SITE / "stories"
T = S / "thumbs"
THUMB_W = 400       # card width on the page is 360px max; 400 covers 1x cleanly
PANEL3_W = 320      # the punchline tile (bottom 20% of a strip; right frame of a short)


def banner(p):
    try:
        b = json.loads(p.read_text())["script"]["banner"]
        return b.get("title", ""), b.get("year", "")
    except Exception:
        return "", ""


def stale(src, dst):
    return not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime


def thumb(src, dst, width):
    im = Image.open(src).convert("RGB")
    im.thumbnail((width, width * 3), Image.LANCZOS)
    im.save(dst, "JPEG", quality=82, optimize=True)


def face_side(band):
    """Which half of the panel-3 band holds the reacting bot. The bot's FACE is
    dark features inside a white box; the bubble is white text inside a black
    slab - the reverse. Count rows that are mostly white with some dark in the
    middle third, per half. (Column-ink and 'speaker' from the JSON both fail:
    a bot's black base looks like the bubble, and the JSON is wrong for the
    older strips.)"""
    g = band.convert("L"); W, H = g.size; p = g.load()
    def score(x0, x1):
        n = 0
        for y in range(int(H * 0.25), int(H * 0.85), 2):
            row = [p[x, y] for x in range(x0, x1)]; w = sum(1 for v in row if v > 200)
            if w > len(row) * 0.55 and len(row) - w > len(row) * 0.04 and any(v < 80 for v in row[len(row) // 3: 2 * len(row) // 3]):
                n += 1
        return n
    return "L" if score(0, W // 2) >= score(W // 2, W) else "R"


def face(src, dst, short):
    """The reacting bot alone, squared: the wall tile."""
    im = Image.open(src).convert("RGB"); W, H = im.size
    if short:
        crop = im.crop((int(W * 0.70), int(H * 0.45), W, int(H * 0.93)))
    else:
        y0, y1 = int(H * 0.75), int(H * 0.95); h = y1 - y0
        s = face_side(im.crop((0, y0, W, y1))); w = int(h * 1.15); x0 = 0 if s == "L" else W - w
        crop = im.crop((x0, y0, x0 + w, y1))
    crop.thumbnail((240, 240), Image.LANCZOS)
    sq = Image.new("RGB", (240, 240), (248, 249, 242)); sq.paste(crop, ((240 - crop.width) // 2, (240 - crop.height) // 2))
    sq.save(dst, "JPEG", quality=82, optimize=True)


def panel3(src, dst, short):
    """The HOLY CHIP moment: bottom panel of a strip (template bands 5/35/35/20/5),
    or the right frame of a short."""
    im = Image.open(src).convert("RGB"); W, H = im.size
    crop = im.crop((int(W * 0.70), int(H * 0.12), W, int(H * 0.93))) if short \
        else im.crop((0, int(H * 0.75), W, int(H * 0.95)))
    crop.thumbnail((PANEL3_W, PANEL3_W), Image.LANCZOS)
    crop.save(dst, "JPEG", quality=82, optimize=True)


T.mkdir(exist_ok=True)
out, made = [], 0
for png in sorted(S.glob("HC[0-9][0-9][0-9].png")):
    sid = png.stem
    title, year = banner(S / f"{sid}.json")
    pre = S / f"{sid}.pre.png"
    e = {"id": sid, "kind": "story", "title": title, "year": year,
         "src": f"stories/{sid}.png", "thumb": f"stories/thumbs/{sid}.jpg",
         "p3": f"stories/thumbs/{sid}.p3.jpg", "face": f"stories/thumbs/{sid}.face.jpg",
         "origin": (SITE / "origins" / f"{sid}.html").exists()}
    if pre.exists():
        e["pre"] = f"stories/{sid}.pre.png"; e["preThumb"] = f"stories/thumbs/{sid}.pre.jpg"
        if stale(pre, T / f"{sid}.pre.jpg"): thumb(pre, T / f"{sid}.pre.jpg", THUMB_W); made += 1
    if stale(png, T / f"{sid}.jpg"): thumb(png, T / f"{sid}.jpg", THUMB_W); made += 1
    if stale(png, T / f"{sid}.p3.jpg"): panel3(png, T / f"{sid}.p3.jpg", False); made += 1
    if stale(png, T / f"{sid}.face.jpg"): face(png, T / f"{sid}.face.jpg", False); made += 1
    ptp = S / "pt" / f"{sid}.png"            # the Brazilian-Portuguese edition, same names
    if ptp.exists():
        e["pt"] = f"stories/pt/{sid}.png"; e["ptThumb"] = f"stories/thumbs/{sid}.pt.jpg"
        if stale(ptp, T / f"{sid}.pt.jpg"): thumb(ptp, T / f"{sid}.pt.jpg", THUMB_W); made += 1
    out.append(e)
for png in sorted(S.glob("HC[0-9][0-9][0-9].short.png")):
    sid = png.name[:-10]
    title, year = banner(S / f"{sid}.short.json")
    e = {"id": f"{sid}.short", "kind": "short", "title": title, "year": year,
         "src": f"stories/{sid}.short.png", "thumb": f"stories/thumbs/{sid}.short.jpg",
         "p3": f"stories/thumbs/{sid}.short.p3.jpg", "face": f"stories/thumbs/{sid}.short.face.jpg", "origin": False}
    if stale(png, T / f"{sid}.short.jpg"): thumb(png, T / f"{sid}.short.jpg", THUMB_W); made += 1
    if stale(png, T / f"{sid}.short.p3.jpg"): panel3(png, T / f"{sid}.short.p3.jpg", True); made += 1
    if stale(png, T / f"{sid}.short.face.jpg"): face(png, T / f"{sid}.short.face.jpg", True); made += 1
    ptp = S / "pt" / f"{sid}.short.png"
    if ptp.exists():
        e["pt"] = f"stories/pt/{sid}.short.png"; e["ptThumb"] = f"stories/thumbs/{sid}.short.pt.jpg"
        if stale(ptp, T / f"{sid}.short.pt.jpg"): thumb(ptp, T / f"{sid}.short.pt.jpg", THUMB_W); made += 1
    out.append(e)
(S / "manifest.json").write_text(json.dumps({"stories": out}, indent=1) + "\n")
n = sum(1 for o in out if o["kind"] == "story"); m = len(out) - n
print(f"manifest: {n} stories, {m} shorts; {made} thumbnails written")

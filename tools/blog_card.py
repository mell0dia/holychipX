#!/usr/bin/env python3
"""blog_card.py - render a whole origin blog onto one comic-sized image.

    blog_card.py HC040                 # -> /tmp/HC040.blog.png
    blog_card.py HC040 out.png --lang pt
    blog_card.py HC040 --width 896 --height 1800   # taller if it will not fit

Same canvas as the comic (896x1200) so it sits in a feed the same way, in the
house palette: sage paper, a black header bar carrying the story number, title
and year, the blog title, then the body, then the holy-chip.com footer.

THE FONT SIZE IS SOLVED FOR, NOT CHOSEN. An origin blog is 500+ words across 30+
short paragraphs, and the paragraph gaps cost as much vertical space as several
lines of text. So the renderer measures a real layout at each candidate size and
takes the largest that fits, rather than guessing from an average character
width. If even the floor does not fit it says so and tells you how much taller
the canvas needs to be - silently shrinking text to 9px would produce an image
nobody can read, which defeats the point.
"""
import argparse, os, re, sys
from PIL import Image, ImageDraw, ImageFont

HC = os.path.expanduser("~/holy-chip")
ADIR = os.path.join(HC, "stories", "analysis")
TOOLS = os.path.join(HC, "tools")
FONT_PSTART = os.path.join(TOOLS, "fonts", "PressStart2P-Regular.ttf")
FONT_BODY = os.path.join(TOOLS, "fonts", "ShareTechMono-Regular.ttf")

BG = (248, 244, 232)
FG = (28, 28, 26)
BAR = (20, 20, 18)
BAR_FG = (248, 244, 232)
MUTED = (140, 140, 132)

MARGIN = 54
BAR_H = 64
FOOT_H = 46
MIN_SIZE, MAX_SIZE = 11, 30


def load(sid, lang):
    suffix = "" if lang == "en" else f".{lang}"
    p = os.path.join(ADIR, f"{sid}.blog{suffix}.md")
    if not os.path.exists(p):
        sys.exit(f"no blog at {p}")
    raw = open(p, encoding="utf-8").read()

    title = subtitle = ""
    paras = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("# "):
            title = s[2:].strip(); continue
        if s.startswith("## "):
            subtitle = s[3:].strip(); continue
        if not s or s.startswith("---") or s.startswith("*holy-chip.com"):
            continue
        s = re.sub(r"[*_`]", "", s)
        paras.append(s)
    return title, subtitle, paras


def wrap(draw, text, font, max_w):
    out, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            out.append(line); line = word
    if line:
        out.append(line)
    return out


def layout(draw, paras, size, max_w):
    """Real measured layout at `size`. Returns (lines, total_height)."""
    font = ImageFont.truetype(FONT_BODY, size)
    lh = round(size * 1.42)
    gap = round(size * 0.85)          # blank line between paragraphs
    lines, h = [], 0
    for i, p in enumerate(paras):
        for l in wrap(draw, p, font, max_w):
            lines.append((l, font)); h += lh
        if i != len(paras) - 1:
            lines.append((None, None)); h += gap
    return lines, h, lh, gap


def render(sid, lang, out_path, W, H, paras=None, part=None, title=None, subtitle=None):
    if paras is None:
        title, subtitle, paras = load(sid, lang)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # header bar, mirroring the comic's
    d.rectangle([0, 0, W, BAR_H], fill=BAR)
    hf = ImageFont.truetype(FONT_PSTART, 15)
    d.text((MARGIN, BAR_H // 2), f"#{sid}", font=hf, fill=BAR_FG, anchor="lm")
    head = subtitle.split("--")[-1].strip() if "--" in subtitle else subtitle
    d.text((W // 2, BAR_H // 2), head.upper()[:34], font=hf, fill=BAR_FG, anchor="mm")
    if part:
        d.text((W - MARGIN, BAR_H // 2), part, font=hf, fill=BAR_FG, anchor="rm")

    # blog title
    tf = ImageFont.truetype(FONT_PSTART, 21)
    ty = BAR_H + 34
    if part and not part.startswith('1'):
        title = ''
    for tline in wrap(d, title.upper(), tf, W - 2 * MARGIN):
        d.text((W // 2, ty), tline, font=tf, fill=FG, anchor="ma")
        ty += 30

    body_top = ty + 22
    avail_h = H - body_top - FOOT_H - MARGIN
    max_w = W - 2 * MARGIN

    best = None
    for size in range(MAX_SIZE, MIN_SIZE - 1, -1):
        lines, h, lh, gap = layout(d, paras, size, max_w)
        if h <= avail_h:
            best = (size, lines, lh, gap); break
    if best is None:
        size, lines, lh, gap = MIN_SIZE, *layout(d, paras, MIN_SIZE, max_w)[0:1], 0, 0
        lines, h, lh, gap = layout(d, paras, MIN_SIZE, max_w)
        need = body_top + h + FOOT_H + MARGIN
        sys.exit(f"will not fit at {MIN_SIZE}px on {W}x{H} — needs about "
                 f"{need}px of height. Rerun with --height {int(need) + 20}.")

    size, lines, lh, gap = best
    y = body_top
    for text, font in lines:
        if text is None:
            y += gap; continue
        d.text((MARGIN, y), text, font=font, fill=FG)
        y += lh

    ff = ImageFont.truetype(FONT_BODY, 22)
    d.line([(MARGIN, H - FOOT_H - 12), (W - MARGIN, H - FOOT_H - 12)], fill=MUTED, width=1)
    d.text((W // 2, H - FOOT_H + 12), "holy-chip.com", font=ff, fill=MUTED, anchor="ma")

    # IG's container API takes JPEG only, so honour the extension
    if out_path.lower().endswith((".jpg", ".jpeg")):
        img.convert("RGB").save(out_path, "JPEG", quality=92)
    else:
        img.save(out_path)
    print(f"OK:{out_path}")
    print(f"SIZE:{W}x{H}  BODY:{size}px  PARAS:{len(paras)}  "
          f"LINES:{sum(1 for t,_ in lines if t)}")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--lang", default="en", choices=("en", "pt", "es", "fr"))
    ap.add_argument("--width", type=int, default=896)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--break-after",
                    help="place the carousel split by hand: the paragraph "
                         "STARTING with this text ends a panel. Character-count "
                         "splitting balances the panels but cuts arguments in "
                         "half, and a swipe should land on a beat.")
    ap.add_argument("--split", type=int, default=1,
                    help="spread across N comic-sized panels (a carousel)")
    a = ap.parse_args()
    sid = a.story.upper()
    stem = a.out or f"/tmp/{sid}.blog{'' if a.lang=='en' else '.'+a.lang}.png"
    if a.split <= 1:
        render(sid, a.lang, stem, a.width, a.height); return

    # Split by CHARACTER COUNT, not paragraph count: the paragraphs here range
    # from three words to forty, so an even split by count would leave one panel
    # crammed and another half empty.
    title, subtitle, paras = load(sid, a.lang)
    if a.break_after:
        groups, cur = [], []
        for p in paras:
            cur.append(p)
            if p.startswith(a.break_after):
                groups.append(cur); cur = []
        if cur:
            groups.append(cur)
        if len(groups) < 2:
            sys.exit(f"--break-after {a.break_after!r} matched no paragraph")
    else:
        total = sum(len(p) for p in paras)
        target = total / a.split
        groups, cur, acc = [], [], 0
        for p in paras:
            cur.append(p); acc += len(p)
            if acc >= target and len(groups) < a.split - 1:
                groups.append(cur); cur, acc = [], 0
        groups.append(cur)
    base, ext = os.path.splitext(stem)
    for i, g in enumerate(groups, 1):
        render(sid, a.lang, f"{base}.{i}{ext}", a.width, a.height,
               paras=g, part=f"{i}/{len(groups)}", title=title, subtitle=subtitle)


if __name__ == "__main__":
    sys.exit(main())

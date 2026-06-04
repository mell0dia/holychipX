#!/usr/bin/env python3
"""Render the full Holy Chip blog as a tall typographic poster image.

Layout:
  - Top banner (~270 px): "JUST RELEASED" + title (Press Start 2P + accent rules)
  - Body: full blog text at fixed readable size (Share Tech Mono)
    * italic opener kept italic-feeling (smaller, muted accent)
    * first narrative paragraph rendered as 'lead' (1.4x body size)
  - Footer (~130 px): READ THE FULL STORY AT holy-chip.com/origins/<SID>

Canvas:
  - Width fixed at 1080
  - Height computed from content (no hard cap)
  - Designed for FB (and X full-resolution view); too tall for IG single image.

Usage:
  python3 story_poster.py <SID> <blog.md> <out.jpg> <header> [<footer>]

  - header: line for the banner ("Holy Chip #006 — Lingering")
  - footer: URL line ("holy-chip.com/origins/HC006"). default "holy-chip.com".
"""
import os, sys, re
from PIL import Image, ImageDraw, ImageFont

W = 1080
PADDING_X = 50           # was 90 — text column is now 980 px wide
BANNER_H = 200           # was 270 — tighter banner
FOOTER_H = 110           # was 150 — tighter footer

BG       = (248, 244, 232)
FG       = (28, 28, 26)
ACCENT   = (176, 138, 32)
MUTED    = (140, 140, 132)
RULE     = (200, 188, 156)
BANNER_BG  = (16, 16, 16)
BANNER_FG  = (245, 240, 226)
BANNER_DIM = (170, 165, 150)

FONT_PSTART = os.path.expanduser("~/holy-chip/tools/fonts/PressStart2P-Regular.ttf")
FONT_BODY   = os.path.expanduser("~/holy-chip/tools/fonts/ShareTechMono-Regular.ttf")

BODY_SIZE   = 30            # was 34 — slightly smaller, more lines per inch
LEAD_SIZE   = int(BODY_SIZE * 1.3)
OPENER_SIZE = int(BODY_SIZE * 0.95)
LINE_RATIO  = 1.42          # was 1.55 — tighter line height
PARA_GAP    = int(BODY_SIZE * 0.7)   # was 0.95 — tighter paragraph spacing


def strip_md(text):
    out = []
    for line in text.splitlines():
        s = re.sub(r"^#+\s*", "", line)
        s = re.sub(r"^\*(.+)\*$", r"\1", s)
        s = s.replace("--", "—")
        out.append(s)
    return "\n".join(out).rstrip()


def wrap_to_width(text, font, draw, max_w):
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def parse_blog(md_text):
    """Return (opener_text, [body_paragraphs])."""
    # Slice from first italic opener line to the '---' footer separator
    # Drop title (#) and subtitle (##) heading lines.
    lines = md_text.splitlines()
    body_lines = []
    in_body = False
    for ln in lines:
        s = ln.strip()
        if not in_body:
            if s.startswith("*") and s.endswith("*") and len(s) > 2:
                in_body = True
                body_lines.append(s)
                continue
            # also kick off body if we see a non-heading, non-empty line
            if s and not s.startswith("#") and not s.startswith("---"):
                in_body = True
                body_lines.append(s)
            continue
        if s.startswith("---"):
            break
        body_lines.append(s)

    block = "\n".join(body_lines).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
    if not paras:
        return ("", [])

    # First paragraph may be the italic opener
    opener = ""
    if paras[0].startswith("*") and paras[0].endswith("*"):
        opener = paras[0].strip("*").strip()
        paras = paras[1:]

    # Strip residual markdown
    opener = strip_md(opener) if opener else ""
    paras  = [strip_md(p) for p in paras]
    return (opener, paras)


def main():
    if len(sys.argv) < 5:
        print("usage: story_poster.py <SID> <blog.md> <out.jpg> <header> [<footer>]")
        sys.exit(1)
    sid, blog_path, out_path, header = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    footer = sys.argv[5] if len(sys.argv) > 5 else "holy-chip.com"

    if not os.path.exists(blog_path):
        print(f"ERROR: blog not found: {blog_path}", file=sys.stderr)
        sys.exit(1)

    opener, paras = parse_blog(open(blog_path).read())
    if not paras and not opener:
        print("ERROR: nothing parsed from blog", file=sys.stderr)
        sys.exit(1)

    # First pass: a dummy 1×1 canvas just to measure with the fonts
    f_body   = ImageFont.truetype(FONT_BODY, BODY_SIZE)
    f_lead   = ImageFont.truetype(FONT_BODY, LEAD_SIZE)
    f_opener = ImageFont.truetype(FONT_BODY, OPENER_SIZE)
    dummy = Image.new("RGB", (1, 1), BG)
    dd = ImageDraw.Draw(dummy)
    body_w = W - 2 * PADDING_X

    lines_per_para = []
    fonts_per_para = []
    for i, p in enumerate(paras):
        fnt = f_lead if i == 0 else f_body
        fonts_per_para.append(fnt)
        lines_per_para.append(wrap_to_width(p, fnt, dd, body_w))

    if opener:
        opener_lines = wrap_to_width(opener, f_opener, dd, body_w)
    else:
        opener_lines = []

    # Heights
    body_top = BANNER_H + 70
    h = body_top

    if opener_lines:
        op_line_h = int(OPENER_SIZE * LINE_RATIO)
        h += len(opener_lines) * op_line_h
        h += PARA_GAP + 20  # extra breathing under opener

    for i, lines in enumerate(lines_per_para):
        fnt = fonts_per_para[i]
        sz  = LEAD_SIZE if i == 0 else BODY_SIZE
        lh  = int(sz * LINE_RATIO)
        h += len(lines) * lh
        if i < len(lines_per_para) - 1:
            h += PARA_GAP

    h += FOOTER_H  # footer area

    H = h
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # --- top banner (200 px tall) ---
    d.rectangle([(0, 0), (W, BANNER_H)], fill=BANNER_BG)
    tag_font   = ImageFont.truetype(FONT_PSTART, 16)
    title_font = ImageFont.truetype(FONT_PSTART, 28)
    snap_font  = ImageFont.truetype(FONT_BODY, 22)
    d.text((W // 2, 38), "JUST RELEASED", fill=ACCENT, font=tag_font, anchor="ma")
    d.line([(W // 2 - 220, 95), (W // 2 - 60, 95)], fill=ACCENT, width=2)
    d.line([(W // 2 + 60, 95), (W // 2 + 220, 95)], fill=ACCENT, width=2)
    d.text((W // 2, 95), header.upper(), fill=BANNER_FG, font=title_font, anchor="ma")
    d.text((W // 2, 156), "The full story", fill=BANNER_DIM, font=snap_font, anchor="ma")

    # --- body ---
    y = body_top
    if opener_lines:
        op_line_h = int(OPENER_SIZE * LINE_RATIO)
        for ln in opener_lines:
            d.text((PADDING_X, y), ln, fill=MUTED, font=f_opener)
            y += op_line_h
        y += PARA_GAP + 20

    for i, lines in enumerate(lines_per_para):
        fnt = fonts_per_para[i]
        sz  = LEAD_SIZE if i == 0 else BODY_SIZE
        lh  = int(sz * LINE_RATIO)
        for ln in lines:
            d.text((PADDING_X, y), ln, fill=FG, font=fnt)
            y += lh
        y += PARA_GAP

    # --- footer (110 px tall) ---
    d.line([(PADDING_X, H - FOOTER_H + 12), (W - PADDING_X, H - FOOTER_H + 12)], fill=RULE, width=1)
    label_font = ImageFont.truetype(FONT_PSTART, 12)
    url_font   = ImageFont.truetype(FONT_PSTART, 16)
    d.text((W // 2, H - FOOTER_H + 42), "READ THE FULL STORY AT", fill=MUTED, font=label_font, anchor="ma")
    d.text((W // 2, H - FOOTER_H + 78), footer.upper(), fill=FG, font=url_font, anchor="ma")

    img.save(out_path, "JPEG", quality=90, optimize=True)
    sz_kb = os.path.getsize(out_path) // 1024
    print(f"OK:{out_path}")
    print(f"SIZE:{W}x{H}")
    print(f"FILE:{sz_kb} KB")


if __name__ == "__main__":
    main()

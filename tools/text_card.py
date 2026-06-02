#!/usr/bin/env python3
"""Holy Chip long-form text card — 1080x1350 for FB/IG carousel slide.

Carries a multi-paragraph tease from a blog (no punchline). Designed to sit as
the second slide of a 2-image carousel — the comic comes first, this delivers
the readable text portion that captions would otherwise hide behind "See more".

Usage:
  python3 text_card.py <out.jpg> <header> <body> [<footer>]
    - header: single line, gets uppercased, drawn in Press Start 2P
    - body: paragraphs separated by '||' (rendered with blank lines between)
    - footer: optional, default "holy-chip.com"

Paragraph wrapped in surrounding '"' is treated as a pull-quote (italic-ish,
centered, with accent rule on either side).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
PADDING_X = 90
BANNER_H = 270                 # top "JUST RELEASED" banner band

BG       = (248, 244, 232)  # sage paper
FG       = (28, 28, 26)     # near-black ink
ACCENT   = (176, 138, 32)   # gold
MUTED    = (140, 140, 132)  # footer
RULE     = (200, 188, 156)  # subtle paper rule
BANNER_BG  = (16, 16, 16)   # near-black banner
BANNER_FG  = (245, 240, 226)# warm-white banner text
BANNER_DIM = (170, 165, 150)# muted banner text

FONT_PSTART = os.path.expanduser("~/holy-chip/tools/fonts/PressStart2P-Regular.ttf")
FONT_BODY   = os.path.expanduser("~/holy-chip/tools/fonts/ShareTechMono-Regular.ttf")
FONT_COMIC  = "/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf"
FONT_KGHAPPY = os.path.expanduser("~/holy-chip/tools/fonts/KGHAPPY.ttf")

# A paragraph that contains ONLY this marker tells the renderer to draw the
# CTA block (READ THE FULL BLOG POST + holy-chip.com + language badges) INLINE
# at that point in the body flow, instead of as a fixed footer at the bottom.
CTA_MARKER = "[[CTA]]"


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


def main():
    if len(sys.argv) < 4:
        print("usage: text_card.py <out.jpg> <header> <body-with-||> [<footer>]")
        sys.exit(1)
    out_path = sys.argv[1]
    header   = sys.argv[2]
    body     = sys.argv[3]
    footer   = sys.argv[4] if len(sys.argv) > 4 else "holy-chip.com"

    raw_paragraphs = [p.strip() for p in body.split("||") if p.strip()]

    def is_quote(p):
        return p.startswith('"') and p.endswith('"')

    def is_cta(p):
        return p.strip() == CTA_MARKER

    # tuple: (is_quote, is_cta, text)
    paragraphs = []
    for p in raw_paragraphs:
        if is_cta(p):
            paragraphs.append((False, True, ""))
        else:
            paragraphs.append((is_quote(p), False, p.strip('"').strip() if is_quote(p) else p))
    inline_cta = any(c for _, c, _ in paragraphs)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # --- top banner ("JUST RELEASED" band) ---
    d.rectangle([(0, 0), (W, BANNER_H)], fill=BANNER_BG)
    # tag line
    tag_font   = ImageFont.truetype(FONT_PSTART, 18)
    title_font = ImageFont.truetype(FONT_PSTART, 32)
    snap_font  = ImageFont.truetype(FONT_BODY, 26)
    d.text((W // 2, 56), "JUST RELEASED", fill=ACCENT, font=tag_font, anchor="ma")
    # accent rules either side of the title
    d.line([(W // 2 - 240, 120), (W // 2 - 70, 120)], fill=ACCENT, width=2)
    d.line([(W // 2 + 70, 120), (W // 2 + 240, 120)], fill=ACCENT, width=2)
    d.text((W // 2, 120), header.upper(), fill=BANNER_FG, font=title_font, anchor="ma")
    d.text((W // 2, 195), "A snapshot of the story", fill=BANNER_DIM, font=snap_font, anchor="ma")

    # --- body: auto-fit so all paragraphs fit between body_top and body_bottom ---
    # RULE: top section (banner + body) targets the top 60% of image height.
    # CTA + footer own the bottom 40% (≥ y = H * 0.60). The body may slip a few
    # percent past 60% if the lead-paragraph boost demands it.
    TOP_FRACTION = 0.62
    FOOTER_TOP_FRACTION = 0.60   # CTA block anchors here regardless of body slip
    body_top = BANNER_H + 50
    body_bottom = H - 60 if inline_cta else int(H * TOP_FRACTION)
    body_h_avail = body_bottom - body_top
    body_w_avail = W - 2 * PADDING_X

    # The inline CTA block reserves this much vertical space when it lands in body flow.
    CTA_INLINE_H = 250

    # Lead paragraph (first non-quote, non-CTA) gets a modest size boost, plus a
    # +4px floor so the hook reads bigger than the supporting text even at small
    # auto-fit sizes.
    LEAD_RATIO = 1.20
    LEAD_BONUS = 4
    lead_idx = next((i for i, (q, c, _) in enumerate(paragraphs) if not q and not c), None)

    size = 46
    while size >= 20:
        lead_size = int(size * LEAD_RATIO) + LEAD_BONUS
        f_body = ImageFont.truetype(FONT_BODY, size)
        f_lead = ImageFont.truetype(FONT_BODY, lead_size)
        line_h_body = int(size * 1.55)
        line_h_lead = int(lead_size * 1.45)
        para_gap = int(size * 0.95)
        lines_per_para = []
        for i, (is_q, is_c, p) in enumerate(paragraphs):
            if is_c:
                lines_per_para.append([])  # CTA paragraph has no body lines
                continue
            f_use = f_lead if i == lead_idx else f_body
            max_w = int(body_w_avail * 0.86) if is_q else body_w_avail
            lines_per_para.append(wrap_to_width(p, f_use, d, max_w))
        total_h = 0
        for i, lp in enumerate(lines_per_para):
            if paragraphs[i][1]:
                total_h += CTA_INLINE_H
                continue
            lh = line_h_lead if i == lead_idx else line_h_body
            total_h += len(lp) * lh
        total_h += (len(paragraphs) - 1) * para_gap
        n_quotes = sum(1 for q, _, _ in paragraphs if q)
        total_h += n_quotes * int(para_gap * 0.6)
        if total_h <= body_h_avail:
            break
        size -= 2

    # top-align with small offset for visual balance
    y = body_top + max(0, (body_h_avail - total_h) // 6)

    label_font = ImageFont.truetype(FONT_KGHAPPY, 60)
    url_font = ImageFont.truetype(FONT_BODY, 24)
    lang_label_font = ImageFont.truetype(FONT_COMIC, 14)
    lang_badge_font = ImageFont.truetype(FONT_PSTART, 16)

    def draw_cta_block(y_start):
        """Draw rule + 'READ THE FULL BLOG POST' (KG Happy) + URL + language badges.
        Returns the y after the block. Total height = CTA_INLINE_H."""
        d.line([(PADDING_X, y_start + 10), (W - PADDING_X, y_start + 10)], fill=RULE, width=1)
        d.text((W // 2, y_start + 50), "READ THE FULL BLOG POST", fill=ACCENT, font=label_font, anchor="ma")
        d.text((W // 2, y_start + 130), "holy-chip.com", fill=FG, font=url_font, anchor="ma")
        d.text((W // 2, y_start + 170), "AVAILABLE IN", fill=MUTED, font=lang_label_font, anchor="ma")
        langs = ["EN", "ES", "PT", "FR"]
        badge_w, badge_h, gap = 64, 36, 14
        total_w = len(langs) * badge_w + (len(langs) - 1) * gap
        start_x = (W - total_w) // 2
        y_top = y_start + 195
        for i, lang in enumerate(langs):
            x = start_x + i * (badge_w + gap)
            d.rectangle([(x, y_top), (x + badge_w, y_top + badge_h)], outline=FG, width=2)
            d.text((x + badge_w // 2, y_top + badge_h // 2 + 1), lang, fill=FG, font=lang_badge_font, anchor="mm")
        return y_start + CTA_INLINE_H

    for i, ((is_q, is_c, _p), lines) in enumerate(zip(paragraphs, lines_per_para)):
        is_lead = (i == lead_idx)
        f_use = f_lead if is_lead else f_body
        lh = line_h_lead if is_lead else line_h_body
        if is_c:
            # CTA renders right after the body content. Empty space goes BELOW
            # the CTA, not between body and CTA. (Previously bottom-anchored;
            # reverted on HC016 — the gained-space-from-trim flows below the badges.)
            y = draw_cta_block(y)
        elif is_q:
            y += int(para_gap * 0.3)
            top_y = y
            for ln in lines:
                d.text((W // 2, y), ln, fill=FG, font=f_use, anchor="ma")
                y += lh
            bot_y = y
            mid_y = (top_y + bot_y) // 2
            d.line([(PADDING_X, mid_y), (PADDING_X + 50, mid_y)], fill=ACCENT, width=2)
            d.line([(W - PADDING_X - 50, mid_y), (W - PADDING_X, mid_y)], fill=ACCENT, width=2)
            y += int(para_gap * 0.3)
        else:
            for ln in lines:
                d.text((PADDING_X, y), ln, fill=FG, font=f_use)
                y += lh
        y += para_gap

    # --- bottom footer band (only when no inline CTA) ---
    if inline_cta:
        # Skip the fixed footer — CTA already drawn inline above.
        langs = ["EN", "ES", "PT", "FR"]
        badge_w, badge_h, gap = 64, 36, 14
        total_w = len(langs) * badge_w + (len(langs) - 1) * gap
        start_x = (W - total_w) // 2
        y_top = -1  # sentinel so the loop below is harmless / no-op
        langs = []
    else:
        # Footer occupies bottom 40% (y = H*0.60 .. H). Spread vertically so the
        # KGHAPPY label, URL, "AVAILABLE IN", and badges do not collide.
        footer_top = int(H * FOOTER_TOP_FRACTION)
        d.line([(PADDING_X, footer_top + 30), (W - PADDING_X, footer_top + 30)], fill=RULE, width=1)
        d.text((W // 2, footer_top + 90),  "READ THE FULL BLOG POST", fill=ACCENT, font=label_font, anchor="ma")
        d.text((W // 2, footer_top + 220), "holy-chip.com",           fill=FG,     font=url_font,   anchor="ma")
        d.text((W // 2, footer_top + 290), "AVAILABLE IN",            fill=MUTED,  font=lang_label_font, anchor="ma")
        langs = ["EN", "ES", "PT", "FR"]
        badge_w, badge_h, gap = 64, 36, 14
        total_w = len(langs) * badge_w + (len(langs) - 1) * gap
        start_x = (W - total_w) // 2
        y_top = footer_top + 330
    for i, lang in enumerate(langs):
        x = start_x + i * (badge_w + gap)
        d.rectangle([(x, y_top), (x + badge_w, y_top + badge_h)], outline=FG, width=2)
        d.text((x + badge_w // 2, y_top + badge_h // 2 + 1), lang, fill=FG, font=lang_badge_font, anchor="mm")

    img.save(out_path, "JPEG", quality=92, optimize=True)
    print(f"OK:{out_path}")
    print(f"SIZE:{W}x{H}")
    print(f"BODY_FONT_SIZE:{size}")


if __name__ == "__main__":
    main()

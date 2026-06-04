#!/usr/bin/env python3
"""Holy Chip daily-gm card — 1080x1080.

Picks an NFT (image + personality name) and pairs it with a paragraph
pulled from a random already-released story blog. Footer shows a 'read more'
link back to the origins page. Sage paper background to match the brand.

Usage:
  python3 gm_card.py <out.png> [<nft-id>] [<HC###>]
    - nft-id: integer NFT id (random unused if omitted; tracked in gm-history.json)
    - HC###:  story id — pulls a random narrative paragraph from its EN blog.
              If omitted, picks a random released story.
"""
import os, sys, json, random, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1080
PAD = 60
BG       = (248, 244, 232)   # sage paper
FG       = (28, 28, 26)      # near-black ink
ACCENT   = (176, 138, 32)    # gold
MUTED    = (140, 140, 132)
BUBBLE_BG = (16, 16, 16)
BUBBLE_FG = (245, 240, 226)

TOOLS = Path.home() / "holy-chip/tools"
SITE = Path.home() / "holy-chip/website/holy-chip-site"
NFT_DIR = Path.home() / "holy-chip/nft/collection/assets"
BLOGS = SITE / "stories/analysis"
TRACKER = Path.home() / "holy-chip/content/story-posts.json"
HISTORY = Path.home() / "holy-chip/content/gm-history.json"
PHRASES_FILE = Path.home() / "holy-chip/content/gm-phrases.md"
ORIGIN_BASE = "holy-chip.com/origins"

FONT_PSTART = str(TOOLS / "fonts/PressStart2P-Regular.ttf")
FONT_BODY   = str(TOOLS / "fonts/ShareTechMono-Regular.ttf")


def strip_md(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s); s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s); s = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", s)
    return s


def released_story_ids():
    """Stories that have already gone out on FB AND Nostr — safe to quote from."""
    data = json.loads(TRACKER.read_text())
    return [e["story"] for e in data["posted"]
            if e.get("fb_post_id") and e.get("nostr_event_id")]


def blog_paragraphs(sid):
    """Narrative paragraphs from a story's EN blog, excluding headers, italic
    openers, the title 'Holy Chip ...' line, and the post-rule footer."""
    p = BLOGS / f"{sid}.blog.md"
    if not p.exists():
        return []
    out = []
    for para in [x.strip() for x in p.read_text().split("\n\n") if x.strip()]:
        if para.startswith("#"): continue
        if para.startswith("*") and para.endswith("*") and "\n" not in para: continue
        if para.lower().startswith("holy chip"): break
        if para.startswith("---"): break
        cleaned = strip_md(para)
        # keep paragraphs that fit in a bubble (cap at ~280 chars to stay readable)
        if 40 <= len(cleaned) <= 280:
            out.append(cleaned)
    return out


def load_phrases():
    """Approved GM phrases from content/gm-phrases.md.
    Each numbered line is 'N. <phrase> (HC0xx)'. The (HC0xx) tag is the source
    story (drives the 'read the full blog post' CTA). Returns [(phrase, sid)]."""
    out = []
    if not PHRASES_FILE.exists():
        return out
    for line in PHRASES_FILE.read_text().splitlines():
        m = re.match(r"^\s*\d+\.\s+(.*\S)\s*$", line)
        if not m:
            continue
        text = m.group(1).strip()
        sid = ""
        sm = re.search(r"\s*\((HC\d+)\)\s*$", text)
        if sm:
            sid = sm.group(1)
            text = text[:sm.start()].strip()
        out.append((text, sid))
    return out


def pick_thought(sid=None):
    """Pick an approved phrase, no repeats until the whole list cycles. Falls
    back to a random blog paragraph only if the approved list is missing/empty."""
    phrases = load_phrases()
    if not phrases:
        candidates = [sid] if sid else released_story_ids()
        random.shuffle(candidates)
        for s in candidates:
            paras = blog_paragraphs(s)
            if paras:
                return random.choice(paras), s
        return "AI WILL FIGURE IT OUT.", "HC000"
    if sid:                                   # optional: force a phrase from one story
        filtered = [p for p in phrases if p[1] == sid]
        if filtered:
            phrases = filtered
    data = json.loads(HISTORY.read_text()) if HISTORY.exists() else {}
    used = set(data.get("used_phrases", []))
    unused = [(t, s) for (t, s) in phrases if t not in used]
    if not unused:                            # cycled through all — reset rotation
        unused = phrases
        if HISTORY.exists():
            data["used_phrases"] = []
            HISTORY.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return random.choice(unused)


def load_nft(nft_id):
    img = NFT_DIR / f"{nft_id}.png"
    meta = NFT_DIR / f"{nft_id}.json"
    if not img.exists() or not meta.exists():
        return None
    name = json.loads(meta.read_text()).get("name", f"#{nft_id}")
    # "Holy Chip #001 - ROBOT" → "ROBOT"
    personality = name.split(" - ", 1)[-1] if " - " in name else name
    return img, personality


def pick_nft():
    candidates = sorted([int(p.stem) for p in NFT_DIR.glob("*.png")
                         if p.stem.isdigit() and (NFT_DIR/f"{p.stem}.json").exists()])
    used = set()
    if HISTORY.exists():
        used = set(json.loads(HISTORY.read_text()).get("used_ids", []))
    unused = [i for i in candidates if i not in used]
    if not unused:
        unused = candidates  # all used, start over
    chosen = random.choice(unused)
    return load_nft(chosen), chosen


def record_use(nft_id, thought, source_sid, out_path):
    data = {"used_ids": [], "log": []}
    if HISTORY.exists():
        data = json.loads(HISTORY.read_text())
    data.setdefault("used_ids", [])
    data.setdefault("log", [])
    if nft_id not in data["used_ids"]:
        data["used_ids"].append(nft_id)
    data.setdefault("used_phrases", [])
    if thought not in data["used_phrases"]:
        data["used_phrases"].append(thought)
    data["log"].append({"nft_id": nft_id, "source": source_sid,
                        "thought": thought, "out": str(out_path)})
    HISTORY.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n")


def wrap_to_width(text, font, draw, max_w):
    words = text.split()
    if not words: return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gm_card.png"
    nft_arg = sys.argv[2] if len(sys.argv) > 2 else None
    sid_arg = sys.argv[3] if len(sys.argv) > 3 else None

    thought, source_sid = pick_thought(sid_arg)

    if nft_arg is not None:
        nft_id = int(nft_arg)
        loaded = load_nft(nft_id)
        if loaded is None:
            sys.exit(f"no NFT {nft_id} in {NFT_DIR}")
        char_path, personality = loaded
    else:
        (char_path, personality), nft_id = pick_nft()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # --- footer reservation (small holy-chip.com line at the bottom) ---
    foot_font = ImageFont.truetype(FONT_BODY, 28)
    footer_y = H - 38
    footer_top_y = footer_y - 34

    # --- character (centered, bottom half) ---
    # Reduced 15% vs prior layout to give the bubble more vertical room.
    # The NFT PNGs have a white square framing the character; flood-fill the
    # outer white to sage so the character blends with the card background.
    chr_img = Image.open(char_path).convert("RGB")
    for corner in [(0, 0), (chr_img.width - 1, 0),
                   (0, chr_img.height - 1),
                   (chr_img.width - 1, chr_img.height - 1)]:
        if chr_img.getpixel(corner) == (255, 255, 255):
            ImageDraw.floodfill(chr_img, corner, BG, thresh=8)
    target_h = 510
    ratio = target_h / chr_img.height
    chr_resized = chr_img.resize((int(chr_img.width * ratio), target_h), Image.LANCZOS)
    char_x = (W - chr_resized.width) // 2
    char_y = footer_top_y - 30 - target_h
    img.paste(chr_resized, (char_x, char_y))

    # --- speech bubble (full width, top half) ---
    bubble_left = PAD
    bubble_right = W - PAD
    bubble_w = bubble_right - bubble_left
    # auto-fit font — pixel font for short shouts, body font for longer paragraphs.
    # Start large; the loop shrinks until the bubble fits.
    bubble_text = thought.strip()
    is_long = len(bubble_text) > 60
    if is_long:
        font_path = FONT_BODY
        size = 50
        min_size = 22
        body_text = bubble_text  # mixed case for readability
    else:
        font_path = FONT_PSTART
        size = 64
        min_size = 24
        body_text = bubble_text.upper()
    bubble_top = PAD
    bubble_max_bottom = char_y - 28          # tight gap so the bubble can grow taller
    bubble_max_h = bubble_max_bottom - bubble_top
    while size >= min_size:
        f = ImageFont.truetype(font_path, size)
        lines = wrap_to_width(body_text, f, d, bubble_w - 60)
        line_h = int(size * (1.4 if is_long else 1.5))
        bubble_h = line_h * len(lines) + 80
        if bubble_h <= bubble_max_h:
            break
        size -= 2
    bubble_bottom = bubble_top + bubble_h

    # bubble box
    d.rounded_rectangle([(bubble_left, bubble_top), (bubble_right, bubble_bottom)],
                         radius=14, fill=BUBBLE_BG)
    # tail pointing DOWN toward the character below
    tail_tip_x = W // 2
    tail_tip_y = bubble_bottom + 30
    d.polygon([(tail_tip_x - 24, bubble_bottom),
               (tail_tip_x + 24, bubble_bottom),
               (tail_tip_x, tail_tip_y)], fill=BUBBLE_BG)

    # text inside bubble
    text_y = bubble_top + 40
    text_x = bubble_left + bubble_w // 2
    for ln in lines:
        d.text((text_x, text_y), ln, fill=BUBBLE_FG, font=f, anchor="ma")
        text_y += line_h

    # --- footer (only holy-chip.com) ---
    d.line([(PAD, footer_top_y - 14), (W - PAD, footer_top_y - 14)], fill=MUTED, width=1)
    d.text((W // 2, footer_y), "holy-chip.com", fill=FG, font=foot_font, anchor="md")

    fmt = "JPEG" if str(out_path).lower().endswith((".jpg", ".jpeg")) else "PNG"
    save_kw = {"quality": 92, "optimize": True} if fmt == "JPEG" else {"optimize": True}
    img.save(out_path, fmt, **save_kw)
    record_use(nft_id, thought, source_sid, out_path)
    print(f"OK:{out_path}")
    print(f"NFT:{nft_id} ({personality})")
    print(f"SOURCE:{source_sid}")
    print(f"THOUGHT:{thought}")


if __name__ == "__main__":
    main()

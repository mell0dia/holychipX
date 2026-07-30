#!/usr/bin/env python3
"""HC010 custom-art pipeline — single combined pass with strict in-bounds constraints.

Current SGen render (stories/HC010.png) = pristine crisp base; HC010.refart.png = style ref.
ONE Gemini pass redraws BOTH:
  - PANEL 2 poof: a COMPACT cloud in the empty left, NOT touching the bubbles.
  - PANEL 3: the whole scene redrawn ENTIRELY BELOW the panel-2/3 divider (nothing crosses
    the separation line), round chip + Holy Chip body + clouds-above-head + T-bubble + GOD!
Then composite ONLY the poof + panel-3 regions onto the PRISTINE base so panels 1-2 / banner
/ footer stay crisp. Output: /tmp/HC010.final.png
"""
import os, base64, subprocess, requests
from PIL import Image

HC   = os.path.expanduser("~/holy-chip")
BASE = f"{HC}/stories/HC010.png"
REF  = f"{HC}/stories/HC010.refart.png"
OUT  = "/tmp/HC010.final.png"
GRAPH = ("https://generativelanguage.googleapis.com/v1beta/models/"
         "gemini-3.1-flash-image-preview:generateContent")

for line in open(os.path.expanduser("~/claude-agent/.env")):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
KEY = os.environ["GEMINI_API_KEY"]


def img_part(path):
    return {"inlineData": {"mimeType": "image/png",
                           "data": base64.b64encode(open(path, "rb").read()).decode()}}


PROMPT = (
    "FIRST image = the SOURCE comic. Reproduce it EXACTLY — the top banner, panel 1 (both "
    "robots and all its bubbles), the master robot on the RIGHT of panel 2, every speech "
    "bubble and its exact text, all panel borders and panel heights, the bottom footer, the "
    "near-white #F8F9F2 background, and the overall dimensions stay PIXEL-IDENTICAL. The "
    "SECOND image is ONLY a style reference for the poof and the round chip.\n\n"
    "Make EXACTLY these two additions, and keep every element strictly INSIDE its own "
    "panel:\n\n"
    "=== PANEL 2 (middle) — the POOF ===\n"
    "In the empty near-white space on the LEFT of panel 2, draw a COMPACT poof cloud: one "
    "puffy bumpy cloud outline with the bold word 'POOF!' inside, plus 2 small puff clouds. "
    "IMPORTANT SIZING: keep it SMALL and tucked in the lower-left corner of panel 2. It must "
    "NOT touch, overlap, or crowd the 'JEESH, ANOTHER POWER OUTAGE?' or 'DEAR ALMIGHTY "
    "POWER...' speech bubbles — leave a clear empty gap between the poof and those bubbles. "
    "Black outline only, no fill.\n\n"
    "=== PANEL 3 (bottom) — redraw the whole scene ===\n"
    "Completely redraw the bottom panel. CRITICAL CONSTRAINT: EVERY element of panel 3 — the "
    "chip, its body, the small clouds above its head, and ALL speech bubbles — must sit "
    "ENTIRELY BELOW the horizontal black line that separates panel 2 from panel 3. NOTHING "
    "may cross, touch, or stick above that divider line. Leave a small clear margin just "
    "below the divider. Compose the scene to FIT within the panel's height.\n"
    "Contents:\n"
    "  - A NEW round-headed chip on the LEFT: circular head, two big round eyes, small open "
    "'O' surprised mouth, one antenna on top, Holy Chip ears. Face/eyes/antenna SMOOTH "
    "(non-pixelated). It just materialized and is startled.\n"
    "  - Its BODY = the SAME style as the robots in panel 1: a black shouldered torso with a "
    "row of small WHITE SQUARES (dotted trim) along the top edge and small black connector "
    "tabs on the sides. NOT a keyboard grid, NOT a plain black blob.\n"
    "  - 2 small puff clouds floating just above the chip's head (but still BELOW the divider, "
    "inside the panel).\n"
    "  - A black T-shaped bubble in the center: 'HOLY CHIP !!' large & bold on top, 'WHO "
    "BROUGHT ME HERE?' about 3x smaller underneath (white text on black, T silhouette).\n"
    "  - A small WHITE bubble at the FAR RIGHT edge, tail pointing right, containing only "
    "'GOD!'.\n\n"
    "Do not alter the banner, panel 1, the panel-2 bubbles, the master robot, or the footer."
)

print("=== single combined pass (poof + panel 3, in-bounds) ===")
body = {"contents": [{"role": "user", "parts": [
            img_part(BASE), {"text": "↑ FIRST = SOURCE comic to clone exactly."},
            img_part(REF),  {"text": "↑ SECOND = style reference for poof + round chip only."},
            {"text": PROMPT}]}],
        "generationConfig": {"temperature": 0.1,
                             "imageConfig": {"aspectRatio": "3:4", "imageSize": "1K"}}}
r = requests.post(GRAPH, params={"key": KEY}, json=body, timeout=180)
r.raise_for_status()
gem_b = None
for p in r.json()["candidates"][0]["content"].get("parts", []):
    inline = p.get("inlineData") or p.get("inline_data")
    if inline and inline.get("data"):
        gem_b = base64.b64decode(inline["data"]); break
    if p.get("text"):
        print("TEXT:", p["text"][:200])
if not gem_b:
    raise SystemExit("no image in response")
open("/tmp/HC010.gem.png", "wb").write(gem_b)

print("=== composite onto pristine base ===")
base = Image.open(BASE).convert("RGB")
gem  = Image.open("/tmp/HC010.gem.png").convert("RGB")

# POOF -> masked overlay (lower-left of panel 2); only linework transfers, crisp bg stays
poof = gem.crop((0, 620, 240, 905))
mask = poof.convert("L").point(lambda p: 255 if p < 170 else 0)
base.paste(poof, (0, 620), mask)

# PANEL 3 -> clean crop at the divider (art now stays in-bounds, so no cut needed)
base.paste(gem.crop((0, 960, 896, 1172)), (0, 960))

base.save(OUT)
print("saved", OUT)
subprocess.run(["open", OUT])

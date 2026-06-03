#!/usr/bin/env python3
"""Retroactively flip Holy Chip bubble colors via Gemini image editing.

Rule (matches SGen convention):
- The panel-3 speaker bot's bubbles in panels 1 & 2 stay BLACK rectangle / WHITE text.
- The OTHER bot's bubbles in panels 1 & 2 become WHITE rectangle / BLACK text /
  thin BLACK border (1-2 px).
- Panel 3 is untouched.

Panel-3 speaker is determined by the LAST dialog of panel 3's `dialogs` array in
HC###.json (i.e. the bot delivering the final punchline reaction). If panel 3
has only one speaker, that speaker wins.

Usage:
  python3 fix_bubble_colors.py <SID>          # writes /tmp/<SID>.flipped.png, opens it
  python3 fix_bubble_colors.py <SID> --apply  # also overwrites canonical HC###.png
"""
import os, sys, json, base64, subprocess, requests

SITE = os.path.expanduser("~/holy-chip/website/holy-chip-site")
STORIES = f"{SITE}/stories"
GRAPH = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent"

def load_env():
    env_path = os.path.expanduser("~/claude-agent/.env")
    if not os.path.exists(env_path):
        return
    for line in open(env_path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def die(m, code=1):
    print(f"ERROR: {m}", file=sys.stderr)
    sys.exit(code)

def main():
    if len(sys.argv) < 2:
        die("usage: fix_bubble_colors.py <SID> [--apply]")
    SID = sys.argv[1].upper()
    apply_canonical = "--apply" in sys.argv

    png_path  = f"{STORIES}/{SID}.png"
    json_path = f"{STORIES}/{SID}.json"
    out_path  = f"/tmp/{SID}.flipped.png"

    if not os.path.exists(png_path):
        die(f"image not found: {png_path}")

    if os.path.exists(json_path):
        # ---- Precise mode: use HC###.json bubble indices ----
        d = json.load(open(json_path))
        scenes = d["script"]["scenes"]
        if len(scenes) < 3:
            die("expected at least 3 scenes (panels)")
        p3_dialogs = scenes[2].get("dialogs") or []
        if not p3_dialogs:
            die("panel 3 has no dialogs — cannot determine panel-3 speaker")
        panel3_speaker = p3_dialogs[-1]["speaker"]
        other_bot = "Right Bot" if panel3_speaker == "Left Bot" else "Left Bot"

        flip_indices, keep_indices, bubble_summary, idx = [], [], [], 0
        for panel_i in (0, 1):
            for dialog in scenes[panel_i].get("dialogs") or []:
                idx += 1
                spk = dialog["speaker"]
                text = dialog["text"]
                bubble_summary.append(f"  bubble {idx} (panel {panel_i+1}): {spk} — \"{text}\"")
                (flip_indices if spk == other_bot else keep_indices).append(idx)
        if not flip_indices:
            die(f"no '{other_bot}' bubbles in panels 1-2 — nothing to flip")

        print(f"--- {SID} ---  (precise mode, JSON present)")
        print(f"panel-3 speaker: {panel3_speaker}")
        print(f"flipping {other_bot} bubbles in panels 1-2: {flip_indices}")
        print(f"keeping {panel3_speaker} bubbles in panels 1-2: {keep_indices}")
        print("bubble layout:")
        print("\n".join(bubble_summary))

        flip_list = ", ".join(str(i) for i in flip_indices)
        keep_list = ", ".join(str(i) for i in keep_indices) if keep_indices else "(none)"
        prompt = (
            f"Reproduce the source image exactly except for ONE precise edit:\n\n"
            f"Counting the speech bubbles in this 3-panel comic from top to bottom "
            f"(panel 1 bubbles first, then panel 2), change ONLY bubbles "
            f"{flip_list} (the {other_bot} bubbles in panels 1 and 2) from their "
            f"current style (solid BLACK rectangle with WHITE pixel text) to: "
            f"solid WHITE rectangle background, BLACK pixel text inside, with a thin "
            f"BLACK border (1-2 px) around the rectangle.\n\n"
            f"Same shape, same size, same position, same tail direction, same text "
            f"content — only the colors flip.\n\n"
            f"Do NOT change bubbles {keep_list} ({panel3_speaker} bubbles in panels "
            f"1-2): they MUST stay BLACK rectangle / WHITE text.\n\n"
            f"Panel 3 (the bottom panel) MUST remain pixel-identical to the source. "
            f"Do not touch its bubble, its characters, or anything inside it.\n\n"
            f"Do NOT change anything else: characters, faces, eyes, mouths, antennas, "
            f"body colors, panel borders, panel sizes, banner, footer — all stay "
            f"pixel-identical to the source. Keep the exact same overall image "
            f"dimensions."
        )
    else:
        # ---- Visual mode: no JSON, Gemini infers the panel-3 bot from the image ----
        print(f"--- {SID} ---  (visual mode, no JSON)")
        print("no HC###.json found — letting Gemini identify the panel-3 bot visually")
        prompt = (
            "Reproduce the source image exactly except for one precise edit, "
            "following this visual rule:\n\n"
            "STEP 1 — Look at PANEL 3 (the bottom panel of this 3-panel comic). "
            "Identify which bot character is in it: the LEFT BOT (on the left "
            "side of the panel) or the RIGHT BOT (on the right side). If both "
            "bots appear in panel 3, pick whichever one is delivering the "
            "punchline (largest bubble / most expressive face). Call that bot "
            "the 'panel-3 bot'.\n\n"
            "STEP 2 — In PANELS 1 and 2 ONLY, find every speech bubble that "
            "belongs to the OTHER BOT (the one that is NOT the panel-3 bot). "
            "Change each of those bubbles from their current style (solid BLACK "
            "rectangle with WHITE pixel text) to: solid WHITE rectangle "
            "background, BLACK pixel text inside, with a thin BLACK border "
            "(1-2 px) around the rectangle. Same shape, same size, same "
            "position, same tail direction, same text content — only the "
            "colors flip.\n\n"
            "STEP 3 — Leave every other bubble exactly as it is. The panel-3 "
            "bot's bubbles in panels 1 and 2 stay BLACK rectangle / WHITE text. "
            "Panel 3 (the bottom panel) MUST remain pixel-identical to the "
            "source — do not touch its bubble, its characters, or anything "
            "inside it.\n\n"
            "Do NOT change anything else: characters, faces, eyes, mouths, "
            "antennas, body colors, panel borders, panel sizes, banner, footer "
            "— all stay pixel-identical to the source. Keep the exact same "
            "overall image dimensions."
        )

    load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        die("GEMINI_API_KEY not set in ~/claude-agent/.env")

    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inlineData": {"mimeType": "image/png", "data": b64}},
                {"text": "↑ Source image. Clone every pixel except for the changes specified below."},
                {"text": prompt},
            ],
        }],
        "generationConfig": {
            "temperature": 0.1,
            "imageConfig": {"aspectRatio": "3:4", "imageSize": "1K"},
        },
    }

    r = requests.post(GRAPH, params={"key": key}, json=body, timeout=180)
    if r.status_code != 200:
        die(f"Gemini API failed: {r.status_code} {r.text[:500]}")

    parts = (r.json().get("candidates", [{}])[0].get("content", {}).get("parts") or [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(inline["data"]))
            print(f"\nOK:{out_path}")
            subprocess.run(["open", out_path])
            if apply_canonical:
                # backup old, replace
                bk = f"{STORIES}/{SID}.png.bak"
                if not os.path.exists(bk):
                    subprocess.run(["cp", png_path, bk])
                subprocess.run(["cp", out_path, png_path])
                print(f"APPLIED:{png_path}  (backup: {bk})")
            return
        if p.get("text"):
            print(f"TEXT: {p['text'][:200]}", file=sys.stderr)
    die("no image in Gemini response")

if __name__ == "__main__":
    main()

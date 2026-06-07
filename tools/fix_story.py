#!/usr/bin/env python3
"""Fix something in a Holy Chip story comic via Gemini image editing.

Resubmits stories/<SID>.png to Gemini with your edit instructions; Gemini clones
every pixel of the comic EXCEPT the requested changes. Same call as the SGen
pipeline / fix_bubble_colors.py (model gemini-3.1-flash-image-preview, 3:4, 1K).

Use this whenever a finished comic needs a text/word/banner/font/color tweak
without rebuilding it in SGen.

Usage:
  fix_story.py <SID> "<what to change>"              # preview -> /tmp/<OUT>.fixed.png, opens it
  fix_story.py <SID> "<...>" --apply                 # also overwrite canonical PNG + website copy
  fix_story.py <SID> "<...>" --out HC015             # write/apply under a different SID (renumber/remake)

Multiple edits: put them as a numbered list inside the one quoted string.
"""
import os, sys, base64, subprocess, requests

HC = os.path.expanduser("~/holy-chip")
STORIES = f"{HC}/stories"
WEB = f"{HC}/website/holy-chip-site/stories"
GRAPH = ("https://generativelanguage.googleapis.com/v1beta/models/"
         "gemini-3.1-flash-image-preview:generateContent")


def load_env():
    p = os.path.expanduser("~/claude-agent/.env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def die(m):
    print(f"ERROR: {m}", file=sys.stderr); sys.exit(1)


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        die('usage: fix_story.py <SID> "<what to change>" [--apply] [--out HC###]')
    sid = args[0].upper()
    instr = args[1]
    apply_ = "--apply" in args
    out_sid = sid
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            die("--out needs a SID")
        out_sid = args[i + 1].upper()

    in_png = f"{STORIES}/{sid}.png"
    out_png = f"/tmp/{out_sid}.fixed.png"
    if not os.path.exists(in_png):
        die(f"not found: {in_png}")

    load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        die("GEMINI_API_KEY not set in ~/claude-agent/.env")

    with open(in_png, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    prompt = (
        "Reproduce the source image exactly — every character (body, face, eyes, "
        "mouth, antennas, colors), every panel border and panel height, the banner, "
        "the footer, and the overall image dimensions stay PIXEL-IDENTICAL — EXCEPT "
        "for these precise edits:\n\n" + instr + "\n\n"
        "Make ONLY the edits listed above. Anything not mentioned must remain "
        "pixel-identical to the source. Keep the same overall dimensions."
    )
    body = {
        "contents": [{"role": "user", "parts": [
            {"inlineData": {"mimeType": "image/png", "data": b64}},
            {"text": "↑ Source image. Clone every pixel except the edits specified below."},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": 0.1,
                             "imageConfig": {"aspectRatio": "3:4", "imageSize": "1K"}},
    }
    print(f"--- fixing {sid}" + (f" -> {out_sid}" if out_sid != sid else "") + " ---")
    r = requests.post(GRAPH, params={"key": key}, json=body, timeout=180)
    if r.status_code != 200:
        die(f"Gemini API failed: {r.status_code} {r.text[:500]}")
    parts = (r.json().get("candidates", [{}])[0].get("content", {}).get("parts") or [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            with open(out_png, "wb") as f:
                f.write(base64.b64decode(inline["data"]))
            print(f"OK:{out_png}")
            subprocess.run(["open", out_png])
            if apply_:
                canon = f"{STORIES}/{out_sid}.png"
                if os.path.exists(canon):
                    subprocess.run(["cp", canon, f"{canon}.bak"])
                subprocess.run(["cp", out_png, canon])
                subprocess.run(["cp", out_png, f"{WEB}/{out_sid}.png"])
                print(f"APPLIED: {canon} (+ website copy){' [backup .bak]' if os.path.exists(canon + '.bak') else ''}")
            return
        if p.get("text"):
            print(f"TEXT: {p['text'][:200]}", file=sys.stderr)
    die("no image in Gemini response")


if __name__ == "__main__":
    main()

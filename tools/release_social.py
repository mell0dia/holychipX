#!/usr/bin/env python3
"""Release a Holy Chip story to Facebook + Instagram.

- Facebook: full bilingual origin (EN + PT) + Origins URL + hashtags, native PNG.
- Instagram: TEASER caption (title + opener + first paragraph + link) because the
  full origin overflows IG's 2,200-char cap; PT teaser as the first comment; uses
  the 1080x1350 square.jpg variant (IG rejects the native 0.747 ratio).

Builds captions from the finalized blog files at run-time, posts FB then IG, and
records the post IDs to story-posts.json. Built for scheduled/manual release.
Usage: release_social.py HC###
"""
import json, re, subprocess, sys
from datetime import datetime
from pathlib import Path

HC = Path.home() / "holy-chip"
TOOLS = HC / "tools"
ADIR = HC / "stories" / "analysis"
TRACKER = HC / "content" / "story-posts.json"
IMG_DIR = HC / "stories"
SITE_WWW = "https://www.holy-chip.com"   # IG rejects redirects, needs canonical www host

HASHTAGS = "#HolyChip #AI #AGI #DailyComic"   # base; per-story theme tags appended via argv
IG_LIMIT = 2200


def strip_md(text):
    """Full body for the FB caption — keeps title, opener, all paragraphs."""
    text = text.split("\n---\n", 1)[0].strip()
    out = []
    for line in text.splitlines():
        s = re.sub(r"^#+\s*", "", line)
        s = re.sub(r"^\*(.+)\*$", r"\1", s)
        s = s.replace("--", "—")
        out.append(s)
    return "\n".join(out).rstrip()


def parse(md):
    """Return (h1, h2, opener, [body paragraphs])."""
    paras = [p.strip() for p in md.split("\n\n") if p.strip()]
    h1 = h2 = opener = None
    body = []
    for p in paras:
        if p.startswith("# "):
            h1 = p[2:].strip(); continue
        if p.startswith("## "):
            h2 = p[3:].strip().replace("--", "—"); continue
        if p.startswith("---"):
            break
        if opener is None and p.startswith("*") and p.endswith("*"):
            opener = p.strip("*").strip(); continue
        body.append(" ".join(l.strip() for l in p.splitlines()))
    return h1, h2, opener, body


def teaser(md, sid, with_hashtags):
    h1, h2, opener, body = parse(md)
    first = body[0] if body else ""
    head = f"{h1}\n\n{h2}\n\n{opener}\n\n{first}"
    if with_hashtags:
        tail = f"\n\n→ Full origin (EN/PT/ES/FR):\nholy-chip.com/origins/{sid}.html\n\n{HASHTAGS}"
    else:
        tail = f"\n\n→ holy-chip.com/origins/{sid}.html"
    cap = head + tail
    if len(cap) > IG_LIMIT:                      # safety: trim the first paragraph if needed
        over = len(cap) - IG_LIMIT + 1
        first = first[: max(0, len(first) - over)].rstrip() + "…"
        cap = f"{h1}\n\n{h2}\n\n{opener}\n\n{first}" + tail
    return cap


def build(sid):
    en_full = strip_md((ADIR / f"{sid}.blog.md").read_text())
    pt_full = strip_md((ADIR / f"{sid}.blog.pt.md").read_text())
    fb = (f"{en_full}\n\n— — — — —\n\n{pt_full}\n\n"
          f"→ Read all language versions: holy-chip.com/origins/{sid}.html\n\n{HASHTAGS}")
    ig_caption = teaser((ADIR / f"{sid}.blog.md").read_text(), sid, with_hashtags=True)
    ig_comment = teaser((ADIR / f"{sid}.blog.pt.md").read_text(), sid, with_hashtags=False)
    return fb, ig_caption, ig_comment


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
    return r.stdout


def grab(out, key):
    for line in out.splitlines():
        if line.startswith(key):
            return line.split(":", 1)[1].strip()
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: release_social.py HC###")
    sid = sys.argv[1]
    if len(sys.argv) > 2:                       # optional per-story theme hashtags
        globals()["HASHTAGS"] = HASHTAGS + " " + " ".join(sys.argv[2:])
    fb_cap, ig_cap, ig_comment = build(sid)
    img_local = str(IMG_DIR / f"{sid}.png")
    ig_url = f"{SITE_WWW}/stories/{sid}.square.jpg"

    print(f"=== {sid}: posting to Facebook (full EN+PT) ===")
    out = run(["python3", str(TOOLS / "post_facebook.py"), img_local, fb_cap])
    fb_id, fb_link = grab(out, "FB_POST_ID:"), grab(out, "PERMALINK:")

    print(f"=== {sid}: posting to Instagram (teaser EN, PT first comment) ===")
    out = run(["python3", str(TOOLS / "post_instagram.py"), ig_url, ig_cap, "--comment", ig_comment])
    ig_id, ig_link = grab(out, "IG_POST_ID:"), grab(out, "PERMALINK:")

    data = json.loads(TRACKER.read_text())
    entry = next((e for e in data["posted"] if e.get("story") == sid), None)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if entry is None:
        entry = {"story": sid}
        data["posted"].append(entry)
    if fb_id:
        entry["fb_post_id"], entry["fb_permalink"], entry["fb_posted_at"] = fb_id, fb_link, now
    if ig_id:
        entry["ig_post_id"], entry["ig_permalink"], entry["ig_posted_at"] = ig_id, ig_link, now
    data.setdefault("metadata", {})["updated"] = now
    TRACKER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"recorded: fb={fb_id} ig={ig_id}")

    if not fb_id or not ig_id:
        sys.exit(f"INCOMPLETE: fb={fb_id} ig={ig_id}")


if __name__ == "__main__":
    main()

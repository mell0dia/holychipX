#!/usr/bin/env python3
"""Release a Holy Chip story to Facebook + Instagram.

Caption is MINIMAL and identical on both platforms — just a "READ THE BLOG" link
to the origin page plus hashtags. The comic image is the content; the full
multilingual blog lives on the site, so the caption only drives traffic there.
No long text, no PT comment (changed 2026-06-07 per user).

  release_social.py HC### [extra #hashtags ...]

Posts FB then IG (IG uses the 1080x1350 square.jpg variant), records the post IDs
to story-posts.json, auto-fills the story title from the blog footer if missing.
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


def caption(sid):
    return f"Read the full blog post (EN · ES · PT · FR): holy-chip.com/origins/{sid}\n{HASHTAGS}"


def blog_title(sid):
    """Best-effort story title from the EN blog footer ('Story #NNN -- <Name>')."""
    try:
        txt = (ADIR / f"{sid}.blog.md").read_text()
        m = re.search(r"Story #\d+\s*(?:--|—)\s*(.+?)\s*\*", txt)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


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
        sys.exit("usage: release_social.py HC### [extra #hashtags ...]")
    sid = sys.argv[1]
    if len(sys.argv) > 2:                       # optional per-story theme hashtags
        globals()["HASHTAGS"] = HASHTAGS + " " + " ".join(sys.argv[2:])
    cap = caption(sid)
    img_local = str(IMG_DIR / f"{sid}.png")
    ig_url = f"{SITE_WWW}/stories/{sid}.square.jpg"

    print(f"=== {sid}: posting to Facebook ===")
    out = run(["python3", str(TOOLS / "post_facebook.py"), img_local, cap])
    fb_id, fb_link = grab(out, "FB_POST_ID:"), grab(out, "PERMALINK:")

    print(f"=== {sid}: posting to Instagram ===")
    out = run(["python3", str(TOOLS / "post_instagram.py"), ig_url, cap])
    ig_id, ig_link = grab(out, "IG_POST_ID:"), grab(out, "PERMALINK:")

    data = json.loads(TRACKER.read_text())
    entry = next((e for e in data["posted"] if e.get("story") == sid), None)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if entry is None:
        entry = {"story": sid}
        title = blog_title(sid)
        if title:
            entry["title"] = title
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

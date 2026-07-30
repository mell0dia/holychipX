#!/usr/bin/env python3
"""Post an APPROVED X (Twitter) tease for a story and record the tweet_id to
story-posts.json. The caption comes from content/x-teases.json (keyed by SID) and
must have been human-approved (never auto-generate X teases — they hide the joke).

  post_x_tease.py HC015 [--force]

Idempotent: skips if this story already has a `tease_tweet_id` (so a re-fired
launchd one-shot won't double-post). Uses the local comic PNG (X uploads it
directly — no website/Pages dependency).
"""
import json, subprocess, sys
from pathlib import Path

HC = Path.home() / "holy-chip"
PY = HC / "venv/nostr/bin/python"
TWEET = HC / "tools/tweet_image.py"
TRACKER = HC / "content/story-posts.json"
TEASES = HC / "content/x-teases.json"
IMG_DIR = HC / "stories"


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: post_x_tease.py HC### [--force]")
    sid = sys.argv[1].upper()
    force = "--force" in sys.argv

    caption = json.loads(TEASES.read_text())[sid]
    img = IMG_DIR / f"{sid}.png"
    if not img.exists():
        sys.exit(f"image not found: {img}")

    tr = json.loads(TRACKER.read_text())
    entry = next((e for e in tr.get("posted", [])
                  if (e.get("story") or e.get("id") or e.get("sid")) == sid), None)
    if entry and entry.get("tease_tweet_id") and not force:
        print(f"{sid}: tease already posted ({entry['tease_tweet_id']}) — skipping")
        return

    print(f"--- {sid}: posting X tease ---")
    r = subprocess.run([str(PY), str(TWEET), str(img), caption],
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(f"tweet failed (rc={r.returncode})")

    tid = None
    for line in r.stdout.splitlines():
        if line.startswith("TWEET_ID:"):
            tid = line.split(":", 1)[1].strip()
    if not tid:
        sys.exit("no TWEET_ID in tweet_image.py output")

    if entry is None:
        entry = {"story": sid}
        tr.setdefault("posted", []).append(entry)
    entry["tweet_id"] = tid            # primary X marker
    entry["tease_tweet_id"] = tid      # marks the approved-tease post specifically
    meta = tr.get("metadata")
    if isinstance(meta, dict):
        from datetime import datetime
        meta["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    TRACKER.write_text(json.dumps(tr, indent=2, ensure_ascii=False) + "\n")
    print(f"recorded tweet_id={tid} for {sid}")
    print(f"https://x.com/_holychip/status/{tid}")


if __name__ == "__main__":
    main()

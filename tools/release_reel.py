#!/usr/bin/env python3
"""Release one Holy Chip story as a Reel on Facebook, Instagram, X and Nostr.

  release_reel.py HC### [extra #hashtags ...] [--dry-run] [--only fb,ig,x,nostr]

Caption is the same minimal format the still releases use - a BLOG POST link
plus hashtags. The Reel is the content.

PREFLIGHT IS NOT OPTIONAL. Meta and X both fetch the mp4 from the public site,
so a Reel that is built locally but not pushed to gh-pages fails mid-run. That
is exactly how HC039 broke on 2026-08-14: Facebook succeeded, Instagram 404'd
on a missing file, the run exited non-zero, and X and Nostr were skipped. We
now HEAD the public URL first and refuse to post anything if it is not live.

IDEMPOTENCE. Each platform is skipped if the tracker already has its Reel id,
so a retry after a partial failure completes the run instead of duplicating
the posts that already succeeded. Pass --force to override.
"""
import argparse, json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

HC = Path.home() / "holy-chip"
TOOLS = HC / "tools"
TRACKER = HC / "content" / "story-posts.json"
VIDEOS = HC / "website" / "holy-chip-site" / "videos"
NOSTR_PY = HC / "venv" / "nostr" / "bin" / "python"
SITE_WWW = "https://www.holy-chip.com"

HASHTAGS = "#HolyChip #AI #AGI #DailyComic"
PLATFORMS = ("fb", "ig", "x", "nostr")

# tracker keys, per platform: (id key, permalink key, timestamp key)
KEYS = {
    "fb":    ("fb_reel_id", "fb_reel_permalink", "fb_reel_posted_at"),
    "ig":    ("ig_reel_id", "ig_reel_permalink", "ig_reel_posted_at"),
    "x":     ("reel_tweet_id", "reel_tweet_permalink", "reel_tweet_posted_at"),
    "nostr": ("nostr_reel_event_id", None, "nostr_reel_posted_at"),
}


def caption(sid, tags):
    lead = os.environ.get("THROWBACK_LEAD", "").strip()
    head = f"{lead}\n\n" if lead else ""
    return (f"{head}BLOG POST [EN,PT,FR,ES]: holy-chip.com/origins/{sid}.html"
            f"\n\n{tags}")


def public_url(sid):
    return f"{SITE_WWW}/videos/{sid}.reel.mp4"


def preflight(sid):
    local = VIDEOS / f"{sid}.reel.mp4"
    if not local.exists():
        sys.exit(f"no local Reel: {local}\n  build it: reel_vo.py {sid}")
    url = public_url(sid)
    r = subprocess.run(["curl", "-sIL", "-o", "/dev/null",
                        "-w", "%{http_code} %{size_download} %{header_json}",
                        "-m", "30", url], capture_output=True, text=True)
    parts = r.stdout.strip().split(" ", 2)
    code = parts[0][-3:]
    if code != "200":
        sys.exit(f"Reel is not live yet: {url} -> {code}\n"
                 f"  push it first: cd {VIDEOS.parent} && git add videos && "
                 f"git commit && git push origin gh-pages")
    # A 200 only proves SOMETHING is at that URL. When a Reel is rebuilt the
    # stale copy still answers 200, and Meta would happily publish the old
    # video. Compare sizes so "built but not pushed" fails here, not on air.
    size = local.stat().st_size
    try:
        remote = int(json.loads(parts[2])["content-length"][0])
    except Exception:
        remote = None
    if remote is not None and remote != size:
        sys.exit(f"the live Reel is not the local one: {url}\n"
                 f"  local {size} bytes, live {remote} bytes — push first")
    print(f"  preflight OK  {url}  ({size / 1024:.0f} KB, matches live)")
    return str(local), url


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, end="")
    return r.stdout


def grab(out, key):
    for line in out.splitlines():
        if line.startswith(key):
            return line.split(":", 1)[1].strip()
    return None


def load_entry(sid):
    data = json.loads(TRACKER.read_text())
    entry = next((e for e in data["posted"] if e.get("story") == sid), None)
    if entry is None:
        entry = {"story": sid}
        data["posted"].append(entry)
    return data, entry


def save(data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    data.setdefault("metadata", {})["updated"] = now
    TRACKER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("tags", nargs="*", help="extra #hashtags")
    ap.add_argument("--only", default=",".join(PLATFORMS),
                    help="comma list of fb,ig,x,nostr")
    ap.add_argument("--force", action="store_true",
                    help="post even if the tracker says it already went out")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sid = a.story.upper()
    want = [p.strip() for p in a.only.split(",") if p.strip()]
    bad = [p for p in want if p not in PLATFORMS]
    if bad:
        ap.error(f"unknown platform(s): {', '.join(bad)}")

    tags = HASHTAGS + (" " + " ".join(a.tags) if a.tags else "")
    cap = caption(sid, tags)
    local, url = preflight(sid)

    data, entry = load_entry(sid)
    todo = [p for p in want
            if a.force or not entry.get(KEYS[p][0])]
    done = [p for p in want if p not in todo]
    if done:
        print(f"  already posted, skipping: {' '.join(done)}")
    if not todo:
        print(f"{sid}: nothing to do")
        return 0

    print(f"=== {sid} Reel -> {' '.join(todo)} ===")
    print(cap)
    if a.dry_run:
        print("\n[dry-run] nothing posted")
        return 0

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    failed = []

    for plat in todo:
        idk, linkk, timek = KEYS[plat]
        print(f"\n--- {plat} ---")
        if plat in ("fb", "ig"):
            out = run(["python3", TOOLS / "post_reel.py", url, cap, f"--{plat}"])
            pid = grab(out, "FB_VIDEO_ID:" if plat == "fb" else "IG_POST_ID:")
            link = grab(out, "FB_PERMALINK:" if plat == "fb" else "IG_PERMALINK:")
        elif plat == "x":
            out = run(["python3", TOOLS / "tweet_video.py", local, cap])
            pid = grab(out, "TWEET_ID:")
            link = f"https://x.com/_holychip/status/{pid}" if pid else None
        else:
            out = run([NOSTR_PY, TOOLS / "post_nostr.py",
                       "--story", sid, "--video"])
            # post_nostr.py writes nostr_reel_event_id to the tracker itself.
            # Read it back rather than scraping stdout: "posted: nostr event
            # <id>" splits on the wrong colon and stores "nostr event <id>".
            _, fresh = load_entry(sid)
            pid, link = fresh.get(idk), None

        if not pid:
            failed.append(plat)
            continue
        # re-read: post_nostr.py writes the tracker itself
        data, entry = load_entry(sid)
        entry[idk] = pid
        if linkk and link:
            entry[linkk] = link
        entry[timek] = now
        save(data)
        print(f"  recorded {idk}={pid}")

    if failed:
        print(f"\nINCOMPLETE: {' '.join(failed)} failed — rerun "
              f"`release_reel.py {sid}` to retry only those")
        return 1
    print(f"\n{sid}: Reel live on {' '.join(todo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

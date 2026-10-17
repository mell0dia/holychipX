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

HASHTAGS = " ".join(__import__("hashtags").CORE + ["#DailyComic"])
PLATFORMS = ("fb", "fbvideo", "ig", "x", "nostr", "youtube")      # fbvideo = the same mp4 as a Facebook feed post ("a reel AND a post"); youtube = Short on @holy-chip

# tracker keys, per platform: (id key, permalink key, timestamp key)
KEYS = {
    "fb":    ("fb_reel_id", "fb_reel_permalink", "fb_reel_posted_at"),
    "fbvideo": ("fb_reel_video_id", "fb_reel_video_permalink", "fb_reel_video_posted_at"),
    "ig":    ("ig_reel_id", "ig_reel_permalink", "ig_reel_posted_at"),
    "x":     ("reel_tweet_id", "reel_tweet_permalink", "reel_tweet_posted_at"),
    "nostr": ("nostr_reel_event_id", None, "nostr_reel_posted_at"),
    "youtube": ("yt_reel_id", "yt_reel_url", "yt_reel_posted_at"),
}


KIND = "reel"          # reel (the comic re-read) | doc (the documentary video); set by --kind
PT = False             # --pt: the Portuguese video (<sid>.doc.pt.mp4) to the Portuguese Page only


def keys_for(plat):
    """Tracker keys. The original Reels keep their legacy names; other kinds
    (doc, doc_pt) get fb_doc_id / ig_doc_id / doc_tweet_id / nostr_doc_event_id."""
    if KIND == "reel" and not PT:
        return KEYS[plat]
    k = KIND + ("_pt" if PT else "")
    return {"fb": (f"fb_{k}_id", f"fb_{k}_permalink", f"fb_{k}_posted_at"),
            "fbvideo": (f"fb_{k}_video_id", f"fb_{k}_video_permalink", f"fb_{k}_video_posted_at"),
            "ig": (f"ig_{k}_id", f"ig_{k}_permalink", f"ig_{k}_posted_at"),
            "x": (f"{k}_tweet_id", f"{k}_tweet_permalink", f"{k}_tweet_posted_at"),
            "nostr": (f"nostr_{k}_event_id", None, f"nostr_{k}_posted_at"),
            "youtube": (f"yt_{k}_id", f"yt_{k}_url", f"yt_{k}_posted_at")}[plat]


def caption(sid, tags):
    lead = os.environ.get("THROWBACK_LEAD", "").strip()
    head = f"{lead}\n\n" if lead else ""
    if PT:
        return f"{head}A ORIGEM DA HISTÓRIA: holy-chip.com/origins/{sid}.html?lang=pt\n\n{tags}"
    return (f"{head}BLOG POST [EN,PT,FR,ES]: holy-chip.com/origins/{sid}.html"
            f"\n\n{tags}")


def video_name(sid):
    return f"{sid}.{KIND}{'.pt' if PT else ''}.mp4"


def public_url(sid):
    return f"{SITE_WWW}/videos/{video_name(sid)}"


def preflight(sid):
    local = VIDEOS / video_name(sid)
    if not local.exists():
        sys.exit(f"no local video: {local}")
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
    ap.add_argument("--kind", default="reel", choices=["reel", "doc"], help="which video: <sid>.reel.mp4 or <sid>.doc.mp4")
    ap.add_argument("--pt", action="store_true", help="the Portuguese video (<sid>.doc.pt.mp4) to the Portuguese Facebook Page only")
    ap.add_argument("--lead", default="", help="tease line above the link")
    a = ap.parse_args()
    global KIND, PT
    KIND, PT = a.kind, a.pt
    if a.lead: os.environ["THROWBACK_LEAD"] = a.lead
    if PT:                                        # the PT Page: same posting code, other page + token
        env = {}
        for line in open(os.path.expanduser("~/claude-agent/.env")):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
        os.environ["FB_PAGE_ID"] = env["FB_PT_PAGE_ID"]; os.environ["FB_PAGE_ACCESS_TOKEN"] = env["FB_PT_PAGE_ACCESS_TOKEN"]
        if a.only == ",".join(PLATFORMS): a.only = "fb,fbvideo,youtube"

    sid = a.story.upper()
    want = [p.strip() for p in a.only.split(",") if p.strip()]
    bad = [p for p in want if p not in PLATFORMS]
    if bad:
        ap.error(f"unknown platform(s): {', '.join(bad)}")

    tags = ("#HolyChip #IA #AGI" if PT else HASHTAGS) + (" " + " ".join(a.tags) if a.tags else "")
    cap = caption(sid, tags)
    local, url = preflight(sid)

    data, entry = load_entry(sid)
    todo = [p for p in want
            if a.force or not entry.get(keys_for(p)[0])]
    done = [p for p in want if p not in todo]
    if done:
        print(f"  already posted, skipping: {' '.join(done)}")
    if not todo:
        print(f"{sid}: nothing to do")
        return 0

    print(f"=== {sid} {KIND}{' PT' if PT else ''} -> {' '.join(todo)} ===")
    print(cap)
    if a.dry_run:
        print("\n[dry-run] nothing posted")
        return 0

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    failed = []

    for plat in todo:
        idk, linkk, timek = keys_for(plat)
        print(f"\n--- {plat} ---")
        if plat in ("fb", "ig", "fbvideo"):
            out = run(["python3", TOOLS / "post_reel.py", url, cap, f"--{plat}"])
            pid = grab(out, {"fb": "FB_VIDEO_ID:", "ig": "IG_POST_ID:", "fbvideo": "FB_FEEDVIDEO_ID:"}[plat])
            link = grab(out, {"fb": "FB_PERMALINK:", "ig": "IG_PERMALINK:", "fbvideo": "FB_FEEDVIDEO_PERMALINK:"}[plat])
        elif plat == "x":
            # X: 280 chars - lead + link + the X tag policy (hashtags.x_tags), not the full set
            lead = os.environ.get("THROWBACK_LEAD", "").strip()
            xcap = (f"{lead}\n\n" if lead else "") + f"holy-chip.com/origins/{sid}.html\n\n" + \
                   __import__("hashtags").x_tags(" ".join(a.tags), sid=sid)
            while len(xcap) > 280 and " #" in xcap:
                xcap = xcap.rsplit(" #", 1)[0]
            out = run(["python3", TOOLS / "tweet_video.py", local, xcap])
            pid = grab(out, "TWEET_ID:")
            link = f"https://x.com/_holychip/status/{pid}" if pid else None
        elif plat == "youtube":
            # the description IS the origin essay in the video's language (user, 2026-10-17); see youtube_meta.py
            sys.path.insert(0, str(TOOLS)); import youtube_meta as ym
            m = ym.meta(sid, "pt" if PT else "en", KIND)
            out = run([HC / "venv" / "yt" / "bin" / "python", TOOLS / "youtube_upload.py", local, "--title", m["title"],
                       "--description", m["description"], "--tags", ",".join(m["tags"]), "--lang", "pt" if PT else "en"])
            pid = grab(out, "YT_VIDEO_ID:")
            link = f"https://youtube.com/shorts/{pid}" if pid else None
        else:
            out = run([NOSTR_PY, TOOLS / "post_nostr.py",
                       "--story", sid, "--video", "--kind", KIND + (".pt" if PT else "")])
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

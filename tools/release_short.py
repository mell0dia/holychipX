#!/usr/bin/env python3
"""Release a SHORT (HC###.short.png) to FB, IG, X and Nostr - "full force".

    release_short.py HC044 "#tags ..." "<tease line>" [--dry-run]

Shorts have no origin page, so every caption links to the short itself on
stories.html. Same caption on every platform: tease line, link, tags. One image
per post (the X / Nostr one-image-lead rule). The image must already be live on
the site - IG fetches it by URL - so push the website first; the scheduler
entry is the release, the push is the preparation.

Each post is recorded in content/story-posts.json under "shorts" (never under
"posted", which the story pipelines walk). A platform already recorded for this
short is skipped, so a retry after a partial failure does not double-post.
"""
import json, os, subprocess, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

HC = Path.home() / "holy-chip"
SITE = HC / "website" / "holy-chip-site"
TRACKER = HC / "content" / "story-posts.json"
TOOLS = HC / "tools"
VENV = HC / "venv" / "nostr" / "bin" / "python"
WWW = "https://www.holy-chip.com"


def load_env():
    for line in (Path.home() / "claude-agent" / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run(cmd, key):
    """Run a poster, return the value of its KEY:value line (or None)."""
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HC)
    sys.stdout.write(r.stdout[-600:]); sys.stderr.write(r.stderr[-600:])
    for line in r.stdout.splitlines():
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if len(args) < 3:
        sys.exit(__doc__)
    sid, tags, lead = args[0], args[1], args[2]
    key = f"{sid}.short"
    png = SITE / "stories" / f"{key}.png"
    if not png.exists():
        sys.exit(f"missing {png}")
    url = f"{WWW}/stories/{key}.png"
    link = f"holy-chip.com/stories.html?story={key}"
    sys.path.insert(0, str(TOOLS)); import hashtags
    caption = f"{lead}\n\n{link}\n\n{hashtags.join('#HolyChip #AI #AGI', tags, sid=sid)}".strip()
    title = json.loads((SITE / "stories" / f"{key}.json").read_text())["script"]["banner"]["title"]
    print(f"--- {key}: {title}\n{caption}\n")

    # the image must be live before IG can fetch it
    for _ in range(30):
        try:
            if urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15).status == 200:
                break
        except Exception:
            pass
        time.sleep(20)
    else:
        sys.exit(f"{url} is not live - push the website first")
    if dry:
        print("--dry-run: image is live, nothing posted"); return

    load_env()
    d = json.loads(TRACKER.read_text())
    shorts = d.setdefault("shorts", [])
    e = next((x for x in shorts if x.get("story") == key), None)
    if not e:
        e = {"story": key, "title": title, "image": f"stories/{key}.png",
             "link": f"{WWW}/stories.html?story={key}"}
        shorts.append(e)
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    save = lambda: TRACKER.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    failed = []

    if not e.get("fb_post_id"):
        pid = run(["python3", str(TOOLS / "post_facebook.py"), str(png), caption], "FB_POST_ID")
        if pid: e.update(fb_post_id=pid, fb_posted_at=now()); save()
        else: failed.append("FB")
    if not e.get("ig_post_id"):
        pid = run(["python3", str(TOOLS / "post_instagram.py"), url, caption], "IG_POST_ID")
        if pid: e.update(ig_post_id=pid, ig_posted_at=now()); save()
        else: failed.append("IG")
    if not e.get("tweet_id"):
        sys.path.insert(0, str(TOOLS)); import hashtags
        xcap = f"{lead}\n\n{link}\n\n{hashtags.x_tags(tags, sid=sid)}"
        tid = run(["python3", str(TOOLS / "tweet_image.py"), str(png), xcap], "TWEET_ID")
        if tid: e.update(tweet_id=tid, tweet_url=f"https://x.com/_holychip/status/{tid}", tweet_posted_at=now()); save()
        else: failed.append("X")
    if not e.get("nostr_event_id"):
        nostr = f"""
import sys, time, os
sys.path.insert(0, {str(TOOLS)!r})
import post_nostr as pn
from pynostr.key import PrivateKey
from pynostr.event import Event
media = "{url}"
content = media + "\\n\\n" + {caption!r}
tags = [["t", "HolyChip"], ["t", "AI"], ["t", "{sid.lower()}"], ["r", "{WWW}/stories.html?story={key}"],
        ["imeta", "url " + media, "m image/png", "alt Holy Chip {key} - {title}"]]
pk = PrivateKey.from_nsec(os.environ["NOSTR_NSEC"])
ev = Event(content=content, tags=tags); ev.pubkey = pk.public_key.hex(); ev.created_at = int(time.time())
ev.compute_id(); ev.sign(pk.hex()); pn.publish(ev, pn.RELAYS)
print("NOSTR_ID:" + ev.id)
"""
        nid = run([str(VENV), "-c", nostr], "NOSTR_ID")
        if nid:
            e.update(nostr_event_id=nid, nostr_posted_at=now()); save()
        else: failed.append("Nostr")

    print(f"\n{key}: " + ("all four posted" if not failed else f"FAILED on {', '.join(failed)}"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

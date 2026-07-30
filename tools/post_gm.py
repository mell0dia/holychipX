#!/usr/bin/env python3
"""Holy Chip daily gm post.

Generates a gm card via gm_card.py (random unused NFT + random paragraph from
a released story), pushes the image to gh-pages, and publishes it as a kind-1
Nostr note with the phrase in the caption.

Designed to run from cron once per day.
"""
import json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
HC = HOME / "holy-chip"
TOOLS = HC / "tools"
SITE = HC / "website/holy-chip-site"
GM_DIR = SITE / "gm"
HISTORY = HC / "content/gm-history.json"
ENV_FILE = HOME / "claude-agent/.env"
SITE_URL = "https://holy-chip.com"
SITE_URL_WWW = "https://www.holy-chip.com"   # IG rejects redirects, needs canonical www host

# House-promo phrases carry a PROMO-* tag instead of an HC### story id. Route
# each to its real destination so the CTA is never a broken "/origins/" link.
PROMO_CTA = {
    "PROMO-BUILDER": ("BUILD YOUR OWN HOLY CHIP STRIP:", "holy-chip.com/builder.html"),
    "PROMO-SHOP":    ("VISIT THE SHOP:",                 "holy-chip.com/store.html"),
    "PROMO-BLOG":    ("READ THE BLOG:",                  "holy-chip.com/origins"),
}


def cta_lines(source_sid):
    """Two-line CTA (label + arrow URL) routed by the phrase's source tag:
    a PROMO-* type, an HC### story, or empty (blog hub)."""
    if source_sid in PROMO_CTA:
        label, url = PROMO_CTA[source_sid]
        return f"{label}\n→ {url}"
    if source_sid:
        return f"READ THE FULL BLOG POST:\n→ holy-chip.com/origins/{source_sid}"
    return "READ THE BLOG:\n→ holy-chip.com/origins"


def cta_url(source_sid):
    """Bare destination URL for the same routing (Nostr 'r' tag / link refs)."""
    if source_sid in PROMO_CTA:
        return "https://" + PROMO_CTA[source_sid][1]
    if source_sid:
        return f"{SITE_URL}/origins/{source_sid}"
    return f"{SITE_URL}/origins"

RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://relay.snort.social",
]


def load_env():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def parse_gm_output(stdout):
    """Extract NFT id, source story id, personality, and thought from gm_card.py stdout."""
    info = {}
    for line in stdout.splitlines():
        if line.startswith("NFT:"):
            m = re.match(r"NFT:(\d+) \((.+)\)", line)
            if m:
                info["nft_id"] = int(m.group(1))
                info["personality"] = m.group(2)
        elif line.startswith("SOURCE:"):
            info["source"] = line.split(":", 1)[1].strip()
        elif line.startswith("THOUGHT:"):
            info["thought"] = line.split(":", 1)[1].strip()
    return info


def push_to_ghpages(filename):
    """Commit + push the gm card to gh-pages and wait for live."""
    rel = f"gm/{filename}"
    run(["git", "-C", str(SITE), "add", rel])
    msg = f"Add daily gm card {filename}"
    r = subprocess.run(["git", "-C", str(SITE), "commit", "-m", msg],
                       capture_output=True, text=True)
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
        raise RuntimeError(f"commit failed: {r.stdout} {r.stderr}")
    run(["git", "-C", str(SITE), "push", "origin", "gh-pages"])

    import urllib.request
    url = f"{SITE_URL}/{rel}"
    # holy-chip.com 301-redirects to www; check the canonical host directly.
    # GitHub Pages builds can take several minutes (sometimes longer when queued),
    # so wait up to ~15 min before giving up — the old 160s window was far too short
    # and caused the card to deploy but never get posted.
    check_url = f"{SITE_URL_WWW}/{rel}"
    for i in range(90):
        try:
            req = urllib.request.Request(check_url, method="HEAD")
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.status == 200:
                return url
        except Exception:
            pass
        # If it still hasn't deployed after ~5 min, the Pages build likely hit a
        # transient error (happens occasionally). Force a fresh build with an empty
        # commit and keep waiting — this self-heals without manual intervention.
        if i == 30:
            subprocess.run(["git", "-C", str(SITE), "commit", "--allow-empty",
                            "-m", f"Retrigger Pages build for {filename}"],
                           capture_output=True, text=True)
            subprocess.run(["git", "-C", str(SITE), "push", "origin", "gh-pages"],
                           capture_output=True, text=True)
        time.sleep(10)
    raise RuntimeError(f"{check_url} never went live")


def with_cache_bust(url):
    """Append a ?v=<timestamp> query so Nostr clients re-fetch instead of
    serving a cached prior image at the same path."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={int(time.time())}"


def post_to_nostr(image_url, info):
    image_url = with_cache_bust(image_url)
    from pynostr.key import PrivateKey
    from pynostr.event import Event
    from pynostr.relay_manager import RelayManager

    pk = PrivateKey.from_nsec(os.environ["NOSTR_NSEC"])
    my_pub = pk.public_key.hex()

    phrase = info["thought"].strip()
    source_sid = info.get("source", "")
    blog_url = cta_url(source_sid)
    # Caption — link CTA first, then image URL (so it renders below the CTA),
    # then hashtags. The phrase stays in the bubble inside the image, no repeat.
    content = (
        f"gm 🟧\n\n"
        f"{cta_lines(source_sid)}\n\n"
        f"{image_url}\n\n"
        f"#HolyChip #Bitcoin #AI #gm"
    )
    tags = [
        ["t", "HolyChip"], ["t", "Bitcoin"], ["t", "AI"], ["t", "gm"], ["t", "nostr"],
        ["r", blog_url],
        ["imeta", f"url {image_url}", "m image/jpeg",
         f"alt Holy Chip gm — {phrase[:80]}"],
    ]
    ev = Event(content=content, tags=tags)
    ev.pubkey = my_pub
    ev.created_at = int(time.time())
    ev.compute_id()
    ev.sign(pk.hex())

    rm = RelayManager(timeout=8)
    for r in RELAYS: rm.add_relay(r)
    rm.publish_event(ev); rm.run_sync(); time.sleep(2); rm.close_all_relay_connections()
    return ev.id


def post_to_x(local_path, info):
    """Tweet via tools/tweet_image.py. Tweets are size-capped at 280 chars,
    so we ship a short caption rather than the full paragraph."""
    sid = info.get("source", "")
    caption = (
        f"{cta_lines(sid)}\n\n"
        f"#HolyChip #Bitcoin #AI"
    )
    r = subprocess.run([str(HC/"venv/nostr/bin/python"), str(TOOLS/"tweet_image.py"),
                        str(local_path), caption], capture_output=True, text=True)
    print(r.stdout);
    if r.returncode != 0:
        print(r.stderr); return None
    for line in r.stdout.splitlines():
        if line.startswith("TWEET_ID:"):
            return line.split(":", 1)[1].strip()
    return None


def post_to_facebook(local_path, info):
    sid = info.get("source", "")
    caption = (
        f"{cta_lines(sid)}\n\n"
        f"#HolyChip #Bitcoin #AI"
    )
    r = subprocess.run(["python3", str(TOOLS/"post_facebook.py"),
                        str(local_path), caption], capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr); return None
    out = {"id": None, "permalink": None}
    for line in r.stdout.splitlines():
        if line.startswith("FB_POST_ID:"): out["id"] = line.split(":", 1)[1].strip()
        elif line.startswith("PERMALINK:"): out["permalink"] = line.split(":", 1)[1].strip()
    return out


def post_to_instagram(image_url, info):
    sid = info.get("source", "")
    caption = (
        f"{cta_lines(sid)}\n\n"
        f"#HolyChip #Bitcoin #AI"
    )
    r = subprocess.run(["python3", str(TOOLS/"post_instagram.py"),
                        image_url, caption], capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr); return None
    out = {"id": None, "permalink": None}
    for line in r.stdout.splitlines():
        if line.startswith("IG_POST_ID:"): out["id"] = line.split(":", 1)[1].strip()
        elif line.startswith("PERMALINK:"): out["permalink"] = line.split(":", 1)[1].strip()
    return out


def main():
    load_env()
    if "NOSTR_NSEC" not in os.environ:
        sys.exit("NOSTR_NSEC not in env")

    force = "--force" in sys.argv          # allow an extra same-day post (testing/manual)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = GM_DIR / f"gm-{today}.jpg"
    if out_path.exists():
        if not force:
            print(f"already exists: {out_path}")
            sys.exit(0)
        i = 2                               # forced extra post — give it a unique filename
        while (GM_DIR / f"gm-{today}-{i}.jpg").exists():
            i += 1
        out_path = GM_DIR / f"gm-{today}-{i}.jpg"

    print(f"generating {out_path}")
    r = run([str(HC / "venv/nostr/bin/python"), str(TOOLS / "gm_card.py"), str(out_path)])
    print(r.stdout)
    info = parse_gm_output(r.stdout)
    if not info.get("nft_id"):
        sys.exit(f"could not parse gm_card output:\n{r.stdout}")

    print("pushing to gh-pages")
    url = push_to_ghpages(out_path.name)
    print(f"live: {url}")

    print("posting to nostr")
    event_id = post_to_nostr(url, info)
    print(f"nostr event: {event_id}")
    print(f"njump: https://njump.me/{event_id}")

    print("posting to x")
    tweet_id = post_to_x(out_path, info)
    print(f"tweet: {tweet_id}")

    print("posting to facebook")
    fb = post_to_facebook(out_path, info)
    print(f"fb: {fb}")

    print("posting to instagram")
    ig_url = url.replace(SITE_URL, SITE_URL_WWW, 1)
    ig = post_to_instagram(ig_url, info)
    print(f"ig: {ig}")

    # log to history
    log_entry = {
        "date": today, "nft_id": info["nft_id"],
        "personality": info["personality"], "source": info.get("source", ""),
        "thought": info["thought"], "image_url": url,
        "nostr_event_id": event_id,
        "tweet_id": tweet_id,
        "fb": fb, "ig": ig,
    }
    if HISTORY.exists():
        data = json.loads(HISTORY.read_text())
    else:
        data = {"used_ids": [], "log": []}
    data.setdefault("posts", []).append(log_entry)
    HISTORY.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # Delete-on-use — ONLY now that at least one platform actually posted. This
    # is the correct gate: on an offline day the script dies at push_to_ghpages
    # before reaching here, so the phrase is preserved and reused next run.
    posted_ok = bool(event_id) or bool(fb and fb.get("id")) or bool(ig and ig.get("id"))
    if posted_ok:
        remove_gm_phrase(info["thought"])
        print("phrase consumed (removed from gm-phrases.md)")
    else:
        print("no platform confirmed a post — phrase NOT consumed")


def remove_gm_phrase(text):
    """Remove the used phrase line from gm-phrases.md and renumber survivors.
    Plain text-file edit (no PIL), so it runs safely under post_gm's python."""
    ph = HC / "content" / "gm-phrases.md"
    if not ph.exists():
        return
    target = (text or "").strip()
    result, removed, n = [], False, 0
    for line in ph.read_text().splitlines():
        m = re.match(r"^\s*\d+\.\s+(.*\S)\s*$", line)
        if m:
            body = m.group(1).strip()
            core = re.sub(r"\s*\((?:HC\d+|PROMO-[A-Z]+)\)\s*$", "", body).strip()
            if not removed and core == target:
                removed = True
                continue
            n += 1
            result.append(f"{n}. {body}")
        else:
            result.append(line)
    if removed:
        ph.write_text("\n".join(result) + "\n")


if __name__ == "__main__":
    main()

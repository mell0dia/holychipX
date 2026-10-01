#!/usr/bin/env python3
"""merch_post.py — the weekly product posts: one MUG and one SHIRT a week.

Rules (user, 2026-10-01):
  * Only the image. No price, no copy. The caption is just the store link.
  * A different bot every post — no character repeats across mug AND shirt
    posts until all of them have been used; then the cycle restarts.
  * The photos must SHOW THE CHIP. Mug angles right/back/context1 only show
    the "HOLY CHIP!" lettering, and so does the Fitted tee's back. Those may go
    in "once in a while" (user) - about one post in three gets ONE of them as
    the LAST slide. The lead image always shows the chip.
  * The shirt alternates the two tees the store sells: Ringer, then Fitted.

Schedule: launchd com.holychip.merch, Monday 14:00 = mug, Thursday 14:00 =
shirt. Posts FB -> IG -> X -> Nostr (Nostr last: its relays are the step that
hangs). Safe to re-run: a kind already posted today is skipped.

    merch_post.py                 # today's kind from the weekday (Mon mug, Thu shirt)
    merch_post.py --kind mug      # force a kind
    merch_post.py --kind shirt --dry-run   # show the plan, touch nothing
"""
import asyncio, json, os, random, subprocess, sys, threading, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import post_gm as g   # load_env, run, push_site_file, with_cache_bust, RELAYS, NOSTR_LIMIT

HC = g.HC
SITE = g.SITE
ASSETS = SITE / "assets"
MERCH_DIR = ASSETS / "merch"                 # JPEG copies for IG (it refuses PNG)
HISTORY = HC / "content" / "merch-history.json"
STORE = "holy-chip.com/store.html"
STORE_URL = "https://www.holy-chip.com/store.html"

# The first two posts were picked by the user from samples (2026-10-01).
FIRST = {"mug": "Chip_1", "shirt": "Chip_1011"}


def bots():
    """Every bot that has both a mug and the two shirts."""
    out = []
    for p in sorted((ASSETS / "mug-mockups").glob("Chip_*_mug_left.png")):
        c = p.name.split("_mug_")[0]
        if all((ASSETS / "mockups" / f"{c}_{s}_white_front.png").exists()
               for s in ("ringer", "style5")):
            out.append(c)
    return out


LETTERING_ODDS = 1 / 3      # how often a lettering-only shot rides along at the end


def photos(kind, bot, style=None, lettering=False):
    """Photos that show the chip, lead first; with `lettering`, one shot of the
    "HOLY CHIP!" side goes last."""
    if kind == "mug":
        mm = ASSETS / "mug-mockups"
        order = ["context2", "left", "front"]      # context2 only on the 12 full sets
        out = [mm / f"{bot}_mug_{v}.png" for v in order if (mm / f"{bot}_mug_{v}.png").exists()]
        if lettering:
            extra = next((mm / f"{bot}_mug_{v}.png" for v in ("context1", "back")
                          if (mm / f"{bot}_mug_{v}.png").exists()), None)
            if extra: out.append(extra)
        return out
    sh = ASSETS / "mockups"
    if style == "ringer":                          # chip on both sides; back is biggest
        return [sh / f"{bot}_ringer_white_back.png", sh / f"{bot}_ringer_white_front.png"]
    out = [sh / f"{bot}_style5_white_front.png"]   # Fitted: the back is lettering only
    if lettering:
        out.append(sh / f"{bot}_style5_white_back.png")
    return out


def load_hist():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return {"used_bots": [], "next_shirt_style": "ringer", "posts": []}


def pick_bot(hist, kind):
    pool = bots()
    unused = [b for b in pool if b not in hist["used_bots"]]
    if not unused:                                 # full cycle done - start again
        hist["used_bots"] = []
        unused = pool
    first = FIRST.get(kind)
    if first in unused and not any(p["kind"] == kind for p in hist["posts"]):
        return first
    return random.choice(unused)


def to_jpeg(png):
    from PIL import Image
    MERCH_DIR.mkdir(exist_ok=True)
    out = MERCH_DIR / (png.stem + ".jpg")
    if not out.exists():
        im = Image.open(png).convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[3])
        bg.save(out, "JPEG", quality=90)
    return out


def wait_live(url, tries=90):
    import urllib.request
    for _ in range(tries):
        try:
            if urllib.request.urlopen(urllib.request.Request(url, method="HEAD"),
                                      timeout=10).status == 200:
                return
        except Exception:
            pass
        time.sleep(10)
    raise RuntimeError(f"never went live: {url}")


def tweet(paths, text, reply_to=None):
    argv = [str(HC / "venv/nostr/bin/python"), str(g.TOOLS / "tweet_image.py")]
    argv += ([str(paths[0]), text] if len(paths) == 1 else [*map(str, paths), "--", text])
    if reply_to:
        argv += ["--reply-to", reply_to]
    r = subprocess.run(argv, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        return None
    for line in r.stdout.splitlines():
        if line.startswith("TWEET_ID:"):
            return line.split(":", 1)[1].strip()
    return None


def meta_post(script, args, prefix):
    r = subprocess.run(["python3", str(g.TOOLS / script), *args], capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        return None
    out = {"id": None, "permalink": None}
    for line in r.stdout.splitlines():
        if line.startswith(prefix):
            out["id"] = line.split(":", 1)[1].strip()
        elif line.startswith("PERMALINK:"):
            out["permalink"] = line.split(":", 1)[1].strip()
    return out


def nostr(urls, label):
    """Lead image alone in the root note, the rest in a NIP-10 reply. Runs in a
    thread with its own event loop and a hard time limit (see post_gm)."""
    from pynostr.key import PrivateKey
    from pynostr.event import Event
    from pynostr.relay_manager import RelayManager
    pk = PrivateKey.from_nsec(os.environ["NOSTR_NSEC"])
    pub = pk.public_key.hex()

    def sign(content, tags):
        ev = Event(content=content, tags=tags)
        ev.pubkey = pub; ev.created_at = int(time.time())
        ev.compute_id(); ev.sign(pk.hex())
        return ev

    lead = g.with_cache_bust(urls[0])
    root = sign(f"{lead}\n\n{STORE_URL}",
                [["t", "HolyChip"], ["r", STORE_URL],
                 ["imeta", f"url {lead}", "m image/jpeg", f"alt Holy Chip {label}"]])
    events = [root]
    if len(urls) > 1:
        tags = [["e", root.id, g.RELAYS[0], "root"], ["p", pub]]
        tags += [["imeta", f"url {u}", "m image/jpeg", f"alt Holy Chip {label}"] for u in urls[1:]]
        events.append(sign("\n".join(urls[1:]), tags))

    rm = RelayManager(timeout=8)
    for r in g.RELAYS:
        rm.add_relay(r)
    for ev in events:
        rm.publish_event(ev)

    def go():
        asyncio.set_event_loop(asyncio.new_event_loop())
        try:
            rm.run_sync(); time.sleep(2); rm.close_all_relay_connections()
        except Exception as e:
            print(f"  nostr: relay error after publish: {e}", flush=True)
    t = threading.Thread(target=go, daemon=True)
    t.start(); t.join(g.NOSTR_LIMIT)
    if t.is_alive():
        print(f"  nostr: relays still busy after {g.NOSTR_LIMIT}s - moving on", flush=True)
    return root.id


def main():
    sys.stdout.reconfigure(line_buffering=True)
    dry = "--dry-run" in sys.argv
    kind = None
    if "--kind" in sys.argv:
        kind = sys.argv[sys.argv.index("--kind") + 1]
    else:
        kind = {0: "mug", 3: "shirt"}.get(datetime.now().weekday())
    if kind not in ("mug", "shirt"):
        print("not a merch day - nothing to do")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    hist = load_hist()
    if any(p["date"] == today and p["kind"] == kind for p in hist["posts"]) and not dry:
        print(f"{kind} already posted today - nothing to do")
        return

    bot = pick_bot(hist, kind)
    style = hist.get("next_shirt_style", "ringer") if kind == "shirt" else None
    shots = photos(kind, bot, style, lettering=random.random() < LETTERING_ODDS)
    product = "mug" if kind == "mug" else ("Ringer tee" if style == "ringer" else "Fitted tee")
    label = f"{bot} {product}"
    print(f"{today}: {kind} post - {label}")
    for p in shots:
        print(f"  {p.relative_to(SITE)}")
    print(f"  caption: {STORE}")
    if dry:
        print("  --dry-run: not posting")
        return

    g.load_env()
    jpgs = [to_jpeg(p) for p in shots]
    rels = [str(j.relative_to(SITE)) for j in jpgs]
    for rel in rels[:-1]:
        g.run(["git", "-C", str(SITE), "add", rel])
    g.push_site_file(rels[-1], f"Merch post images: {label}")   # one commit for all
    urls = [f"{g.SITE_URL_WWW}/{rel}" for rel in rels]
    for u in urls[:-1]:                         # same push - just wait until each serves
        wait_live(u)

    print("posting to facebook")
    fb = meta_post("post_facebook.py",
                   [str(shots[0]), STORE] if len(shots) == 1 else [*map(str, shots), "--", STORE],
                   "FB_POST_ID:")
    print(f"fb: {fb}")

    print("posting to instagram")
    ig = meta_post("post_instagram.py",
                   [urls[0], STORE] if len(urls) == 1 else [*urls, "--", STORE],
                   "IG_POST_ID:")
    print(f"ig: {ig}")

    print("posting to x")
    x = tweet([jpgs[0]], STORE)
    if x and len(jpgs) > 1:
        tweet(jpgs[1:5], STORE, reply_to=x)
    print(f"x: {x}")

    print("posting to nostr")                   # LAST - see post_gm
    ev = nostr(urls, label)
    print(f"nostr: {ev}")

    hist["used_bots"].append(bot)
    if kind == "shirt":
        hist["next_shirt_style"] = "style5" if style == "ringer" else "ringer"
    hist["posts"].append({"date": today, "kind": kind, "bot": bot, "product": product,
                          "images": rels, "fb": fb, "ig": ig, "tweet_id": x,
                          "nostr_event_id": ev})
    HISTORY.write_text(json.dumps(hist, indent=2, ensure_ascii=False) + "\n")
    print("logged to merch-history.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""One promo image on the English channels: Facebook -> Instagram -> X -> Nostr.

    promo_post.py KEY IMAGE "caption text" "#story #tags" [--dry-run]

KEY names the post in content/promo-posts.json; each platform is recorded the
moment it succeeds, so a re-run after a partial failure only posts what is
missing (no double posts - the merch lesson of 2026-10-06). The image is
published to the site first (assets/promo/KEY.jpg) because Instagram and Nostr
fetch by URL. X gets the core AI tags (hashtags.x_tags) + the post's own tags;
FB/IG/Nostr get the caption + the post's tags.

Run with the nostr venv python (pynostr): ~/holy-chip/venv/nostr/bin/python
"""
import json, shutil, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import post_gm as g          # load_env, push_site_file, SITE, SITE_URL_WWW
import merch_post as m       # tweet, meta_post, nostr, wait_live
import hashtags

LOG = g.HC / "content" / "promo-posts.json"


def nostr_note(content, img_url, label):
    """Root note with the caption and the image (one image: the lead rule)."""
    import asyncio, os, threading, time
    from pynostr.key import PrivateKey
    from pynostr.event import Event
    from pynostr.relay_manager import RelayManager
    pk = PrivateKey.from_nsec(os.environ["NOSTR_NSEC"])
    ev = Event(content=content, tags=[["t", "HolyChip"], ["t", "AI"],
                                      ["imeta", f"url {g.with_cache_bust(img_url)}", "m image/jpeg", f"alt Holy Chip {label}"]])
    ev.pubkey = pk.public_key.hex(); ev.created_at = int(time.time()); ev.compute_id(); ev.sign(pk.hex())
    rm = RelayManager(timeout=8)
    for r in g.RELAYS:
        rm.add_relay(r)
    rm.publish_event(ev)
    def go():
        asyncio.set_event_loop(asyncio.new_event_loop())
        try:
            rm.run_sync(); time.sleep(2); rm.close_all_relay_connections()
        except Exception as e:
            print(f"  nostr: relay error after publish: {e}", flush=True)
    t = threading.Thread(target=go, daemon=True); t.start(); t.join(g.NOSTR_LIMIT)
    return ev.id


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    key, image, caption, tags = args[0], Path(args[1]), args[2], args[3]
    log = json.loads(LOG.read_text()) if LOG.exists() else {}
    rec = log.setdefault(key, {"created": datetime.now().strftime("%Y-%m-%d %H:%M"), "image": str(image)})
    save = lambda: LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n")
    fb_ig_text = f"{caption}\n\n{tags}"
    x_text = f"{caption}\n\n{hashtags.x_tags(tags)}"
    print(f"{key}\n--- FB/IG/Nostr caption ---\n{fb_ig_text}\n--- X ---\n{x_text}")
    if dry:
        print("--dry-run: nothing posted"); return

    g.load_env()
    # publish the image (JPEG: IG refuses PNG)
    rel = f"assets/promo/{key}.jpg"
    dst = g.SITE / rel
    if not dst.exists():
        from PIL import Image
        Image.open(image).convert("RGB").save(dst, "JPEG", quality=92)
        g.push_site_file(rel, f"Promo image: {key}")
    url = f"{g.SITE_URL_WWW}/{rel}"
    m.wait_live(url)

    if not rec.get("fb"):
        rec["fb"] = m.meta_post("post_facebook.py", [str(dst), fb_ig_text], "FB_POST_ID:"); save()
        print("fb:", rec["fb"])
    if not rec.get("ig"):
        rec["ig"] = m.meta_post("post_instagram.py", [url, fb_ig_text], "IG_POST_ID:"); save()
        print("ig:", rec["ig"])
    if not rec.get("tweet_id"):
        rec["tweet_id"] = m.tweet([dst], x_text); save()
        print("x:", rec["tweet_id"])
    if not rec.get("nostr_event_id"):
        rec["nostr_event_id"] = nostr_note(f"{fb_ig_text}\n\n{g.with_cache_bust(url)}", url, key); save()
        print("nostr:", rec["nostr_event_id"])
    rec["posted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M"); save()


if __name__ == "__main__":
    main()

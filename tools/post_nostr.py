#!/usr/bin/env python3
"""Post Holy Chip stories to Nostr.

Reads ~/holy-chip/content/story-posts.json to pick the next un-posted story,
composes a tease-style kind-1 note (image URL via NIP-92 imeta), signs with
NOSTR_NSEC from ~/claude-agent/.env, publishes to a relay set, and writes
nostr_event_id + nostr_posted_at + nostr_relays back to the tracker.

Subcommands / flags:
  --profile          Publish kind-0 metadata (name, about, picture, banner,
                     website, nip05) and exit.
  --story HC###      Post a specific story (must already exist in tracker).
  --next             (default) Post the next story that has no nostr_event_id.
  --dry-run          Print the event JSON, do not sign or publish.
"""
import argparse, json, os, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "holy-chip"
TRACKER = ROOT / "content" / "story-posts.json"
ENV_FILE = Path.home() / "claude-agent" / ".env"
STORIES_DIR = ROOT / "website" / "holy-chip-site" / "stories"

SITE = "https://holy-chip.com"
RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://relay.nostr.band",
    "wss://relay.snort.social",
]

PROFILE = {
    "name": "holychip",
    "display_name": "Holy Chip",
    "about": "AI comics. New stories and in depth AI thoughts at holy-chip.com. Created by a human.",
    "website": SITE,
    "nip05": "_@holy-chip.com",
    "picture": f"{SITE}/characters/Chip_10100_paper.png",
    "banner": f"{SITE}/assets/twitter-banner.png",
    "lud16": "hugehound21@primal.net",
}


def load_env():
    if not ENV_FILE.exists():
        sys.exit(f"missing env file: {ENV_FILE}")
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_tracker():
    return json.loads(TRACKER.read_text())


def save_tracker(data):
    TRACKER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def pick_story(tracker, requested=None):
    posted = tracker["posted"]
    if requested:
        for entry in posted:
            if entry["story"] == requested:
                return entry
        sys.exit(f"no entry for {requested} in tracker")
    # Auto-pick: only stories already released on FB. Never post to Nostr
    # something that hasn't been released on the older channels yet.
    for entry in posted:
        if entry.get("fb_post_id") and not entry.get("nostr_event_id"):
            return entry
    sys.exit("all FB-released stories already on nostr — nothing to do")


def compose(entry, video=False):
    story = entry["story"]
    title = entry.get("title", story)
    origin = f"{SITE}/origins/{story}.html"
    # --video posts the animated Reel instead of the still comic. The mp4 must
    # already be live on the site; nostr clients fetch it themselves.
    media = (f"{SITE}/videos/{story}.reel.mp4" if video
             else f"{SITE}/stories/{story}.png")
    mime = "video/mp4" if video else "image/png"
    # Tease style — same as X: title, drop, link, hashtags. Never the joke.
    # Media URL FIRST so clients render it as hero at the top, text below.
    content = (
        f"{media}\n\n"
        f"HOLY CHIP !! #{story}\n"
        f"{title}\n\n"
        f"Created by a human.\n\n"
        f"→ {origin}\n\n"
        f"#HolyChip #AI #comics"
    )
    tags = [
        ["t", "HolyChip"],
        ["t", "AI"],
        ["t", "comics"],
        ["t", story.lower()],
        ["r", origin],
        ["imeta", f"url {media}", f"m {mime}", f"alt Holy Chip {story} — {title}"],
    ]
    return content, tags, media


def publish(event, relays, timeout=8):
    from pynostr.relay_manager import RelayManager
    rm = RelayManager(timeout=timeout)
    for r in relays:
        rm.add_relay(r)
    rm.publish_event(event)
    rm.run_sync()
    time.sleep(2)
    rm.close_all_relay_connections()
    return {r: "sent" for r in relays}  # pynostr doesn't easily expose per-relay OK


def cmd_profile(args):
    from pynostr.key import PrivateKey
    from pynostr.metadata import Metadata
    nsec = os.environ["NOSTR_NSEC"]
    pk = PrivateKey.from_nsec(nsec)
    meta = Metadata(**PROFILE)
    meta.created_at = int(time.time())
    meta.pubkey = pk.public_key.hex()
    meta.update()
    meta.sign(pk.hex())
    if args.dry_run:
        print(json.dumps(meta.to_dict(), indent=2))
        return
    publish(meta, RELAYS)
    print(f"profile published: {meta.id}")


def cmd_post(args):
    from pynostr.key import PrivateKey
    from pynostr.event import Event
    tracker = load_tracker()
    entry = pick_story(tracker, args.story)
    content, tags, media = compose(entry, video=args.video)
    print(f"--- {entry['story']} — {entry.get('title','')} ---")
    print(content)
    print(f"({'video' if args.video else 'image'}: {media})")
    if args.dry_run:
        print("\n[dry-run] not signing or publishing")
        return
    nsec = os.environ["NOSTR_NSEC"]
    pk = PrivateKey.from_nsec(nsec)
    event = Event(content=content, tags=tags)
    event.pubkey = pk.public_key.hex()
    event.created_at = int(time.time())
    event.compute_id()
    event.sign(pk.hex())
    publish(event, RELAYS)
    # A Reel post is recorded under its own key. Writing it to nostr_event_id
    # would make the daily backfill cron think the still comic already went
    # out, and that story would never get its image note.
    key = "nostr_reel_event_id" if args.video else "nostr_event_id"
    entry[key] = event.id
    entry[key.replace("event_id", "posted_at")] = \
        datetime.now().strftime("%Y-%m-%d %H:%M")
    entry["nostr_relays"] = RELAYS
    save_tracker(tracker)
    print(f"\nposted: nostr event {event.id}")
    print(f"njump: https://njump.me/{event.id}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", action="store_true", help="publish kind-0 metadata and exit")
    p.add_argument("--story", help="post specific HC###")
    p.add_argument("--video", action="store_true",
                   help="post the Reel mp4 instead of the still comic")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    load_env()
    if "NOSTR_NSEC" not in os.environ:
        sys.exit("NOSTR_NSEC not in env")
    if args.profile:
        cmd_profile(args)
    else:
        cmd_post(args)


if __name__ == "__main__":
    main()

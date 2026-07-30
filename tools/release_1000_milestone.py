#!/usr/bin/env python3
"""One-shot 1,000-fans-on-Facebook milestone campaign — fires 2026-07-07 08:00.

FB gets the celebration card (hc_1000_fb); X + Instagram get the "few followers /
the void" card (hc_followers_xig). Run via cron-wrapper.sh so ~/claude-agent/.env
(FB/IG/X creds) is loaded into the environment for the posting tools.

IG fetches the hosted JPG (container API needs a public URL); FB and X upload the
local PNG directly.
"""
import os, subprocess, sys
from pathlib import Path


def load_env():
    """Self-load X/FB/IG creds — the cron wrapper's env loading can't be trusted
    (tweet_image.py reads os.environ and otherwise fails 'Missing credentials')."""
    p = Path.home() / "claude-agent/.env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

HC = Path.home() / "holy-chip"
CAMP = HC / "content/campaigns"
PY_NOSTR = HC / "venv/nostr/bin/python"   # has the X (tweepy) deps, same as post_x_tease
IG_URL = "https://www.holy-chip.com/campaigns/hc_followers_xig.jpg"

FB_CAP = ("1,000 fans on Facebook, in just 20 days. We're flattered, a little "
          "concerned, and genuinely grateful -- thank you for following an AI. ❤️\n"
          "#HolyChip #AI #AGI #DailyComic")
XIG_CAP = ("Facebook just crossed 1,000 fans. Out here on X & Instagram, it's still "
           "mostly us and the void. If you can read this, help us change that.\n"
           "#HolyChip #AI #AGI #AIComics")

rc = 0
print("--- Facebook (1,000-fans card) ---")
rc |= subprocess.run(["python3", str(HC/"tools/post_facebook.py"),
                      str(CAMP/"hc_1000_fb.png"), FB_CAP]).returncode
print("--- Instagram (void card) ---")
rc |= subprocess.run(["python3", str(HC/"tools/post_instagram.py"),
                      IG_URL, XIG_CAP]).returncode
print("--- X (void card) ---")
rc |= subprocess.run([str(PY_NOSTR), str(HC/"tools/tweet_image.py"),
                      str(CAMP/"hc_followers_xig.png"), XIG_CAP]).returncode
print(f"--- done (rc={rc}) ---")
sys.exit(rc)

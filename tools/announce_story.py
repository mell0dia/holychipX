#!/usr/bin/env python3
"""announce_story.py - post a "New Story! HC### is out!" card to all four platforms.

The companion post to a story release. Run it a minute or two after the comic
goes out: the comic is the content, this is the pointer, and it carries the
origin-page link in its CTA so the second post drives the traffic the first one
cannot (the comic caption is deliberately minimal).

    announce_story.py HC040                       # default wording
    announce_story.py HC040 --text "HC040 just dropped!"
    announce_story.py HC040 --dry-run             # build the card, post nothing

It reuses the daily GM card: same sage layout, same NFT character, same posting
path. Two things differ and both matter.

THE LINE IS NOT DRAWN FROM gm-phrases.md. It is passed in with --text, so the
approved-phrase list is untouched and nothing is consumed - an announcement is
not a thought, and burning a curated phrase on one would be a waste.

THE CTA ROUTES TO THE STORY. Passing the story id makes post_gm's cta_lines()
emit "READ THE FULL BLOG POST -> holy-chip.com/origins/HC###" instead of the
blog hub, which is the whole point of the post.

Idempotence is inherited from post_gm: it refuses a second card the same day
unless --force, and forced cards get a -N suffix so they cannot clobber the
morning one. This always forces, because the daily card has usually already
gone out by the time a story is released.
"""
import argparse, os, subprocess, sys
from pathlib import Path

HC = Path.home() / "holy-chip"
TOOLS = HC / "tools"
VENV = HC / "venv" / "nostr" / "bin" / "python"

DEFAULT_TEXT = "New Story! {sid} is out!"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", help="HC### - drives both the wording and the CTA")
    ap.add_argument("--text", help=f"override the line (default: {DEFAULT_TEXT!r})")
    ap.add_argument("--nft", help="pin the character by id instead of picking at "
                    "random - check what you get before posting")
    ap.add_argument("--dry-run", action="store_true",
                    help="render the card to /tmp and post nothing")
    a = ap.parse_args()

    sid = a.story.upper()
    text = a.text or DEFAULT_TEXT.format(sid=sid)

    if not (HC / "website" / "holy-chip-site" / "stories" / f"{sid}.png").exists():
        sys.exit(f"no artwork for {sid} - is the story released?")

    if a.dry_run:
        out = f"/tmp/announce-{sid}.png"
        r = subprocess.run([str(VENV), str(TOOLS / "gm_card.py"), out,
                            "--text", text, a.nft or "-", sid],
                           capture_output=True, text=True)
        print(r.stdout or r.stderr)
        print(f"--dry-run: card at {out}, nothing posted")
        return 0

    # post_gm owns the whole pipeline: render, push the image to gh-pages, then
    # Nostr, X, Facebook, Instagram, and the history log.
    cmd = [str(VENV), str(TOOLS / "post_gm.py"), "--force",
           "--story", sid, "--text", text]
    if a.nft:
        cmd += ["--nft", a.nft]
    return subprocess.run(cmd, cwd=str(HC)).returncode


if __name__ == "__main__":
    sys.exit(main())

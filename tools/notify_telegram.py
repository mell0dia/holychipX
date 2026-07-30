#!/usr/bin/env python3
"""Send a Telegram heads-up after a (throwback) release. Best-effort — never
fails the calling job. Reads the just-updated tracker entry for the permalinks.

  notify_telegram.py <SID> <release_rc> [<x_tweet_id>]

Needs TELEGRAM_BOT_TOKEN + TELEGRAM_HOME_CHANNEL in the environment
(cron-wrapper.sh sources ~/claude-agent/.env, so they're present under cron).
"""
import json, os, sys, urllib.parse, urllib.request
from pathlib import Path

TRACKER = Path.home() / "holy-chip" / "content" / "story-posts.json"


def main():
    if len(sys.argv) < 2:
        return
    sid = sys.argv[1]
    rc = sys.argv[2] if len(sys.argv) > 2 else "0"
    xid = sys.argv[3] if len(sys.argv) > 3 else ""

    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_HOME_CHANNEL")
    if not tok or not chat:
        print("telegram: no token/chat in env, skipping")
        return

    try:
        data = json.loads(TRACKER.read_text())
        entry = next((e for e in data.get("posted", []) if e.get("story") == sid), {})
    except Exception:
        entry = {}
    title = entry.get("title", sid)

    lines = [f"\U0001F5C4️ Vault post — {sid} · {title}"]
    if rc == "0":
        if entry.get("fb_permalink"):
            lines.append(f"FB: {entry['fb_permalink']}")
        if entry.get("ig_permalink"):
            lines.append(f"IG: {entry['ig_permalink']}")
        if entry.get("nostr_event_id"):
            lines.append(f"Nostr: njump.me/{entry['nostr_event_id']}")
        if xid:
            lines.append(f"X: x.com/_holychip/status/{xid}")
        lines.append(f"Blog: holy-chip.com/origins/{sid}.html")
    else:
        lines.append(f"⚠️ release FAILED (rc={rc}) — check launchd-vault-{sid.lower()}.err")

    msg = "\n".join(lines)
    body = urllib.parse.urlencode({
        "chat_id": chat, "text": msg, "disable_web_page_preview": "true",
    }).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage",
                               data=body, timeout=15)
        print("telegram: heads-up sent")
    except Exception as ex:
        print(f"telegram notify failed: {ex}")


if __name__ == "__main__":
    main()

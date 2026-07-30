#!/bin/bash
# Scheduled first-time release of HC029 — fires 2026-06-18 08:00.
# FB + IG (comic, minimal caption) -> Nostr (after FB) -> X tease.
#
# Self-loads ~/claude-agent/.env directly (set -a; .; set +a) — the cron
# wrapper's env-loading does NOT reliably pass the X creds to tweet_image,
# which is why HC026/HC027 X teases failed. This sources them the proven way.
cd "$HOME/holy-chip" || exit 1
set -a; . "$HOME/claude-agent/.env" 2>/dev/null; set +a
RC=0

echo "--- HC029: Facebook + Instagram ---"
python3 tools/release_social.py HC029 "#Faith" "#AIethics" || RC=1

echo "--- HC029: Nostr ---"
venv/nostr/bin/python tools/post_nostr.py --story HC029 || RC=1

echo "--- HC029: X tease ---"
python3 tools/post_x_tease.py HC029 || RC=1

echo "--- done (rc=$RC) ---"
exit $RC

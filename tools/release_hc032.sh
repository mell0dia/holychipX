#!/bin/bash
# Scheduled first-time release of HC032 — fires 2026-06-23 08:00.
# FB + IG (comic, minimal caption) -> Nostr (after FB) -> X tease.
# Self-loads ~/claude-agent/.env (the cron wrapper's env-loading can't be trusted
# to pass X creds to tweet_image — this sources them the proven way).
cd "$HOME/holy-chip" || exit 1
set -a; . "$HOME/claude-agent/.env" 2>/dev/null; set +a
RC=0

echo "--- HC032: Facebook + Instagram ---"
python3 tools/release_social.py HC032 "#SmartHome" "#SmartMirror" || RC=1

echo "--- HC032: Nostr ---"
venv/nostr/bin/python tools/post_nostr.py --story HC032 || RC=1

echo "--- HC032: X tease ---"
python3 tools/post_x_tease.py HC032 || RC=1

echo "--- done (rc=$RC) ---"
exit $RC

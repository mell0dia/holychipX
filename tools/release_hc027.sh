#!/bin/bash
# Scheduled first-time release of HC027 — fires 2026-06-17 08:00.
# FB + IG (comic, minimal caption) -> Nostr (after FB) -> X tease.
# Run via cron-wrapper.sh so ~/claude-agent/.env (FB/IG/X creds) is loaded.
# The daily GM card (~morning) is the feed buffer; no extra card here.
cd "$HOME/holy-chip" || exit 1
RC=0

echo "--- HC027: Facebook + Instagram ---"
python3 tools/release_social.py HC027 "#AISafety" "#Asimov" || RC=1

echo "--- HC027: Nostr ---"
venv/nostr/bin/python tools/post_nostr.py --story HC027 || RC=1

echo "--- HC027: X tease ---"
python3 tools/post_x_tease.py HC027 || RC=1

echo "--- done (rc=$RC) ---"
exit $RC

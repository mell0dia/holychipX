#!/bin/bash
# One-shot re-release of HC026 with the CORRECTED comic art (FB + IG + X).
#
# Nostr is intentionally skipped: its existing post references the image URL
# (holy-chip.com/stories/HC026.png), which now serves the new PNG, so it already
# shows the corrected art. FB / IG / X each uploaded a copy of the old image, so
# those are the ones that need delete-and-repost (the user deletes the old posts).
#
# Run via cron-wrapper.sh so ~/claude-agent/.env (FB/IG/X creds) is loaded.
cd "$HOME/holy-chip" || exit 1
RC=0

echo "--- HC026 re-release: Facebook + Instagram ---"
python3 tools/release_social.py HC026 "#Productivity" "#Automation" || RC=1

echo "--- HC026 re-release: X tease ---"
python3 tools/post_x_tease.py HC026 || RC=1

echo "--- done (rc=$RC) ---"
exit $RC

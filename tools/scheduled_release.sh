#!/bin/bash
# Scheduled story release: FB + IG (release_social.py) then Nostr (post_nostr.py).
# Nostr only runs if the FB+IG step succeeded (never post Nostr before FB).
# X is NOT included — it needs a human-approved tease.
# Usage: scheduled_release.sh <SID> "<theme hashtags>"
set -uo pipefail
SID="${1:?usage: scheduled_release.sh HC### \"#tags\"}"
THEME="${2:-}"
VENV=/Users/rmello/holy-chip/venv/nostr/bin/python
cd /Users/rmello/holy-chip || exit 1

echo "--- $SID: FB + IG ---"
python3 tools/release_social.py "$SID" "$THEME"
RC=$?

if [ $RC -eq 0 ]; then
  echo "--- $SID: Nostr ---"
  "$VENV" tools/post_nostr.py --story "$SID"
else
  echo "release_social failed (rc=$RC) — skipping Nostr"
fi
exit $RC

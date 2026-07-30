#!/bin/bash
# "From the Vault" throwback re-release of an early story. Same channels as
# scheduled_release.sh (FB+IG via release_social.py, then Nostr, then X) but the
# FB/IG caption gets a "FROM THE VAULT" lead line (THROWBACK_LEAD) so it reads as
# intentional curation, not a duplicate. X uses a freshly-generated tease; Nostr
# re-broadcasts (reposts are fine there).
# Usage: throwback_release.sh <SID> "<theme tags>" "<lead line>"
set -uo pipefail
SID="${1:?usage: throwback_release.sh HC### \"#tags\" \"<lead>\"}"
THEME="${2:-}"
export THROWBACK_LEAD="${3:-}"
VENV=/Users/rmello/holy-chip/venv/nostr/bin/python
cd /Users/rmello/holy-chip || exit 1

echo "--- $SID: FB + IG (throwback) ---"
python3 tools/release_social.py "$SID" "$THEME"
RC=$?

XID=""
if [ $RC -eq 0 ]; then
  echo "--- $SID: Nostr ---"
  "$VENV" tools/post_nostr.py --story "$SID"
  echo "--- $SID: X ---"
  XID=$(python3 tools/x_tease.py "$SID" "$THEME" | grep '^TWEET_ID:' | cut -d: -f2)
else
  echo "release_social failed (rc=$RC) — skipping Nostr + X"
fi

# Morning Telegram heads-up (best-effort, never fails the job)
python3 tools/notify_telegram.py "$SID" "$RC" "$XID" || true
exit $RC

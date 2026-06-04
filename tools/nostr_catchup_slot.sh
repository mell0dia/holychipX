#!/bin/bash
# One-shot Nostr catch-up post. Releases the next un-nostred story (auto-pick,
# story-only — no card), then deletes THIS slot's own crontab line so it never
# repeats. Arg: <slot-tag> (e.g. slot2). Auto-pick is self-healing: if an earlier
# slot failed, this one picks up the story it missed.
set -uo pipefail
TAG="${1:?usage: nostr_catchup_slot.sh <slot-tag>}"

/Users/rmello/holy-chip/venv/nostr/bin/python /Users/rmello/holy-chip/tools/post_nostr.py
RC=$?

# Self-remove this slot's cron line (idempotent; survives the post's exit code).
( crontab -l 2>/dev/null | grep -v "nostr_catchup_slot.sh ${TAG}" ) | crontab -

exit $RC

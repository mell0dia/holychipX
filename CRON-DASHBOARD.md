# Holy Chip Cron Job Dashboard

Every scheduled job that touches Holy Chip. Updated 2026-08-18.

**Releases run from launchd, not cron.** cron silently skips anything scheduled
while the Mac is asleep and never returns to it, which quietly lost three
releases on 1–3 Aug 2026. launchd runs a missed `StartCalendarInterval` job when
the machine wakes. Anything that publishes belongs in launchd.

## launchd (~/Library/LaunchAgents/)

| job | when | what it runs |
|---|---|---|
| `com.holychip.daily-gm` | 08:57 daily | `post_gm.py` — the morning card to all four platforms |
| `com.holychip.release-queue` | 09:00 daily | `release_queue.py` — the one story due today, if any |
| `com.holychip.healthcheck` | 09:00 daily | `holychip-submission-healthcheck.sh` |
| `com.holychip.submissions` | 09:15 daily | `holychip-check-submissions.sh` |

## cron (`crontab -l`)

| job | when | what it runs |
|---|---|---|
| `youtube-monitor` | 09:00 daily | `youtube-pipeline.sh` |
| `nostr-backfill` | 09:00 daily | `post_nostr.py` — the oldest FB-released story with no Nostr note |
| `story-check` | 10:00 daily | site reachability ping |
| `git-autocommit` | 23:00 daily | `git-autocommit.sh` |

## The release queue

`release_queue.py` takes the OLDEST entry that is due, not strictly today's, so a
missed day drains one release per run instead of firing a backlog at once. An
entry already marked `done` is skipped, so a manual run cannot double-post.

Three kinds of entry:

- **`reel`** → `release_reel.py` — the voice-over Reel to FB + IG + X + Nostr.
  Idempotent per platform: rerunning after a partial failure posts only what is
  still missing.
- **`vault`** → `throwback_release.sh` — a "FROM THE VAULT" still with a lead line.
- anything else → `scheduled_release.sh` — a normal still release.

Do NOT call `release_social.py` from here. It is FB + IG only, and calling it
directly gave HC038 (2026-08-09) half its reach — no Nostr, no X. Both wrappers
above do FB+IG → Nostr → X.

**Current schedule.** The vault stills finish 2026-08-24 (HC004 08-20, HC006
08-22, HC016 08-24). The daily Reel run is HC001 on **2026-08-25** through HC039
on **2026-10-01**, one story a day. HC000 went out by hand on 2026-08-18.

## Logging

`~/claude-agent/tools/cron-wrapper.sh` wraps every job above and writes
`~/claude-agent/logs/<job-name>-YYYY-MM-DD.log`.

Watch out when reading a vault run's log: the wrapper pipes `x_tease.py`'s stdout
into a shell variable, so `TWEET_ID` shows 0 even on a successful post. The
tracker (`content/story-posts.json`) and the live account are the sources of
truth, not the log.

**RULE:** any new scheduled job must be added to this file and to PROJECT.md.

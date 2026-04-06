# Holy Chip — Project Manifest
# This is the single source of truth for project structure.
# Updated: 2026-04-03

## Data Files (~/holy-chip/content/)
- **dm-tracker.json** — DM outreach tracker: targets, who got what, when
- **influencers.json** — Twitter influencers we follow/track
- **phrases.json** — Profound phrases extracted from videos + tweets
- **video-library.json** — Video digests (summaries, key points, topics)
- **influencers_db.json** — Influencer tweet database: every captured tweet + extracted phrases (written by influencer-monitor.py)
- **MASTER-PLAYBOOK.md** — Brand voice, narrative rules, content strategy
- **influencer-target-list.md** — Original DM target research (tiered)
- **dm-target-list-researchers.md** — AI researcher targets

## Scripts (~/holy-chip/tools/)
- **dm-blast.py** — Daily outreach: DMs first (up to 20 sent OR 20 denied), then quote tweets for denied. 5s delay between attempts. Max 60 attempts/run. Never contacts anyone twice.
- **video-digest.py** — YouTube URL → transcript → Haiku summary → save to library
- **phrase-extract.py** — Extract profound phrases from video transcripts
- **hashtag-hunter.py** — (deprecated, replaced by lead-finder.py)
- **influencer-monitor.py** — Dedicated influencer tracker (4x/day). Detects new tweets, extracts phrases via Haiku, saves to influencers_db.json. Separate from other data pipelines.
- **lead-finder.py** — Find high-profile accounts (50K+ followers) tweeting about story topics. Sends tweet links + story image to Telegram for manual reply. Reads from story-campaigns.json.
- **phrase-extract.py** — Extract profound phrases from video transcripts via Haiku API. Saves to phrases.json.
- **punch-generator.py** — Generate 5-word-max .pre punch lines from phrases.json via Haiku. Saves to pre-punches.json. Commands: --list, --pending, --next, --mark-posted N, --add "TEXT". Run with no args to auto-process new phrases.
- **tweet_image.py** — Post tweets with image attachments
- **index.js** — SGen pre-image generator (needs GEMINI_API_KEY)

## CLI Shortcuts (~/.local/bin/)
- **runSonnet** — Hermes chat on Sonnet (default execution)
- **runHaiku** — Hermes chat on Haiku (cheap/fast)
- **runOpus** — Hermes chat on Opus (planning only)
- **runLocal** — Hermes chat on Gemma via Ollama (free, local)
- **xcli** — Tweet wrapper (x-cli with correct creds)
- **x-dm** — Send DMs with image attachments

## Comic Assets
- **~/holy-chip/stories/** — HC000-HC018 (.png, .pre.png, .json)
- **~/holy-chip/characters/** — Chip 0, Chip 1 base characters
- **~/holy-chip/campaigns/** — Per-story campaign folders with post tracking

## Hermes Config (~/.hermes/)
- **config.yaml** — Models, providers, smart routing, fallbacks, custom_providers (ollama)
- **.env** — API keys (Anthropic, Telegram, X/Twitter, FAL, HF)
- **prefill.md** — Telegram bot behavior (YouTube handling)
- **skills/** — 79+ skills including video-digest, holy-chip-social-media

## Data Files (~/holy-chip/content/) — continued
- **story-campaigns.json** — Story config: hashtags, reply templates, DM text per story. Both dm-blast.py and lead-finder.py read from this.

## Cron Jobs (automated)
- Full details, file mutations, and logs: **~/holy-chip/CRON-DASHBOARD.md**
- **daily-ai-briefing** — Daily: influencer tweet report (Haiku → Telegram)
- **daily-token-monitor** — Hourly: token/cost report (Haiku → Telegram)
- **holy-chip-story-check** — Daily: detect new stories on website
- **lead-finder-morning** — Daily: find 50K+ follower tweets for manual reply
- **holy-chip-dm-blast** — Daily: DM outreach + quote tweet fallback (writes dm-tracker.json)
- **holy-chip-story-poster** — Every 3 days: post next story to Twitter (writes story-posts.json)
- **influencer-monitor** — 4x/day: capture new influencer tweets + extract phrases (writes influencers_db.json)
- RULE: Any new cron must be added to CRON-DASHBOARD.md + this file

## War Room
- **~/holy-chip/warroom/** — Local web dashboard (being built)
- Tabs: token costs, phrases (keep/delete), stories (filterable)

## Relevant Skills (in ~/.hermes/skills/)
- **hermes-ollama-local** — Running Gemma/local models with Hermes (critical gotchas)
- **video-digest** — YouTube transcript → summary → save pipeline
- **holy-chip-daily-ops** — Morning briefing, DM outreach, phrase collection
- **holy-chip-social-media** — Posting flow, hooks, campaigns, narrative rules
- **hermes-local-dashboard** — War room Flask dashboard

## Logging (~/holy-chip/logs/)
- **cron-wrapper.sh** — Wraps all cron commands. Logs to ~/holy-chip/logs/<job-name>-YYYY-MM-DD.log
- **cron-history.log** — One-liner per run: timestamp | job | OK/FAIL | duration
- All 6 cron jobs updated to use cron-wrapper.sh for persistent logging

## Key Rules
- Stories from chips' perspective. Humans are 3rd person.
- Never define who's in charge. Credit: "created by a human."
- DMs: if send fails (403 closed), auto-try next target
- Model tiering: Opus=planning, Sonnet=execution, Haiku=cron, Gemma=free backup
- Gemma needs smart_model_routing disabled to work with Hermes
- Bitcoin/stablecoins/crypto predictions: always flag these

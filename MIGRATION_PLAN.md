# Holy Chip Migration Plan — Local → Remote Machine

**Status (2026-04-27):** ✅ COMPLETE. 7 of 7 functions migrated, final cleanup done. See `MIGRATION_COMPLETE.md` for the post-migration state summary; this file is the historical plan + change log.
**Created:** 2026-04-17
**Goal:** Move all Holy Chip work from this machine to the remote machine on the same home LAN.
**Strategy:** Function-by-function migration. Keep local as dormant hot-spare until remote is proven.

---

## 👉 Resume Point (for next session)

**Next function:** #8 — Final cleanup.

**Scope of #8:**
1. Root `CLAUDE.md` — remove or update the "Project: Holy Chip Store" section (it describes local workflow, but website is shared and store work happens on either machine now — needs updating, not deletion)
2. `MEMORY.md` index — Holy Chip Submission Pipeline section says cron runs locally; already partially updated to note "now runs on hchip remote (local disabled 2026-04-22)" but worth a full sweep
3. `~/.local/bin/holychip-*.sh` scripts on local — keep as hot-spare, or archive
4. `~/Library/LaunchAgents/com.holychip.*.plist.disabled` — already disabled, decide whether to delete
5. Keychain entries (12+) — decide which to migrate to remote vs. keep local-only (see "Secrets Transfer Strategy")
6. `HolyChip/Generator/` — archive (obsolete, superseded by SGen)
7. Decommission marker — final state docs once everything's confirmed

**Remote access:** `ssh hchip` → `rmello@rmellos-MacBook-Pro.local` (Bonjour, DHCP-proof). Key: `~/.ssh/id_ed25519_hchip`, passwordless.

---

## Guiding Principles

1. **Keep local intact until remote is proven** — no deletions until user explicitly says "decommission."
2. **Function-by-function, not big-bang** — migrate one feature at a time, test, verify, then move on.
3. **Local goes dormant** once remote owns a function (stop cron, stop writes, keep files).
4. **Rollback must be <5 minutes** at any point.
5. **Private home LAN** — no gpg/encryption layer needed beyond SSH/SMB's built-in encryption.
6. **Per-function sign-off** — user green-lights each function's migration before next starts.

---

## The 7-Step Loop (per function)

For each function we migrate:

1. **Scope** — list files, skills, env vars, keychain entries, external services, deps
2. **Transfer** — rsync/scp files to remote
3. **Configure** — env vars, keychain entries, dependency install on remote
4. **Test** — run end-to-end on remote with a known input
5. **Verify** — output matches local (side-by-side or diff)
6. **Activate** — make remote primary for this function; local dormant (stop cron, stop writes)
7. **Dormant on local** — keep files but don't run; revisit in final cleanup phase

---

## Migration Order (simplest → most interconnected)

| # | Function | Why that position | Status |
|---|---|---|---|
| 1 | **SGen** (story generator) | Self-contained; Gemini/FAL keys only | ✅ Done 2026-04-22 — remote at `~/holy-chip/SGen/` |
| 2 | ~~**Generator** (comic generator)~~ | **OBSOLETE** — superseded by SGen; no migration needed. Local folder to be archived in step 8. | ⛔ Skipped 2026-04-22 |
| 3 | **`/analyzeStory` skill** | Pure logic, no live services | ✅ Done 2026-04-22 — remote version already authoritative and correctly path-adapted; local marked DORMANT at top of file. Awaits user to test on remote via Claude Code. |
| 4 | **`/origins` pipeline** | Depends on SGen + analyzeStory | ✅ Done 2026-04-22 — converted skill → command, deployed to remote `~/.claude/commands/origins.md` with paths adapted to `~/holy-chip/website/holy-chip-site/`. Local SKILL.md marked DORMANT (`disable-model-invocation: true`). edge-tts not yet installed on remote (optional, install on first audio request). |
| 5 | **Website tooling** (`holy-chip-site`) | gh-pages/Netlify cloud-hosted; local tooling only | ✅ Done 2026-04-22 — **SHARED (both machines active)**. Remote at `~/holy-chip/website/holy-chip-site/`, branch `gh-pages`, SSH remote. Sync discipline: `git pull` before editing on either side. |
| 6 | **Submission pipeline** (`/submissions`) | Supabase + Resend + cron + live state | ✅ Done 2026-04-22 — cron now runs on remote (`com.holychip.healthcheck` 9:00, `com.holychip.submissions` 9:15). Local plists renamed `.plist.disabled` + unloaded. Local SKILL.md marked DORMANT. Supabase is source of truth — no state file sync needed. |
| 7 | **NFT tooling** (`HolyChip/nft/`) | Phantom wallet; low cadence | ✅ Done 2026-04-27 — discovered already on remote at `~/holy-chip/nft/` (transferred during earlier rsync). All files byte-identical. npm deps installed (4/4), syntax-check passes (8/8), ffmpeg+python3 present. No Solana CLI needed (scripts use JS SDK). No keypair/.env files in folder. Local CLAUDE.md marked DORMANT. |
| 8 | **Final cleanup** — root CLAUDE.md, MEMORY.md, LEARNING.md, keychain | Only after 1–7 proven on remote | Pending — next |

---

## Full Holy Chip Footprint on This Machine

### 1. Main code folder (~815 MB)
- `HolyChip/` — Generator, SGen, nft, website, .env files, LEARNING.md, CLAUDE.md

### 2. Off-tree asset folders (~253 MB)
- `~/Desktop/Holychip Personagens` — **221 MB** — rejected NFT images, stock pile. One-time copy.
- `~/Desktop/Pessoal/holy-chip Originals` — **32 MB** — one-time copy
- `~/Devel/Target/svelte/_holy-chip` — **EXCLUDED** (old 2018, not migrating)
- `~/Devel/Target/svelte/holy-chip` — **EXCLUDED** (old 2018, not migrating)

### 3. Memory files (10) — `~/.claude/projects/-Users-wakanda2-Desktop-4D-Documents-Claude/memory/`
- `holychip.md`
- `holychip-submission.md`
- `nft-creator-wallets.md`
- `nft-image-consolidation.md`
- `feedback_nft_cnft_not_regular.md`
- `feedback_nft_copy_then_delete.md`
- `feedback_nft_cost_transparency.md`
- `feedback_submission_emails.md`
- `feedback_submission_quality_gate.md`
- `project_sgen_dual_bubbles.md`

Plus Holy Chip-related lines inside `MEMORY.md` index (Submission Pipeline section + launchd entries).

### 4. Skills (project-level `.claude/skills/`)
- `submissions/`
- `origins/`
- `analyzeStory` — location TBD (user-level or project-level)

### 5. launchd scripts + plists
- `~/.local/bin/holychip-check-submissions.sh`
- `~/.local/bin/holychip-submission-healthcheck.sh`
- `~/Library/LaunchAgents/com.holychip.healthcheck.plist` (fires 9:00 AM daily)
- `~/Library/LaunchAgents/com.holychip.submissions.plist` (fires 9:15 AM daily)

### 6. Runtime state + logs — `~/.local/share/`
- `holychip-healthcheck.log`
- `holychip-submissions.log`
- `holychip-submissions-pending.json` — **live state**
- `holychip-submissions-confirmed.json` — **live state**
- `holychip-submissions-clarify.json` — **live state**
- `solana/install/` — Solana CLI install (not wallet — wallet is in Phantom browser ext)

### 7. Keychain entries (12+)
- `RM Printify rico.duoba api-key`
- `RM @_holychip API Consumer Key`
- `RM @_holychip API Key Consumer Key Secret`
- `RM @_holychip Access Token`
- `RM @_holychip Access Token Secret`
- `RM @_holychip Bearer Token`
- `RM @_holychip X account rm@mellodia.com`
- `RM Supabase rico.duoba`
- `RM resend key holychip_netlify rico.duoba key`
- `RM bot1.holychip.gmail gmail account`
- `RM holychip twitter @_holychip`

### 8. `.env` files (5, inside `HolyChip/`)
- `HolyChip/.env` — X/Twitter, Anthropic, Gemini, Telegram, FAL.ai
- `HolyChip/SGen/.env`
- `HolyChip/Generator/.env`
- `HolyChip/website/holy-chip-site/.env.production.local`
- `HolyChip/website/holy-chip-site/.env.check`

### 9. Cross-references (handled in final cleanup, step 8)
- Root `CLAUDE.md` — "Project: Holy Chip Store" section
- Root `LEARNING.md` — Holy Chip entries (if any)
- `MEMORY.md` index — Holy Chip Submission Pipeline section + launchd entries

---

## Secrets Transfer Strategy

On private home LAN, SSH/scp encryption is sufficient. No gpg layer needed.

- **`.env` files** — rsync over SSH; plain text fine over trusted LAN
- **Keychain entries** — cannot rsync; per-item export via `security find-generic-password -w`, re-import via `security add-generic-password`. User approves each entry before export.
- **Phantom wallet (Solana)** — install Phantom on remote browser, import via seed phrase. No file transfer.
  - ⚠ Phase 0 task: check `HolyChip/nft/` for any local keypair JSON files. If any, treat as highest-sensitivity secret — user moves on USB stick, not network.
- **CLI tool auth (gh, netlify, stripe)** — re-authenticate on remote via their browser flows. Do not copy sessions.
- **Shell profile (`~/.bash_profile`)** — selective grep, hand-pick relevant lines, append to remote's profile. Do not overwrite.
- **`~/.claude/settings.json`** — selective merge only, never wholesale overwrite.

---

## Watch-Outs

1. **Double-running cron** — if both machines have `com.holychip.*.plist` loaded, both will write to Supabase. **Unload local launchd before remote starts firing.**
2. **Live state files** — `holychip-submissions-*.json` in `~/.local/share/`. Do NOT overwrite remote's version with local's. Compare first; if remote has been running, its state is authoritative.
3. **iCloud Desktop sync** — `.env` files in Desktop sync to iCloud if enabled. Worth checking on both machines (System Settings → Apple ID → iCloud → Drive → Desktop & Documents).
4. **Solana keypair files** — if any exist in `HolyChip/nft/`, treat with highest care. Transfer via USB, not network.
5. **Root `CLAUDE.md` Holy Chip section** — do not remove until ALL functions migrated and verified.

---

## Rollback (at any stage)

While local is dormant, rollback takes ~2 minutes:
1. Rename `~/Library/LaunchAgents/com.holychip.*.plist.disabled` back to `.plist`
2. `launchctl load` both plists
3. Remove dormancy note from `CLAUDE.md`
4. Unload on remote

---

## Current State / Next Action

**What's been done:** Plan documented, footprint inventoried. Nothing transferred, nothing modified.

**Blocking items (need from user):**
1. Remote hostname/IP + username (e.g., `wakanda@192.168.1.50`)
2. SSH enabled on remote? Yes/no
3. Green light on function-by-function framework + proposed order
4. Confirm SGen first (or reorder)

**First function to migrate once unblocked:** SGen (see Step 1 in Migration Order table above).

---

## Pilot: SGen Migration (Function #1)

When green-lit, SGen migration will run through the 7-step loop:

1. **Scope:**
   - `HolyChip/SGen/` folder (~250 MB)
   - `HolyChip/SGen/.env`
   - Gemini + FAL.ai keys (likely also in parent `HolyChip/.env`)
   - Memory file: `project_sgen_dual_bubbles.md`
   - SGen section of `HolyChip/LEARNING.md`
   - Node/Python deps (confirm `package.json` / `requirements.txt`)

2. **Transfer:** rsync over SSH (dry-run first)

3. **Configure:** Gemini + FAL keys into remote's `.env`; install deps

4. **Test:** Run one known story generation on remote

5. **Verify:** Compare output to same run on local

6. **Activate:** Remote becomes SGen primary; local dormant

7. **Dormant local:** Marker file in `HolyChip/SGen/`, stop using local. Move to function #2.

---

## Change Log

- **2026-04-17** — Plan created. Awaiting green light to start Phase 0 scoped to SGen.
- **2026-04-21** — SSH passwordless auth set up (key: `id_ed25519_hchip`, alias `hchip`). Remote confirmed at `rmello@192.168.1.72` with existing `~/holy-chip/` workspace (git repo, full Twitter/DM/influencer toolchain, separate `tools/sgen-pre` pre-image CLI — not the same as local SGen).
- **2026-04-22** — **SGen migration complete.** Transferred 2.87 MB (210 files) → `~/holy-chip/SGen/`. `npm install` + `npm run build` + dev server verified (HTTP 200). End-to-end story generation confirmed working via Gemini API on remote. Local SGen marked DORMANT.
- **2026-04-22** — **Function #2 (Generator) skipped.** User confirmed Comic Generator was superseded by SGen. No migration needed; local `HolyChip/Generator/` to be archived in step 8. Next: analyzeStory skill.
- **2026-04-22** — **Function #3 (`/analyzeStory`) complete (no-transfer migration).** Diff showed remote version already correctly adapted to `~/holy-chip/stories/` paths; local version references Desktop paths that don't exist on remote. No transfer needed. Local `~/.claude/commands/analyzeStory.md` prepended with DORMANT notice to prevent accidental local invocation. Verification pending user to test `/analyzeStory` via Claude Code on remote. Next: `/origins` pipeline.
- **2026-04-22** — **Function #6 (Submissions pipeline) complete — cutover done.** 5-phase migration: (0) Inventoried local — skill at `.claude/skills/submissions/SKILL.md`, 2 shell scripts in `~/.local/bin/`, 2 plists in `~/Library/LaunchAgents/`, 3 live JSON state files in `~/.local/share/`. Scripts use `$HOME` (portable). Secrets (Supabase service key, Resend API key) are embedded inline in the check-submissions script — no keychain migration needed for the pipeline. (1) Converted SKILL.md → command-style `hchip:~/.claude/commands/submissions.md` (10 KB). Rsync'd both scripts to `hchip:~/.local/bin/` preserving exec bits. (2) Wrote remote-adapted plists with `/Users/rmello/` paths, scp'd as `.plist.disabled` so they wouldn't auto-load. (3) Manual dry-run on remote: healthcheck logged `OK (preflight:204 post:200 supabase:401)`, submissions check logged `pending:1 confirmed:2 clarify:0` — byte-identical state files to local (proves Supabase is source of truth, no sync needed). (4) Cutover: local `launchctl unload` + rename both plists to `.disabled`; remote rename `.disabled` → `.plist` + `launchctl load`. Confirmed `launchctl list | grep holychip` shows 2 entries on remote, 0 on local. Local `SKILL.md` marked DORMANT (`disable-model-invocation: true`). First remote cron fires tomorrow 2026-04-23 at 9:00 AM. Next: NFT tooling.
- **2026-04-22** — **Function #4 (`/origins`) complete.** Converted skill (YAML frontmatter) → command-style markdown matching remote's `analyzeStory.md` convention. Deployed to `hchip:~/.claude/commands/origins.md` (8.9 KB) with all paths adapted from `~/Desktop/4D Documents/Claude/HolyChip/...` to `~/holy-chip/website/holy-chip-site/...`. Added sync-discipline note at top (git pull before editing). Local `.claude/skills/origins/SKILL.md` marked DORMANT with `disable-model-invocation: true`. edge-tts not pre-installed on remote — the command docs tell Claude to `pip3 install edge-tts` only if user asks for audio. User to restart Claude Code session on remote to pick up the new command (same pattern as analyzeStory). Next: Submissions pipeline.
- **2026-04-27** — **Function #8 keychain step complete.** 10 of 11 Holy Chip keychain entries mirrored to remote. **`RM Phantom Holychip Seed` intentionally NOT mirrored** — seed phrase stays local-only per user decision (single-machine attack surface preferred for the highest-sensitivity item; remote already has Phantom browser extension imported via the seed phrase if needed). Mirror process used file-export pattern after macOS blocked direct SSH-driven `security add-generic-password` calls with "User interaction is not allowed" (a hard restriction — keychain adds require GUI session context). Workflow: (1) local export script read 10 entries via `security find-generic-password -w` to `/tmp/holychip-keychain-export.json` (mode 600). (2) scp to remote `/tmp/`. (3) user ran `python3 /tmp/import_keychain.py` in **VNC Terminal on remote** (GUI context — adds work). (4) Script auto-deleted JSON on success. (5) Local `/tmp/*.json` and all helper scripts cleaned up. All 10 entries verified present on remote keychain. Used `-A` flag (any-app access) and `-U` (update if existing). Settings: added `permissions.deny` rules in `~/.claude/settings.json` to block `security dump-keychain -d` (which exposes passwords) at the Claude Code permission layer.
- **2026-04-27** — **Function #7 (NFT tooling) complete (silent migration discovered).** SSH config updated to use Bonjour name `rmellos-MacBook-Pro.local` (DHCP-proof; remote IP had drifted from `.72` to `.67`). Side-by-side inventory found local and remote `nft/` folders nearly identical (1052 vs 1051 files, only diff is local's `.DS_Store`). 10/10 key files SHA256-match. Remote was populated on Apr 24 — likely during the website rsync, never logged. Functional check on remote: npm ls shows 4/4 deps installed (`@metaplex-foundation/js@0.20.1`, `@metaplex-foundation/mpl-token-metadata@3.4.0`, `@solana/web3.js@1.98.4`, `bs58@6.0.0`); `node -c` passes on all 8 JS files; ffmpeg+python3 present for `copy-images.js`. Solana CLI NOT installed on remote and NOT needed — scripts use JS SDK only, no `execSync('solana ...')` calls. No keypair JSON files or `.env` files in either folder (Phantom handles signing). Local `nft/CLAUDE.md` prepended with DORMANT notice. Next: Function #8 (final cleanup).
- **2026-04-22** — **Function #5 (Website) complete — SHARED, not dormant.** User chose to keep both machines active for website work. Steps done: (a) cleaned uncommitted items locally — committed `twitter-banner.png`, `stories/reference.png`, `stories/story-posts.json`, `tools/tweet_image.py`, portable `fetch-mockups-scheduled.sh`; gitignored `debug-*.js` (hardcoded Printify JWT), `draft_emails/` (PII), `__pycache__/`. (b) Pushed 2 commits to `origin/gh-pages`. (c) Remote auth: `gh auth login` created fresh SSH key `id_ed25519` on remote, added to GitHub as `hchip-mac`. (d) Fresh SSH clone at `~/holy-chip/website/holy-chip-site/` (52 MB, no PAT leak). (e) Rsync'd `.env.production.local`, `.env.check`, `.netlify/state.json`. (f) `npm install` at root + `netlify/functions/`. (g) Netlify CLI 25.2.0 installed, logged in as Rico Mello, linked to `holychip` project. (h) `netlify dev` verified on port 8899: static server HTTP 200, 7 functions load, env vars auto-injected from Netlify cloud. **Sync discipline going forward: always `git pull` on the machine you're about to edit on, before editing.** Function #4 (`/origins`) still on hold per earlier decision.

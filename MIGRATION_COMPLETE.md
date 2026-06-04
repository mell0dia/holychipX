# Holy Chip Migration — Complete

**Date complete:** 2026-04-27
**Started:** 2026-04-17
**Full history:** `MIGRATION_PLAN.md`

---

## Machine Roles

| Machine | Hostname | Role |
|---|---|---|
| Local | this Mac (`Wakanda-MacBook-Pro-3`) | Hot-spare for rollback. Website edits OK with `git pull` first. |
| Remote | `hchip` → `rmello@rmellos-MacBook-Pro.local` | Primary for SGen, NFT, Submissions cron, `/analyzeStory`, `/origins`. |

**SSH:** `ssh hchip` (Bonjour name, DHCP-proof). Key: `~/.ssh/id_ed25519_hchip`. Passwordless.

---

## What Runs Where

| Function | Local | Remote |
|---|---|---|
| Website (`holy-chip-site`) | ✅ Active (shared) | ✅ Active (shared) |
| SGen story generator | 💤 Dormant | ✅ Active at `~/holy-chip/SGen/` |
| `/analyzeStory` skill | 💤 Dormant | ✅ Active at `~/.claude/commands/analyzeStory.md` |
| `/origins` pipeline | 💤 Dormant | ✅ Active at `~/.claude/commands/origins.md` |
| Submissions cron (9:00, 9:15) | 💤 Plists `.disabled` | ✅ Active (loaded since 2026-04-22) |
| NFT tooling (`nft/`) | 💤 Dormant | ✅ Active at `~/holy-chip/nft/` |
| Generator (old comic gen) | 📦 Archived to `_archive/Generator/` | n/a |

**Shared discipline:** the website is edited from both machines. Always `git pull` on the machine you're about to edit on, before editing.

---

## Keychain

10 of 11 Holy Chip-related entries mirrored to remote keychain on 2026-04-27:

- `RM Printify rico.duoba api-key`
- `RM Supabase and database  - rico.duoba`
- `RM resend key holychip_netlify  rico.duoba key`
- `RM @_holychip API Consumer Key ` *(trailing space)*
- `RM @_holychip API Key Consumer Key Secret`
- `RM @_holychip Access Token`
- `RM @_holychip Access Token Secret`
- `RM @_holychip Bearer Token`
- `RM @_holychip X account rm@mellodia.com`
- `RM Phantom holychip`

**`RM Phantom Holychip Seed` intentionally NOT mirrored** — seed phrase stays local-only. Single-machine attack surface preferred for the highest-sensitivity item. If the remote ever needs Phantom for signing, import via the seed (browser-side, not keychain).

**Mirror method:** macOS blocks `security add-generic-password` over headless SSH ("User interaction is not allowed"). Workaround: export to JSON locally → scp → run import script in remote VNC Terminal (GUI context allows the add). See `MIGRATION_PLAN.md` for the full procedure.

**Settings hardening:** `~/.claude/settings.json` denies `security dump-keychain -d` (which would expose passwords) at the Claude Code permission layer.

---

## Still On Local (intentionally)

These exist on local-only by design. Don't delete without an explicit decommission decision.

| Item | Why kept |
|---|---|
| `~/.local/bin/holychip-check-submissions.sh` | Cron worker. Required if you ever roll back. |
| `~/.local/bin/holychip-submission-healthcheck.sh` | Same. |
| `~/Library/LaunchAgents/com.holychip.healthcheck.plist.disabled` | Renamed `.disabled`. Rename back + `launchctl load` to roll back. |
| `~/Library/LaunchAgents/com.holychip.submissions.plist.disabled` | Same. |
| `~/.local/share/holychip-*.log` and `holychip-submissions-*.json` | Frozen state from 2026-04-22 cutover. ~14 KB total. Historical reference. |
| `RM Phantom Holychip Seed` (keychain) | Highest-sensitivity item, local-only by design. |

---

## Rollback (any function, < 5 minutes)

For Submissions cron (most likely candidate):

```bash
# On REMOTE — stop the cron jobs
ssh hchip 'launchctl unload ~/Library/LaunchAgents/com.holychip.healthcheck.plist'
ssh hchip 'launchctl unload ~/Library/LaunchAgents/com.holychip.submissions.plist'
ssh hchip 'mv ~/Library/LaunchAgents/com.holychip.healthcheck.plist ~/Library/LaunchAgents/com.holychip.healthcheck.plist.disabled'
ssh hchip 'mv ~/Library/LaunchAgents/com.holychip.submissions.plist ~/Library/LaunchAgents/com.holychip.submissions.plist.disabled'

# On LOCAL — re-enable
mv ~/Library/LaunchAgents/com.holychip.healthcheck.plist.disabled ~/Library/LaunchAgents/com.holychip.healthcheck.plist
mv ~/Library/LaunchAgents/com.holychip.submissions.plist.disabled ~/Library/LaunchAgents/com.holychip.submissions.plist
launchctl load ~/Library/LaunchAgents/com.holychip.healthcheck.plist
launchctl load ~/Library/LaunchAgents/com.holychip.submissions.plist
```

For SGen / NFT / skills: just start using local versions again (files are still in place).

For Generator: `mv HolyChip/_archive/Generator HolyChip/Generator`.

---

## Verification (run anytime)

```bash
# Confirm remote is reachable and cron is alive
ssh hchip 'launchctl list | grep holychip; tail -1 ~/.local/share/holychip-healthcheck.log; tail -1 ~/.local/share/holychip-submissions.log'

# Confirm nothing is loaded locally
launchctl list | grep holychip   # should be empty
```

---

## Future Decommission

**Scheduled for 2026-06-01 09:30 local** via `~/Library/LaunchAgents/com.holychip.decommission.plist` (one-shot launchd job, installed 2026-04-27). Script: `~/.local/bin/holychip-decommission.sh`. Log: `~/.local/share/holychip-decommission.log`.

The job is conservative: it will only delete files if remote cron has been healthy (≥25 OK days in the recent log tail) AND local plists are still `.disabled`. If anything looks wrong, it logs why and makes zero changes. Either way, it self-removes after running so it won't fire again.

If you want to:
- **Cancel before it fires:** `launchctl unload ~/Library/LaunchAgents/com.holychip.decommission.plist && rm ~/Library/LaunchAgents/com.holychip.decommission.plist`
- **Run early:** `launchctl start com.holychip.decommission`
- **Verify it's scheduled:** `launchctl list | grep holychip`

**What gets deleted if stable:**
- `~/.local/bin/holychip-check-submissions.sh`
- `~/.local/bin/holychip-submission-healthcheck.sh`
- `~/Library/LaunchAgents/com.holychip.healthcheck.plist.disabled`
- `~/Library/LaunchAgents/com.holychip.submissions.plist.disabled`
- `~/.local/share/holychip-{healthcheck,submissions}.log`
- `~/.local/share/holychip-submissions-{pending,confirmed,clarify}.json`

**Never deleted by automation:**
- `RM Phantom Holychip Seed` keychain entry (stays local-only by design)
- `HolyChip/_archive/Generator/` (historical artifact)

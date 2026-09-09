#!/usr/bin/env python3
"""vault_refill.py - start the next vault cycle when the current one runs dry.

The vault rotation is finite: every story gets thrown back once, and then there
is nothing left to schedule. Rather than letting the feed fall to reels-only,
this starts a fresh cycle from scratch - the whole catalogue again, lowest
number first.

    vault_refill.py --dry-run    # show the cycle it would append
    vault_refill.py              # append it
    vault_refill.py --force      # append even if vaults are still pending

Called automatically by release_queue.py, so the rotation refills itself. It is
a no-op while any vault is still pending, which makes it safe to call daily.

THE THREE RULES THE SCHEDULE HAS TO KEEP, all of them learned the hard way:

  1. ONE ENTRY PER DAY. The runner posts the oldest due entry and only that, so
     two entries sharing a date silently pushes one late and cascades. Reels sit
     on offsets that are multiples of 4 from REEL_EPOCH; vaults take odd
     offsets, which can never collide.

  2. A STORY'S VAULT MUST NOT LAND NEAR ITS OWN REEL. Otherwise the same strip
     goes out twice in a week. Anything within GUARD_DAYS either side of its own
     reel is skipped and picked up later in the cycle, once its reel has aired.

  3. LOW NUMBER FIRST. "From the vault" means going back to the beginning, so
     the cycle walks the catalogue in order, subject to rule 2.

Leads and tags are reused from previous cycles - they are already written and
already published, so a repeat throwback carries the copy it had before.
"""
import argparse, datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_gif as sg

HC = os.path.expanduser("~/holy-chip")
QUEUE = os.path.join(HC, "content", "release-queue.json")

REEL_EPOCH = datetime.date(2026, 8, 20)   # reels sit on EPOCH + 4n
GUARD_DAYS = 21
GAP_DAYS = 2                              # a vault every other day


def load():
    with open(QUEUE) as fh:
        return json.load(fh)


def save(d):
    tmp = QUEUE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, QUEUE)


def copy_bank(queue):
    """Lead + tags per story: whatever the last cycle carried, plus the
    standing bank in content/vault-leads.json for stories that have never been
    vaulted (a story with no lead cannot be scheduled, so it would silently
    drop out of every future cycle)."""
    bank = {}
    for e in queue:
        # An entry carrying its own marker is a one-off announcement, not a
        # throwback - HC000's "STORY #000, REWRITTEN" lead would otherwise be
        # recycled as vault copy and claim the strip was just rewritten.
        if e["kind"] != "vault" or not e.get("lead") or e.get("marker"):
            continue
        # early entries baked "FROM THE VAULT ·" into the lead itself; caption()
        # strips it at post time, but it should not be carried forward
        lead = re.sub(r"^\s*(?:\U0001F5C4️?\s*)?FROM THE VAULT\s*[·:.-]*\s*", "",
                      e["lead"], flags=re.I).strip()
        bank[e["story"]] = (e.get("tags", ""), lead)

    # the standing bank wins: it is where hand-written copy lives for stories
    # that have never been vaulted, or whose queue copy should not be reused
    extra = os.path.join(HC, "content", "vault-leads.json")
    if os.path.exists(extra):
        with open(extra) as fh:
            for sid, v in json.load(fh).items():
                bank[sid] = (v["tags"], v["lead"])
    return bank


def reel_dates(queue):
    """When each story's Reel airs - scheduled date, or when it actually went."""
    out = {}
    for e in queue:
        if e["kind"] != "reel":
            continue
        d = e.get("posted_at", "")[:10] if e["status"] == "done" else e["date"]
        if d:
            out[e["story"]] = datetime.date.fromisoformat(d)
    return out


def next_slot_after(day):
    """First date after `day` that no reel can ever occupy (odd offset)."""
    # reels occupy offsets that are multiples of 4, so any ODD offset is
    # permanently safe - and stepping by 2 from there stays odd forever
    d = day + datetime.timedelta(days=1)
    while (d - REEL_EPOCH).days % 2 == 0:
        d += datetime.timedelta(days=1)
    return d


def build_cycle(d, cycle_no):
    queue = d["queue"]
    bank = copy_bank(queue)
    reels = reel_dates(queue)

    pool = [s for s in sg.story_ids() if s in bank]
    skipped = [s for s in sg.story_ids() if s not in bank]

    last = max((e["date"] for e in queue if e["kind"] == "vault"), default=None)
    start = next_slot_after(datetime.date.fromisoformat(last) if last
                            else datetime.date.today())

    slots, day = [], start
    while len(slots) < len(pool):
        slots.append(day)
        day += datetime.timedelta(days=GAP_DAYS)

    remaining, out = list(pool), []
    for slot in slots:
        pick = next((s for s in remaining
                     if s not in reels
                     or abs((reels[s] - slot).days) >= GUARD_DAYS), None)
        if pick is None:                      # nothing clean - take the least bad
            pick = max(remaining, key=lambda s: abs((reels[s] - slot).days))
        tags, lead = bank[pick]
        out.append({"date": str(slot), "story": pick, "kind": "vault",
                    "tags": tags, "lead": lead, "status": "pending",
                    "cycle": cycle_no})
        remaining.remove(pick)
    return out, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="append a cycle even if vaults are still pending")
    a = ap.parse_args()

    d = load()
    pending = [e for e in d["queue"]
               if e["kind"] == "vault" and e["status"] != "done"]
    if pending and not a.force:
        print(f"{len(pending)} vault(s) still pending "
              f"(next {min(e['date'] for e in pending)}) - nothing to do")
        return 0

    cycle_no = max((e.get("cycle", 1) for e in d["queue"]
                    if e["kind"] == "vault"), default=1) + 1
    cycle, skipped = build_cycle(d, cycle_no)
    if not cycle:
        print("no stories have a reusable lead - cannot build a cycle")
        return 1

    print(f"vault cycle {cycle_no}: {len(cycle)} posts, "
          f"{cycle[0]['date']} -> {cycle[-1]['date']}")
    if skipped:
        print(f"  no lead on disk, left out: {' '.join(skipped)}")
    for e in cycle[:6]:
        print(f"    {e['date']}  {e['story']}  {e['lead'][:52]}")
    if len(cycle) > 6:
        print(f"    ... and {len(cycle) - 6} more")

    if a.dry_run:
        print("\n--dry-run: queue not written")
        return 0

    d["queue"].extend(cycle)
    d["queue"].sort(key=lambda e: (e["date"], 0 if e["kind"] == "reel" else 1))
    save(d)
    print(f"\nappended {len(cycle)} vault entries to the queue")
    return 0


if __name__ == "__main__":
    sys.exit(main())

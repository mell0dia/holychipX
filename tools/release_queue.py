#!/usr/bin/env python3
"""release_queue.py — post the one story scheduled for today, if any.

Driven by content/release-queue.json and run once a day from LAUNCHD. Not cron:
cron silently skips anything scheduled while the Mac is asleep and never comes
back to it, which quietly lost three releases on 1-3 Aug 2026. launchd runs a
missed StartCalendarInterval job when the machine wakes.

One daily job rather than one entry per release, because dated cron entries have
no year field and would fire again the same date next year.

The runner takes the OLDEST entry that is DUE (date <= today), not strictly
today's. So if a day is missed anyway, the next run picks it up rather than
dropping it - one release per run, so a backlog drains a day at a time instead
of firing all at once.

    release_queue.py            # post today's entry, if it is still pending
    release_queue.py --dry-run  # show what would happen, touch nothing
    release_queue.py --list     # show the whole queue
    release_queue.py --date 2026-08-01   # pretend it is that day

Safe to run repeatedly: an entry already marked done is skipped, so a retry or
a manual run cannot double-post.
"""
import os, sys, json, argparse, subprocess, datetime

HC = os.path.expanduser("~/holy-chip")
QUEUE = os.path.join(HC, "content", "release-queue.json")
THROWBACK = os.path.join(HC, "tools", "throwback_release.sh")
# Stories go through scheduled_release.sh, NOT release_social.py directly:
# release_social.py is FB+IG only, so calling it here silently gave scheduled
# stories half the reach of a vault throwback (HC038, 2026-08-09, went out to
# FB+IG with no Nostr and no X). Both wrappers do FB+IG -> Nostr -> X.
SCHEDULED = os.path.join(HC, "tools", "scheduled_release.sh")
# kind "reel" posts the animated voice-over Reel to all four platforms in one
# process. It does its own preflight and is idempotent per platform, so a
# half-failed run is completed by rerunning it, not restarted.
RELEASE_REEL = os.path.join(HC, "tools", "release_reel.py")


def load():
    with open(QUEUE) as fh:
        return json.load(fh)


def save(d):
    tmp = QUEUE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, QUEUE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    a = ap.parse_args()

    # Top the vault rotation up before choosing today's entry. vault_refill is
    # a no-op while any vault is still pending, so this costs nothing on a normal
    # day; on the day the cycle runs dry it starts the next one, and the feed
    # never silently drops to reels-only.
    if not a.list and not a.dry_run:
        try:
            subprocess.run(["python3", os.path.join(HC, "tools",
                                                    "vault_refill.py")],
                           cwd=HC, timeout=120)
        except Exception as e:
            print(f"  vault refill skipped: {e}")

    d = load()
    today = a.date or datetime.date.today().isoformat()

    if a.list:
        print(f"today is {datetime.date.today().isoformat()}")
        for e in d["queue"]:
            mark = {"done": "OK  ", "pending": "    "}.get(e["status"], "??  ")
            print(f"  {mark}{e['date']}  {e['story']:6s} {e['kind']:6s} "
                  f"{e['tags']}")
            print(f"        {e['lead']}")
            if e.get("posted_at"):
                print(f"        posted {e['posted_at']}")
        return 0

    # Two lanes (user, 2026-10-02). SHORTS go out as soon as possible, in order,
    # whatever else posts that day: each run releases the oldest due short. The
    # other kinds (vault, reel, story) keep their one-a-day rule. Both lanes run
    # on the same morning when both have something due.
    pending = lambda: [e for e in d["queue"] if e["status"] != "done"]
    lanes = [("short", [e for e in pending() if e["kind"] == "short" and e["date"] <= today]),
             ("other", [e for e in pending() if e["kind"] != "short" and e["date"] <= today])]
    if not any(due for _, due in lanes):
        nxt = sorted(pending(), key=lambda e: e["date"])
        print(f"{today}: nothing due"
              + (f" - next is {nxt[0]['story']} on {nxt[0]['date']}" if nxt else ""))
        return 0
    rc_all = 0
    for lane, due in lanes:
        if not due:
            continue
        due.sort(key=lambda e: (e["date"], e["story"]))
        e = due[0]
        if len(due) > 1:
            print(f"{today}: {len(due)} {lane} entries due, releasing the oldest "
                  f"({e['story']}, due {e['date']}); the rest follow on later runs")
        if e["date"] != today:
            print(f"  note: {e['story']} was due {e['date']} - running it late")
        rc_all |= run_entry(d, e, today, a.dry_run)
    return rc_all


def run_entry(d, e, today, dry_run):
    if e["kind"] == "reel":
        cmd = ["python3", RELEASE_REEL, e["story"]] + e["tags"].split()
    elif e["kind"] == "short":
        # HC###.short.png -> FB, IG, X, Nostr (release_short.py)
        cmd = ["python3", os.path.join(HC, "tools", "release_short.py"), e["story"], e["tags"], e["lead"]]
    elif e["kind"] == "vault":
        # optional per-entry marker replaces the "FROM THE VAULT" line
        cmd = ["bash", THROWBACK, e["story"], e["tags"], e["lead"]]
        if e.get("marker"):
            cmd.append(e["marker"])
    else:
        cmd = ["bash", SCHEDULED, e["story"], e["tags"]]

    print(f"{today}: releasing {e['story']} ({e['kind']})")
    print("  " + " ".join(repr(c) if " " in c else c for c in cmd))
    if dry_run:
        print("  --dry-run: not executing")
        return 0

    rc = subprocess.run(cmd, cwd=HC).returncode
    if rc == 0:
        e["status"] = "done"
        e["posted_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        save(d)
        print(f"  {e['story']} released and marked done")
    else:
        print(f"  FAILED rc={rc} - left pending, will retry on a manual run")
    return rc

if __name__ == "__main__":
    sys.exit(main())

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

    # oldest still-pending entry that has come due; a backlog drains one a day
    due = sorted([e for e in d["queue"]
                  if e["status"] != "done" and e["date"] <= today],
                 key=lambda e: e["date"])
    if not due:
        nxt = sorted([e for e in d["queue"] if e["status"] != "done"],
                     key=lambda e: e["date"])
        print(f"{today}: nothing due"
              + (f" - next is {nxt[0]['story']} on {nxt[0]['date']}" if nxt else ""))
        return 0

    e = due[0]
    if len(due) > 1:
        print(f"{today}: {len(due)} entries overdue, releasing the oldest "
              f"({e['story']}, due {e['date']}); the rest follow on later runs")
    if e["date"] != today:
        print(f"  note: {e['story']} was due {e['date']} - running it late")

    if e["kind"] == "vault":
        cmd = ["bash", THROWBACK, e["story"], e["tags"], e["lead"]]
    else:
        cmd = ["bash", SCHEDULED, e["story"], e["tags"]]

    print(f"{today}: releasing {e['story']} ({e['kind']})")
    print("  " + " ".join(repr(c) if " " in c else c for c in cmd))
    if a.dry_run:
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

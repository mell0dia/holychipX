#!/usr/bin/env python3
"""release_queue.py — post the one story scheduled for today, if any.

Driven by content/release-queue.json and run once a day from cron. One daily
job rather than one cron entry per release, because dated cron entries have no
year: they would fire again next July. Entries here fire on their own date and
are then marked done.

    release_queue.py            # post today's entry, if it is still pending
    release_queue.py --dry-run  # show what would happen, touch nothing
    release_queue.py --list     # show the whole queue
    release_queue.py --date 2026-08-01   # pretend it is that day

Safe to run repeatedly: an entry already marked done is skipped, so a cron
retry or a manual run cannot double-post. A missed day does NOT cascade - the
entry simply stays pending until its date is run explicitly.
"""
import os, sys, json, argparse, subprocess, datetime

HC = os.path.expanduser("~/holy-chip")
QUEUE = os.path.join(HC, "content", "release-queue.json")
THROWBACK = os.path.join(HC, "tools", "throwback_release.sh")
RELEASE = os.path.join(HC, "tools", "release_social.py")


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

    due = [e for e in d["queue"] if e["date"] == today]
    if not due:
        print(f"{today}: nothing scheduled")
        return 0

    e = due[0]
    if e["status"] == "done":
        print(f"{today}: {e['story']} already posted at {e.get('posted_at')} "
              f"- skipping")
        return 0

    if e["kind"] == "vault":
        cmd = ["bash", THROWBACK, e["story"], e["tags"], e["lead"]]
    else:
        cmd = ["python3", RELEASE, e["story"], e["tags"]]

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

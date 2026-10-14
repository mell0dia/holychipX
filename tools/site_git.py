"""Push the website (gh-pages) safely when several jobs run at once.

Why (2026-10-06): with the lid closed the Mac only half-wakes for ~45 s at a
time, so the 08:57 gm card and the 09:00 release fire in the same window. Both
commit, the first push wins, and the second is rejected ("fetch first") - that
cost the HC006 vault release. This:

  * takes an exclusive lock, so two jobs never push at the same moment;
  * on a rejected push, rebases on origin/gh-pages and pushes again;
  * on any other failure (no network yet, key not unlocked), waits and retries.

    import site_git; site_git.push(SITE)
"""
import fcntl, subprocess, time
from pathlib import Path

LOCK = Path("/tmp/holychip-site-git.lock")
BRANCH = "gh-pages"


def _git(site, *args):
    return subprocess.run(["git", "-C", str(site), *args], capture_output=True, text=True)


def push(site, tries=6, wait=15):
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)              # waits for any other job's push
        last = ""
        for i in range(tries):
            r = _git(site, "push", "origin", BRANCH)
            if r.returncode == 0:
                if i:
                    print(f"  push succeeded on attempt {i + 1}")
                return
            last = (r.stderr or r.stdout).strip()
            print(f"  push attempt {i + 1}/{tries} failed: {last.splitlines()[-1][:120] if last else '?'}")
            if any(s in last for s in ("rejected", "fetch first", "non-fast-forward")):
                # someone else published first: put our commits on top of theirs
                rb = _git(site, "pull", "--rebase", "--autostash", "origin", BRANCH)
                if rb.returncode != 0:
                    _git(site, "rebase", "--abort")
                    print(f"  rebase failed: {(rb.stderr or rb.stdout).strip()[-200:]}")
                    time.sleep(wait)
                continue
            time.sleep(wait * (i + 1))              # network not up yet, etc.
        raise RuntimeError(f"git push failed after {tries} attempts: {last[-400:]}")

#!/usr/bin/env python3
"""The Portuguese Page's daily ng card as a standing job (user, 2026-10-15:
"make the PT ng a daily job" - after the catch-up the PT page runs the same
program as English).

    pt_ng_daily.py            # queue today's ng (08:30) if there is none yet
    pt_ng_daily.py --dry-run

Takes the next phrase from content/pt-br/gm-phrases-pt.md (the PT phrase bank,
tease style; used lines are deleted like the English gm-phrases.md), appends
{at, kind: ng, story, phrase, tags} to content/pt-br/release-queue-pt.json,
and release_pt.py (launchd, every 10 min) posts it at 08:30 with a fresh NFT.
Stops and warns (Telegram if available) when the bank is empty.
launchd: com.holychip.pt-ng-daily @08:20.
"""
import json, re, subprocess, sys
from datetime import datetime
from pathlib import Path

HC = Path.home() / "holy-chip"
BANK = HC / "content" / "pt-br" / "gm-phrases-pt.md"
QUEUE = HC / "content" / "pt-br" / "release-queue-pt.json"
LOG = Path.home() / ".local/share/holychip-pt-ng.log"
SLOT = "08:30"


def warn(msg):
    print(msg)
    try:
        subprocess.run(["python3", str(HC / "tools" / "notify_telegram.py"), f"PT ng: {msg}"], timeout=30)
    except Exception:
        pass


def main():
    dry = "--dry-run" in sys.argv
    today = datetime.now().strftime("%Y-%m-%d")
    q = json.loads(QUEUE.read_text())
    if any(e["kind"] == "ng" and e["at"].startswith(today) for e in q["queue"]):
        print(f"{today}: ng already queued"); return 0
    text = BANK.read_text()
    m = re.search(r"^\s*\d+\.\s+(.+?)\s+\((HC\d{3})\)\s*((?:#\S+\s*)*)$", text, re.M)
    if not m:
        warn("phrase bank is EMPTY - refill content/pt-br/gm-phrases-pt.md"); return 1
    phrase, sid, tags = m.group(1).strip(), m.group(2), m.group(3).strip()
    entry = {"at": f"{today} {SLOT}", "kind": "ng", "story": sid, "phrase": phrase, "tags": tags, "status": "pending"}
    print(json.dumps(entry, ensure_ascii=False))
    if dry:
        return 0
    q["queue"].append(entry); q["queue"].sort(key=lambda e: e["at"])
    QUEUE.write_text(json.dumps(q, indent=1, ensure_ascii=False) + "\n")
    BANK.write_text(text[:m.start()] + text[m.end():].lstrip("\n") if text[m.end():m.end()+1] == "\n" else text[:m.start()] + text[m.end():])
    left = len(re.findall(r"^\s*\d+\.\s+.+\(HC\d{3}\)", BANK.read_text(), re.M))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.open("a").write(f"{datetime.now():%Y-%m-%d %H:%M} queued {sid} | {phrase[:60]} | {left} left\n")
    if left <= 7:
        warn(f"only {left} phrases left in the PT bank")
    print(f"queued for {today} {SLOT}; {left} phrases left")
    return 0


if __name__ == "__main__":
    sys.exit(main())

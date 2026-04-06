#!/usr/bin/env python3
"""Holy Chip automated DM outreach. Run daily via cron."""
import json
import os
import sys
import subprocess
from datetime import datetime, timedelta

TRACKER = os.path.expanduser("~/holy-chip/content/dm-tracker.json")
STORIES_DIR = os.path.expanduser("~/holy-chip/stories")

# Current campaign config
STORY = "HC003"
STORY_TITLE = "AGI Diversity Dept"
START_DATE = "2026-04-02"

# Ramp-up schedule: (day_range_start, day_range_end, daily_quota)
RAMP = [
    (1, 2, 5),
    (3, 4, 10),
    (5, 7, 15),
    (8, 999, 20),
]

def get_daily_quota():
    """Determine how many DMs to send based on days since start."""
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    day_num = (datetime.now() - start).days + 1
    for lo, hi, quota in RAMP:
        if lo <= day_num <= hi:
            return quota, day_num
    return 20, day_num

def send_dm(handle, message, image_path):
    """Send a DM using x-dm tool. Returns (success, error_type)."""
    cmd = [
        os.path.expanduser("~/.local/bin/x-dm"),
        "send", f"@{handle}", message, "--image", image_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        if "SUCCESS" in output:
            return True, None
        elif "403" in output:
            return False, "dm_closed"
        elif "429" in output:
            return False, "rate_limited"
        else:
            return False, f"error: {output[-200:]}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)

def main():
    # Load tracker
    with open(TRACKER) as f:
        data = json.load(f)

    quota, day_num = get_daily_quota()
    image = os.path.join(STORIES_DIR, f"{STORY}.png")
    message = f"Check out our dystopian AI cartoon\nHoly Chip #{STORY[2:]} - {STORY_TITLE}: https://www.holy-chip.com/stories.html?story={STORY}"

    # Find targets: not yet sent, not dm_closed
    already_sent = set()
    dm_closed = set()
    for t in data['targets']:
        if t.get('dm_open') == False:
            dm_closed.add(t['handle'])
        for dm in t.get('dms', []):
            if dm.get('status') == 'sent':
                already_sent.add(t['handle'])

    candidates = [
        t for t in data['targets']
        if t['handle'] not in already_sent
        and t['handle'] not in dm_closed
    ]

    print(f"=== Holy Chip DM Blast — Day {day_num} ===")
    print(f"Story: {STORY} - {STORY_TITLE}")
    print(f"Quota: {quota} DMs")
    print(f"Already sent: {len(already_sent)}")
    print(f"DMs closed: {len(dm_closed)}")
    print(f"Candidates remaining: {len(candidates)}")
    print()

    if not candidates:
        print("No more candidates! Add more targets to the tracker.")
        return

    sent = 0
    failed_closed = 0
    failed_other = 0
    results = []

    for t in candidates:
        if sent >= quota:
            break

        handle = t['handle']
        name = t['name']
        
        success, error = send_dm(handle, message, image)

        if success:
            sent += 1
            t['dm_open'] = True
            t['dms'].append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "story": STORY,
                "status": "sent",
                "message": message
            })
            results.append(f"✅ @{handle} ({name})")
            print(f"✅ @{handle} ({name}) — sent [{sent}/{quota}]")
        elif error == "dm_closed":
            failed_closed += 1
            t['dm_open'] = False
            t['dms'].append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "story": STORY,
                "status": "failed_closed",
                "message": ""
            })
            print(f"❌ @{handle} ({name}) — DMs closed, skipping")
        elif error == "rate_limited":
            print(f"⚠️ Rate limited! Stopping for today.")
            results.append(f"⚠️ Rate limited after {sent} DMs")
            break
        else:
            failed_other += 1
            t['dms'].append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "story": STORY,
                "status": "failed",
                "message": str(error)[:100]
            })
            print(f"❌ @{handle} ({name}) — {error}")

        # Don't hammer the API
        import time
        time.sleep(3)

    # Save tracker
    with open(TRACKER, 'w') as f:
        json.dump(data, f, indent=2)

    # Summary
    print(f"\n{'='*40}")
    print(f"SUMMARY — Day {day_num}")
    print(f"  Sent: {sent}/{quota}")
    print(f"  DMs closed: {failed_closed}")
    print(f"  Other failures: {failed_other}")
    print(f"  Total sent all-time: {len(already_sent) + sent}")
    print(f"  Remaining candidates: {len(candidates) - sent - failed_closed - failed_other}")
    
    # Output for cron report
    print(f"\n--- DM Report ---")
    for r in results:
        print(r)

if __name__ == "__main__":
    main()

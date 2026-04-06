#!/usr/bin/env python3
"""
Holy Chip .PRE Phrase Poster — generates .pre images and posts to X/Twitter.

Pipeline: pick pending punches → generate .pre image via sgen-pre → tweet → mark posted.
Posts up to 5 phrases per day, only if pending punches exist.
Tracks everything in pre-punches.json (status: pending/posted/failed).

Usage:
  pre-poster.py                  # Post next batch (up to 5)
  pre-poster.py --dry-run        # Preview what would be posted (no actual post)
  pre-poster.py --status         # Show posting stats
  pre-poster.py --post-one N     # Post specific punch #N
  pre-poster.py --batch N        # Override batch size (default: 5)
"""
import sys
import json
import os
import random
import subprocess
import glob
import time
from datetime import datetime, date

PUNCHES_FILE = os.path.expanduser("~/holy-chip/content/pre-punches.json")
CHARACTERS_DIR = os.path.expanduser("~/holy-chip/characters")
OUTPUT_DIR = os.path.expanduser("~/holy-chip/content/pre-images")
TWEET_SCRIPT = os.path.expanduser("~/holy-chip/tools/tweet-with-image.py")
LOG_DIR = os.path.expanduser("~/holy-chip/logs")

# Spacing between tweets (seconds) — avoids rate limits and looks organic
TWEET_SPACING = 300  # 5 minutes between posts

# Known speaker Twitter handles
SPEAKER_HANDLES = {
    "andre karpathy": "@kaboretsky",
    "andrej karpathy": "@karpathy",
    "karpathy": "@karpathy",
    "emmad mustach": "@EMostaque",
    "emad mostaque": "@EMostaque",
    "dwaresh patel": "@dwaboreshpatel",
    "alex wisner gross": "@alexwg",
    "alex wizner gross": "@alexwg",
    "sam altman": "@sama",
    "elon musk": "@elonmusk",
    "dario amodei": "@DarioAmodei",
    "demis hassabis": "@demaboresis",
    "yann lecun": "@ylecun",
    "ilya sutskever": "@iaboreskever",
    "mark zuckerberg": "@faborinkerman",
    "jensen huang": "@nvidia",
    "satya nadella": "@sataborendella",
    "lex fridman": "@lexfridman",
}

def load_punches():
    if os.path.exists(PUNCHES_FILE):
        with open(PUNCHES_FILE) as f:
            return json.load(f)
    return {"metadata": {}, "punches": []}

def save_punches(data):
    data["metadata"]["updated"] = str(date.today())
    with open(PUNCHES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_speaker_handle(speaker):
    """Look up Twitter handle for a speaker."""
    if not speaker or speaker == "unknown":
        return None
    key = speaker.lower().strip()
    return SPEAKER_HANDLES.get(key)

def pick_random_character():
    """Pick a random character image from the characters directory."""
    chip_dirs = glob.glob(os.path.join(CHARACTERS_DIR, "Chip *"))
    if not chip_dirs:
        print("ERROR: No character directories found")
        sys.exit(1)
    
    chip_dir = random.choice(chip_dirs)
    images = glob.glob(os.path.join(chip_dir, "*.png"))
    if not images:
        print(f"ERROR: No images in {chip_dir}")
        sys.exit(1)
    
    return random.choice(images)

def generate_pre_image(punch, punch_idx):
    """Generate a .pre image using sgen-pre CLI."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    bot_image = pick_random_character()
    output_file = os.path.join(OUTPUT_DIR, f"PRE_{punch_idx:03d}.png")
    side = random.choice(["left", "right"])
    
    # Use punch text as both text and title
    punch_text = punch["punch"]
    
    cmd = [
        "node", os.path.expanduser("~/holy-chip/tools/index.js"),
        "--bot", bot_image,
        "--text", punch_text,
        "--title", "HOLY CHIP",
        "--year", str(datetime.now().year),
        "--id", f"PRE{punch_idx:03d}",
        "--side", side,
        "--out", output_file
    ]
    
    print(f"  🎨 Generating .pre image for: \"{punch_text}\"")
    print(f"     Bot: {os.path.basename(bot_image)} ({side} side)")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output_file):
            size_kb = os.path.getsize(output_file) / 1024
            print(f"     ✅ Image generated: {output_file} ({size_kb:.0f}KB)")
            return output_file
        else:
            print(f"     ❌ sgen-pre failed: {result.stderr[:200]}")
            print(f"        stdout: {result.stdout[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"     ❌ sgen-pre timed out (120s)")
        return None
    except Exception as e:
        print(f"     ❌ Error: {e}")
        return None

def build_tweet_text(punch):
    """Build the tweet text with punch line and attribution."""
    text = f'"{punch["punch"]}"\n\n'
    
    # Add speaker attribution with handle if available
    speaker = punch.get("speaker", "unknown")
    handle = get_speaker_handle(speaker)
    
    if speaker and speaker != "unknown":
        if handle:
            text += f"— {handle}\n\n"
        else:
            text += f"— {speaker}\n\n"
    
    # Add source if it exists
    source = punch.get("source_title", "")
    if source:
        text += f"📺 {source}\n\n"
    
    text += "#HolyChip #AI #AGI #Singularity"
    
    return text

def post_tweet(image_path, tweet_text, dry_run=False):
    """Post tweet with image to X/Twitter."""
    if dry_run:
        print(f"  📝 [DRY RUN] Would tweet:")
        for line in tweet_text.split("\n"):
            print(f"     {line}")
        return True
    
    cmd = ["python3", TWEET_SCRIPT, image_path, tweet_text]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"  ✅ Posted! {result.stdout.strip()}")
            return True
        else:
            print(f"  ❌ Tweet failed: {result.stdout[:200]} {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Error posting: {e}")
        return False

def get_pending_punches(punch_data):
    """Get list of (index, punch) tuples for pending punches, HIGH weight first."""
    pending = []
    for i, p in enumerate(punch_data["punches"]):
        if p.get("status") == "pending":
            pending.append((i, p))
    
    # Sort: high weight first, then original order
    pending.sort(key=lambda x: (0 if x[1].get("weight") == "high" else 1, x[0]))
    return pending

def already_posted_today(punch_data):
    """Count how many punches were posted today."""
    today = str(date.today())
    return sum(1 for p in punch_data["punches"]
               if p.get("status") == "posted" and p.get("date_posted", "").startswith(today))

def cmd_post(batch_size=5, dry_run=False, specific=None):
    """Post next batch of punches."""
    punch_data = load_punches()
    
    if specific is not None:
        # Post specific punch
        idx = specific - 1
        if idx < 0 or idx >= len(punch_data["punches"]):
            print(f"Invalid punch number: {specific}")
            return
        punch = punch_data["punches"][idx]
        if punch.get("status") == "posted":
            print(f"Punch #{specific} already posted on {punch.get('date_posted', '?')}")
            return
        targets = [(idx, punch)]
    else:
        # Check daily limit
        posted_today = already_posted_today(punch_data)
        if posted_today >= batch_size:
            print(f"Already posted {posted_today} today (limit: {batch_size}). Done.")
            return
        
        remaining = batch_size - posted_today
        pending = get_pending_punches(punch_data)
        
        if not pending:
            print("No pending punches. Nothing to post.")
            return
        
        targets = pending[:remaining]
        print(f"📤 Posting {len(targets)} punches (posted today: {posted_today}, limit: {batch_size})")
    
    print(f"{'=' * 60}")
    
    success_count = 0
    for i, (idx, punch) in enumerate(targets):
        punch_num = idx + 1
        print(f"\n--- Punch #{punch_num} ({i+1}/{len(targets)}) ---")
        print(f"  💬 \"{punch['punch']}\"")
        
        # Generate .pre image
        image_path = generate_pre_image(punch, punch_num)
        if not image_path:
            punch_data["punches"][idx]["status"] = "failed"
            punch_data["punches"][idx]["fail_reason"] = "image_generation"
            save_punches(punch_data)
            print(f"  ⏭️  Skipping (image failed)")
            continue
        
        # Build tweet text
        tweet_text = build_tweet_text(punch)
        
        # Post
        success = post_tweet(image_path, tweet_text, dry_run=dry_run)
        
        if success:
            if not dry_run:
                punch_data["punches"][idx]["status"] = "posted"
                punch_data["punches"][idx]["date_posted"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                punch_data["punches"][idx]["image_path"] = image_path
                save_punches(punch_data)
            success_count += 1
        else:
            if not dry_run:
                punch_data["punches"][idx]["status"] = "failed"
                punch_data["punches"][idx]["fail_reason"] = "tweet_post"
                save_punches(punch_data)
        
        # Wait between posts (except after last one)
        if i < len(targets) - 1 and not dry_run:
            wait = TWEET_SPACING + random.randint(0, 60)
            print(f"  ⏳ Waiting {wait}s before next post...")
            time.sleep(wait)
    
    print(f"\n{'=' * 60}")
    print(f"✅ Posted: {success_count}/{len(targets)}")
    
    remaining_pending = sum(1 for p in punch_data["punches"] if p.get("status") == "pending")
    print(f"📊 Remaining pending: {remaining_pending}")

def cmd_status():
    """Show posting stats."""
    punch_data = load_punches()
    punches = punch_data.get("punches", [])
    
    total = len(punches)
    posted = sum(1 for p in punches if p.get("status") == "posted")
    pending = sum(1 for p in punches if p.get("status") == "pending")
    failed = sum(1 for p in punches if p.get("status") == "failed")
    today = sum(1 for p in punches
                if p.get("status") == "posted" and p.get("date_posted", "").startswith(str(date.today())))
    
    print(f"📊 .PRE Punch Line Stats")
    print(f"{'=' * 40}")
    print(f"  Total:     {total}")
    print(f"  Posted:    {posted}")
    print(f"  Pending:   {pending}")
    print(f"  Failed:    {failed}")
    print(f"  Today:     {today}/5")
    
    if pending > 0:
        days_left = (pending + 4) // 5  # ceiling division
        print(f"  Runway:    ~{days_left} days of content")
    
    # Show recently posted
    recent = [p for p in punches if p.get("status") == "posted"]
    if recent:
        print(f"\nRecent posts:")
        for p in recent[-5:]:
            print(f"  ✅ \"{p['punch']}\" — {p.get('date_posted', '?')}")
    
    # Show next up
    for p in punches:
        if p.get("status") == "pending":
            handle = get_speaker_handle(p.get("speaker", ""))
            attr = handle or p.get("speaker", "?")
            print(f"\nNext up: \"{p['punch']}\" — {attr}")
            break

def main():
    args = sys.argv[1:]
    
    if not args:
        cmd_post()
        return
    
    if "--status" in args:
        cmd_status()
        return
    
    dry_run = "--dry-run" in args
    batch_size = 5
    specific = None
    
    for i, arg in enumerate(args):
        if arg == "--batch" and i + 1 < len(args):
            batch_size = int(args[i + 1])
        if arg == "--post-one" and i + 1 < len(args):
            specific = int(args[i + 1])
    
    cmd_post(batch_size=batch_size, dry_run=dry_run, specific=specific)

if __name__ == "__main__":
    main()

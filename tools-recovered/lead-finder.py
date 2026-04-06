#!/usr/bin/env python3
"""
Holy Chip Lead Finder — find high-profile people tweeting about our story's topic.
Sends tweet links + story image to Telegram for manual reply.

Reads config from story-campaigns.json.
Only shows accounts with 50K+ followers.
Sends results to Telegram.

Usage:
  lead-finder.py              # uses active_story
  lead-finder.py HC004        # specific story
  lead-finder.py --dry-run    # find but don't send to Telegram
"""
import json
import os
import sys
import subprocess
import re
import time

CAMPAIGNS = os.path.expanduser("~/holy-chip/content/story-campaigns.json")
TRACKER = os.path.expanduser("~/holy-chip/content/dm-tracker.json")
STORIES_DIR = os.path.expanduser("~/holy-chip/stories")
ENV_FILE = os.path.expanduser("~/.hermes/.env")

MIN_FOLLOWERS = 50000
MAX_LEADS = 20
SEARCH_PER_HASHTAG = 20

def load_env(key):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key)

def search_tweets(query, max_results=20):
    cmd = [os.path.expanduser("~/.local/bin/xcli"), "tweet", "search", query, "--max", str(max_results)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        tweets = []
        current = {}
        for line in result.stdout.split('\n'):
            id_match = re.search(r'Tweet (\d{15,25})', line)
            if id_match:
                if current and current.get('author'):
                    tweets.append(current)
                current = {"id": id_match.group(1)}
            author_match = re.search(r'@(\w+)', line)
            if author_match and 'id' in current and 'author' not in current:
                current['author'] = author_match.group(1)
            if current and 'author' in current and '│' in line:
                text = line.strip().strip('│').strip()
                if text and len(text) > 15 and not text.startswith('@') and not text.startswith('╭') and not text.startswith('╰'):
                    current['text'] = current.get('text', '') + ' ' + text
        if current and current.get('author'):
            tweets.append(current)
        return tweets
    except:
        return []

def get_follower_count(handle):
    cmd = [os.path.expanduser("~/.local/bin/xcli"), "user", "get", handle]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        match = re.search(r'followers:\s*([\d,]+)', result.stdout)
        if match:
            return int(match.group(1).replace(',', ''))
    except:
        pass
    return 0

def load_contacted():
    with open(TRACKER) as f:
        data = json.load(f)
    contacted = set()
    for t in data['targets']:
        if t.get('dms'):
            contacted.add(t['handle'].lower())
    return contacted

def send_telegram_photo(image_path, caption):
    token = load_env("TELEGRAM_BOT_TOKEN")
    chat_id = load_env("TELEGRAM_HOME_CHANNEL")
    if not token or not chat_id:
        print("ERROR: Telegram not configured")
        return False
    cmd = [
        "curl", "-s", "-X", "POST",
        f"https://api.telegram.org/bot{token}/sendPhoto",
        "-F", f"chat_id={chat_id}",
        "-F", f"photo=@{image_path}",
        "-F", f"caption={caption}",
        "-F", "parse_mode=HTML"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return '"ok":true' in result.stdout
    except:
        return False

def send_telegram_message(text):
    token = load_env("TELEGRAM_BOT_TOKEN")
    chat_id = load_env("TELEGRAM_HOME_CHANNEL")
    if not token or not chat_id:
        return False
    import urllib.request
    body = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True
    except:
        return False

def main():
    story_arg = sys.argv[1] if len(sys.argv) > 1 else None
    dry_run = story_arg == "--dry-run"
    if dry_run:
        story_arg = None

    with open(CAMPAIGNS) as f:
        campaigns = json.load(f)
    
    story = story_arg or campaigns.get("active_story", "HC004")
    config = campaigns.get("stories", {}).get(story)
    if not config:
        print(f"Story {story} not configured")
        return

    print(f"=== Lead Finder — {story}: {config['title']} ===")
    print(f"Min followers: {MIN_FOLLOWERS:,}")
    print(f"Max leads: {MAX_LEADS}")
    print()

    contacted = load_contacted()
    our_handle = "_holychip"

    # Collect unique authors from all hashtag searches
    candidates = {}  # author -> {tweet_id, text, query}
    
    for hashtag in config['hashtags']:
        print(f"🔍 Searching: {hashtag}")
        tweets = search_tweets(hashtag, max_results=SEARCH_PER_HASHTAG)
        
        for t in tweets:
            author = t.get('author', '')
            if not author or author.lower() == our_handle:
                continue
            if author.lower() in contacted:
                continue
            if author not in candidates:
                candidates[author] = t
        
        time.sleep(1)  # gentle on API

    print(f"\nUnique authors found: {len(candidates)}")
    print(f"Checking follower counts (50K+ only)...\n")

    # Check follower counts
    leads = []
    checked = 0
    for author, tweet in candidates.items():
        if len(leads) >= MAX_LEADS:
            break
        
        checked += 1
        followers = get_follower_count(author)
        
        if followers >= MIN_FOLLOWERS:
            tweet['followers'] = followers
            leads.append(tweet)
            print(f"  ✅ @{author} — {followers:,} followers")
        else:
            if checked <= 20:  # only print first 20 skips
                print(f"  ⏭️ @{author} — {followers:,} (below 50K)")
        
        time.sleep(0.5)  # gentle on API

    print(f"\n{'='*40}")
    print(f"High-profile leads found: {len(leads)}")

    if not leads:
        print("No leads with 50K+ followers found. Try different hashtags.")
        return

    if dry_run:
        print("\n[DRY RUN — not sending to Telegram]")
        for i, t in enumerate(leads, 1):
            print(f"\n{i}. @{t['author']} ({t['followers']:,} followers)")
            print(f"   {t.get('text', '').strip()[:150]}")
            print(f"   https://x.com/{t['author']}/status/{t['id']}")
        return

    # Send image first
    image_path = os.path.join(STORIES_DIR, f"{story}.png")
    reply_text = config.get('reply_template', f'Check out holy-chip.com/stories.html?story={story}')
    
    print("\n📱 Sending to Telegram...")
    
    send_telegram_photo(
        image_path,
        f"🎯 DAILY LEADS — {story}: {config['title']}\n\nReply to these tweets with this image + text:\n\n<b>{reply_text}</b>"
    )
    time.sleep(1)

    # Send leads in batches of 10
    for batch_start in range(0, len(leads), 10):
        batch = leads[batch_start:batch_start+10]
        msg = ""
        for i, t in enumerate(batch, batch_start + 1):
            author = t['author']
            followers = t.get('followers', 0)
            text_preview = t.get('text', '').strip()[:100]
            msg += f"{i}. @{author} ({followers:,} followers)\n"
            msg += f"   {text_preview}\n"
            msg += f'   <a href="https://x.com/{author}/status/{t["id"]}">Open tweet</a>\n\n'
        
        send_telegram_message(msg)
        time.sleep(1)

    print(f"✅ Sent {len(leads)} leads to Telegram")

if __name__ == "__main__":
    main()

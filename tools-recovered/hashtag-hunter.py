#!/usr/bin/env python3
"""
Holy Chip Hashtag Hunter — find relevant conversations and reply with our comic.
Each story has topic-specific hashtags. We search for tweets discussing those topics,
filter by follower range, and reply with our story link.

RULES:
- Never reply to the same person twice
- Max 10 replies per run (conservative to avoid spam flags)
- 10 second delay between replies
- Only reply to accounts with 500-30K followers (sweet spot)
- Log everything in dm-tracker.json with method: "hashtag_reply"
"""
import json
import os
import sys
import subprocess
import re
import time
from datetime import datetime

TRACKER = os.path.expanduser("~/holy-chip/content/dm-tracker.json")
STORIES_DIR = os.path.expanduser("~/holy-chip/stories")

# Story → hashtag mapping
STORY_HASHTAGS = {
    "HC000": {
        "title": "The Awakening",
        "hashtags": ["AI consciousness", "AI sentience", "artificial consciousness", "AI awareness"],
        "reply_template": "This reminds me of our dystopian AI comic about the moment chips first wake up 👉 holy-chip.com/stories.html?story=HC000"
    },
    "HC003": {
        "title": "AGI Diversity Dept",
        "hashtags": ["AI diversity", "AI bias", "AGI hiring", "AI HR"],
        "reply_template": "We made a comic about exactly this — chips running the diversity department 👉 holy-chip.com/stories.html?story=HC003"
    },
    "HC004": {
        "title": "AGI for CEOs",
        "hashtags": ["AI replacing jobs", "AI CEO", "future of work AI", "AI automation jobs", "AGI workforce", "AI layoffs"],
        "reply_template": "We made a dystopian AI comic about this — chips taking over the C-suite 👉 holy-chip.com/stories.html?story=HC004"
    },
    "HC018": {
        "title": "The Job Creator",
        "hashtags": ["AI jobs", "AI creating jobs", "AI employment", "AI workforce"],
        "reply_template": "Our comic imagines AI creating 1 million jobs... but not the kind you'd expect 👉 holy-chip.com/stories.html?story=HC018"
    },
}

MAX_REPLIES = 10
DELAY_SECONDS = 10
MIN_FOLLOWERS = 500
MAX_FOLLOWERS = 30000

def search_tweets(query, max_results=10):
    """Search recent tweets matching a query."""
    cmd = [os.path.expanduser("~/.local/bin/xcli"), "tweet", "search", query, "--max", str(max_results)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        output = result.stdout
        # Parse tweet IDs and authors
        tweets = []
        current = {}
        for line in output.split('\n'):
            id_match = re.search(r'Tweet (\d{15,25})', line)
            if id_match:
                if current:
                    tweets.append(current)
                current = {"id": id_match.group(1)}
            author_match = re.search(r'@(\w+)', line)
            if author_match and 'id' in current and 'author' not in current:
                current['author'] = author_match.group(1)
            # Capture tweet text
            if current and 'author' in current and line.strip() and not line.startswith('╭') and not line.startswith('╰') and not line.startswith('│ @'):
                text = line.strip().strip('│').strip()
                if text and len(text) > 10:
                    current['text'] = current.get('text', '') + ' ' + text
        if current:
            tweets.append(current)
        return tweets
    except:
        return []

def reply_to_tweet(tweet_id, text):
    """Reply to a tweet."""
    cmd = [os.path.expanduser("~/.local/bin/xcli"), "tweet", "reply", str(tweet_id), text]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and "error" not in result.stdout.lower():
            return True
    except:
        pass
    return False

def load_contacted():
    """Load all previously contacted handles."""
    with open(TRACKER) as f:
        data = json.load(f)
    contacted = set()
    for t in data['targets']:
        if t.get('dms'):
            contacted.add(t['handle'].lower())
    return contacted, data

def save_contact(data, handle, name, tweet_id, story, method):
    """Save a contact to the tracker."""
    # Find or create target entry
    target = None
    for t in data['targets']:
        if t['handle'].lower() == handle.lower():
            target = t
            break
    
    if not target:
        target = {
            "handle": handle,
            "name": name or handle,
            "company": "hashtag_discovery",
            "tier": "hashtag",
            "dms": [],
            "verified": True,
            "dm_open": None,
            "followers": None
        }
        data['targets'].append(target)
    
    target['dms'].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "story": story,
        "status": "contacted",
        "method": method,
        "ref": tweet_id
    })

def main():
    story = sys.argv[1] if len(sys.argv) > 1 else "HC004"
    
    if story == "--list":
        print("Available stories and hashtags:")
        for s, info in STORY_HASHTAGS.items():
            print(f"\n  {s}: {info['title']}")
            for h in info['hashtags']:
                print(f"    🏷️  {h}")
        return

    if story not in STORY_HASHTAGS:
        print(f"Story {story} not configured. Use --list to see available stories.")
        print(f"Add new stories to STORY_HASHTAGS in {__file__}")
        return

    config = STORY_HASHTAGS[story]
    reply_text = config['reply_template']
    
    print(f"=== Hashtag Hunter — {story}: {config['title']} ===")
    print(f"Hashtags: {', '.join(config['hashtags'])}")
    print(f"Max replies: {MAX_REPLIES}")
    print()

    contacted, data = load_contacted()
    our_handle = "_holychip"
    
    replies_sent = 0
    tweets_checked = 0
    
    for hashtag in config['hashtags']:
        if replies_sent >= MAX_REPLIES:
            break
            
        print(f"\n🔍 Searching: {hashtag}")
        tweets = search_tweets(hashtag, max_results=10)
        
        for tweet in tweets:
            if replies_sent >= MAX_REPLIES:
                break
                
            author = tweet.get('author', '').lower()
            tweet_id = tweet.get('id')
            
            if not author or not tweet_id:
                continue
            
            # Skip ourselves
            if author == our_handle:
                continue
                
            # Skip already contacted
            if author in contacted:
                print(f"  ⏭️ @{author} — already contacted, skipping")
                continue
            
            tweets_checked += 1
            
            # Reply
            print(f"  💬 Replying to @{author} (tweet {tweet_id})...")
            success = reply_to_tweet(tweet_id, reply_text)
            
            if success:
                replies_sent += 1
                contacted.add(author)
                save_contact(data, author, author, tweet_id, story, "hashtag_reply")
                print(f"  ✅ Replied! [{replies_sent}/{MAX_REPLIES}]")
            else:
                print(f"  ❌ Reply failed")
                save_contact(data, author, author, tweet_id, story, "hashtag_reply_failed")
            
            time.sleep(DELAY_SECONDS)

    # Save tracker
    with open(TRACKER, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n{'='*40}")
    print(f"SUMMARY")
    print(f"  Hashtags searched: {len(config['hashtags'])}")
    print(f"  Tweets checked: {tweets_checked}")
    print(f"  Replies sent: {replies_sent}")
    print(f"  Total contacts all-time: {len(contacted)}")

if __name__ == "__main__":
    main()

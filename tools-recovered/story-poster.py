#!/usr/bin/env python3
"""
Holy Chip Story Poster — posts one full story every 3 days.
Tracks which stories have been posted in story-posts.json.
Never repeats a story.

Usage:
  story-poster.py           # post next story
  story-poster.py --status  # show what's been posted
  story-poster.py --force HC005  # force post a specific story
"""
import json
import os
import sys
import subprocess
from datetime import datetime

STORIES_DIR = os.path.expanduser("~/holy-chip/stories")
POSTS_FILE = os.path.expanduser("~/holy-chip/content/story-posts.json")
CAMPAIGNS = os.path.expanduser("~/holy-chip/content/story-campaigns.json")

# Story order to post (skip HC017/HC018 split pages)
STORY_ORDER = [
    "HC000", "HC001", "HC002", "HC003", "HC004", "HC005",
    "HC006", "HC007", "HC008", "HC009", "HC010", "HC011",
    "HC012", "HC013", "HC014", "HC015", "HC016", "HC017", "HC018"
]

def load_posts():
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE) as f:
            return json.load(f)
    return {"posted": [], "metadata": {"updated": ""}}

def save_posts(data):
    data["metadata"]["updated"] = str(datetime.now().strftime("%Y-%m-%d %H:%M"))
    with open(POSTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_story_title(story_id):
    """Try to get title from story-campaigns.json or JSON file."""
    if os.path.exists(CAMPAIGNS):
        with open(CAMPAIGNS) as f:
            campaigns = json.load(f)
        stories = campaigns.get("stories", {})
        if story_id in stories:
            return stories[story_id].get("title", "")
    
    json_file = os.path.join(STORIES_DIR, f"{story_id}.json")
    if os.path.exists(json_file):
        try:
            with open(json_file) as f:
                data = json.load(f)
            return data.get("title", data.get("name", ""))
        except:
            pass
    return ""

def get_next_story(posts_data):
    posted_ids = {p["story"] for p in posts_data["posted"]}
    for story in STORY_ORDER:
        if story not in posted_ids:
            image = os.path.join(STORIES_DIR, f"{story}.png")
            if os.path.exists(image):
                return story
    return None

def post_story(story_id):
    image = os.path.join(STORIES_DIR, f"{story_id}.png")
    title = get_story_title(story_id)
    
    num = story_id[2:]  # "000" from "HC000"
    
    if title:
        text = f"Holy Chip #{num} — {title}\n\nholy-chip.com/stories.html?story={story_id}\n\n#HolyChip #AI #AGI #dystopia"
    else:
        text = f"Holy Chip #{num}\n\nholy-chip.com/stories.html?story={story_id}\n\n#HolyChip #AI #AGI #dystopia"
    
    print(f"📤 Posting {story_id}: {title}")
    print(f"   Image: {image}")
    print(f"   Text: {text}")
    
    cmd = ["python3", os.path.expanduser("~/holy-chip/tools/tweet_image.py"), image, text]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ Posted!")
            return True
        else:
            print(f"❌ Failed: {result.stdout[:200]} {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        data = load_posts()
        if not data["posted"]:
            print("No stories posted yet.")
        else:
            print("Posted stories:")
            for p in data["posted"]:
                print(f"  {p['story']}: {p.get('title','')} — {p['date']}")
        
        next_story = get_next_story(data)
        print(f"\nNext up: {next_story}")
        remaining = len([s for s in STORY_ORDER if s not in {p['story'] for p in data['posted']}])
        print(f"Remaining: {remaining} stories")
        return

    if len(sys.argv) > 2 and sys.argv[1] == "--force":
        story_id = sys.argv[2]
        data = load_posts()
        title = get_story_title(story_id)
        success = post_story(story_id)
        if success:
            data["posted"].append({
                "story": story_id,
                "title": title,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "method": "forced"
            })
            save_posts(data)
        return

    # Normal flow: post next story
    data = load_posts()
    next_story = get_next_story(data)
    
    if not next_story:
        print("🎉 All stories have been posted!")
        return
    
    title = get_story_title(next_story)
    success = post_story(next_story)
    
    if success:
        data["posted"].append({
            "story": next_story,
            "title": title,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "method": "scheduled"
        })
        save_posts(data)
        
        # What's next
        next_next = get_next_story(data)
        if next_next:
            print(f"\n📅 Next story: {next_next} (in 3 days)")
        else:
            print(f"\n🎉 That was the last story!")
    else:
        print(f"\n⚠️ Failed to post. Will retry next run.")

if __name__ == "__main__":
    main()

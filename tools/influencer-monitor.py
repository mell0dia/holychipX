#!/usr/bin/env python3
"""
Holy Chip Influencer Monitor — dedicated tracker for the influencer list.
Runs 4x/day. Detects NEW tweets, extracts phrases, saves to influencers_db.json.

Separate from: video digests, hashtag searches, DM outreach.
Those have their own pipelines.

Usage:
  influencer-monitor.py              # normal run: check all, report new
  influencer-monitor.py --status     # show DB stats
  influencer-monitor.py --search <q> # search DB
  influencer-monitor.py @karpathy    # check one influencer only
"""
import json
import os
import sys
import subprocess
import re
import urllib.request
from datetime import datetime, date

# ── Paths ──
INFLUENCERS_FILE = os.path.expanduser("~/holy-chip/content/influencers.json")
DB_FILE = os.path.expanduser("~/holy-chip/content/influencers_db.json")
ENV_FILE = os.path.expanduser("~/.hermes/.env")
XCLI = os.path.expanduser("~/.local/bin/xcli")

MAX_TWEETS_PER_INFLUENCER = 10


def load_env(key):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key)


def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {
        "metadata": {
            "description": "Influencer tweet database — new tweets + extracted phrases",
            "created": str(date.today()),
            "updated": "",
            "total_tweets": 0,
            "total_phrases": 0
        },
        "tweets": []
    }


def save_db(db):
    db["metadata"]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    db["metadata"]["total_tweets"] = len(db["tweets"])
    db["metadata"]["total_phrases"] = sum(
        len(t.get("phrases", [])) for t in db["tweets"]
    )
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


def get_known_tweet_ids(db):
    return {t["tweet_id"] for t in db["tweets"]}


def fetch_tweets(handle):
    """Fetch latest tweets from an influencer via xcli."""
    handle = handle.lstrip("@")
    cmd = [XCLI, "tweet", "search", f"from:{handle}", "--max",
           str(MAX_TWEETS_PER_INFLUENCER)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        tweets = []
        current = {}
        current_text_lines = []

        for line in result.stdout.split("\n"):
            # New tweet header
            id_match = re.search(r"Tweet (\d{15,25})", line)
            if id_match:
                # Save previous tweet
                if current.get("tweet_id") and current_text_lines:
                    current["text"] = " ".join(current_text_lines).strip()
                    tweets.append(current)
                current = {
                    "tweet_id": id_match.group(1),
                    "handle": handle
                }
                current_text_lines = []
                continue

            # Author line (skip)
            if current.get("tweet_id") and re.match(r"^│\s*@\w+\s*│?$", line.strip()):
                continue

            # Tweet text lines
            if current.get("tweet_id") and "│" in line:
                text = line.strip().strip("│").strip()
                # Skip decorative lines
                if text and not text.startswith("╭") and not text.startswith("╰"):
                    if len(text) > 2:
                        current_text_lines.append(text)

        # Don't forget the last tweet
        if current.get("tweet_id") and current_text_lines:
            current["text"] = " ".join(current_text_lines).strip()
            tweets.append(current)

        return tweets
    except Exception as e:
        print(f"  ERROR fetching @{handle}: {e}")
        return []


def extract_links(text):
    """Extract URLs from tweet text."""
    return re.findall(r"https?://\S+", text)


def extract_phrases_from_tweet(tweet_text, handle):
    """Use Haiku to extract profound phrases from a tweet, if substantial."""
    # Skip short tweets — not enough content for phrase extraction
    if len(tweet_text.split()) < 25:
        return []

    api_key = load_env("ANTHROPIC_API_KEY") or load_env("ANTHROPIC_TOKEN")
    if not api_key:
        return []

    prompt = f"""Extract 1-3 profound, quotable phrases from this tweet by @{handle}.
Only extract if there's genuine insight about AI, technology, humanity, or the future.
If the tweet is mundane (just a reply, link share, joke with no depth), return an empty array.

Rules:
- Each phrase must stand alone and make sense without context
- Clean up but keep the speaker's voice
- Only genuinely profound/insightful/visionary statements

Return ONLY valid JSON array (no markdown, no backticks):
[
  {{
    "phrase": "the exact quote",
    "context": "one sentence about what they were discussing",
    "weight": "high or medium"
  }}
]

If nothing profound, return: []

TWEET:
{tweet_text}"""

    body = json.dumps({
        "model": "claude-3-haiku-20240307",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text = result["content"][0]["text"].strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            phrases = json.loads(text)
            if isinstance(phrases, list):
                return phrases
    except Exception as e:
        print(f"    Phrase extraction error: {e}")
    return []


def run_status(db):
    """Show DB statistics."""
    print(f"═══ Influencer DB Status ═══")
    print(f"  Total tweets tracked: {db['metadata']['total_tweets']}")
    print(f"  Total phrases extracted: {db['metadata']['total_phrases']}")
    print(f"  Last updated: {db['metadata'].get('updated', 'never')}")
    print()

    # Per-influencer breakdown
    by_handle = {}
    for t in db["tweets"]:
        h = t["handle"]
        if h not in by_handle:
            by_handle[h] = {"tweets": 0, "phrases": 0}
        by_handle[h]["tweets"] += 1
        by_handle[h]["phrases"] += len(t.get("phrases", []))

    if by_handle:
        print("  Per influencer:")
        for h, stats in sorted(by_handle.items(), key=lambda x: -x[1]["tweets"]):
            print(f"    @{h}: {stats['tweets']} tweets, {stats['phrases']} phrases")
    else:
        print("  No data yet.")


def run_search(db, query):
    """Search tweets and phrases in DB."""
    query = query.lower()
    matches = []
    for t in db["tweets"]:
        if (query in t.get("text", "").lower() or
            query in t.get("handle", "").lower() or
            any(query in p.get("phrase", "").lower() for p in t.get("phrases", []))):
            matches.append(t)

    if not matches:
        print(f"No matches for '{query}'")
        return

    print(f"Found {len(matches)} matching tweets:\n")
    for t in matches:
        print(f"  @{t['handle']} | {t.get('captured_at', '?')}")
        print(f"  {t['text'][:200]}")
        for p in t.get("phrases", []):
            w = "🔥" if p.get("weight") == "high" else "💡"
            print(f"    {w} \"{p['phrase']}\"")
        print()


def main():
    db = load_db()

    # --status
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        run_status(db)
        return

    # --search
    if len(sys.argv) > 1 and sys.argv[1] == "--search":
        query = " ".join(sys.argv[2:])
        run_search(db, query)
        return

    # Load influencer list
    with open(INFLUENCERS_FILE) as f:
        data = json.load(f)
    influencers = [i for i in data["influencers"] if i["type"] == "twitter"]

    # Filter to one if specified
    if len(sys.argv) > 1 and sys.argv[1].startswith("@"):
        target = sys.argv[1].lstrip("@").lower()
        influencers = [i for i in influencers
                       if i["handle"].lstrip("@").lower() == target]

    known_ids = get_known_tweet_ids(db)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  INFLUENCER MONITOR — {now}")
    print(f"  Checking {len(influencers)} accounts")
    print(f"  Known tweets in DB: {len(known_ids)}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    total_new = 0
    total_phrases = 0
    new_tweets_report = []

    for inf in influencers:
        handle = inf["handle"].lstrip("@")
        desc = inf.get("description", "")

        tweets = fetch_tweets(handle)

        if not tweets:
            continue

        new_tweets = [t for t in tweets if t["tweet_id"] not in known_ids]

        if not new_tweets:
            continue

        print(f"\n{'='*50}")
        print(f"👤 @{handle} — {len(new_tweets)} NEW tweet(s)")
        if desc:
            print(f"   {desc}")
        print(f"{'='*50}")

        for t in new_tweets:
            total_new += 1
            links = extract_links(t.get("text", ""))

            # Extract phrases from substantial tweets
            phrases = extract_phrases_from_tweet(t.get("text", ""), handle)
            total_phrases += len(phrases)

            # Build DB entry
            entry = {
                "tweet_id": t["tweet_id"],
                "handle": handle,
                "text": t.get("text", ""),
                "links": links,
                "tweet_url": f"https://x.com/{handle}/status/{t['tweet_id']}",
                "captured_at": now,
                "phrases": phrases
            }
            db["tweets"].append(entry)

            # Print for report
            text_preview = t.get("text", "")[:250]
            print(f"\n  💬 {text_preview}")
            print(f"  🔗 https://x.com/{handle}/status/{t['tweet_id']}")
            if links:
                print(f"  📎 Links: {', '.join(links[:3])}")
            for p in phrases:
                w = "🔥" if p.get("weight") == "high" else "💡"
                print(f"  {w} \"{p['phrase']}\"")

            # Build Telegram report entry
            new_tweets_report.append({
                "handle": handle,
                "text": text_preview,
                "url": entry["tweet_url"],
                "phrases": phrases
            })

    # Save DB
    save_db(db)

    # Summary
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  SUMMARY")
    print(f"  New tweets captured: {total_new}")
    print(f"  Phrases extracted: {total_phrases}")
    print(f"  Total in DB: {db['metadata']['total_tweets']} tweets, "
          f"{db['metadata']['total_phrases']} phrases")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if total_new == 0:
        print("\n📭 No new tweets from influencers since last check.")


if __name__ == "__main__":
    main()

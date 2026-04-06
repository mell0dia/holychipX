#!/usr/bin/env python3
"""
Run Influencers — check latest tweets from all tracked influencers.
Extract profound phrases, organize by person.

Usage:
  run-influencers.py              # check all influencers
  run-influencers.py @karpathy    # check one person
"""
import json
import os
import sys
import subprocess
import re

INFLUENCERS_FILE = os.path.expanduser("~/holy-chip/content/influencers.json")

def get_tweets(handle):
    """Get latest tweets from a handle."""
    handle = handle.lstrip("@")
    cmd = [os.path.expanduser("~/.local/bin/xcli"), "tweet", "search", f"from:{handle}", "--max", "10"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        # Parse tweets
        tweets = []
        current_text = ""
        for line in result.stdout.split('\n'):
            if '───' in line and 'Tweet' in line:
                if current_text.strip():
                    tweets.append(current_text.strip())
                current_text = ""
            elif '│' in line:
                text = line.strip().strip('│').strip()
                if text and not text.startswith('@') and len(text) > 5:
                    # Skip if it's just a handle line
                    if not re.match(r'^@\w+\s*$', text):
                        current_text += " " + text
        if current_text.strip():
            tweets.append(current_text.strip())
        return tweets
    except:
        return []

def main():
    # Load influencers
    with open(INFLUENCERS_FILE) as f:
        data = json.load(f)
    
    influencers = [i for i in data['influencers'] if i['type'] == 'twitter']
    
    # Filter to one person if specified
    if len(sys.argv) > 1 and sys.argv[1].startswith("@"):
        target = sys.argv[1].lstrip("@").lower()
        influencers = [i for i in influencers if i['handle'].lstrip("@").lower() == target]
    
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  INFLUENCER REPORT — {len(influencers)} accounts")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    for inf in influencers:
        handle = inf['handle'].lstrip("@")
        desc = inf.get('description', '')
        
        tweets = get_tweets(handle)
        
        if not tweets:
            print(f"\n🔇 @{handle} — silent")
            continue
        
        print(f"\n{'='*50}")
        print(f"👤 @{handle}")
        if desc:
            print(f"   {desc}")
        print(f"   Tweets found: {len(tweets)}")
        print(f"{'='*50}")
        
        for i, tweet in enumerate(tweets, 1):
            # Clean up
            tweet = tweet.strip()
            if len(tweet) < 10:
                continue
            # Flag crypto
            crypto = ""
            if any(w in tweet.lower() for w in ['bitcoin', 'btc', 'crypto', 'stablecoin', 'ethereum', 'solana']):
                crypto = " 🪙 CRYPTO"
            
            print(f"\n  💬 {tweet[:300]}")
            if crypto:
                print(f"  {crypto}")
    
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Done. {len(influencers)} influencers checked.")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Video digest tool — fetch YouTube transcript, summarize, save to library."""
import sys
import json
import re
import subprocess
import os
from datetime import date

LIBRARY = os.path.expanduser("~/holy-chip/content/video-library.json")
TRANSCRIPT_SCRIPT = os.path.expanduser("~/.hermes/skills/media/youtube-content/scripts/fetch_transcript.py")

def extract_video_id(url):
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:v=|\/)([\w-]{11})(?:\?|&|$)',
        r'youtu\.be\/([\w-]{11})',
        r'embed\/([\w-]{11})',
        r'shorts\/([\w-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return url.strip()[-11:]  # last resort

def fetch_transcript(url):
    """Fetch transcript using the youtube-content skill script."""
    result = subprocess.run(
        ["python3", TRANSCRIPT_SCRIPT, url, "--text-only"],
        capture_output=True, text=True, timeout=30
    )
    text = result.stdout.strip()
    # Filter out warnings
    lines = [l for l in text.split('\n') if 'urllib3' not in l and 'NotOpenSSL' not in l and 'warnings' not in l]
    return '\n'.join(lines)

def save_to_library(entry):
    """Append video entry to the library JSON."""
    with open(LIBRARY) as f:
        data = json.load(f)
    
    # Don't duplicate
    existing_ids = {v['id'] for v in data['videos']}
    if entry['id'] in existing_ids:
        print(f"Video {entry['id']} already in library, updating...")
        data['videos'] = [v for v in data['videos'] if v['id'] != entry['id']]
    
    data['videos'].append(entry)
    data['metadata']['updated'] = str(date.today())
    
    with open(LIBRARY, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    if len(sys.argv) < 2:
        print("Usage: video-digest.py <youtube-url>")
        print("       video-digest.py --remove <video-id>")
        print("       video-digest.py --search <keyword>")
        sys.exit(1)

    if sys.argv[1] == "--remove":
        vid_id = sys.argv[2] if len(sys.argv) > 2 else None
        if not vid_id:
            # Remove last
            with open(LIBRARY) as f:
                data = json.load(f)
            if data['videos']:
                removed = data['videos'].pop()
                with open(LIBRARY, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"Removed: {removed['title']}")
            else:
                print("Library is empty")
            return

    if sys.argv[1] == "--search":
        query = ' '.join(sys.argv[2:]).lower()
        with open(LIBRARY) as f:
            data = json.load(f)
        matches = []
        for v in data['videos']:
            searchable = f"{v.get('title','')} {v.get('summary','')} {' '.join(v.get('topics',[]))} {' '.join(v.get('key_points',[]))}".lower()
            if query in searchable:
                matches.append(v)
        if matches:
            for v in matches:
                print(f"🎬 {v['title']}")
                print(f"   {v['url']}")
                print(f"   Topics: {', '.join(v.get('topics',[]))}")
                print(f"   {v['summary'][:150]}...")
                print()
        else:
            print(f"No videos found matching '{query}'")
        return

    url = sys.argv[1]
    video_id = extract_video_id(url)
    
    print(f"Fetching transcript for {video_id}...")
    transcript = fetch_transcript(url)
    
    if not transcript or len(transcript) < 50:
        print("ERROR: Could not fetch transcript")
        print(f"Raw output: {transcript[:200]}")
        sys.exit(1)
    
    # Truncate for output (full transcript available but we summarize)
    word_count = len(transcript.split())
    print(f"Transcript: {word_count} words")
    
    # Output transcript for LLM to summarize
    # The LLM calling this script will read stdout and do the summarization
    print(f"VIDEO_ID: {video_id}")
    print(f"URL: {url}")
    print(f"TRANSCRIPT_START")
    # Limit to first 8000 words to avoid token explosion
    words = transcript.split()
    if len(words) > 8000:
        print(' '.join(words[:8000]))
        print(f"\n[TRUNCATED — {len(words)} total words, showing first 8000]")
    else:
        print(transcript)
    print(f"TRANSCRIPT_END")

if __name__ == "__main__":
    main()

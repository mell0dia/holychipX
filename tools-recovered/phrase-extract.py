#!/usr/bin/env python3
"""
Extract profound, impactful phrases from video transcripts.
Usage:
  phrase-extract.py <youtube-url>          # Extract from a video
  phrase-extract.py --file <transcript>    # Extract from a text file
  phrase-extract.py --list                 # Show all collected phrases
  phrase-extract.py --search <keyword>     # Search phrases
"""
import sys
import json
import os
import re
import subprocess
import urllib.request
from datetime import date

PHRASES_FILE = os.path.expanduser("~/holy-chip/content/phrases.json")
TRANSCRIPT_SCRIPT = os.path.expanduser("~/.hermes/skills/media/youtube-content/scripts/fetch_transcript.py")
ENV_FILE = os.path.expanduser("~/.hermes/.env")

def load_api_key():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY=") and not line.startswith("#"):
                val = line.split("=", 1)[1].strip()
                if val: return val
            if line.startswith("ANTHROPIC_TOKEN=") and not line.startswith("#"):
                val = line.split("=", 1)[1].strip()
                if val: return val
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_TOKEN")

def extract_video_id(url):
    for p in [r'(?:v=)([\w-]{11})', r'youtu\.be/([\w-]{11})', r'embed/([\w-]{11})']:
        m = re.search(p, url)
        if m: return m.group(1)
    return url.strip()[-11:]

def fetch_transcript(url):
    result = subprocess.run(
        ["python3", TRANSCRIPT_SCRIPT, url, "--text-only"],
        capture_output=True, text=True, timeout=30
    )
    lines = [l for l in result.stdout.split('\n')
             if 'urllib3' not in l and 'NotOpenSSL' not in l and 'warnings' not in l]
    return '\n'.join(lines).strip()

def extract_phrases(transcript, source_title="", source_url=""):
    api_key = load_api_key()
    if not api_key:
        print("ERROR: No API key"); sys.exit(1)

    # Chunk if too long (keep under 8000 words per call)
    words = transcript.split()
    chunks = []
    for i in range(0, len(words), 7000):
        chunks.append(' '.join(words[i:i+7000]))

    all_phrases = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"  Processing chunk {i+1}/{len(chunks)}...")

        prompt = f"""You are a phrase curator. Extract the most PROFOUND, IMPACTFUL, and QUOTABLE phrases from this transcript.

Rules:
- Find 5-15 phrases that have DEEPER MEANING about the future, technology, humanity, or AI
- Each phrase should stand alone — make sense without context
- Prefer phrases that are surprising, philosophical, or visionary
- Clean up filler words (um, uh, like) but keep the speaker's voice
- Include who said it if identifiable from context

Return ONLY valid JSON array (no markdown, no backticks):
[
  {{
    "phrase": "the exact quote, cleaned up",
    "speaker": "name if known, or 'unknown'",
    "context": "one sentence about what they were discussing",
    "weight": "high/medium — how profound is this"
  }}
]

TRANSCRIPT:
{chunk}"""

        body = json.dumps({
            "model": "claude-3-haiku-20240307",
            "max_tokens": 2000,
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
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                text = result["content"][0]["text"].strip()
                if text.startswith("```"):
                    text = re.sub(r'^```(?:json)?\n?', '', text)
                    text = re.sub(r'\n?```$', '', text)
                phrases = json.loads(text)
                for p in phrases:
                    p["source_title"] = source_title
                    p["source_url"] = source_url
                    p["date_extracted"] = str(date.today())
                all_phrases.extend(phrases)
        except Exception as e:
            print(f"  Error on chunk {i+1}: {e}")

    return all_phrases

def save_phrases(new_phrases):
    if os.path.exists(PHRASES_FILE):
        with open(PHRASES_FILE) as f:
            data = json.load(f)
    else:
        data = {"metadata": {"description": "Collected profound phrases from videos and influencers", "updated": ""}, "phrases": []}

    data["phrases"].extend(new_phrases)
    data["metadata"]["updated"] = str(date.today())

    with open(PHRASES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  phrase-extract.py <youtube-url>")
        print("  phrase-extract.py --list")
        print("  phrase-extract.py --search <keyword>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--list":
        if not os.path.exists(PHRASES_FILE):
            print("No phrases collected yet."); return
        with open(PHRASES_FILE) as f:
            data = json.load(f)
        for i, p in enumerate(data["phrases"], 1):
            weight = "🔥" if p.get("weight") == "high" else "💡"
            print(f"{weight} \"{p['phrase']}\"")
            print(f"   — {p.get('speaker', '?')} | {p.get('source_title', '?')}")
            print()
        print(f"Total: {len(data['phrases'])} phrases")
        return

    if cmd == "--search":
        query = ' '.join(sys.argv[2:]).lower()
        if not os.path.exists(PHRASES_FILE):
            print("No phrases collected yet."); return
        with open(PHRASES_FILE) as f:
            data = json.load(f)
        matches = [p for p in data["phrases"]
                   if query in p.get("phrase","").lower()
                   or query in p.get("context","").lower()
                   or query in p.get("speaker","").lower()]
        for p in matches:
            weight = "🔥" if p.get("weight") == "high" else "💡"
            print(f"{weight} \"{p['phrase']}\"")
            print(f"   — {p.get('speaker', '?')} | {p.get('context', '')}")
            print()
        print(f"Found: {len(matches)} phrases matching '{query}'")
        return

    # Extract from YouTube URL
    url = cmd
    video_id = extract_video_id(url)
    print(f"📥 Fetching transcript for {video_id}...")
    transcript = fetch_transcript(url)
    if not transcript or len(transcript) < 50:
        print("ERROR: Could not fetch transcript"); sys.exit(1)

    word_count = len(transcript.split())
    print(f"📄 Transcript: {word_count} words")
    print(f"🔍 Extracting profound phrases via Haiku (~${word_count * 0.0000008:.3f})...")

    # Try to get title from video library
    title = ""
    lib_path = os.path.expanduser("~/holy-chip/content/video-library.json")
    if os.path.exists(lib_path):
        with open(lib_path) as f:
            lib = json.load(f)
        for v in lib["videos"]:
            if v.get("id") == video_id:
                title = v.get("title", "")
                break

    phrases = extract_phrases(transcript, source_title=title, source_url=url)

    if phrases:
        save_phrases(phrases)
        print(f"\n{'='*60}")
        print(f"💎 EXTRACTED {len(phrases)} PROFOUND PHRASES")
        print(f"{'='*60}\n")
        for p in phrases:
            weight = "🔥" if p.get("weight") == "high" else "💡"
            print(f"{weight} \"{p['phrase']}\"")
            print(f"   — {p.get('speaker', '?')} | {p.get('context', '')}")
            print()
        print(f"✅ Saved to {PHRASES_FILE}")
    else:
        print("No phrases extracted.")

if __name__ == "__main__":
    main()

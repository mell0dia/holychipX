#!/usr/bin/env python3
"""Post a tweet with an image to X/Twitter.
Usage: python3 tweet_image.py <image_path> <text> [--reply-to <tweet_id>]
"""
import json, os, sys, subprocess

def ensure_oauthlib():
    try:
        from requests_oauthlib import OAuth1Session
        return OAuth1Session
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests-oauthlib", "-q"])
        from requests_oauthlib import OAuth1Session
        return OAuth1Session

def get_creds():
    """Get credentials, sourcing from xcli wrapper if needed."""
    keys = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    creds = {k: os.environ.get(k) for k in keys}

    # If any missing, try sourcing from xcli wrapper
    if not all(creds.values()):
        xcli_path = os.path.expanduser("~/.local/bin/xcli")
        if os.path.exists(xcli_path):
            with open(xcli_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export "):
                        parts = line[7:].split("=", 1)
                        if len(parts) == 2 and parts[0] in keys:
                            val = parts[1].strip('"').strip("'")
                            creds[parts[0]] = val

    missing = [k for k in keys if not creds.get(k)]
    if missing:
        print(f"Error: Missing credentials: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return creds

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 tweet_image.py <image_path> <text> [--reply-to <tweet_id>]")
        sys.exit(0)

    image_path = sys.argv[1]
    text = sys.argv[2]
    reply_to = None

    if "--reply-to" in sys.argv:
        idx = sys.argv.index("--reply-to")
        if idx + 1 < len(sys.argv):
            reply_to = sys.argv[idx + 1]

    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    OAuth1Session = ensure_oauthlib()
    creds = get_creds()

    oauth = OAuth1Session(
        creds["X_API_KEY"],
        client_secret=creds["X_API_SECRET"],
        resource_owner_key=creds["X_ACCESS_TOKEN"],
        resource_owner_secret=creds["X_ACCESS_TOKEN_SECRET"],
    )

    # Step 1: Upload media
    print(f"Uploading: {image_path}")
    with open(image_path, "rb") as f:
        resp = oauth.post("https://upload.twitter.com/1.1/media/upload.json", files={"media": f})

    if resp.status_code != 200:
        print(f"Upload failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    media_id = resp.json()["media_id_string"]
    print(f"Media ID: {media_id}")

    # Step 2: Post tweet
    payload = {
        "text": text,
        "media": {"media_ids": [media_id]}
    }
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}

    resp = oauth.post("https://api.twitter.com/2/tweets", json=payload)

    if resp.status_code in (200, 201):
        data = resp.json()
        tweet_id = data["data"]["id"]
        print(f"Posted! https://x.com/_holychip/status/{tweet_id}")
        # Output just the ID on last line for scripting
        print(f"TWEET_ID:{tweet_id}")
    else:
        print(f"Post failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

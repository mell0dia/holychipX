#!/bin/bash
# tweet-with-image.sh — Post a tweet with an image to X/Twitter
# Usage: ./tweet-with-image.sh <image_path> <text>
# Requires: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET env vars

set -e

IMAGE_PATH="$1"
TEXT="$2"

if [ -z "$IMAGE_PATH" ] || [ -z "$TEXT" ]; then
  echo "Usage: tweet-with-image.sh <image_path> <text>"
  exit 1
fi

if [ ! -f "$IMAGE_PATH" ]; then
  echo "Error: Image not found: $IMAGE_PATH"
  exit 1
fi

# Source credentials from xcli wrapper if they exist
if [ -f ~/.local/bin/xcli ]; then
  eval $(grep "^export" ~/.local/bin/xcli)
fi

# Step 1: Upload media via v1.1 media/upload endpoint
echo "Uploading image: $IMAGE_PATH"
MEDIA_RESPONSE=$(curl -s -X POST "https://upload.twitter.com/1.1/media/upload.json" \
  --oauth-consumer-key "$X_API_KEY" \
  --oauth-consumer-secret "$X_API_SECRET" \
  --oauth-token "$X_ACCESS_TOKEN" \
  --oauth-token-secret "$X_ACCESS_TOKEN_SECRET" \
  -F "media=@${IMAGE_PATH}")

# Try with python + tweepy if curl oauth doesn't work
if echo "$MEDIA_RESPONSE" | grep -q "media_id_string"; then
  MEDIA_ID=$(echo "$MEDIA_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['media_id_string'])")
  echo "Media uploaded: $MEDIA_ID"
else
  # Fallback: use python with requests_oauthlib
  MEDIA_ID=$(python3 << PYEOF
import json, os, sys
try:
    from requests_oauthlib import OAuth1Session
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests-oauthlib", "-q"])
    from requests_oauthlib import OAuth1Session

oauth = OAuth1Session(
    os.environ["X_API_KEY"],
    client_secret=os.environ["X_API_SECRET"],
    resource_owner_key=os.environ["X_ACCESS_TOKEN"],
    resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
)

# Upload media
with open("${IMAGE_PATH}", "rb") as f:
    files = {"media": f}
    resp = oauth.post("https://upload.twitter.com/1.1/media/upload.json", files=files)
    if resp.status_code != 200:
        print(f"Upload failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    media_id = resp.json()["media_id_string"]
    print(media_id)
PYEOF
  )
  echo "Media uploaded: $MEDIA_ID"
fi

# Step 2: Post tweet with media
python3 << PYEOF
import json, os, sys
try:
    from requests_oauthlib import OAuth1Session
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests-oauthlib", "-q"])
    from requests_oauthlib import OAuth1Session

oauth = OAuth1Session(
    os.environ["X_API_KEY"],
    client_secret=os.environ["X_API_SECRET"],
    resource_owner_key=os.environ["X_ACCESS_TOKEN"],
    resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
)

payload = {
    "text": """${TEXT}""",
    "media": {"media_ids": ["${MEDIA_ID}"]}
}

resp = oauth.post("https://api.twitter.com/2/tweets", json=payload)
if resp.status_code in (200, 201):
    data = resp.json()
    tweet_id = data["data"]["id"]
    print(f"Tweet posted! ID: {tweet_id}")
    print(f"https://x.com/_holychip/status/{tweet_id}")
else:
    print(f"Failed: {resp.status_code} {resp.text}", file=sys.stderr)
    sys.exit(1)
PYEOF

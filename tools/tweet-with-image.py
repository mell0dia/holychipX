#!/usr/bin/env python3
"""Post a tweet with an image using OAuth 1.0a (same auth as x-dm)."""
import sys
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import uuid
import os
import requests

# Read creds from xcli wrapper
def load_creds():
    xcli = os.path.expanduser("~/.local/bin/xcli")
    creds = {}
    with open(xcli) as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                parts = line[7:].split("=", 1)
                if len(parts) == 2:
                    key = parts[0]
                    val = parts[1].strip('"').strip("'")
                    creds[key] = val
    return creds

CREDS = load_creds()
CONSUMER_KEY = CREDS["X_API_KEY"]
CONSUMER_SECRET = CREDS["X_API_SECRET"]
ACCESS_TOKEN = CREDS["X_ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = CREDS["X_ACCESS_TOKEN_SECRET"]

def oauth_sign(method, url, params=None):
    if params is None:
        params = {}
    oauth_params = {
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": ACCESS_TOKEN,
        "oauth_version": "1.0",
    }
    all_params = {**oauth_params, **params}
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_string = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(sorted_params, safe='')}"
    signing_key = f"{urllib.parse.quote(CONSUMER_SECRET, safe='')}&{urllib.parse.quote(ACCESS_TOKEN_SECRET, safe='')}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = signature
    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return auth_header

def upload_media(image_path):
    """Upload image via v1.1 media upload endpoint."""
    url = "https://upload.twitter.com/1.1/media/upload.json"
    
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    # For media upload, we need multipart form and OAuth in header
    auth = oauth_sign("POST", url)
    headers = {"Authorization": auth}
    files = {"media_data": base64.b64encode(image_data).decode()}
    
    resp = requests.post(url, headers=headers, data=files)
    
    if resp.status_code == 200:
        media_id = resp.json()["media_id_string"]
        print(f"📷 Media uploaded: {media_id}")
        return media_id
    else:
        print(f"❌ Upload failed: {resp.status_code} {resp.text[:200]}")
        return None

def post_tweet(text, media_id=None):
    """Post tweet via v2 API."""
    url = "https://api.twitter.com/2/tweets"
    
    body = {"text": text}
    if media_id:
        body["media"] = {"media_ids": [media_id]}
    
    auth = oauth_sign("POST", url)
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json"
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    if resp.status_code in (200, 201):
        tweet_id = resp.json().get("data", {}).get("id")
        print(f"✅ Tweet posted: {tweet_id}")
        return tweet_id
    else:
        print(f"❌ Tweet failed: {resp.status_code} {resp.text[:200]}")
        return None

def main():
    if len(sys.argv) < 3:
        print("Usage: tweet-with-image.py <image_path> <text>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    text = sys.argv[2]
    
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        sys.exit(1)
    
    print(f"📤 Uploading: {image_path}")
    media_id = upload_media(image_path)
    
    if media_id:
        post_tweet(text, media_id)
    else:
        print("Failed to upload media, posting text only...")
        post_tweet(text)

if __name__ == "__main__":
    main()

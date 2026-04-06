#!/usr/bin/env python3
"""Send a DM with an image on X/Twitter.
Usage: python3 dm_image.py <username> <image_path> <text>
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
    keys = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    creds = {k: os.environ.get(k) for k in keys}
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

def get_user_id(oauth, username):
    """Look up user ID from username."""
    username = username.lstrip("@")
    resp = oauth.get(f"https://api.twitter.com/2/users/by/username/{username}")
    if resp.status_code == 200:
        return resp.json()["data"]["id"]
    else:
        print(f"User lookup failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

def get_my_id(oauth):
    """Get authenticated user's ID."""
    resp = oauth.get("https://api.twitter.com/2/users/me")
    if resp.status_code == 200:
        return resp.json()["data"]["id"]
    else:
        print(f"Failed to get own user ID: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

def upload_media(oauth, image_path):
    """Upload media for DM (category: dm_image)."""
    # Init upload
    file_size = os.path.getsize(image_path)
    init_data = {
        "command": "INIT",
        "total_bytes": str(file_size),
        "media_type": "image/png",
        "media_category": "dm_image"
    }
    resp = oauth.post("https://upload.twitter.com/1.1/media/upload.json", data=init_data)
    if resp.status_code not in (200, 201, 202):
        # Fallback: simple upload
        with open(image_path, "rb") as f:
            resp = oauth.post("https://upload.twitter.com/1.1/media/upload.json",
                            files={"media": f},
                            data={"media_category": "dm_image"})
            if resp.status_code == 200:
                return resp.json()["media_id_string"]
            print(f"Upload failed: {resp.status_code} {resp.text}", file=sys.stderr)
            sys.exit(1)

    media_id = resp.json()["media_id_string"]

    # Append
    with open(image_path, "rb") as f:
        append_data = {
            "command": "APPEND",
            "media_id": media_id,
            "segment_index": "0"
        }
        resp = oauth.post("https://upload.twitter.com/1.1/media/upload.json",
                         data=append_data, files={"media": f})
        if resp.status_code not in (200, 204):
            print(f"Append failed: {resp.status_code} {resp.text}", file=sys.stderr)
            sys.exit(1)

    # Finalize
    finalize_data = {"command": "FINALIZE", "media_id": media_id}
    resp = oauth.post("https://upload.twitter.com/1.1/media/upload.json", data=finalize_data)
    if resp.status_code not in (200, 201):
        print(f"Finalize failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    return media_id

def main():
    if len(sys.argv) < 4 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 dm_image.py <username> <image_path> <text>")
        print("       python3 dm_image.py <username> --text-only <text>")
        sys.exit(0)

    username = sys.argv[1]
    image_path = sys.argv[2]
    text = sys.argv[3]

    text_only = image_path == "--text-only"
    if not text_only and not os.path.exists(image_path):
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

    # Get recipient user ID
    print(f"Looking up @{username.lstrip('@')}...")
    recipient_id = get_user_id(oauth, username)
    print(f"Recipient ID: {recipient_id}")

    # Get our own ID
    my_id = get_my_id(oauth)

    # Upload media if not text-only
    media_id = None
    if not text_only:
        print(f"Uploading: {image_path}")
        media_id = upload_media(oauth, image_path)
        print(f"Media ID: {media_id}")

    # Create DM conversation and send message
    # Using v2 DM endpoint
    payload = {
        "text": text
    }
    if media_id:
        payload["attachments"] = [{"media_id": media_id}]

    resp = oauth.post(
        f"https://api.twitter.com/2/dm_conversations/with/{recipient_id}/messages",
        json=payload
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        dm_id = data.get("data", {}).get("dm_event_id", "unknown")
        print(f"DM sent to @{username.lstrip('@')}! Event ID: {dm_id}")
        print(f"DM_ID:{dm_id}")
    else:
        print(f"DM failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

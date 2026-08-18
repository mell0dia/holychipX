#!/usr/bin/env python3
"""Post a tweet with a video to X/Twitter.

Usage: python3 tweet_video.py <video_path> <text> [--reply-to <tweet_id>]

Video CANNOT use the one-shot upload that tweet_image.py uses. X requires the
chunked v1.1 flow - INIT, APPEND (5MB slices), FINALIZE - followed by polling
STATUS until async transcoding reports succeeded. Posting the tweet before
`state: succeeded` fails with "media not found", which is why the poll is not
optional even though our Reels are small enough to upload in one chunk.
"""
import os, sys, time, subprocess

CHUNK = 4 * 1024 * 1024          # under X's 5MB per-APPEND ceiling
UPLOAD = "https://upload.twitter.com/1.1/media/upload.json"


def ensure_oauthlib():
    try:
        from requests_oauthlib import OAuth1Session
        return OAuth1Session
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "requests-oauthlib", "-q"])
        from requests_oauthlib import OAuth1Session
        return OAuth1Session


def get_creds():
    keys = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    creds = {k: os.environ.get(k) for k in keys}
    if not all(creds.values()):
        env = os.path.expanduser("~/claude-agent/.env")
        if os.path.exists(env):
            for line in open(env):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() in keys and not creds.get(k.strip()):
                        creds[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in keys if not creds.get(k)]
    if missing:
        sys.exit(f"Error: Missing credentials: {', '.join(missing)}")
    return creds


def upload_video(oauth, path):
    size = os.path.getsize(path)

    r = oauth.post(UPLOAD, data={"command": "INIT", "media_type": "video/mp4",
                                 "media_category": "tweet_video",
                                 "total_bytes": size})
    if r.status_code not in (200, 201, 202):
        sys.exit(f"INIT failed: {r.status_code} {r.text}")
    mid = r.json()["media_id_string"]

    with open(path, "rb") as f:
        idx = 0
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            r = oauth.post(UPLOAD, data={"command": "APPEND", "media_id": mid,
                                         "segment_index": idx},
                           files={"media": chunk})
            if r.status_code not in (200, 201, 204):
                sys.exit(f"APPEND {idx} failed: {r.status_code} {r.text}")
            idx += 1
    print(f"  uploaded {size / 1024:.0f} KB in {idx} chunk(s)")

    r = oauth.post(UPLOAD, data={"command": "FINALIZE", "media_id": mid})
    if r.status_code not in (200, 201):
        sys.exit(f"FINALIZE failed: {r.status_code} {r.text}")

    info = r.json().get("processing_info")
    while info and info.get("state") in ("pending", "in_progress"):
        wait = int(info.get("check_after_secs", 5))
        print(f"  transcoding ({info['state']}), waiting {wait}s")
        time.sleep(wait)
        r = oauth.get(UPLOAD, params={"command": "STATUS", "media_id": mid})
        if r.status_code != 200:
            sys.exit(f"STATUS failed: {r.status_code} {r.text}")
        info = r.json().get("processing_info")
    if info and info.get("state") == "failed":
        sys.exit(f"transcode failed: {info}")
    return mid


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit("Usage: python3 tweet_video.py <video_path> <text> "
                 "[--reply-to <tweet_id>]")
    path, text = args[0], args[1]
    reply_to = None
    if "--reply-to" in sys.argv:
        i = sys.argv.index("--reply-to")
        if i + 1 < len(sys.argv):
            reply_to = sys.argv[i + 1]
    if not os.path.exists(path):
        sys.exit(f"Error: Video not found: {path}")

    OAuth1Session = ensure_oauthlib()
    c = get_creds()
    oauth = OAuth1Session(c["X_API_KEY"], client_secret=c["X_API_SECRET"],
                          resource_owner_key=c["X_ACCESS_TOKEN"],
                          resource_owner_secret=c["X_ACCESS_TOKEN_SECRET"])

    print(f"Uploading: {path}")
    mid = upload_video(oauth, path)
    print(f"Media ID: {mid}")

    payload = {"text": text, "media": {"media_ids": [mid]}}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}
    r = oauth.post("https://api.twitter.com/2/tweets", json=payload)
    if r.status_code not in (200, 201):
        sys.exit(f"Post failed: {r.status_code} {r.text}")
    tid = r.json()["data"]["id"]
    print(f"Posted! https://x.com/_holychip/status/{tid}")
    print(f"TWEET_ID:{tid}")


if __name__ == "__main__":
    main()

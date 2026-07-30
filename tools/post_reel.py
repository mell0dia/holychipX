#!/usr/bin/env python3
"""Post a video as a Reel to Facebook and/or Instagram from a public video URL.

Meta fetches the video from a public URL, so the .mp4 must already be live
(e.g. pushed to gh-pages). Usage:

  post_reel.py <public_video_url> "<caption>" [--fb] [--ig]

With neither --fb nor --ig, posts to BOTH. Prints FB_VIDEO_ID / IG_POST_ID +
permalinks.
"""
import os, sys, time, json
import requests

GRAPH = "https://graph.facebook.com/v19.0"
ENV = os.path.expanduser("~/claude-agent/.env")


def load_env():
    for line in open(ENV):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def post_facebook_reel(video_url, caption):
    pid = os.environ["FB_PAGE_ID"]; tok = os.environ["FB_PAGE_ACCESS_TOKEN"]
    # Phase 1 — start (get a video_id + upload_url)
    r = requests.post(f"{GRAPH}/{pid}/video_reels",
                      data={"upload_phase": "start", "access_token": tok}).json()
    if "video_id" not in r:
        print("FB start failed:", r); return None
    vid, upload_url = r["video_id"], r["upload_url"]
    # Phase 2 — hosted upload: tell FB to fetch the file from our public URL
    up = requests.post(upload_url, headers={
        "Authorization": f"OAuth {tok}", "file_url": video_url}).json()
    if not up.get("success", True) and "error" in up:
        print("FB upload failed:", up); return None
    # Phase 3 — finish + publish
    fin = requests.post(f"{GRAPH}/{pid}/video_reels", data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": caption, "access_token": tok}).json()
    if not fin.get("success"):
        print("FB finish response:", fin)
    print(f"FB_VIDEO_ID:{vid}")
    print(f"FB_PERMALINK:https://www.facebook.com/reel/{vid}")
    return vid


def post_instagram_reel(video_url, caption):
    ig = os.environ["IG_BUSINESS_ACCOUNT_ID"]; tok = os.environ["FB_PAGE_ACCESS_TOKEN"]
    # 1 — create REELS container
    r = requests.post(f"{GRAPH}/{ig}/media", data={
        "media_type": "REELS", "video_url": video_url,
        "caption": caption, "access_token": tok}).json()
    if "id" not in r:
        print("IG container failed:", r); return None
    cid = r["id"]
    # 2 — poll until the video is processed (FINISHED)
    for _ in range(40):                       # up to ~4 min
        st = requests.get(f"{GRAPH}/{cid}", params={
            "fields": "status_code", "access_token": tok}).json()
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            print("IG processing ERROR:", st); return None
        time.sleep(6)
    else:
        print("IG processing timed out"); return None
    # 3 — publish
    pub = requests.post(f"{GRAPH}/{ig}/media_publish", data={
        "creation_id": cid, "access_token": tok}).json()
    if "id" not in pub:
        print("IG publish failed:", pub); return None
    mid = pub["id"]
    link = requests.get(f"{GRAPH}/{mid}", params={
        "fields": "permalink", "access_token": tok}).json().get("permalink", "")
    print(f"IG_POST_ID:{mid}")
    print(f"IG_PERMALINK:{link}")
    return mid


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit('usage: post_reel.py <public_video_url> "<caption>" [--fb] [--ig]')
    url, caption = args[0], args[1]
    load_env()
    do_fb = "--fb" in sys.argv or "--ig" not in sys.argv
    do_ig = "--ig" in sys.argv or "--fb" not in sys.argv
    if do_fb:
        print("=== Facebook Reel ===")
        post_facebook_reel(url, caption)
    if do_ig:
        print("=== Instagram Reel ===")
        post_instagram_reel(url, caption)


if __name__ == "__main__":
    main()

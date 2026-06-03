#!/usr/bin/env python3
"""Post a photo (or photo carousel) + caption to the Holy Chip Facebook Page.

Usage:
  python3 post_facebook.py <image_path> <caption>
  python3 post_facebook.py <image_path1> <image_path2> [...] -- <caption>

When multiple images are provided, the script uploads each as an unpublished
photo (published=false), then creates a single feed post that attaches all of
them — Facebook renders this as a multi-photo "album" post.

Reads from ~/claude-agent/.env:
  FB_PAGE_ID
  FB_PAGE_ACCESS_TOKEN

Prints on success:
  FB_POST_ID:<post_id>
  PERMALINK:<url>
"""
import os
import sys
import requests

GRAPH = "https://graph.facebook.com/v19.0"

def load_env():
    env_path = os.path.expanduser("~/claude-agent/.env")
    if not os.path.exists(env_path):
        return
    for line in open(env_path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)

def parse_args(argv):
    """Returns (image_paths, caption).

    Supported forms:
      <single_image> <caption>
      <image1> <image2> ... -- <caption>
    """
    if len(argv) >= 4 and "--" in argv:
        sep = argv.index("--")
        imgs = argv[1:sep]
        if sep + 1 >= len(argv):
            die("missing caption after --")
        cap = argv[sep + 1]
        return imgs, cap
    if len(argv) >= 3:
        return [argv[1]], argv[2]
    die("usage: post_facebook.py <image> <caption>  |  <img1> <img2> [...] -- <caption>")

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 post_facebook.py <image> <caption>")
        print("       python3 post_facebook.py <img1> <img2> [...] -- <caption>")
        sys.exit(0)

    image_paths, caption = parse_args(sys.argv)
    for p in image_paths:
        if not os.path.exists(p):
            die(f"image not found: {p}")

    load_env()
    page_id    = os.environ.get("FB_PAGE_ID")
    page_token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if not page_id or not page_token:
        die("FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN required in ~/claude-agent/.env")

    if len(image_paths) == 1:
        # single photo — original path, simplest
        with open(image_paths[0], "rb") as f:
            r = requests.post(f"{GRAPH}/{page_id}/photos",
                              data={"message": caption, "access_token": page_token},
                              files={"source": f})
        if r.status_code != 200:
            die(f"FB post failed: {r.status_code} {r.text}")
        body = r.json()
        photo_id = body.get("id")
        post_id  = body.get("post_id") or photo_id
    else:
        # multi-photo: upload each as unpublished, then post to /feed with attached_media
        media_fbids = []
        for p in image_paths:
            with open(p, "rb") as f:
                r = requests.post(f"{GRAPH}/{page_id}/photos",
                                  data={"published": "false", "access_token": page_token},
                                  files={"source": f})
            if r.status_code != 200:
                die(f"FB photo upload failed for {p}: {r.status_code} {r.text}")
            mid = r.json().get("id")
            if not mid:
                die(f"no media id for {p}: {r.text}")
            media_fbids.append(mid)

        # attached_media is a list of {"media_fbid": "..."} JSON-encoded as separate fields
        import json as _json
        data = {
            "message": caption,
            "access_token": page_token,
        }
        for i, mid in enumerate(media_fbids):
            data[f"attached_media[{i}]"] = _json.dumps({"media_fbid": mid})
        r = requests.post(f"{GRAPH}/{page_id}/feed", data=data)
        if r.status_code != 200:
            die(f"FB feed post failed: {r.status_code} {r.text}")
        post_id = r.json().get("id")
        photo_id = media_fbids[0]

    print(f"FB_POST_ID:{post_id}")
    if "_" in str(post_id):
        url = f"https://www.facebook.com/{page_id}/posts/{str(post_id).split('_', 1)[1]}"
    else:
        url = f"https://www.facebook.com/{photo_id}"
    print(f"PERMALINK:{url}")

if __name__ == "__main__":
    main()

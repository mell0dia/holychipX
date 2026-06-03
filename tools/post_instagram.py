#!/usr/bin/env python3
"""Post a single image OR carousel + caption to the Holy Chip Instagram account.

Single-image flow:
  1. Create container (POST /{ig_user_id}/media with image_url + caption)
  2. Publish container (POST /{ig_user_id}/media_publish with creation_id)

Carousel flow (2+ images):
  1. For each image: create child container (POST /{ig_user_id}/media with
     image_url + is_carousel_item=true, no caption)
  2. Create carousel container (POST /{ig_user_id}/media with media_type=CAROUSEL,
     children=<comma-separated child IDs>, caption=<full caption>)
  3. Publish carousel container

Requirements:
  - All images must be publicly accessible at their URLs (IG fetches them).
  - JPEG (not PNG). Aspect ratio between 4:5 and 1.91:1; 1080x1350 is the
    Holy Chip default.

Usage:
  python3 post_instagram.py <image_url> <caption> [--comment <text>]
  python3 post_instagram.py <url1> <url2> [...] -- <caption> [--comment <text>]

Prints on success:
  IG_POST_ID:<media_id>
  PERMALINK:<url>
  IG_COMMENT_ID:<comment_id>   (only if --comment supplied)
"""
import os
import sys
import time
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

def wait_for_container(creation_id, token, timeout_attempts=30):
    """Wait for IG to process the container before publishing.

    As of mid-2026 the Graph API status-check endpoint
    (GET /{creation_id}?fields=status_code) returns code 100 subcode 33
    ("Authorization Error") even with a valid token that just created the
    container — Meta-side regression. Workaround: skip the poll, sleep a
    fixed 10s (image containers typically process in 3-6s), and rely on
    the publish call to surface any real error.
    """
    time.sleep(10)

def parse_args(argv):
    """Returns (image_urls, caption, comment)."""
    # find optional --comment first and lop it off
    comment = None
    if "--comment" in argv:
        i = argv.index("--comment")
        if i + 1 >= len(argv):
            die("--comment requires a value")
        comment = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]

    if "--" in argv:
        sep = argv.index("--")
        urls = argv[1:sep]
        if sep + 1 >= len(argv):
            die("missing caption after --")
        cap = argv[sep + 1]
    else:
        if len(argv) < 3:
            die("usage: post_instagram.py <url> <caption>  |  <u1> <u2> [...] -- <caption>")
        urls = [argv[1]]
        cap = argv[2]
    return urls, cap, comment

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 post_instagram.py <image_url> <caption> [--comment <text>]")
        print("       python3 post_instagram.py <u1> <u2> [...] -- <caption> [--comment <text>]")
        sys.exit(0)

    image_urls, caption, comment = parse_args(sys.argv)

    load_env()
    ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if not ig_id or not token:
        die("IG_BUSINESS_ACCOUNT_ID and FB_PAGE_ACCESS_TOKEN required in ~/claude-agent/.env")

    # Sanity: each URL must return 200 directly (IG fetcher doesn't follow redirects)
    for u in image_urls:
        h = requests.head(u, allow_redirects=False)
        if h.status_code != 200:
            die(f"image_url returned {h.status_code} (need direct 200, no redirects): {u}")

    if len(image_urls) == 1:
        # single-image: container + publish
        r = requests.post(f"{GRAPH}/{ig_id}/media", data={
            "image_url": image_urls[0],
            "caption": caption,
            "access_token": token,
        })
        if r.status_code != 200:
            die(f"container create failed: {r.status_code} {r.text}")
        creation_id = r.json().get("id")
        if not creation_id:
            die(f"container create returned no id: {r.text}")
        wait_for_container(creation_id, token)
        p = requests.post(f"{GRAPH}/{ig_id}/media_publish", data={
            "creation_id": creation_id, "access_token": token,
        })
    else:
        # carousel: create children, then parent, then publish
        child_ids = []
        for u in image_urls:
            r = requests.post(f"{GRAPH}/{ig_id}/media", data={
                "image_url": u,
                "is_carousel_item": "true",
                "access_token": token,
            })
            if r.status_code != 200:
                die(f"child container failed for {u}: {r.status_code} {r.text}")
            cid = r.json().get("id")
            if not cid:
                die(f"child returned no id: {r.text}")
            child_ids.append(cid)
        # wait for every child to be ready
        for cid in child_ids:
            wait_for_container(cid, token)

        r = requests.post(f"{GRAPH}/{ig_id}/media", data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": token,
        })
        if r.status_code != 200:
            die(f"carousel container failed: {r.status_code} {r.text}")
        creation_id = r.json().get("id")
        if not creation_id:
            die(f"carousel container no id: {r.text}")
        wait_for_container(creation_id, token)
        p = requests.post(f"{GRAPH}/{ig_id}/media_publish", data={
            "creation_id": creation_id, "access_token": token,
        })

    if p.status_code != 200:
        die(f"publish failed: {p.status_code} {p.text}")
    media_id = p.json().get("id")
    if not media_id:
        die(f"publish returned no media id: {p.text}")

    # Permalink
    perm = requests.get(f"{GRAPH}/{media_id}", params={
        "fields": "permalink", "access_token": token,
    })
    permalink = perm.json().get("permalink", "") if perm.status_code == 200 else ""

    print(f"IG_POST_ID:{media_id}")
    if permalink:
        print(f"PERMALINK:{permalink}")

    if comment:
        c = requests.post(f"{GRAPH}/{media_id}/comments", data={
            "message": comment, "access_token": token,
        })
        if c.status_code != 200:
            print(f"WARN: comment failed: {c.status_code} {c.text}", file=sys.stderr)
        else:
            cid = c.json().get("id")
            if cid:
                print(f"IG_COMMENT_ID:{cid}")

if __name__ == "__main__":
    main()

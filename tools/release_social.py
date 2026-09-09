#!/usr/bin/env python3
"""Release a Holy Chip story to Facebook + Instagram.

Caption is MINIMAL and identical on both platforms — just a "READ THE BLOG" link
to the origin page plus hashtags. The comic image is the content; the full
multilingual blog lives on the site, so the caption only drives traffic there.
No long text, no PT comment (changed 2026-06-07 per user).

  release_social.py HC### [extra #hashtags ...] [--only fb,ig] [--force]

Posts FB then IG (IG uses the 1080x1350 square.jpg variant), records the post IDs
to story-posts.json, auto-fills the story title from the blog footer if missing.

RETRIES ARE SAFE, AND THEY DID NOT USED TO BE. Instagram's fetcher fails
transiently - it has refused a perfectly good live JPEG three times now - and
this script exits non-zero when either platform fails. Before 2026-09-08 the
obvious recovery, rerunning the script or throwback_release.sh, would post to
FACEBOOK A SECOND TIME, because nothing checked what had already gone out. Now
a platform already posted TODAY is skipped, so a retry completes the run instead
of duplicating it. --force overrides; --only fb,ig restricts, as release_reel.py
does. Same-day rather than ever-posted is deliberate: a vault throwback is a
legitimate re-post of a story released months ago.

ORIGINAL RELEASE DATES ARE NEVER OVERWRITTEN. A vault re-release used to
overwrite fb_post_id/fb_posted_at with the throwback's, erasing when the story
FIRST went out - which is exactly the field the vault rotation uses to decide
whether something is old enough to be a throwback at all. The first values are
now moved to first_fb_* / first_ig_* before the new ones are written.
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime
from pathlib import Path

HC = Path.home() / "holy-chip"
TOOLS = HC / "tools"
ADIR = HC / "stories" / "analysis"
TRACKER = HC / "content" / "story-posts.json"
IMG_DIR = HC / "stories"
SITE_WWW = "https://www.holy-chip.com"   # IG rejects redirects, needs canonical www host

HASHTAGS = "#HolyChip #AI #AGI #DailyComic"   # base; per-story theme tags appended via argv


def caption(sid):
    """Minimal caption. Vault throwbacks get a marker, then the link, then the hook.

    ORDER MATTERS ON A VAULT POST. The link is the whole point of the throwback,
    so it goes directly under "FROM THE VAULT" where it is visible before the
    feed truncates the caption - not below the hook line, where it used to sit
    (2026-08-20, per user). The hook follows and can be cut off harmlessly.

    THROWBACK_LEAD carries the hook ALONE. Older queue entries wrote it with a
    "FROM THE VAULT ·" prefix baked in, which would now print the marker twice,
    so any such prefix is stripped rather than trusted.
    """
    link = f"BLOG POST [EN,PT,FR,ES]: holy-chip.com/origins/{sid}.html"
    lead = os.environ.get("THROWBACK_LEAD", "").strip()
    if not lead:
        return f"{link}\n\n{HASHTAGS}"

    # The marker is overridable because not every lead-carrying post is a vault
    # throwback. A rewritten strip announces itself as a rewrite; labelling it
    # "FROM THE VAULT" would tell readers it is old when the point is that it
    # is new. Defaults to the vault marker so existing callers are unchanged.
    marker = os.environ.get("THROWBACK_MARKER", "").strip() or "FROM THE VAULT"
    lead = re.sub(r"^\s*(?:\U0001F5C4️?\s*)?FROM THE VAULT\s*[·:.-]*\s*", "",
                  lead, flags=re.I)
    return f"{marker}\n{link}\n\n{lead}\n\n{HASHTAGS}"


def blog_title(sid):
    """Best-effort story title from the EN blog footer ('Story #NNN -- <Name>')."""
    try:
        txt = (ADIR / f"{sid}.blog.md").read_text()
        m = re.search(r"Story #\d+\s*(?:--|—)\s*(.+?)\s*\*", txt)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
    return r.stdout


def grab(out, key):
    for line in out.splitlines():
        if line.startswith(key):
            return line.split(":", 1)[1].strip()
    return None


def preserve_first(entry, plat):
    """Move the ORIGINAL release's ids aside before a re-release overwrites them.

    Only ever writes first_* once. A story can be vaulted more than once; the
    field must keep meaning "when this first went out", not "the previous time".
    """
    src = f"{plat}_post_id"
    if not entry.get(src) or entry.get(f"first_{src}"):
        return False
    for suffix in ("post_id", "permalink", "posted_at"):
        k = f"{plat}_{suffix}"
        if entry.get(k):
            entry[f"first_{k}"] = entry[k]
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("tags", nargs="*", help="extra #hashtags")
    ap.add_argument("--only", default="fb,ig",
                    help="restrict platforms, e.g. --only ig after a partial failure")
    ap.add_argument("--force", action="store_true",
                    help="post even if this platform already went out today")
    a = ap.parse_args()

    sid = a.story
    # throwback_release.sh passes the theme as ONE quoted arg and it may be
    # empty; joining blindly would leave a trailing space in the caption
    extra = " ".join(t for t in a.tags if t.strip()).strip()
    if extra:
        globals()["HASHTAGS"] = HASHTAGS + " " + extra
    want = {p.strip() for p in a.only.split(",") if p.strip()}
    cap = caption(sid)
    img_local = str(IMG_DIR / f"{sid}.png")
    ig_url = f"{SITE_WWW}/stories/{sid}.square.jpg"

    data = json.loads(TRACKER.read_text())
    entry = next((e for e in data["posted"] if e.get("story") == sid), None)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = now[:10]
    if entry is None:
        entry = {"story": sid}
        title = blog_title(sid)
        if title:
            entry["title"] = title
        data["posted"].append(entry)

    def already_today(plat):
        return (not a.force and entry.get(f"{plat}_post_id")
                and str(entry.get(f"{plat}_posted_at", "")).startswith(today))

    results = {}
    for plat, script, target in (("fb", "post_facebook.py", img_local),
                                 ("ig", "post_instagram.py", ig_url)):
        if plat not in want:
            print(f"=== {sid}: {plat} not requested, skipping ===")
            results[plat] = entry.get(f"{plat}_post_id")
            continue
        if already_today(plat):
            print(f"=== {sid}: {plat} already posted today "
                  f"({entry[f'{plat}_post_id']}), skipping - use --force to repost ===")
            results[plat] = entry[f"{plat}_post_id"]
            continue
        print(f"=== {sid}: posting to "
              f"{'Facebook' if plat == 'fb' else 'Instagram'} ===")
        out = run(["python3", str(TOOLS / script), target, cap])
        pid = grab(out, "FB_POST_ID:" if plat == "fb" else "IG_POST_ID:")
        link = grab(out, "PERMALINK:")
        results[plat] = pid
        if pid:
            if preserve_first(entry, plat):
                print(f"  kept the original {plat} release as first_{plat}_post_id "
                      f"({entry[f'first_{plat}_posted_at']})")
            entry[f"{plat}_post_id"] = pid
            entry[f"{plat}_permalink"] = link
            entry[f"{plat}_posted_at"] = now

    data.setdefault("metadata", {})["updated"] = now
    TRACKER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    fb_id, ig_id = results.get("fb"), results.get("ig")
    print(f"recorded: fb={fb_id} ig={ig_id}")

    if not fb_id or not ig_id:
        sys.exit(f"INCOMPLETE: fb={fb_id} ig={ig_id}")


if __name__ == "__main__":
    main()

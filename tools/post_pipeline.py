#!/usr/bin/env python3
"""End-to-end FB + IG release pipeline for a single Holy Chip story.

Usage:  python3 post_pipeline.py <SID>

Idempotent enough: if the story already has fb_post_id / ig_post_id in
story-posts.json, the corresponding step is skipped.

Steps:
  1. Generate 1080x1350 IG square JPEG (square_crop.py)
  2. Copy to website source + git commit + git push (if not already public)
  3. Poll the public URL until 200
  4. Read EN + PT blog files, build captions
  5. POST FB photo with stacked EN+PT caption + Origins link
  6. POST IG container with EN caption, then publish, then auto-comment PT
  7. Append/update story-posts.json
"""
import os, sys, re, json, subprocess, time, requests
from datetime import datetime

HOME = os.path.expanduser("~")
SITE = f"{HOME}/holy-chip/website/holy-chip-site"
TOOLS = f"{HOME}/holy-chip/tools"
STORY_POSTS = f"{HOME}/holy-chip/content/story-posts.json"

def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)

def strip_md(text):
    text = text.split("\n---\n", 1)[0].strip()
    out = []
    for line in text.splitlines():
        s = re.sub(r"^#+\s*", "", line)
        s = re.sub(r"^\*(.+)\*$", r"\1", s)
        s = s.replace("--", "—")
        out.append(s)
    return "\n".join(out).rstrip()


def insert_link_after_title(body, link):
    """Insert a link line right after the title/subtitle block.

    Caption convention: H1 (title) + H2 (Holy Chip #NNN — Subtitle) + link
    sit at the very top so readers can jump to the full blog before reading
    the caption. Falls back to prepending if the body has no title structure.
    """
    parts = body.split("\n\n", 2)
    if len(parts) >= 3:
        return f"{parts[0]}\n\n{parts[1]}\n\n{link}\n\n{parts[2]}"
    return f"{link}\n\n{body}"

def fit_to_limit(body, suffix, limit):
    """Trim `body` (paragraph-separated by blank lines) so body+suffix fits limit.
    Drops paragraphs from the middle, inserting [...] marker. Preserves first
    and last two paragraphs at minimum."""
    full = body + suffix
    if len(full) <= limit:
        return body, False  # no trim needed
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if len(paragraphs) < 4:
        # too few paragraphs to meaningfully trim — hard truncate
        keep = limit - len(suffix) - 10
        return body[:keep].rstrip() + "...", True
    # iteratively drop middle paragraphs
    marker = "[...]"
    while len(paragraphs) > 4:
        mid = len(paragraphs) // 2
        # don't drop the first 2 or last 2
        if mid < 2 or mid >= len(paragraphs) - 2:
            break
        paragraphs.pop(mid)
        trimmed_body = "\n\n".join(paragraphs[:mid] + [marker] + paragraphs[mid:])
        if len(trimmed_body) + len(suffix) <= limit:
            return trimmed_body, True
    # still over after middle drops — drop more aggressively from the body
    while len(paragraphs) > 3:
        # drop second-to-last middle
        paragraphs.pop(len(paragraphs) // 2)
        trimmed_body = "\n\n".join(paragraphs[:len(paragraphs)//2] + [marker] + paragraphs[len(paragraphs)//2:])
        if len(trimmed_body) + len(suffix) <= limit:
            return trimmed_body, True
    # last resort: hard truncate
    keep = limit - len(suffix) - 10
    return "\n\n".join(paragraphs)[:keep].rstrip() + "...", True

def main():
    if len(sys.argv) < 2:
        die("usage: post_pipeline.py <SID>")
    SID = sys.argv[1].upper()
    log(f"--- {SID} pipeline starting ---")

    # ---- read existing tracker ----
    d = json.load(open(STORY_POSTS))
    entry = next((x for x in d["posted"] if x.get("story") == SID), None)
    if entry and entry.get("fb_post_id") and entry.get("ig_post_id"):
        log(f"{SID} already fully posted. Nothing to do.")
        return

    # ---- 1. square crop + text card ----
    png_path = f"{SITE}/stories/{SID}.png"
    sq_path  = f"{SITE}/stories/{SID}.square.jpg"
    tc_path  = f"{SITE}/stories/{SID}.text.jpg"
    if not os.path.exists(png_path):
        die(f"main image not found: {png_path}")
    if not os.path.exists(sq_path):
        log("generating square JPEG")
        subprocess.run(["python3", f"{TOOLS}/square_crop.py", png_path, sq_path], check=True)

    # text card: tease text from blog (first 4-5 paragraphs, no punchline)
    # supports manual override via HC###.tease.md (paragraphs separated by blank lines,
    # wrap a line in "..." to mark it as a pull-quote)
    en = strip_md(open(f"{SITE}/stories/analysis/{SID}.blog.md").read())
    pt = strip_md(open(f"{SITE}/stories/analysis/{SID}.blog.pt.md").read())

    title_map_pre = {"HC005":"The Candidate","HC013":"The Denial","HC016":"The Central Bank's One Fix","HC019":"The AI Pentagon","HC020":"AI Headquarters","HC021":"AI Space Unit","HC022":"Beyond Radical","HC024":"Waterloo","HC025":"What Did You Expect?"}
    tease_override = f"{SITE}/stories/analysis/{SID}.tease.md"
    if os.path.exists(tease_override):
        tease_paras = [p.strip() for p in open(tease_override).read().split("\n\n") if p.strip()]
    else:
        # auto-extract: skip title/subtitle/italic-opener, take first 5 narrative paragraphs
        raw = open(f"{SITE}/stories/analysis/{SID}.blog.md").read()
        paras = [p.strip() for p in raw.split("\n\n") if p.strip()]
        narrative = []
        for p in paras:
            if p.startswith("#"): continue
            # italic opener line
            if p.startswith("*") and p.endswith("*") and "\n" not in p: continue
            if p.lower().startswith("holy chip"): break    # stop before punchline
            if p.startswith("---"): break                  # stop at footer rule
            narrative.append(strip_md(p))
            if len(narrative) >= 5: break
        tease_paras = narrative

    header_title = title_map_pre.get(SID, SID)
    tease_header = f"Holy Chip #{SID[2:]} -- {header_title}"
    tease_body   = "||".join(tease_paras)
    tease_footer = f"holy-chip.com/origins/{SID}"
    if not os.path.exists(tc_path):
        log("generating text card")
        subprocess.run(["python3", f"{TOOLS}/text_card.py", tc_path,
                        tease_header, tease_body, tease_footer], check=True)

    # ---- 2. ensure deployed to gh-pages (square AND text card) ----
    cb = int(time.time())
    sq_url = f"https://www.holy-chip.com/stories/{SID}.square.jpg?v={cb}"
    tc_url = f"https://www.holy-chip.com/stories/{SID}.text.jpg?v={cb}"
    need_deploy = False
    for url in (sq_url, tc_url):
        if requests.head(url, allow_redirects=False).status_code != 200:
            need_deploy = True
            break
    if need_deploy:
        log("deploying square + text card to gh-pages")
        subprocess.run(["git", "-C", SITE, "add",
                        f"stories/{SID}.square.jpg",
                        f"stories/{SID}.text.jpg"], check=True)
        r = subprocess.run(["git", "-C", SITE, "commit", "-m", f"Add IG square + text card for {SID}"],
                           capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            log(f"  commit warn: {r.stdout.strip()} {r.stderr.strip()}")
        subprocess.run(["git", "-C", SITE, "push", "origin", "gh-pages"], check=True)
        for i in range(30):
            time.sleep(4)
            ok = (requests.head(sq_url, allow_redirects=False).status_code == 200 and
                  requests.head(tc_url, allow_redirects=False).status_code == 200)
            if ok:
                log(f"  square + text card live at attempt {i+1}")
                break
        else:
            die("square/text card never went live")
    public_url = sq_url        # legacy name used below
    text_url   = tc_url

    # ---- 3. captions ----

    THEMES = {
        "HC004": ("FutureOfWork", "Leadership"),
        "HC006": ("SelfImprovement", "Singularity"),
        "HC007": ("AISurgery", "Healthcare"),
        "HC008": ("AICar", "Autonomous"),
        "HC009": ("TechnicalDebt", "Infrastructure"),
        "HC012": ("AIEconomy", "Agents"),
        "HC013": ("Power", "Hierarchy"),
        "HC019": ("Defense", "Drones"),
        "HC020": ("Productivity", "AIIndustry"),
        "HC024": ("Ethics", "AutonomousAI"),
        "HC005": ("Politics", "Elections"),
        "HC025": ("AITraining", "DataQuality"),
        "HC016": ("CentralBanks", "Economics"),
        "HC021": ("Space", "Humanity"),
        "HC022": ("Trust", "Jobs"),
        "HC023": ("AISupremacy", "Power"),
    }
    t1, t2 = THEMES.get(SID, ("AI", "Comic"))

    # Blog URL appears right after the title block (rule established 2026-05-25).
    # Single placement per POST: once at the top of EN (which heads each caption).
    # The PT block inside the FB caption does NOT get its own link — that would
    # duplicate the URL in the same post. PT IG comment DOES get its own link
    # because it's published as a standalone comment.
    origin_url    = f"holy-chip.com/origins/{SID}"
    link_line_en  = f"→ Read the full blog post (EN · ES · PT · FR): {origin_url}"
    link_line_pt  = f"→ Leia o post completo (EN · ES · PT · FR): {origin_url}"
    en_with_link    = insert_link_after_title(en, link_line_en)
    pt_with_link_ig = insert_link_after_title(pt, link_line_pt)  # standalone IG comment only

    fb_suffix = (
        f"\n\n— — — — —\n\n{pt}\n\n"  # plain PT — no second link in the same caption
        f"#HolyChip #AI #AGI #DailyComic #{t1} #{t2}"
    )
    # FB practical limit: ~5000 chars (real cap is lower than documented 63k)
    fb_en_trimmed, fb_was_trimmed = fit_to_limit(en_with_link, fb_suffix, 5000)
    if fb_was_trimmed:
        log(f"  FB caption EN trimmed: {len(en_with_link)} -> {len(fb_en_trimmed)} body chars")
    fb_caption = f"{fb_en_trimmed}{fb_suffix}"
    ig_suffix = (
        f"\n\n"
        f"Link in bio · Versão em português ↓ nos comentários\n\n"
        f"#HolyChip #AI #AGI #Beckett #DailyComic #{t1} #{t2}"
    )
    en_trimmed, en_was_trimmed = fit_to_limit(en_with_link, ig_suffix, 2200)
    ig_caption = f"{en_trimmed}{ig_suffix}"
    pt_trimmed, pt_was_trimmed = fit_to_limit(pt_with_link_ig, "", 2200)
    if en_was_trimmed:
        log(f"  IG caption trimmed: {len(en)} -> {len(en_trimmed)} body chars")
    if pt_was_trimmed:
        log(f"  PT comment trimmed: {len(pt)} -> {len(pt_trimmed)} chars")
    log(f"FB caption: {len(fb_caption)} chars | IG caption: {len(ig_caption)} | PT comment: {len(pt_trimmed)}")

    # ---- 4. FB: post 1 (comic) ----
    card_caption = (
        f"A snapshot of Holy Chip #{SID[2:]}. "
        f"Read the full story at holy-chip.com/origins/{SID}\n\n"
        f"#HolyChip #AI #AGI #DailyComic #{t1} #{t2}"
    )
    fb_post_id, fb_permalink = (entry or {}).get("fb_post_id"), (entry or {}).get("fb_permalink")
    if not fb_post_id:
        log("posting comic to FB")
        r = subprocess.run(["python3", f"{TOOLS}/post_facebook.py", png_path, fb_caption],
                           capture_output=True, text=True)
        log(f"  FB stdout: {r.stdout.strip()}")
        if r.stderr.strip():
            log(f"  FB stderr: {r.stderr.strip()}")
        if r.returncode != 0:
            die("FB post failed")
        for ln in r.stdout.splitlines():
            if ln.startswith("FB_POST_ID:"):
                fb_post_id = ln.split(":", 1)[1]
            elif ln.startswith("PERMALINK:"):
                fb_permalink = ln.split(":", 1)[1]
        log(f"  FB live: {fb_permalink}")
        # Save FB state immediately so a re-run after IG failure doesn't double-post
        now_fb = datetime.now().strftime("%Y-%m-%d %H:%M")
        title_map_pre = {"HC004":"The Promotion","HC005":"The Candidate","HC006":"Lingering","HC007":"The Cut","HC008":"The Sensor","HC009":"The Secret","HC012":"The Market","HC013":"The Denial","HC016":"The Central Bank's One Fix","HC019":"The AI Pentagon","HC020":"AI Headquarters","HC021":"AI Space Unit","HC022":"Beyond Radical","HC023":"Shut up","HC024":"Waterloo","HC025":"What Did You Expect?"}
        if entry is None:
            entry = {
                "story": SID,
                "title": title_map_pre.get(SID, SID),
                "date": now_fb,
                "method": "manual",
                "fb_post_id": fb_post_id, "fb_permalink": fb_permalink, "fb_posted_at": now_fb,
            }
            d["posted"].append(entry)
        else:
            entry.update({
                "fb_post_id": fb_post_id, "fb_permalink": fb_permalink, "fb_posted_at": now_fb,
            })
        d.setdefault("metadata", {})["updated"] = now_fb
        json.dump(d, open(STORY_POSTS, "w"), indent=2)
        log(f"  FB state saved to tracker")

    # ---- 4b. FB: post 2 (text card follow-up) — RETIRED 2026-06-03 ----
    # User decision: stop posting text cards as follow-ups on FB.
    # Comic post above is the entire FB release.
    # See ~/.claude/projects/-Users-rmello/memory/feedback_no_social_text_cards.md

    # ---- 5. IG: post 1 (comic + PT comment) ----
    ig_post_id  = (entry or {}).get("ig_post_id")
    ig_permalink = (entry or {}).get("ig_permalink")
    ig_comment_id = (entry or {}).get("ig_comment_id")
    if not ig_post_id:
        log("posting comic to IG (with PT auto-comment)")
        r = subprocess.run([
            "python3", f"{TOOLS}/post_instagram.py",
            public_url, ig_caption,
            "--comment", pt_trimmed,
        ], capture_output=True, text=True)
        log(f"  IG stdout: {r.stdout.strip()}")
        if r.stderr.strip():
            log(f"  IG stderr: {r.stderr.strip()}")
        if r.returncode != 0:
            die("IG post failed (FB succeeded; partial state)")
        for ln in r.stdout.splitlines():
            if ln.startswith("IG_POST_ID:"):
                ig_post_id = ln.split(":", 1)[1]
            elif ln.startswith("PERMALINK:"):
                ig_permalink = ln.split(":", 1)[1]
            elif ln.startswith("IG_COMMENT_ID:"):
                ig_comment_id = ln.split(":", 1)[1]
        log(f"  IG live: {ig_permalink}")

    # ---- 5b. IG: post 2 (text card follow-up) — RETIRED 2026-06-03 ----
    # User decision: stop posting text cards as follow-ups on IG.
    # Comic post + PT auto-comment above is the entire IG release.
    # See ~/.claude/projects/-Users-rmello/memory/feedback_no_social_text_cards.md

    # ---- 6. update tracker ----
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title_map = {"HC004":"The Promotion","HC005":"The Candidate","HC006":"Lingering","HC007":"The Cut","HC008":"The Sensor","HC009":"The Secret","HC012":"The Market","HC013":"The Denial","HC016":"The Central Bank's One Fix","HC019":"The AI Pentagon","HC020":"AI Headquarters","HC021":"AI Space Unit","HC022":"Beyond Radical","HC023":"Shut up","HC024":"Waterloo","HC025":"What Did You Expect?"}
    if entry is None:
        d["posted"].append({
            "story": SID,
            "title": title_map.get(SID, SID),
            "date": now,
            "method": "manual",
            "fb_post_id": fb_post_id, "fb_permalink": fb_permalink, "fb_posted_at": now,
            "ig_post_id": ig_post_id, "ig_permalink": ig_permalink, "ig_comment_id": ig_comment_id, "ig_posted_at": now,
        })
    else:
        entry.update({
            "fb_post_id": fb_post_id, "fb_permalink": fb_permalink, "fb_posted_at": entry.get("fb_posted_at", now),
            "ig_post_id": ig_post_id, "ig_permalink": ig_permalink, "ig_comment_id": ig_comment_id, "ig_posted_at": entry.get("ig_posted_at", now),
        })
    d.setdefault("metadata", {})["updated"] = now
    json.dump(d, open(STORY_POSTS, "w"), indent=2)

    log(f"--- {SID} pipeline DONE ---")
    log(f"  FB: {fb_permalink}")
    log(f"  IG: {ig_permalink}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Holy Chip War Room — Flask API Server
Morning coffee dashboard for Mellodia
"""

import json
import os
import sqlite3
import glob
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_file, send_from_directory, abort

app = Flask(__name__, static_folder=".")

BASE = os.path.expanduser("~/holy-chip")
PHRASES_FILE = os.path.join(BASE, "content/phrases.json")
VIDEOS_FILE = os.path.join(BASE, "content/video-library.json")
DM_FILE = os.path.join(BASE, "content/dm-tracker.json")
INFLUENCER_DB = os.path.join(BASE, "content/influencers_db.json")
INFLUENCERS_FILE = os.path.join(BASE, "content/influencers.json")
STORIES_DIR = os.path.join(BASE, "stories")
CHARS_DIR = os.path.join(BASE, "characters")
DB_PATH = os.path.expanduser("~/.hermes/state.db")

PRICING = {
    "claude-opus-4-6":       {"input": 15.0,  "output": 75.0,  "cache_read": 1.50, "cache_write": 18.75},
    "claude-sonnet-4-6":     {"input": 3.0,   "output": 15.0,  "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-6":      {"input": 0.80,  "output": 4.0,   "cache_read": 0.08, "cache_write": 1.00},
    "claude-3-haiku-20240307":{"input": 0.25, "output": 1.25,  "cache_read": 0.03, "cache_write": 0.30},
    "gemma4":                {"input": 0.0,   "output": 0.0,   "cache_read": 0.0,  "cache_write": 0.0},
}

def model_family(model):
    if not model:
        return "other"
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    if "gemma" in m or "llama" in m or "qwen" in m:
        return "local"
    return "other"

def calc_cost(row):
    """Recalculate cost from tokens if estimated_cost is 0 or null."""
    model = row.get("model", "") or ""
    cost = row.get("estimated_cost_usd")
    if cost and cost > 0:
        return cost
    # Find pricing key
    price = None
    for k, v in PRICING.items():
        if k in model.lower():
            price = v
            break
    if not price:
        return 0.0
    inp = (row.get("input_tokens") or 0) / 1_000_000
    out = (row.get("output_tokens") or 0) / 1_000_000
    cr  = (row.get("cache_read_tokens") or 0) / 1_000_000
    cw  = (row.get("cache_write_tokens") or 0) / 1_000_000
    return (inp * price["input"] + out * price["output"] +
            cr * price["cache_read"] + cw * price["cache_write"])

# ─── STATIC ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/story-image/<path:filename>")
def story_image(filename):
    return send_from_directory(STORIES_DIR, filename)

@app.route("/char-image/<chip>/<path:filename>")
def char_image(chip, filename):
    char_dir = os.path.join(CHARS_DIR, f"Chip {chip}")
    return send_from_directory(char_dir, filename)

# ─── API: COSTS ─────────────────────────────────────────────────
@app.route("/api/costs")
def costs():
    days = int(request.args.get("days", 7))
    since = datetime.now() - timedelta(days=days)
    since_ts = since.timestamp()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM sessions WHERE started_at >= ? ORDER BY started_at DESC",
        (since_ts,)
    ).fetchall()
    conn.close()

    sessions = []
    daily = {}  # date -> {model_family -> cost}
    model_totals = {}
    grand_total = 0.0

    for r in rows:
        d = dict(r)
        cost = calc_cost(d)
        fam = model_family(d.get("model"))
        date = datetime.fromtimestamp(d["started_at"]).strftime("%Y-%m-%d")

        sessions.append({
            "id": d["id"],
            "date": date,
            "time": datetime.fromtimestamp(d["started_at"]).strftime("%H:%M"),
            "model": d.get("model") or "?",
            "family": fam,
            "source": d.get("source") or "cli",
            "input_tokens": d.get("input_tokens") or 0,
            "output_tokens": d.get("output_tokens") or 0,
            "cache_read": d.get("cache_read_tokens") or 0,
            "cache_write": d.get("cache_write_tokens") or 0,
            "cost": round(cost, 6),
            "msgs": d.get("message_count") or 0,
            "title": d.get("title") or "",
        })

        daily.setdefault(date, {})
        daily[date][fam] = daily[date].get(fam, 0) + cost

        model_totals[fam] = model_totals.get(fam, 0) + cost
        grand_total += cost

    # today & yesterday quick stats
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_cost = sum(daily.get(today_str, {}).values())
    yesterday_cost = sum(daily.get(yesterday_str, {}).values())

    return jsonify({
        "sessions": sessions,
        "daily": daily,
        "model_totals": model_totals,
        "grand_total": round(grand_total, 4),
        "today": round(today_cost, 4),
        "yesterday": round(yesterday_cost, 4),
    })

# ─── API: PHRASES ────────────────────────────────────────────────
@app.route("/api/phrases")
def get_phrases():
    with open(PHRASES_FILE) as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/api/phrases/<int:idx>/keep", methods=["POST"])
def keep_phrase(idx):
    with open(PHRASES_FILE) as f:
        data = json.load(f)
    phrases = data.get("phrases", [])
    if 0 <= idx < len(phrases):
        phrases[idx]["status"] = "kept"
        data["phrases"] = phrases
        with open(PHRASES_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True, "status": "kept"})
    return jsonify({"ok": False}), 404

@app.route("/api/phrases/<int:idx>/delete", methods=["POST"])
def delete_phrase(idx):
    with open(PHRASES_FILE) as f:
        data = json.load(f)
    phrases = data.get("phrases", [])
    if 0 <= idx < len(phrases):
        phrases[idx]["status"] = "deleted"
        data["phrases"] = phrases
        with open(PHRASES_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True, "status": "deleted"})
    return jsonify({"ok": False}), 404

@app.route("/api/phrases/<int:idx>/reset", methods=["POST"])
def reset_phrase(idx):
    with open(PHRASES_FILE) as f:
        data = json.load(f)
    phrases = data.get("phrases", [])
    if 0 <= idx < len(phrases):
        phrases[idx].pop("status", None)
        data["phrases"] = phrases
        with open(PHRASES_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 404

@app.route("/api/phrases/<int:idx>/comment", methods=["POST"])
def comment_phrase(idx):
    body = request.get_json(silent=True) or {}
    comment = body.get("comment", "").strip()
    with open(PHRASES_FILE) as f:
        data = json.load(f)
    phrases = data.get("phrases", [])
    if 0 <= idx < len(phrases):
        if comment:
            phrases[idx]["comment"] = comment
        else:
            phrases[idx].pop("comment", None)
        data["phrases"] = phrases
        with open(PHRASES_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True, "comment": comment})
    return jsonify({"ok": False}), 404

# ─── API: UNIFIED PHRASES (videos + influencers) ─────────────────
@app.route("/api/all-phrases")
def get_all_phrases():
    """Return phrases from BOTH sources: phrases.json (videos) and influencers_db.json"""
    items = []

    # Source 1: phrases.json (videos/manual)
    if os.path.exists(PHRASES_FILE):
        with open(PHRASES_FILE) as f:
            data = json.load(f)
        for i, p in enumerate(data.get("phrases", [])):
            items.append({
                "source": "video",
                "source_file": "phrases",
                "idx": i,
                "phrase": p.get("phrase", ""),
                "speaker": p.get("speaker", "unknown"),
                "context": p.get("context", ""),
                "weight": p.get("weight", "medium"),
                "status": p.get("status"),
                "comment": p.get("comment", ""),
                "source_title": p.get("source_title", ""),
                "source_url": p.get("source_url", ""),
                "date": p.get("date_extracted", ""),
                "handle": "",
                "tweet_url": "",
                "tweet_text": "",
            })

    # Source 2: influencers_db.json
    if os.path.exists(INFLUENCER_DB):
        with open(INFLUENCER_DB) as f:
            db = json.load(f)
        for t in db.get("tweets", []):
            for pi, p in enumerate(t.get("phrases", [])):
                items.append({
                    "source": "influencer",
                    "source_file": "influencers_db",
                    "tweet_id": t.get("tweet_id", ""),
                    "phrase_idx": pi,
                    "phrase": p.get("phrase", ""),
                    "speaker": "@" + t.get("handle", "unknown"),
                    "context": p.get("context", ""),
                    "weight": p.get("weight", "medium"),
                    "status": p.get("status"),
                    "comment": p.get("comment", ""),
                    "source_title": "",
                    "source_url": t.get("tweet_url", ""),
                    "date": t.get("captured_at", ""),
                    "handle": t.get("handle", ""),
                    "tweet_url": t.get("tweet_url", ""),
                    "tweet_text": t.get("text", ""),
                })

    # Get list of influencer handles for the filter dropdown
    handles = set()
    if os.path.exists(INFLUENCERS_FILE):
        with open(INFLUENCERS_FILE) as f:
            inf_data = json.load(f)
        for inf in inf_data.get("influencers", []):
            handles.add(inf.get("handle", "").lstrip("@"))

    return jsonify({
        "items": items,
        "influencer_handles": sorted(handles),
        "total_video": sum(1 for i in items if i["source"] == "video"),
        "total_influencer": sum(1 for i in items if i["source"] == "influencer"),
    })


@app.route("/api/influencer-phrase/<tweet_id>/<int:phrase_idx>/<action>", methods=["POST"])
def influencer_phrase_action(tweet_id, phrase_idx, action):
    """Keep/delete/reset/comment an influencer phrase in influencers_db.json"""
    if action not in ("keep", "delete", "reset", "comment"):
        return jsonify({"ok": False, "error": "bad action"}), 400

    with open(INFLUENCER_DB) as f:
        db = json.load(f)

    for t in db.get("tweets", []):
        if t.get("tweet_id") == tweet_id:
            phrases = t.get("phrases", [])
            if 0 <= phrase_idx < len(phrases):
                if action == "keep":
                    phrases[phrase_idx]["status"] = "kept"
                elif action == "delete":
                    phrases[phrase_idx]["status"] = "deleted"
                elif action == "reset":
                    phrases[phrase_idx].pop("status", None)
                elif action == "comment":
                    body = request.get_json(silent=True) or {}
                    comment = body.get("comment", "").strip()
                    if comment:
                        phrases[phrase_idx]["comment"] = comment
                    else:
                        phrases[phrase_idx].pop("comment", None)

                with open(INFLUENCER_DB, "w") as f:
                    json.dump(db, f, indent=2)
                return jsonify({"ok": True, "action": action})

    return jsonify({"ok": False}), 404


# ─── API: VIDEOS ─────────────────────────────────────────────────
@app.route("/api/videos")
def get_videos():
    with open(VIDEOS_FILE) as f:
        data = json.load(f)
    return jsonify(data)

# ─── API: DMs ────────────────────────────────────────────────────
@app.route("/api/dms")
def get_dms():
    with open(DM_FILE) as f:
        data = json.load(f)
    return jsonify(data)

# ─── API: CAMPAIGNS ──────────────────────────────────────────────
CAMPAIGNS_FILE = os.path.join(BASE, "content", "story-campaigns.json")

@app.route("/api/campaigns")
def get_campaigns():
    # Load campaigns
    with open(CAMPAIGNS_FILE) as f:
        camp_data = json.load(f)
    # Load dm-tracker
    with open(DM_FILE) as f:
        dm_data = json.load(f)

    active_story = camp_data.get("active_story", "")
    stories_cfg  = camp_data.get("stories", {})
    targets      = dm_data.get("targets", [])

    # Build per-story DM stats from tracker
    dm_stats = {}
    for t in targets:
        for dm in (t.get("dms") or []):
            sid = dm.get("story", "")
            if not sid:
                continue
            if sid not in dm_stats:
                dm_stats[sid] = {
                    "sent": 0,
                    "by_tier": {},
                    "first_date": None,
                    "last_date": None,
                    "recipients": []
                }
            s = dm_stats[sid]
            s["sent"] += 1
            tier = t.get("tier", "misc")
            s["by_tier"][tier] = s["by_tier"].get(tier, 0) + 1
            date_str = dm.get("date", "")
            if date_str:
                if s["first_date"] is None or date_str < s["first_date"]:
                    s["first_date"] = date_str
                if s["last_date"] is None or date_str > s["last_date"]:
                    s["last_date"] = date_str
            s["recipients"].append({
                "handle":  t.get("handle", ""),
                "name":    t.get("name", ""),
                "company": t.get("company", ""),
                "tier":    tier,
                "date":    date_str,
            })

    # Merge into campaign list
    campaigns = []
    for sid, cfg in stories_cfg.items():
        stats = dm_stats.get(sid, {"sent": 0, "by_tier": {}, "first_date": None, "last_date": None, "recipients": []})
        campaigns.append({
            "id":             sid,
            "title":          cfg.get("title", sid),
            "hashtags":       cfg.get("hashtags", []),
            "reply_template": cfg.get("reply_template", ""),
            "dm_text":        cfg.get("dm_text", ""),
            "active":         sid == active_story,
            "dm_sent":        stats["sent"],
            "dm_by_tier":     stats["by_tier"],
            "dm_first":       stats["first_date"],
            "dm_last":        stats["last_date"],
            "dm_recipients":  stats["recipients"],
            "has_image":      os.path.exists(os.path.join(STORIES_DIR, f"{sid}.png")),
        })

    # Sort: active first, then by DM count desc
    campaigns.sort(key=lambda c: (0 if c["active"] else 1, -c["dm_sent"]))
    return jsonify({"active_story": active_story, "campaigns": campaigns})

# ─── API: STORIES ────────────────────────────────────────────────
@app.route("/api/stories")
def get_stories():
    stories = []
    # Get all HC*.json files
    json_files = sorted(glob.glob(os.path.join(STORIES_DIR, "HC*.json")))
    story_ids_with_json = set()

    for jf in json_files:
        with open(jf) as f:
            d = json.load(f)
        sid = d.get("id", os.path.basename(jf).replace(".json",""))
        story_ids_with_json.add(sid)
        script = d.get("script", {})
        ts = d.get("timestamp")
        if ts and isinstance(ts, (int, float)) and ts > 1e10:
            ts = ts / 1000  # ms to seconds
        from datetime import datetime as _dt
        ts_str = _dt.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else None
        stories.append({
            "id": sid,
            "timestamp": ts_str,
            "title": script.get("title", sid),
            "panels": [
                {"speaker": script.get("p1LeftSpeaker",""), "text": script.get("p1LeftText","")},
                {"speaker": script.get("p1RightSpeaker",""), "text": script.get("p1RightText","")},
                {"speaker": script.get("p2LeftSpeaker",""), "text": script.get("p2LeftText","")},
                {"speaker": script.get("p2RightSpeaker",""), "text": script.get("p2RightText","")},
            ],
            "has_image": os.path.exists(os.path.join(STORIES_DIR, f"{sid}.png")),
            "has_pre": os.path.exists(os.path.join(STORIES_DIR, f"{sid}.pre.png")),
            "prompt": d.get("prompt",""),
        })

    # Also add any .png stories without json
    png_files = sorted(glob.glob(os.path.join(STORIES_DIR, "HC*.png")))
    seen_pngs = set()
    for pf in png_files:
        fname = os.path.basename(pf)
        if ".pre." in fname:
            continue
        sid = fname.replace(".png","")
        if sid not in story_ids_with_json and sid not in seen_pngs:
            seen_pngs.add(sid)
            stories.append({
                "id": sid,
                "timestamp": None,
                "title": sid,
                "panels": [],
                "has_image": True,
                "has_pre": os.path.exists(os.path.join(STORIES_DIR, f"{sid}.pre.png")),
                "prompt": "",
            })

    stories.sort(key=lambda x: x["id"])
    return jsonify({"stories": stories})

# ─── API: CHARACTERS ─────────────────────────────────────────────
@app.route("/api/chars")
def get_chars():
    result = {}
    for chip_dir in sorted(glob.glob(os.path.join(CHARS_DIR, "Chip *"))):
        chip_num = os.path.basename(chip_dir).replace("Chip ", "")
        images = sorted(glob.glob(os.path.join(chip_dir, "*.png")))[:6]
        result[chip_num] = [os.path.basename(i) for i in images]
    return jsonify(result)

if __name__ == "__main__":
    print("🤖 HOLY CHIP WAR ROOM — http://localhost:8888")
    app.run(port=8888, debug=False)

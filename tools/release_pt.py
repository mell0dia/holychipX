#!/usr/bin/env python3
"""Release queue for the Portuguese Facebook Page ("Holy Chip - Português").

    release_pt.py              # post the OLDEST due entry (one per run), then stop
    release_pt.py --list       # show the queue
    release_pt.py --dry-run    # build the next due post (images + caption), post nothing
    release_pt.py --preview N  # build entry N (index in --list) without posting

Queue: content/pt-br/release-queue-pt.json, entries {at "YYYY-MM-DD HH:MM", kind,
...}. Kinds: opener, story, short, book, merch, ng. The plan the user approved
(2026-10-06) lives in content/pt-br/facebook-pt-plano.md.

Run by launchd (com.holychip.release-pt) every 10 minutes. One post per run, so
after the Mac sleeps through several slots they go out 10 minutes apart instead
of in a burst. A posted entry gets status "done" + fb_post_id and is never
re-posted. Everything goes ONLY to the PT Page (post_facebook.py --pt); the
English queue (release-queue.json) is separate.
"""
import json, os, random, re, subprocess, sys
from datetime import datetime
from pathlib import Path

HC = Path.home() / "holy-chip"
TOOLS = HC / "tools"
SITE = HC / "website" / "holy-chip-site"
PT = HC / "content" / "pt-br"
QUEUE = PT / "release-queue-pt.json"
WORK = PT / "fb"                       # built slides (square crops, blog cards, ng cards)
MERCH_HIST = PT / "merch-history-pt.json"
NFT_DIR = HC / "nft" / "collection" / "assets"
LOCK = Path("/tmp/holychip-release-pt.lock")

BASE_TAGS = "#HolyChip #IA #InteligenciaArtificial #Humor #Tirinhas"
WWW = "holy-chip.com"


def load():
    return json.loads(QUEUE.read_text())


def save(q):
    tmp = QUEUE.with_suffix(".tmp")
    tmp.write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(QUEUE)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HC)
    if r.returncode != 0:
        raise RuntimeError(f"{Path(cmd[1]).name} failed: {r.stderr.strip()[-400:] or r.stdout.strip()[-400:]}")
    return r.stdout


def blog_cards(sid):
    """The story's PT blog as 1080x1350 text slides (same renderer as English)."""
    WORK.mkdir(exist_ok=True)
    stem = WORK / f"{sid}.blog.pt.jpg"
    cards = sorted(WORK.glob(f"{sid}.blog.pt.[0-9].jpg"))
    if not cards:
        run(["python3", str(TOOLS / "blog_card.py"), sid, str(stem), "--lang", "pt",
             "--split", "2", "--width", "1080", "--height", "1350"])
        cards = sorted(WORK.glob(f"{sid}.blog.pt.[0-9].jpg"))
    return [str(c) for c in cards]


def comic_square(sid):
    """The PT comic as a 4:5 slide (for the ng carousel, like the English one)."""
    WORK.mkdir(exist_ok=True)
    sq = WORK / f"{sid}.pt.square.jpg"
    if not sq.exists():
        run(["python3", str(TOOLS / "square_crop.py"), str(SITE / "stories" / "pt" / f"{sid}.png"), str(sq)])
    return str(sq)


def ng_card(phrase, sid, q):
    """A PT gm card: random NFT not yet used on the PT page; not logged in the
    English gm-history (--no-record)."""
    WORK.mkdir(exist_ok=True)
    used = set(q.setdefault("ng_used_nfts", []))
    ids = sorted(int(p.stem) for p in NFT_DIR.glob("*.png") if p.stem.isdigit())
    pool = [i for i in ids if i not in used] or ids
    nft = random.choice(pool)
    out = WORK / f"ng-{datetime.now():%Y%m%d}-{sid}.png"
    run(["python3", str(TOOLS / "gm_card.py"), "--no-record", "--text", phrase, str(out), str(nft), sid])
    q["ng_used_nfts"].append(nft)
    return str(out), nft


def merch_photos(kind):
    """Same rules as the English merch posts (merch_post.py): a different bot
    every post, the chip always shown, Ringer/Fitted alternate - but with the
    PT page's own history."""
    sys.path.insert(0, str(TOOLS))
    import merch_post as m
    hist = json.loads(MERCH_HIST.read_text()) if MERCH_HIST.exists() else \
        {"used_bots": [], "next_shirt_style": "ringer", "posts": []}
    bot = m.pick_bot(hist, kind)
    style = None
    if kind == "shirt":
        style = hist.get("next_shirt_style", "ringer")
    paths = m.photos(kind, bot, style, lettering=random.random() < m.LETTERING_ODDS)
    return [str(p) for p in paths], bot, style, hist


def build(e, q):
    """[(image paths, caption), ...] - the Facebook posts for an entry, in order."""
    out = _build(e, q)
    return out if isinstance(out, list) else [out]


def _build(e, q):
    k = e["kind"]
    if k == "opener":
        return [str(SITE / e["image"])], e["caption"]
    if k == "story":
        # TWO posts (user, 2026-10-06): Facebook shows a multi-photo post as a
        # mosaic that cuts the comic. So the origin text goes first, and the
        # comic alone right after - the newest post sits on top, full size.
        sid = e["story"]
        link = f"{WWW}/origins/{sid}.html?lang=pt"
        return [(blog_cards(sid), f"A ORIGEM DA HISTÓRIA {sid}: {link}\n\n{BASE_TAGS} {e['tags']}"),
                ([str(SITE / "stories" / "pt" / f"{sid}.png")], f"ORIGEM DA HISTÓRIA: {link}\n\n{BASE_TAGS} {e['tags']}")]
    if k == "short":
        sid = e["story"]
        cap = (f"{e['lead']}\n\n{WWW}/stories.html?story={sid}.short&lang=pt\n\n"
               f"#HolyChip #IA #InteligenciaArtificial #Humor {e['tags']}")
        return [str(SITE / "stories" / "pt" / f"{sid}.short.png")], cap
    if k == "book":
        return [str(SITE / e["image"])], e["caption"]
    if k == "merch":
        imgs, bot, style, _ = merch_photos(e["merch"])
        e["_merch"] = {"bot": bot, "style": style}
        tag = "#Caneca" if e["merch"] == "mug" else "#Camiseta"
        return imgs, f"LOJA: {WWW}/store.html\n\n#HolyChip {tag}"
    if k == "ng":
        sid = e["story"]
        card, nft = ng_card(e["phrase"], sid, q)
        e["_nft"] = nft
        imgs = [card]          # Facebook: the card alone, like the English ng (no mosaic)
        cap = f"{e['phrase']}\n\nLEIA A ORIGEM: {WWW}/origins/{sid}.html?lang=pt\n\n{BASE_TAGS} {e.get('tags', '')}".rstrip()
        return imgs, cap
    raise ValueError(f"unknown kind {k}")


def post(imgs, cap):
    for p in imgs:
        if not Path(p).exists():
            raise FileNotFoundError(p)
    args = ["python3", str(TOOLS / "post_facebook.py"), "--pt"]
    args += (imgs + ["--", cap]) if len(imgs) > 1 else [imgs[0], cap]
    out = run(args)
    pid = re.search(r"FB_POST_ID:(\S+)", out)
    link = re.search(r"PERMALINK:(\S+)", out)
    if not pid:
        raise RuntimeError(f"no FB_POST_ID in output: {out[-300:]}")
    return pid.group(1), (link.group(1) if link else "")


def describe(i, e):
    what = e.get("story") or e.get("merch") or ""
    return f"{i:3d}  {e['at']}  {e['kind']:6s} {what:6s} {e.get('status', 'pending')}"


def main():
    q = load()
    entries = q["queue"]
    if "--list" in sys.argv:
        for i, e in enumerate(entries):
            print(describe(i, e))
        return
    if "--preview" in sys.argv:
        i = int(sys.argv[sys.argv.index("--preview") + 1])
        for n, (imgs, cap) in enumerate(build(entries[i], q), 1):
            print(f"--- post {n}"); print("IMAGES:", *imgs, sep="\n  "); print("CAPTION:\n" + cap)
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    due = [e for e in entries if e.get("status") != "done" and e["at"] <= now]
    if not due:
        print(f"{now}: nothing due"); return
    due.sort(key=lambda e: e["at"])
    e = due[0]
    dry = "--dry-run" in sys.argv
    if LOCK.exists() and not dry:
        print("another run is posting; skipping"); return
    try:
        if not dry: LOCK.write_text(str(os.getpid()))
        posts = build(e, q)
        print(f"{now}: {e['kind']} {e.get('story', e.get('merch', ''))} (due {e['at']})"
              + (f"; {len(due) - 1} more due" if len(due) > 1 else ""))
        for n, (imgs, cap) in enumerate(posts, 1):
            print(f"--- post {n}"); print("IMAGES:", *imgs, sep="\n  "); print("CAPTION:\n" + cap)
        if dry:
            print("--dry-run: nothing posted"); return
        done = e.setdefault("fb_posts", [])           # parts already out (a retry skips them)
        for n, (imgs, cap) in enumerate(posts):
            if n < len(done):
                continue
            pid, link = post(imgs, cap)
            done.append({"id": pid, "permalink": link})
            save(q)
        pid, link = done[-1]["id"], done[-1]["permalink"]
        e.update(status="done", posted_at=now, fb_post_id=pid, permalink=link)
        if e["kind"] == "merch":
            hist = json.loads(MERCH_HIST.read_text()) if MERCH_HIST.exists() else \
                {"used_bots": [], "next_shirt_style": "ringer", "posts": []}
            info = e.pop("_merch")
            hist["used_bots"].append(info["bot"])
            if e["merch"] == "shirt":
                hist["next_shirt_style"] = "style5" if info["style"] == "ringer" else "ringer"
            hist["posts"].append({"date": now, "kind": e["merch"], "bot": info["bot"],
                                  "style": info["style"], "fb_post_id": pid})
            MERCH_HIST.write_text(json.dumps(hist, indent=2) + "\n")
        e.pop("_nft", None)
        save(q)
        print(f"POSTED {pid} {link}")
    except Exception as exc:
        e["last_error"] = f"{now}: {exc}"
        if not dry: save(q)
        print(f"ERROR: {exc}", file=sys.stderr); sys.exit(1)
    finally:
        if not dry and LOCK.exists(): LOCK.unlink()


if __name__ == "__main__":
    main()

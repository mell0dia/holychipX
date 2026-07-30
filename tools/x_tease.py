#!/usr/bin/env python3
"""Generate + post an X/Twitter tease for a Holy Chip story.

Auto-generates the teaser line with local Gemma (Ollama) following the X craft
rules — NEVER reveal the punchline, pull the OPPOSITE emotional direction — then
assembles link + hashtags, validates < 280 chars, and posts via tweet_image.py.

Used by scheduled_release.sh so X is part of the automated release. The tease
decision is delegated to the model per user (2026-06-28); previously X required
a human-approved tease.

  x_tease.py HC### ["#theme #tags"] [--dry-run]

Prints TWEET_ID:<id> on success (or the assembled tweet text on --dry-run).
"""
import json, os, re, subprocess, sys, urllib.request
from pathlib import Path

HC = Path.home() / "holy-chip"
TOOLS = HC / "tools"
SDIR = HC / "stories"                      # HC###.json + HC###.png live here
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "gemma4:31b-it-q8_0"               # best local model for creative tease
BASE_TAGS = "#HolyChip #AI #AGI"
LINK = "holy-chip.com/stories.html?story={sid}"
MAXLEN = 280
ENV_FILE = os.path.expanduser("~/claude-agent/.env")


def load_env():
    """Load creds from ~/claude-agent/.env into the environment. tweet_image.py
    reads X_* keys from os.environ and does NOT self-load .env, so the cron/
    launchd path (which relies on the wrapper's export) can leave them unset.
    Loading here makes the automated X post self-sufficient like FB/IG/Nostr."""
    try:
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass


def load_story(sid):
    d = json.loads((SDIR / f"{sid}.json").read_text())
    s = d["script"]
    lines = [f"{dl['speaker']}: {dl['text']}"
             for sc in s["scenes"] for dl in sc["dialogs"]]
    return s["banner"]["title"], "\n".join(lines)


def ask_gemma(prompt):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.8}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=180).read()).get("response", "").strip()


def gen_tease(sid):
    title, dialog = load_story(sid)
    prompt = f"""You write one-line teasers for a darkly funny 3-panel comic strip ("Holy Chip") posted on X/Twitter. Two AI robots talk; the last panel is always a dark or absurd twist ending in "HOLY CHIP!!".

STRICT RULES:
- NEVER reveal, state, or hint at the twist/punchline. The reader must be surprised by the comic.
- Pull in the OPPOSITE emotional direction of the ending: if it ends dark, sound warm or hopeful; if absurd, sound earnest and serious. Maximum contrast.
- Be emotional and human — make someone want to click. Not a summary.
- ONE line, UNDER 130 characters. No hashtags, no links, no surrounding quotes. Plain text only.

COMIC TITLE: {title}
TRANSCRIPT:
{dialog}

Teaser line:"""
    raw = ask_gemma(prompt)
    # take first non-empty line, strip quotes/markdown
    line = ""
    for ln in raw.splitlines():
        ln = ln.strip().strip('"').strip("*").strip()
        if ln:
            line = ln
            break
    return re.sub(r"\s+", " ", line).strip()


def assemble(sid, tease, theme):
    link = LINK.format(sid=sid)
    tags = (BASE_TAGS + " " + theme).strip()
    tweet = f"{tease}\n\n{link}\n\n{tags}"
    # If over the limit, trim the tease (never the link/tags).
    if len(tweet) > MAXLEN:
        budget = MAXLEN - len(f"\n\n{link}\n\n{tags}") - 1
        tease = tease[:max(0, budget)].rstrip(" .,;:") + "…"
        tweet = f"{tease}\n\n{link}\n\n{tags}"
    return tweet


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if not args:
        sys.exit('usage: x_tease.py HC### ["#theme #tags"] [--dry-run]')
    sid = args[0]
    theme = args[1] if len(args) > 1 else ""

    tease = gen_tease(sid)
    if not tease:
        sys.exit("ERROR: model returned no tease")
    tweet = assemble(sid, tease, theme)
    print(f"--- {sid} X tease ({len(tweet)} chars) ---")
    print(tweet)
    if dry:
        print("\n[dry-run] not posting")
        return

    load_env()
    img = str(SDIR / f"{sid}.png")
    r = subprocess.run(["python3", str(TOOLS / "tweet_image.py"), img, tweet],
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        sys.exit(f"tweet_image failed (rc={r.returncode})")
    for line in r.stdout.splitlines():
        if line.startswith("TWEET_ID:"):
            print(line)
            return


if __name__ == "__main__":
    main()

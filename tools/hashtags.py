"""Hashtags, decided in one place (user, 2026-10-02).

* Every X post carries the core set of the most-used AI tags (see CORE).
  ("the posts on twitter, in general, have very poor hashtags")
* #Bitcoin ONLY when the post is about a Bitcoin story - not on everything.
* A post's own topic tags go after the core set; duplicates are dropped.
"""

# The most-used AI tags first, then each post adds a few of its own story's
# tags (user: "use all the AI related hashtags, the most used, then add a few
# hashtags related to the story itself"). No brand tags (#ChatGPT, #OpenAI...)
# unless a story is about that brand.
CORE = ["#HolyChip", "#AI", "#ArtificialIntelligence", "#AGI", "#ASI", "#LLM",
        "#AIAgents", "#GenAI", "#MachineLearning"]

# Stories (and shorts) that are actually about Bitcoin.
BITCOIN_STORIES = {"HC041", "HC042"}


def is_bitcoin(sid):
    return bool(sid) and sid.split(".")[0].upper() in BITCOIN_STORIES


def join(*groups, sid=None):
    """Space-joined tags, in order, no duplicates (case-insensitive); adds
    #Bitcoin when `sid` is a Bitcoin story."""
    out, seen = [], set()
    tags = [t for g in groups for t in (g.split() if isinstance(g, str) else g)]
    if is_bitcoin(sid):
        tags.append("#Bitcoin")
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return " ".join(out)


def x_tags(*extra, sid=None):
    """The tag line for an X post: core set + the post's own tags."""
    return join(CORE, *extra, sid=sid)


def story_tags(sid):
    """A story's own topic tags, as written for its release in
    content/release-queue.json (the latest entry wins). '' if it has none."""
    import json, os
    q = os.path.expanduser("~/holy-chip/content/release-queue.json")
    try:
        entries = json.load(open(q))["queue"]
    except Exception:
        return ""
    sid = (sid or "").split(".")[0].upper()
    found = [e.get("tags", "") for e in entries if e.get("story", "").upper() == sid and e.get("tags")]
    return found[-1] if found else ""

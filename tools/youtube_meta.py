#!/usr/bin/env python3
"""YouTube metadata for a Holy Chip story (user, 2026-10-17): the description IS
the origin essay, in the video's language, followed by the links and a wall of
AI hashtags; the tag field carries ~30 AI + theme keywords so the video is
findable in the AI world.

    youtube_meta.py HC013 --lang en|pt [--kind doc|short|story] [--json]

Prints title / tags / description (or JSON for the uploader).
"""
import argparse, json, re, sys
from pathlib import Path

HC = Path.home() / "holy-chip"
SITE = HC / "website" / "holy-chip-site"
ADIR = SITE / "stories" / "analysis"

# the searchable core, both languages (YouTube tags are not hashtags: plain keywords, <= 500 chars total)
TAGS_EN = ["Holy Chip", "AI", "artificial intelligence", "AGI", "superintelligence", "ASI", "machine learning", "LLM",
           "large language models", "AI agents", "generative AI", "AI comic", "AI humor", "AI satire", "AI comedy", "robots",
           "future of AI", "AI ethics", "AI alignment", "AI takeover", "AI vs humans", "technology", "singularity", "AI art",
           "AI animation", "webcomic", "science fiction", "near future", "AI explained", "AI documentary"]
TAGS_PT = ["Holy Chip", "IA", "inteligência artificial", "AGI", "superinteligência", "machine learning", "LLM", "agentes de IA",
           "IA generativa", "quadrinhos de IA", "humor de IA", "sátira", "robôs", "futuro da IA", "ética da IA", "tecnologia",
           "singularidade", "tirinha", "ficção científica", "IA explicada", "documentário", "ChatGPT", "automação", "futuro"]
HASH_EN = "#HolyChip #AI #ArtificialIntelligence #AGI #ASI #Superintelligence #MachineLearning #LLM #AIAgents #GenAI #AIComics #AIHumor #AISatire #Robots #FutureOfAI #AIEthics #AIAlignment #Singularity #TechHumor #Comics #Webcomic #Shorts"
HASH_PT = "#HolyChip #IA #InteligenciaArtificial #AGI #Superinteligencia #MachineLearning #LLM #AgentesDeIA #IAGenerativa #Quadrinhos #Tirinha #HumorDeIA #Robos #FuturoDaIA #EticaDaIA #Singularidade #Tecnologia #Shorts"
THEME_TAGS = {   # from stories/categories.json names -> extra keywords
    "Mind & Soul": (["consciousness", "philosophy of mind", "AI consciousness"], ["consciência", "filosofia"]),
    "Home & Family": (["smart home", "family", "relationships", "love"], ["casa inteligente", "família", "amor"]),
    "Work & Money": (["jobs", "economy", "automation", "productivity", "bitcoin"], ["empregos", "economia", "automação", "bitcoin"]),
    "Power & Politics": (["politics", "power", "democracy", "dictatorship", "AI politics"], ["política", "poder", "democracia", "ditadura"]),
    "Body & Science": (["science", "biology", "medicine", "DNA", "longevity"], ["ciência", "biologia", "medicina", "DNA", "longevidade"]),
    "Machines Among Us": (["autonomous cars", "AI assistants", "AI in daily life"], ["carros autônomos", "assistentes de IA"]),
}


def blog(sid, lang):
    p = ADIR / (f"{sid}.blog.md" if lang == "en" else f"{sid}.blog.{lang}.md")
    if not p.exists():
        return None, None, None, ""
    s = p.read_text()
    title = re.search(r"^#\s+(.+)$", s, re.M).group(1).strip()
    m = re.search(r"^##\s*Holy Chip #\d+\s*(?:--|—|–|-)\s*(.+)$", s, re.M); name = m.group(1).strip() if m else sid
    body = s.split("\n", 1)[1]
    body = body.split("\n---", 1)[0]                                   # drop the footer
    body = re.sub(r"^##\s.*$", "", body, flags=re.M)                     # drop the sub-heading
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", body); body = re.sub(r"\*(.+?)\*", r"\1", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    opener = body.split("\n\n")[0]
    return title, name, body, opener


def theme(sid):
    try:
        cats = json.loads((SITE / "stories" / "categories.json").read_text())["categories"]
        return [c["name"] for c in cats if sid in c["ids"]]
    except Exception:
        return []


def meta(sid, lang="en", kind="doc"):
    sid = sid.upper(); base = sid.split(".")[0]
    banner = json.loads((SITE / "stories" / f"{sid}.json").read_text())["script"]["banner"] if (SITE / "stories" / f"{sid}.json").exists() else {"title": base, "year": ""}
    title, name, body, opener = blog(base, lang)
    pt = lang == "pt"
    origin = f"https://holy-chip.com/origins/{base}.html" + ("?lang=pt" if pt else "")
    story = f"https://holy-chip.com/stories.html?story={sid}" + ("&lang=pt" if pt else "")
    if kind == "doc":
        head = (f"{sid} · {name or banner['title'].title()} — a história por trás, em dois minutos" if pt
                else f"{sid} · {name or banner['title'].title()} — the story behind, in two minutes")
        yt_title = f"{head} | Holy Chip {'(quadrinhos de IA)' if pt else '(AI comic)'}"
    else:
        yt_title = f"{sid} · {name or banner['title'].title()} | Holy Chip {'— tirinha de IA' if pt else '— AI comic strip'}"
    links = (f"LEIA A ORIGEM COMPLETA: {origin}\nA TIRINHA: {story}\nTODAS AS HISTÓRIAS: https://holy-chip.com/stories.html?lang=pt\nLOJA: https://holy-chip.com/store.html"
             if pt else f"READ THE FULL ORIGIN: {origin}\nTHE STRIP: {story}\nALL STORIES: https://holy-chip.com/stories.html\nSHOP: https://holy-chip.com/store.html")
    about = ("Holy Chip: dois chips de IA vivendo nos anos logo à nossa frente. Toda tirinha termina com Holy Chip!! — o momento em que a máquina entende alguma coisa sobre os humanos que os humanos prefeririam não dizer em voz alta."
             if pt else "Holy Chip: two little AI chips living in the years just ahead of us. Every strip ends with Holy Chip!! — the moment the machine understands something about humans that humans would rather not say out loud.")
    essay = body or ""
    header = f"{banner['title']} · {banner['year']}" + (f"\n{opener}" if opener and not essay.startswith(opener) else "")
    desc = "\n\n".join(x for x in [header if not essay else f"{banner['title']} · {banner['year']}", essay, links, about, HASH_PT if pt else HASH_EN] if x)
    tags = list(TAGS_PT if pt else TAGS_EN)
    for t in theme(base):
        tags += THEME_TAGS.get(t, ([], []))[1 if pt else 0]
    tags += [sid, banner["title"].lower()]
    # YouTube: 500 chars total, each tag < 30 chars
    out, n = [], 0
    for t in tags:
        t = t[:29]
        if t.lower() in {x.lower() for x in out}: continue
        if n + len(t) + 1 > 490: break
        out.append(t); n += len(t) + 1
    return {"title": yt_title[:100], "description": desc[:5000], "tags": out}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("sid"); ap.add_argument("--lang", default="en"); ap.add_argument("--kind", default="doc"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(); m = meta(a.sid, a.lang, a.kind)
    if a.json: print(json.dumps(m, ensure_ascii=False, indent=1))
    else:
        print("TITLE:", m["title"]); print("TAGS:", ", ".join(m["tags"])); print("\nDESCRIPTION:\n" + m["description"])

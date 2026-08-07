#!/usr/bin/env python3
"""make_origin.py — build origins/HC###.html for a new story.

    make_origin.py HC037
    make_origin.py HC037 --template HC036     # default: the highest existing page

WHY NOT THE /origins SKILL: its template predates the June 2026 layout work
(comic image on top, click-to-zoom lightbox, mobile drop-thumbnail) and
regenerating with it silently reverts those. This clones the most recent page
instead, so whatever the live pages look like is what a new one looks like.

Inputs
    stories/HC###.json                   banner + dialog for the transcript
    stories/analysis/HC###.blog.md       EN  (h1 = subtitle, italic = opener)
    stories/analysis/HC###.blog.es.md    ES
    stories/analysis/HC###.blog.pt.md    PT
    stories/analysis/HC###.blog.fr.md    FR

Also fixes the previous story's "Next >" link, which is otherwise left dangling.
"""
import os, re, sys, json, html, argparse, glob

BASE = os.path.expanduser("~/holy-chip/website/holy-chip-site")
ORIGINS = os.path.join(BASE, "origins")
ANALYSIS = os.path.join(BASE, "stories", "analysis")
STORIES = os.path.join(BASE, "stories")


def read_blog(sid, lang=""):
    """(subtitle, opener, [paragraphs]) from a blog markdown file."""
    suffix = f".blog.{lang}.md" if lang else ".blog.md"
    path = os.path.join(ANALYSIS, sid + suffix)
    if not os.path.exists(path):
        sys.exit(f"missing {path}")
    lines = [l.rstrip() for l in open(path).read().splitlines()]
    subtitle, opener, paras = "", "", []
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if s.startswith("# "):
            subtitle = s[2:].strip()
        elif s.startswith("## "):
            continue
        elif s == "---":
            break
        elif s.startswith("*") and s.endswith("*") and not opener:
            opener = s.strip("*").strip()
        else:
            paras.append(s)
    return subtitle, opener, paras


def md_inline(t):
    """**bold** -> <strong>, then escape everything else."""
    parts = re.split(r"(\*\*[^*]+\*\*)", t)
    out = []
    for p in parts:
        if p.startswith("**") and p.endswith("**"):
            out.append("<strong>" + html.escape(p[2:-2]) + "</strong>")
        else:
            out.append(html.escape(p))
    return "".join(out)


def lang_block(lang, active, opener, paras):
    cls = "lang-content active" if active else "lang-content"
    body = "\n".join(f"          <p>{md_inline(p)}</p>" for p in paras)
    return (f'      <div class="{cls}" data-lang="{lang}">\n'
            f'        <div class="opener">\n'
            f'          {html.escape(opener)}\n'
            f'        </div>\n'
            f'        <div class="body-text">\n{body}\n'
            f'        </div>\n'
            f'      </div>')


def transcript(script, lang, active):
    cls = "lang-content active" if active else "lang-content"
    out = [f'        <div class="{cls}" data-lang="{lang}">']
    for i, scene in enumerate(script["scenes"], 1):
        out.append('        <div class="dialog-panel">')
        out.append(f'          <div class="dialog-panel-label">Panel {i}</div>')
        for d in scene["dialogs"]:
            who = "Chip 0" if "Left" in d.get("speaker", "") else "Chip 1"
            txt = " ".join(d.get("text", "").split())
            out.append('          <div class="dialog-line">')
            out.append(f'            <span class="dialog-speaker-label">{who}</span>')
            out.append(f'            <span class="dialog-text">{html.escape(txt)}</span>')
            out.append('          </div>')
        out.append('        </div>')
    out.append('        </div>')
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--template", help="page to clone (default: highest existing)")
    a = ap.parse_args()
    sid = a.story.upper()
    num = sid[2:]

    pages = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ORIGINS, "HC*.html")))
    tmpl_id = a.template.upper() if a.template else pages[-1]
    if tmpl_id == sid:
        tmpl_id = pages[-2]
    tmpl = open(os.path.join(ORIGINS, tmpl_id + ".html")).read()
    t_num = tmpl_id[2:]
    print(f"cloning layout from {tmpl_id}.html")

    script = json.load(open(os.path.join(STORIES, sid + ".json")))["script"]
    banner = script["banner"]
    meta = f"{banner['title']} -- {banner['year']}"

    subtitle, opener_en, paras_en = read_blog(sid)
    blogs = {"en": (opener_en, paras_en)}
    for lg in ("es", "pt", "fr"):
        _, op, pr = read_blog(sid, lg)
        blogs[lg] = (op, pr)

    # the story's display name is the second heading of the EN blog
    m = re.search(r"^##\s*Holy Chip #\d+\s*--\s*(.+)$",
                  open(os.path.join(ANALYSIS, sid + ".blog.md")).read(), re.M)
    title = m.group(1).strip() if m else sid

    # old title/subtitle/meta, so they can be swapped out of the clone
    t_title = re.search(r'<h1 class="hero-title">([^<]*)</h1>', tmpl).group(1)
    t_sub = re.search(r'<div class="hero-subtitle">([^<]*)</div>', tmpl).group(1)
    t_meta = re.search(r'<div class="hero-meta">([^<]*)</div>', tmpl).group(1)

    out = tmpl
    # blog columns
    start = out.index('      <div class="lang-content active" data-lang="en">')
    end = out.index('    </div>\n\n    <!-- Right: visual -->') if '<!-- Right: visual -->' in out \
        else out.index('    <div class="visual-column">')
    blocks = "\n".join(lang_block(lg, lg == "en", *blogs[lg])
                       for lg in ("en", "es", "pt", "fr"))
    out = out[:start] + blocks + "\n" + out[end:]

    # transcripts
    tstart = out.index('        <div class="lang-content active" data-lang="en">')
    tend = out.index('      </div>\n    </div>', tstart)
    tblocks = "\n".join(transcript(script, lg, lg == "en")
                        for lg in ("en", "es", "pt", "fr"))
    out = out[:tstart] + tblocks + "\n" + out[tend:]

    # identity
    out = out.replace(t_title, title).replace(t_sub, subtitle).replace(t_meta, meta)
    out = out.replace(f"HC{t_num}", sid).replace(f"#{t_num}", f"#{num}")

    # navigation: previous is the template, next is not written yet
    out = re.sub(r'<a href="HC\d+\.html" class="story-nav-link">&lt;[^<]*</a>',
                 f'<a href="{tmpl_id}.html" class="story-nav-link">&lt; {t_title}</a>', out)
    out = re.sub(r'<a href="HC\d+\.html" class="story-nav-link">Next[^<]*</a>',
                 '<span class="story-nav-link disabled">Next &gt;</span>', out)

    dest = os.path.join(ORIGINS, sid + ".html")
    open(dest, "w").write(out)
    print(f"-> {dest}  ({os.path.getsize(dest)/1024:.0f} KB)")

    # point the previous page's Next at this one
    prev_path = os.path.join(ORIGINS, tmpl_id + ".html")
    prev = open(prev_path).read()
    new_prev = re.sub(r'<span class="story-nav-link disabled">Next &gt;</span>',
                      f'<a href="{sid}.html" class="story-nav-link">{title} &gt;</a>', prev)
    if new_prev != prev:
        open(prev_path, "w").write(new_prev)
        print(f"-> {tmpl_id}.html  Next link now points at {sid}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Copy a Portuguese blog (stories/analysis/HC###.blog.pt.md) into the PT
blog block of its origin page (origins/HC###.html) - the opener and the body
paragraphs. Only the blog block; the PT transcript block (origin_pt.py) is
left alone.

    python3 blog_pt_sync.py            # all stories
    python3 blog_pt_sync.py HC010      # one
    python3 blog_pt_sync.py --check    # report pages that differ, write nothing
"""
import html, re, sys
from pathlib import Path

SITE = Path.home() / "holy-chip" / "website" / "holy-chip-site"
A = SITE / "stories" / "analysis"


def inline(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s.replace("\u2014", "--").replace("\u2026", "...")   # site convention


def md_parts(sid):
    """(opener, [paragraph html]) from the blog markdown."""
    lines = (A / f"{sid}.blog.pt.md").read_text().split("\n")
    body = []
    for l in lines:
        if l.strip() == "---":
            break
        body.append(l)
    paras = []
    for l in body:
        if l.startswith("#"):
            continue
        if l.strip():
            paras.append(l.strip())                 # each md line is its own <p>, as on the site
    opener = paras.pop(0)
    opener = re.sub(r"^\*(.*)\*$", r"\1", opener.strip()).replace("\u2014", "--")
    return opener, paras


def block_html(sid):
    opener, paras = md_parts(sid)
    out = ['      <div class="lang-content" data-lang="pt">',
           '        <div class="opener">',
           f'          {inline(opener)}',
           '        </div>',
           '        <div class="body-text">']
    for i, p in enumerate(paras):
        if i == len(paras) - 1 and re.fullmatch(r"Holy Chip[.!]+", p.strip()):
            out.append(f'          <p class="holy-chip">{p.strip()}</p>')
        else:
            out.append(f'          <p>{inline(p)}</p>')
    out += ['        </div>', '      </div>']
    return "\n".join(out)


BLOCK = re.compile(r'      <div class="lang-content" data-lang="pt">\n        <div class="opener">[\s\S]*?\n        </div>\n      </div>')


def norm(s):
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    sids = args or sorted(p.name[:5] for p in A.glob("HC0*.blog.pt.md"))
    for sid in sids:
        p = SITE / "origins" / f"{sid}.html"
        if not p.exists():
            continue
        page = p.read_text()
        m = BLOCK.search(page)
        if not m:
            print(f"{sid}: PT blog block NOT FOUND"); continue
        new = block_html(sid)
        if norm(m.group(0)) == norm(new):
            continue
        if check:
            print(f"{sid}: differs"); continue
        p.write_text(page[:m.start()] + new + page[m.end():])
        print(f"{sid}: updated")


if __name__ == "__main__":
    main()

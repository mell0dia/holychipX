#!/usr/bin/env python3
"""Regenerate the 4 blog language blocks (EN/ES/PT/FR) in an origin page from the
blog .md files. Only touches the text-column blog content (first lang-content per
lang); leaves layout, lightbox, transcript, mobile-thumb intact. Usage: regen_blog_blocks.py HC###"""
import re, sys
from pathlib import Path

SITE = Path.home() / "holy-chip/website/holy-chip-site"
ADIR = SITE / "stories/analysis"
SUF = {"en": "blog.md", "es": "blog.es.md", "pt": "blog.pt.md", "fr": "blog.fr.md"}


def parse(md):
    paras = [p.strip() for p in md.split("\n\n") if p.strip()]
    opener, body = None, []
    for p in paras:
        if p.startswith("#"):
            continue
        if p.startswith("---"):
            break
        if opener is None and p.startswith("*") and p.endswith("*"):
            opener = p.strip("*").strip(); continue
        body.append(" ".join(l.strip() for l in p.splitlines()))
    return opener, body


def regen(sid):
    page = SITE / f"origins/{sid}.html"
    html = page.read_text()
    for lang in ["en", "es", "pt", "fr"]:
        opener, body = parse((ADIR / f"{sid}.{SUF[lang]}").read_text())
        ps = []
        for b in body:
            if b == "Holy Chip.":
                ps.append('          <p class="holy-chip">Holy Chip.</p>')
            else:
                ps.append(f'          <p>{b}</p>')
        cls = "lang-content active" if lang == "en" else "lang-content"
        block = (f'<div class="{cls}" data-lang="{lang}">\n'
                 f'        <div class="opener">\n          {opener}\n        </div>\n'
                 f'        <div class="body-text">\n' + "\n".join(ps) + "\n"
                 f'        </div>\n      </div>')
        pat = re.compile(r'<div class="lang-content[^"]*" data-lang="' + lang + r'">.*?</div>\s*</div>',
                         re.DOTALL)
        html, n = pat.subn(block, html, count=1)
        assert n == 1, f"{sid} {lang}: matched {n} (expected 1)"
    page.write_text(html)
    print(f"{sid}: 4 blog language blocks regenerated")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: regen_blog_blocks.py HC###")
    regen(sys.argv[1])

#!/usr/bin/env python3
"""fix_origin_page.py - restore what generate_origins.py strips.

    fix_origin_page.py HC040 [--ref HC033] [--prev HC039]

RUN THIS AFTER EVERY generate_origins.py. The generator rewrites all 35 pages
from a template that predates two hand-added features, so every run silently
removes them:

  1. THE CLICK-TO-ZOOM LIGHTBOX and the mobile drop-thumbnail (added 2026-06-04).
     Note the two JS functions live INSIDE the existing script block, immediately
     before `function setLang`, not in a separate tag at the tail - putting them
     at the end produces a page with a lightbox div and no functions, which fails
     silently on click.

  2. CORRECT PREV/NEXT NAVIGATION. The generator's STORIES list stops at HC033
     even though HC034-HC039 have pages, so a new story's "previous" link points
     at HC033 and skips six stories.

The usual workflow is: regenerate, revert every page but the new one, then run
this. Reverting matters - the other 34 are already correct on disk, and letting
the generator's output stand would strip them too.
"""
import argparse, os, re, sys

SITE = os.path.expanduser("~/holy-chip/website/holy-chip-site")
ORIGINS = os.path.join(SITE, "origins")


def find(lines, needle, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    return -1


def restore_lightbox(tgt_lines, ref_lines, sid, title):
    if find(tgt_lines, "function openLightbox") >= 0:
        return tgt_lines, False

    # CSS: the lightbox rules through the end of the mobile-thumb media query
    c0 = find(ref_lines, "/* Click-to-zoom lightbox */")
    m = find(ref_lines, "@media (max-width: 860px)", c0)
    depth, end = 0, m
    for i in range(m, len(ref_lines)):
        depth += ref_lines[i].count("{") - ref_lines[i].count("}")
        if depth == 0 and i > m:
            end = i
            break
    css = "".join(ref_lines[c0 - 1:end + 1])

    div = [l for l in ref_lines if 'id="lightbox" class="lightbox"' in l]
    fns = [l for l in ref_lines
           if "function openLightbox(src)" in l or "function closeLightbox()" in l]
    if not (div and len(fns) == 2):
        sys.exit("could not lift the lightbox out of the reference page")

    anchor = find(tgt_lines, ".bottom-section { padding: 0 1rem 4rem; }")
    out = tgt_lines[:anchor + 2] + [css] + tgt_lines[anchor + 2:]

    res = []
    for l in out:
        if '<div class="comic-frame"' in l:
            res.append(f'      <img class="mobile-thumb" src="../stories/{sid}.png" '
                       f'alt="{sid} - {title}" onclick="openLightbox(this.src)">\n')
        if (f'src="../stories/{sid}.png"' in l and "hero-bg" not in l
                and "mobile-thumb" not in l and "onclick" not in l):
            l = l.rstrip("\n")
            l = l[:l.rfind(">")] + ' onclick="openLightbox(this.src)">\n'
        res.append(l)

    i = find(res, "function setLang")          # functions go INSIDE this block
    res = res[:i] + fns + res[i:]
    b = find(res, "</body>")
    return res[:b] + div + res[b:], True


def fix_nav(sid, prev):
    """Point this page's 'previous' at `prev`, and give `prev` a 'next' here."""
    p = os.path.join(ORIGINS, f"{sid}.html")
    s = open(p).read()
    prev_title = story_title(prev)
    s = re.sub(r'<a href="HC\d+\.html" class="story-nav-link">&lt; [^<]*</a>',
               f'<a href="{prev}.html" class="story-nav-link">&lt; {prev_title}</a>', s, count=1)
    open(p, "w").write(s)

    pp = os.path.join(ORIGINS, f"{prev}.html")
    ps = open(pp).read()
    if '<span class="story-nav-link disabled">Next &gt;</span>' in ps:
        ps = ps.replace('<span class="story-nav-link disabled">Next &gt;</span>',
                        f'<a href="{sid}.html" class="story-nav-link">{story_title(sid)} &gt;</a>')
        open(pp, "w").write(ps)
        return True
    return False


def story_title(sid):
    p = os.path.join(os.path.expanduser("~/holy-chip/stories/analysis"), f"{sid}.blog.md")
    try:
        for line in open(p, encoding="utf-8"):
            if line.startswith("## ") and "--" in line:
                return line.split("--", 1)[1].strip()
    except Exception:
        pass
    return sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--ref", default="HC033",
                    help="a page that still has the lightbox, to copy from")
    ap.add_argument("--prev", help="the story before this one (fixes prev/next)")
    a = ap.parse_args()
    sid = a.story.upper()

    tgt_path = os.path.join(ORIGINS, f"{sid}.html")
    if not os.path.exists(tgt_path):
        sys.exit(f"no page at {tgt_path}")
    tgt = open(tgt_path).read().splitlines(keepends=True)
    ref = open(os.path.join(ORIGINS, f"{a.ref}.html")).read().splitlines(keepends=True)

    tgt, did = restore_lightbox(tgt, ref, sid, story_title(sid))
    open(tgt_path, "w").write("".join(tgt))
    print(f"  lightbox: {'restored' if did else 'already present'}")

    if a.prev:
        linked = fix_nav(sid, a.prev.upper())
        print(f"  nav: previous -> {a.prev.upper()}"
              + (f", and {a.prev.upper()} now links forward" if linked else ""))

    for label, pat in (("openLightbox", "function openLightbox"),
                       ("closeLightbox", "function closeLightbox"),
                       ("lightbox div", 'id="lightbox"'),
                       ("mobile thumb", 'class="mobile-thumb" src')):
        n = open(tgt_path).read().count(pat)
        print(f"  {label}: {n}" + ("  <-- MISSING" if n == 0 else ""))


if __name__ == "__main__":
    sys.exit(main())

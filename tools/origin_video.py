#!/usr/bin/env python3
"""Origin pages: the documentary video at the top of the essay (user, 2026-10-14).

For every origins/HC###.html whose videos/HC###.doc.mp4 exists, a player goes
in above the text column's first language block: the English video for
EN/ES/FR, videos/HC###.doc.pt.mp4 while PT is selected (when it exists).
Idempotent: re-running replaces what it inserted. Run after any page regen.

    python3 origin_video.py            # all pages
    python3 origin_video.py HC023      # one page
"""
import json, re, sys
from pathlib import Path

SITE = Path.home() / "holy-chip" / "website" / "holy-chip-site"
MARK = "<!-- doc-video -->"
TRACKER = Path.home() / "holy-chip" / "content" / "story-posts.json"


def yt_full(sid):
    """(en id, pt id) of the LONG YouTube versions, when the tracker has them (user, 2026-10-19:
    the site shows the long video via YouTube, never the shorts file)."""
    try:
        e = next(x for x in json.loads(TRACKER.read_text())["posted"] if x.get("story") == sid)
        return e.get("yt_doc_full_id"), e.get("yt_doc_full_pt_id")
    except Exception:
        return None, None

CSS = """    /* -- documentary video (doc-video) -- */
    .doc-video { margin: 0 0 2rem; }
    .doc-video video, .doc-video iframe { display: block; width: 100%; max-width: 360px; margin: 0 auto; aspect-ratio: 9 / 16; background: #000; border-radius: 10px; border: 0; }
    .doc-video .doc-caption { text-align: center; font-size: 0.8rem; letter-spacing: 0.12em; text-transform: uppercase; opacity: .6; margin: .6rem 0 0; }
"""


def block(sid, has_pt):
    pt = f"../videos/{sid}.doc.pt.mp4" if has_pt else f"../videos/{sid}.doc.mp4"
    return f"""{MARK}
      <div class="doc-video">
        <video id="doc-video" controls preload="metadata" playsinline src="../videos/{sid}.doc.mp4"
               data-src-en="../videos/{sid}.doc.mp4" data-src-pt="{pt}"></video>
        <p class="doc-caption" data-en="The story behind, in two minutes" data-es="La historia detr&aacute;s, en dos minutos"
           data-pt="A hist&oacute;ria por tr&aacute;s, em dois minutos" data-fr="L'histoire derri&egrave;re, en deux minutes">The story behind, in two minutes</p>
      </div>
      {MARK}
"""


def embed(sid, en, pt):
    pt = pt or en
    return f"""{MARK}
      <div class="doc-video">
        <iframe id="doc-video" src="https://www.youtube.com/embed/{en}" data-src-en="https://www.youtube.com/embed/{en}" data-src-pt="https://www.youtube.com/embed/{pt}"
                title="Holy Chip #{sid[2:]} - the story behind" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe>
        <p class="doc-caption" data-en="The story behind, the full version" data-es="La historia detr&aacute;s, versi&oacute;n completa"
           data-pt="A hist&oacute;ria por tr&aacute;s, vers&atilde;o completa" data-fr="L'histoire derri&egrave;re, version compl&egrave;te">The story behind, the full version</p>
      </div>
      {MARK}
"""


JS = """    // doc-video: the Portuguese video while PT is selected
    function swapVideo(lang) {
      var v = document.getElementById('doc-video'); if (!v) return;
      var want = (lang === 'pt' && v.dataset.srcPt) ? v.dataset.srcPt : v.dataset.srcEn;
      if (v.getAttribute('src') !== want) { v.setAttribute('src', want); if (v.load) v.load(); }
      var c = document.querySelector('.doc-caption'); if (c && c.dataset[lang]) c.innerHTML = c.dataset[lang];
    }
"""


def apply(page):
    sid = page.stem
    en, pt = yt_full(sid)
    local = (SITE / "videos" / f"{sid}.doc.mp4").exists()
    s = page.read_text()
    had = MARK in s
    s = re.sub(rf"{re.escape(MARK)}.*?{re.escape(MARK)}\n", "", s, flags=re.S)          # idempotent
    if not en and not local:
        if had: page.write_text(s); return "removed"
        return "no video"
    has_pt = (SITE / "videos" / f"{sid}.doc.pt.mp4").exists()
    anchor = '    <div class="text-column">\n'
    if anchor not in s:
        return "no text column"
    s = s.replace(anchor, anchor + (embed(sid, en, pt) if en else block(sid, has_pt)), 1)
    if ".doc-video {" not in s:
        s = s.replace("    .text-column {", CSS + "    .text-column {", 1)
    if "function swapVideo" not in s:
        s = s.replace("    function setLang(lang) {", JS + "    function setLang(lang) {", 1)
    if "swapVideo(lang);" not in s:
        s = s.replace("      swapComic(lang);\n", "      swapComic(lang);\n      swapVideo(lang);\n", 1)
    page.write_text(s)
    return ("youtube" + (" + pt" if pt else "")) if en else ("video" + (" + pt" if has_pt else ""))


pages = [SITE / "origins" / f"{a.upper()}.html" for a in sys.argv[1:]] or sorted((SITE / "origins").glob("HC*.html"))
for p in pages:
    r = apply(p)
    if r != "no video":
        print(p.name, r)

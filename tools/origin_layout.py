#!/usr/bin/env python3
"""Reverse the origin-page right column (image on top, transcript below) and add
a click-to-zoom lightbox. Idempotent. Usage: origin_layout.py <file.html> [...]"""
import re, sys
from pathlib import Path

LIGHTBOX_CSS = """
    /* Click-to-zoom lightbox */
    .comic-frame img { cursor: zoom-in; }
    .lightbox {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.92);
      z-index: 1000;
      cursor: zoom-out;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }
    .lightbox.active { display: flex; }
    .lightbox img {
      max-width: 95vw;
      max-height: 95vh;
      object-fit: contain;
      box-shadow: 0 0 40px rgba(0,0,0,0.6);
    }
"""

LIGHTBOX_HTML = (
    '  <div id="lightbox" class="lightbox" onclick="closeLightbox()">'
    '<img id="lightbox-img" src="" alt="Holy Chip comic"></div>\n'
)

LIGHTBOX_JS = """  <script>
    function openLightbox(src){var lb=document.getElementById('lightbox');document.getElementById('lightbox-img').src=src;lb.classList.add('active');document.body.style.overflow='hidden';}
    function closeLightbox(){document.getElementById('lightbox').classList.remove('active');document.body.style.overflow='';}
    document.addEventListener('keydown',function(e){if(e.key==='Escape')closeLightbox();});
  </script>
"""


def transform(html):
    changed = []

    # 1. Reverse the visual column: image block before transcript block.
    if html.find('<div class="comic-frame"') > html.find('<div class="dialog-section">'):
        region_pat = re.compile(
            r'<div class="dialog-section">.*?<div class="comic-caption">.*?</div>',
            re.DOTALL)
        m = region_pat.search(html)
        if m:
            region = m.group(0)
            idx = region.index('<div class="comic-frame"')
            transcript = region[:idx].rstrip()
            image = region[idx:].replace(' style="margin-top:10px;"', '', 1)
            new_region = image + "\n      " + transcript
            html = html[:m.start()] + new_region + html[m.end():]
            changed.append("reordered")

    # 2. Make the comic image open the lightbox.
    if "openLightbox" not in html:
        html, n = re.subn(
            r'(<div class="comic-frame"[^>]*>\s*<img\b)([^>]*?)(\s*/?>)',
            r'\1\2 onclick="openLightbox(this.src)"\3',
            html, count=1)
        if n:
            changed.append("img-onclick")

    # 3. Inject lightbox CSS / HTML / JS once.
    if 'id="lightbox"' not in html:
        html = html.replace("</style>", LIGHTBOX_CSS + "  </style>", 1)
        html = html.replace("</body>", LIGHTBOX_HTML + LIGHTBOX_JS + "</body>", 1)
        changed.append("lightbox")

    return html, changed


def main():
    for fp in sys.argv[1:]:
        p = Path(fp)
        html = p.read_text()
        new, changed = transform(html)
        if changed:
            p.write_text(new)
            print(f"{p.name}: {', '.join(changed)}")
        else:
            print(f"{p.name}: no change (already done)")


if __name__ == "__main__":
    main()

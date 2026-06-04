#!/usr/bin/env python3
"""Mobile-only: add a small comic drop-thumbnail at the start of the text column
(text wraps around it), hide the big comic on mobile. Desktop unchanged. Reuses
the existing lightbox (tap to zoom). Idempotent. Usage: origin_mobile.py <file> [...]"""
import re, sys
from pathlib import Path

CSS = """
    /* Mobile: small comic drop-thumbnail, text wraps around it */
    .mobile-thumb { display: none; }
    @media (max-width: 860px) {
      .comic-frame, .comic-caption { display: none; }
      .mobile-thumb {
        display: block;
        float: left;
        width: 180px;
        margin: 0.3rem 1rem 0.4rem 0;
        border: 2px solid #999;
        cursor: zoom-in;
      }
    }
"""


def transform(html):
    if 'class="mobile-thumb"' in html:
        return html, False
    m = re.search(r'<div class="comic-frame">\s*<img src="([^"]+)"[^>]*alt="([^"]*)"', html)
    if not m:
        return html, False
    src, alt = m.group(1), m.group(2)
    thumb = (f'      <img class="mobile-thumb" src="{src}" alt="{alt}" '
             f'onclick="openLightbox(this.src)">\n')
    html = html.replace('<div class="text-column">\n',
                        '<div class="text-column">\n' + thumb, 1)
    html = html.replace("</style>", CSS + "  </style>", 1)
    return html, True


def main():
    for fp in sys.argv[1:]:
        p = Path(fp)
        new, changed = transform(p.read_text())
        if changed:
            p.write_text(new)
            print(f"{p.name}: mobile-thumb added")
        else:
            print(f"{p.name}: no change (already done / no comic-frame)")


if __name__ == "__main__":
    main()

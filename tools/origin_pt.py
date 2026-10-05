#!/usr/bin/env python3
"""Origin pages, Portuguese tab = the PT-BR edition (user, 2026-10-04).

For every origins/HC###.html that has a content/pt-br/HC###.pt.dialogo.md:
  * the PT transcript block becomes the new Portuguese dialogue (the one the
    user approved for the PT comic), not a translation of the English one;
  * the comic images (hero, big image, mobile thumb, lightbox) switch to
    stories/pt/HC###.png while PT is selected, and back on EN/ES/FR.

Idempotent: re-running replaces what it inserted. Run after any page regen.

    python3 origin_pt.py            # all pages
    python3 origin_pt.py HC021      # one page
"""
import html, json, re, sys
from pathlib import Path

HC = Path.home() / "holy-chip"
SITE = HC / "website" / "holy-chip-site"
PT = HC / "content" / "pt-br"
MARK = "<!-- pt-edition -->"


def pt_panels(sid):
    """[[(side, text), ...] x3] from the PT dialogue file. side: L / R / FX."""
    md = (PT / f"{sid}.pt.dialogo.md").read_text()
    panels, cur = [[], [], []], None
    for raw in md.splitlines():
        s = raw.strip()
        if s.startswith("---"):
            break
        m = re.match(r"##\s*P\w*inel\s*(\d)", s, re.I)          # tolerates "PÁinel"
        if m:
            cur = int(m.group(1)) - 1; continue
        if s.startswith("##"):
            cur = None; continue
        if cur is None or not s:
            continue
        m = re.match(r"(ESQUERDA|DIREITA|EFEITO)\s*:\s*(.+)", s, re.I)
        if m:
            side = {"ESQUERDA": "L", "DIREITA": "R"}.get(m.group(1).upper(), "FX")
            panels[cur].append((side, m.group(2).strip()))
    return panels


def side_labels(sid, page):
    """Which 'Chip N' label the page uses for the left and the right bot,
    read off the English transcript against the story's own script."""
    labels = {"L": "Chip 0", "R": "Chip 1"}
    try:
        script = json.loads((SITE / "stories" / f"{sid}.json").read_text())["script"]
        en = re.search(r'<div class="lang-content active" data-lang="en">([\s\S]*?)</div>\s*</div>\s*</div>\s*(?=<div class="lang-content")',
                       page.split('class="dialog-section"', 1)[1])
        en_labels = re.findall(r'dialog-speaker-label">([^<]+)<', en.group(1)) if en else []
        speakers = [d["speaker"] for sc in script["scenes"] for d in sc["dialogs"]]
        seen = {}
        for sp, lab in zip(speakers, en_labels):
            side = "L" if sp.startswith("Left") else "R"
            if "+" not in lab and side not in seen:      # first clean line per side
                seen[side] = lab
        labels.update(seen)
    except Exception:
        pass
    if labels["L"] == labels["R"]:
        labels = {"L": "Chip 0", "R": "Chip 1"}
    return labels


def render(panels, labels):
    out = [f'        <div class="lang-content" data-lang="pt">{MARK}']
    for i, panel in enumerate(panels, 1):
        out.append('        <div class="dialog-panel">')
        out.append(f'          <div class="dialog-panel-label">Painel {i}</div>')
        for side, text in panel:
            out.append('          <div class="dialog-line">')
            if side == "FX":
                out.append(f'            <span class="dialog-speaker-label">*</span>')
            else:
                out.append(f'            <span class="dialog-speaker-label">{labels[side]}</span>')
            out.append(f'            <span class="dialog-text">{html.escape(text)}</span>')
            out.append('          </div>')
        out.append('        </div>')
    out.append('        </div>')
    return "\n".join(out)


SWAP_JS = """
    // PT edition: the comic itself is in Portuguese while PT is selected (pt-edition)
    function swapComic(lang) {
      document.querySelectorAll('img[data-src-en]').forEach(function (im) {
        im.src = (lang === 'pt' && im.dataset.srcPt) ? im.dataset.srcPt : im.dataset.srcEn;
      });
    }"""


def patch(sid):
    p = SITE / "origins" / f"{sid}.html"
    page = p.read_text()
    labels = side_labels(sid, page)
    new_block = render(pt_panels(sid), labels)

    # 1) PT transcript block inside the dialog section (the second set of lang-content blocks)
    head, sep, tail = page.partition('class="dialog-section"')
    m = re.search(r'        <div class="lang-content" data-lang="pt">[\s\S]*?\n        </div>\n(?=        <div class="lang-content"|      </div>)', tail)
    if not m:
        raise SystemExit(f"{sid}: PT transcript block not found")
    tail = tail[:m.start()] + new_block + "\n" + tail[m.end():]
    page = head + sep + tail

    # 2) comic images: remember both sources
    en_src, pt_src = f"../stories/{sid}.png", f"../stories/pt/{sid}.png"
    def tag(mo):
        t = mo.group(0)
        if "data-src-en" in t:
            return t
        return t.replace(f'src="{en_src}"', f'src="{en_src}" data-src-en="{en_src}" data-src-pt="{pt_src}"', 1)
    page = re.sub(r'<img[^>]*src="' + re.escape(en_src) + r'"[^>]*>', tag, page)

    # 3) swap on language change (and the lightbox opens whatever is shown)
    if "function swapComic" not in page:
        page = page.replace("    function setLang(lang) {", SWAP_JS + "\n    function setLang(lang) {", 1)
        page = page.replace("      try { localStorage.setItem('hc-lang', lang); } catch(e) {}",
                            "      swapComic(lang);\n      try { localStorage.setItem('hc-lang', lang); } catch(e) {}", 1)
    p.write_text(page)
    return labels


def main():
    sids = sys.argv[1:] or sorted(f.name[:5] for f in PT.glob("HC0[0-4][0-9].pt.dialogo.md"))
    for sid in sids:
        if not (SITE / "origins" / f"{sid}.html").exists() or not (SITE / "stories" / "pt" / f"{sid}.png").exists():
            print(f"{sid}: skipped (no origin page or no PT image)"); continue
        print(sid, patch(sid))


if __name__ == "__main__":
    main()

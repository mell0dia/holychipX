#!/usr/bin/env python3
"""Render a Brazilian-Portuguese SHORT: content/pt-br/HC###.pt.dialogo.md -> HC###.short.pt.png

    python3 render_short_pt.py HC042 [--expr surprise|fear|...]

The dialogue file has ## Banner, ## Diálogo (ESQUERDA:/DIREITA: lines - left
bot talking = black bubble, right bot from off-frame = white) and ## Final (the
punchline, always HOLY CHIP !!). Bots and the reaction expression come from
the published stories/HC###.short.json. Runs SGen's default short engine
(generateShortComicImageGemini: Gemini draws the reaction bot, SGen letters
everything) on the dev server (:3000). Footer credit localized.
"""
import html, json, re, subprocess, sys
from pathlib import Path

HC = Path.home() / "holy-chip"
PT = HC / "content" / "pt-br"
STORIES = HC / "website" / "holy-chip-site" / "stories"
SGEN = HC / "SGen"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FOOTER = "feito por rmello © mellodia"


def parse(md):
    banner, lines, punch, cur = None, [], "HOLY CHIP !!", None
    for raw in md.splitlines():
        s = raw.strip()
        if s.startswith("---"):
            break
        if s.startswith("##"):
            cur = s[2:].strip().lower(); continue
        if cur == "banner" and s.startswith("#HC"):
            p = [x.strip() for x in s.split("·")]
            banner = {"id": p[0].lstrip("#"), "title": p[1], "year": p[2]}
        elif cur and cur.startswith("di") and s:
            m = re.match(r"(ESQUERDA|DIREITA)\s*:\s*(.+)", s, re.I)
            if m:
                lines.append({"text": m.group(2).strip(),
                              "points": "left" if m.group(1).upper() == "ESQUERDA" else "right"})
        elif cur == "final" and s:
            punch = s
    return banner, lines, punch


def main():
    sid = sys.argv[1].upper()
    src = json.loads((STORIES / f"{sid}.short.json").read_text())
    banner, lines, punch = parse((PT / f"{sid}.pt.dialogo.md").read_text())
    short = dict(src["script"]["shortStory"]); short.update(dialogs=lines, punch=punch)
    if "--expr" in sys.argv:
        short["expression"] = sys.argv[sys.argv.index("--expr") + 1]
    script = {"banner": banner, "footer": FOOTER, "scenes": src["script"].get("scenes", []), "shortStory": short}
    left = src.get("shortLeft") or src.get("p1Left"); right = src.get("shortRight") or src.get("p1Right")
    page = SGEN / "zz-render-short-pt.html"
    page.write_text(f"""<!doctype html><html><head><link rel="stylesheet" href="/src/index.css"></head><body><pre id="out"></pre>
<script type="module">
import {{ generateShortComicImageGemini }} from '/src/services/gemini.ts';
const toData = src => new Promise(r => {{ const i = new Image(); i.onload = () => {{ const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight; c.getContext('2d').drawImage(i,0,0); r(c.toDataURL()); }}; i.src = src; }});
try {{
  const tpl = await toData('/images/short-story.png');
  let bub; try {{ bub = await toData('/images/bubbles.png'); }} catch (e) {{ bub = undefined; }}
  const r = await generateShortComicImageGemini({json.dumps(script, ensure_ascii=False)}, tpl, bub, {json.dumps(left)}, {json.dumps(right)});
  document.getElementById('out').textContent = JSON.stringify([r.image]);
}} catch (e) {{ document.getElementById('out').textContent = JSON.stringify(['ERR ' + e]); }}
</script></body></html>""")
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=240000",
                              "--timeout=240000", "--dump-dom", "http://localhost:3000/zz-render-short-pt.html"],
                             capture_output=True, text=True, timeout=300).stdout
    finally:
        page.unlink(missing_ok=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    v = json.loads(html.unescape(m.group(1)))[0] if m and m.group(1) else "EMPTY (is SGen running on :3000?)"
    if not v.startswith("data:"):
        sys.exit(v[:400])
    import base64
    out = PT / f"{sid}.short.pt.png"
    out.write_bytes(base64.b64decode(v.split(",", 1)[1]))
    print(out)


if __name__ == "__main__":
    main()

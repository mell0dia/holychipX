#!/usr/bin/env python3
"""Render a Brazilian-Portuguese episode: content/pt-br/HC###.pt.dialogo.md -> HC###.pt.png

    python3 render_pt.py HC003
    python3 render_pt.py HC005 --expr "PROUD: ..."    # set the panel-3 expression

Reads the dialogue the user edited in Zettlr (## Banner, ## Painel 1-3 with
ESQUERDA:/DIREITA: lines), takes the episode's bots from the story's saved JSON
(p1Left..p2Right) or, for old episodes without them, from content/pt-br/bots/HC###/
(cut out of the published comic), and runs SGen's own generateComicImage in
headless Chrome against the SGen dev server (must be running on :3000).
Only "HOLY CHIP !!" stays in English; the footer credit is localized.
"""
import base64, html, json, re, subprocess, sys
from pathlib import Path

HC = Path.home() / "holy-chip"
PT = HC / "content" / "pt-br"
STORIES = HC / "website" / "holy-chip-site" / "stories"
SGEN = HC / "SGen"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FOOTER = "feito por rmello © mellodia"
WHO = {"ESQUERDA": "Left Bot", "DIREITA": "Right Bot"}


def credit_of(md):
    """Text under '## Crédito' (e.g. IDEIA DE ALDEA) - the idea-by credit, centred in the footer."""
    m = re.search(r"##\s*Cr[ée]dito\s*\n+([^\n#]+)", md, re.I)
    return m.group(1).strip() if m else ""


def stamp_credit(png, text):
    """Centre the credit in the footer strip, like the original strips' IDEA BY line."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(png).convert("RGB"); W, H = im.size
    g = im.convert("L")
    # footer strip = bottom rows below the last panel border (scan up for a dark full-width line)
    y = H - 2
    while y > H - 80 and sum(1 for x in range(0, W, 8) if g.getpixel((x, y)) < 60) < W // 8 * 0.8:
        y -= 1
    top = y + 1
    bg = im.getpixel((W // 2, (top + H) // 2))
    ink = (0, 0, 0) if sum(bg) > 380 else (255, 255, 255)
    f = ImageFont.truetype(str(HC / "content/pt-br/work/ChakraPetch-Bold.ttf"), 20)
    tw = f.getlength(text); bb = f.getbbox(text)
    d = ImageDraw.Draw(im)
    cy = (top + H) / 2
    d.rectangle((W / 2 - tw / 2 - 6, top + 2, W / 2 + tw / 2 + 6, H - 1), fill=bg)
    d.text((W / 2 - tw / 2, cy - (bb[1] + bb[3]) / 2), text, font=f, fill=ink)
    im.save(png)


def parse(md):
    banner, scenes, cur = None, [[], [], []], None
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("---"):
            break                                   # notes below the rule are not dialogue
        m = re.match(r"##\s*Painel\s*(\d)", s, re.I)
        if m:
            cur = int(m.group(1)) - 1; continue
        if s.lower().startswith("## banner"):
            cur = "banner"; continue
        if s.startswith("##"):
            cur = None; continue
        if cur == "banner" and s.startswith("#HC"):
            parts = [p.strip() for p in s.split("·")]
            banner = {"id": parts[0].lstrip("#"), "title": parts[1], "year": parts[2]}
        elif isinstance(cur, int):
            m = re.match(r"(ESQUERDA|DIREITA)\s*:\s*(.+)", s, re.I)
            if m:
                scenes[cur].append({"speaker": WHO[m.group(1).upper()], "text": m.group(2).strip()})
    return banner, scenes


def bots_for(sid):
    j = json.loads((STORIES / f"{sid}.json").read_text())
    keys = ("p1Left", "p1Right", "p2Left", "p2Right")
    if all(j.get(k) for k in keys):
        return {k: j[k] for k in keys}
    d = PT / "bots" / sid
    if not all((d / f"{k}.png").exists() for k in keys):
        sys.exit(f"no bots for {sid}: not in {sid}.json and not in {d}")
    return {k: "data:image/png;base64," + base64.b64encode((d / f"{k}.png").read_bytes()).decode() for k in keys}


def main():
    sid = sys.argv[1].upper()
    banner, scenes = parse((PT / f"{sid}.pt.dialogo.md").read_text())
    script = {"banner": banner, "footer": FOOTER, "scenes": [{"dialogs": d} for d in scenes]}
    if "--expr" in sys.argv:            # fix the panel-3 face, e.g. --expr "PROUD: chin up, smug smile"
        script["panel3Expression"] = sys.argv[sys.argv.index("--expr") + 1]
    if "--sub" in sys.argv:             # words after HOLY CHIP !! at this scale, e.g. --sub 0.5
        script["panel3SubScale"] = float(sys.argv[sys.argv.index("--sub") + 1])
    print(json.dumps(script, ensure_ascii=False, indent=1))
    page = SGEN / "zz-render-pt.html"
    page.write_text(f"""<!doctype html><html><head><link rel="stylesheet" href="/src/index.css"></head><body><pre id="out"></pre>
<script type="module">
import {{ generateComicImage }} from '/src/services/gemini.ts';
const toData = src => new Promise(r => {{ const i = new Image(); i.onload = () => {{ const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight; c.getContext('2d').drawImage(i,0,0); r(c.toDataURL()); }}; i.src = src; }});
const B = {json.dumps(bots_for(sid))};
try {{
  const tpl = await toData('/images/template.png');
  const r = await generateComicImage({json.dumps(script, ensure_ascii=False)}, tpl, undefined, B.p1Left, B.p1Right, B.p2Left, B.p2Right, true);
  document.getElementById('out').textContent = JSON.stringify([r.image]);
}} catch (e) {{ document.getElementById('out').textContent = JSON.stringify(['ERR ' + e]); }}
</script></body></html>""")
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=240000",
                              "--timeout=240000", "--dump-dom", "http://localhost:3000/zz-render-pt.html"],
                             capture_output=True, text=True, timeout=300).stdout
    finally:
        page.unlink(missing_ok=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    v = json.loads(html.unescape(m.group(1)))[0] if m and m.group(1) else "EMPTY (is SGen running on :3000?)"
    if not v.startswith("data:"):
        sys.exit(v[:400])
    out = PT / f"{sid}.pt.png"
    out.write_bytes(base64.b64decode(v.split(",", 1)[1]))
    credit = credit_of((PT / f"{sid}.pt.dialogo.md").read_text())
    if credit:
        stamp_credit(out, credit)
    print(out)


if __name__ == "__main__":
    main()

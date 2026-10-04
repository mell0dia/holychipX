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


def redraw_footer(png, credit=""):
    """Repaint the footer strip under panel 3 and redraw its text. The model's
    panel-3 bot is big and overflows the bottom border; its base used to spill
    into the footer and cut through HOLY-CHIP.COM (HC034)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(png).convert("RGB"); W, H = im.size
    g = im.convert("L")
    y = H - 2
    while y > H - 120 and sum(1 for x in range(0, W, 8) if g.getpixel((x, y)) < 60) < W // 8 * 0.8:
        y -= 1
    top = y + 1                                   # first row under panel 3's bottom border
    bg = im.getpixel((W // 2, min(H - 1, top + 3)))
    if sum(bg) < 380:
        bg = (248, 249, 242)
    d = ImageDraw.Draw(im)
    d.rectangle((0, top, W, H), fill=bg)
    F = str(HC / "content/pt-br/work/ChakraPetch-Bold.ttf")
    f = ImageFont.truetype(F, 20)
    cy = (top + H) / 2
    def put(text, x, anchor):
        bb = f.getbbox(text)
        tx = x if anchor == "l" else (x - f.getlength(text) if anchor == "r" else x - f.getlength(text) / 2)
        d.text((tx, cy - (bb[1] + bb[3]) / 2), text, font=f, fill=(0, 0, 0))
    put("HOLY-CHIP.COM", 6, "l")
    put(FOOTER, W - 6, "r")
    if credit:
        put(credit, W / 2, "c")
    im.save(png)


def paste_p3_bot(png, art, side="right"):
    """Replace the model's panel-3 bot with `art` (an RGBA bot with transparent
    background, e.g. the panel-2 bot with only its face redrawn). Big, top fully
    visible, cut at the panel's bottom border. Used when the model keeps cutting
    the antenna or drifting the face (HC034, HC039)."""
    from PIL import Image, ImageDraw
    im = Image.open(png).convert("RGB"); W, H = im.size; g = im.convert("L")
    full = [y for y in range(H // 2, H) if sum(1 for x in range(0, W, 4) if g.getpixel((x, y)) < 60) > W // 4 * 0.85]
    bands, start = [], None
    for y in range(H // 2, H):
        on = y in full
        if on and start is None: start = y
        if not on and start is not None: bands.append((start, y - 1)); start = None
    if start is not None: bands.append((start, H - 1))
    bands = [b for b in bands if b[1] - b[0] >= 4]         # real borders only (not text rows)
    top, bot = bands[-2][1] + 1, bands[-1][0] - 1          # panel 3 interior
    bg = im.getpixel((W // 2, top + 6))
    d = ImageDraw.Draw(im)
    d.rectangle((0, bands[-2][0], W, bands[-2][1]), fill=(0, 0, 0))   # clean border above
    # Where the punchline bubble (with its tail) ends: walk each row from the
    # bubble side; the bubble ends at the first light gap wider than any gap
    # inside it (letters). Past that edge is the model's bot - erase it.
    GAP = 36
    xs = range(10, W - 10) if side == "right" else range(W - 10, 10, -1)
    edges = []
    for y in range(top + 4, bot - 4, 2):
        last, run, started = None, 0, False
        for x in xs:
            if g.getpixel((x, y)) < 60:
                # a row whose first ink is far from the bubble side is the bot, not the bubble
                if not started and (x > W * 0.25 if side == "right" else x < W * 0.75):
                    break
                started, last, run = True, x, 0
            elif started:
                run += 1
                if run >= GAP:
                    break
        if last is not None:
            edges.append(last)
    if side == "right":
        edge = max(edges) if edges else int(W * 0.66)
        d.rectangle((edge + 6, top, W - 9, bot), fill=bg)
    else:
        edge = min(edges) if edges else int(W * 0.34)
        d.rectangle((9, top, edge - 6, bot), fill=bg)
    a = art if isinstance(art, Image.Image) else Image.open(art).convert("RGBA")
    a = a.crop(a.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox())
    s = min((bot - top) * 1.15 / a.height, (W * 0.30) / a.width)
    a = a.resize((round(a.width * s), round(a.height * s)), Image.LANCZOS)
    x = W - 9 - a.width - 12 if side == "right" else 21
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); layer.paste(a, (x, top + 8), a)
    layer = layer.crop((0, 0, W, bot + 1)); L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); L.paste(layer, (0, 0))
    base = im.convert("RGBA"); base.alpha_composite(L); base.convert("RGB").save(png)


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
    # content/pt-br/bots/HC###/<slot>.png wins over the story JSON, slot by slot -
    # so one bot can be swapped (e.g. HC027's right bot given a smile).
    j = json.loads((STORIES / f"{sid}.json").read_text())
    keys = ("p1Left", "p1Right", "p2Left", "p2Right")
    d = PT / "bots" / sid
    out = {}
    for k in keys:
        f = d / f"{k}.png"
        if f.exists():
            out[k] = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()
        elif j.get(k):
            out[k] = j[k]
        else:
            sys.exit(f"no {k} for {sid}: not in {sid}.json and not in {d}")
    return out


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
    redraw_footer(out, credit)
    print(out)


if __name__ == "__main__":
    main()

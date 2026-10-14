#!/usr/bin/env python3
"""Re-letter panels 1 & 2 of an APPROVED comic without touching the banner or
Gemini's panel 3: SGen's own bubble engine (debugComicBubbles - no model call)
re-composites the bots on the template and lays the bubbles out again, and the
panel 1-2 band (rows 67..954) is spliced into the approved image.

    refit_panels.py HC048 --pt [--dialog other.md] [--fit 0.75] [--out file.png]

--pt reads content/pt-br/HC###.pt.dialogo.md (default: the English
content/HC###.dialog.md). --fit 0.5..1 tightens padding/gaps so wordier text
keeps bigger letters (script.fit in SGen). Bots come from stories/HC###.json
(+ content/pt-br/bots/HC###/ overrides, as render_pt does). SGen on :3000.
"""
import base64, html, json, re, subprocess, sys
from pathlib import Path

HC = Path.home() / "holy-chip"
sys.path.insert(0, str(HC / "tools"))
STORIES = HC / "website" / "holy-chip-site" / "stories"
SGEN = HC / "SGen"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BAND = (67, 954)          # banner bottom .. panel 2/3 border, at 896x1200


def main():
    a = sys.argv[1:]; sid = a[0].upper(); pt = "--pt" in a
    import render_pt, render_story
    if pt:
        dpath = Path(a[a.index("--dialog") + 1]) if "--dialog" in a else HC / "content" / "pt-br" / f"{sid}.pt.dialogo.md"
        banner, scenes = render_pt.parse(dpath.read_text())
        script = {"banner": banner, "footer": render_pt.FOOTER, "scenes": [{"dialogs": d} for d in scenes]}
        approved = HC / "content" / "pt-br" / f"{sid}.pt.png"
    else:
        dpath = Path(a[a.index("--dialog") + 1]) if "--dialog" in a else HC / "content" / f"{sid}.dialog.md"
        script = render_story.parse(dpath.read_text())
        approved = STORIES / f"{sid}.png"
    if "--fit" in a:
        script["fit"] = float(a[a.index("--fit") + 1])
    out = Path(a[a.index("--out") + 1]) if "--out" in a else approved
    bots = render_pt.bots_for(sid)

    page = SGEN / "zz-refit.html"
    page.write_text(f"""<!doctype html><html><head><link rel="stylesheet" href="/src/index.css"></head><body><pre id="out"></pre>
<script type="module">
import {{ debugComicBubbles }} from '/src/services/gemini.ts';
const toData = src => new Promise(r => {{ const i = new Image(); i.onload = () => {{ const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight; c.getContext('2d').drawImage(i,0,0); r(c.toDataURL()); }}; i.src = src; }});
const B = {json.dumps(bots)};
try {{
  const tpl = await toData('/images/template.png');
  const r = await debugComicBubbles({json.dumps(script, ensure_ascii=False)}, tpl, B.p1Left||null, B.p1Right||null, B.p2Left||null, B.p2Right||null);
  document.getElementById('out').textContent = JSON.stringify([r.image, r.summary]);
}} catch (e) {{ document.getElementById('out').textContent = JSON.stringify(['ERR ' + e.stack]); }}
</script></body></html>""")
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=60000", "--timeout=60000",
                              "--dump-dom", "http://localhost:3000/zz-refit.html"], capture_output=True, text=True, timeout=120).stdout
    finally:
        page.unlink(missing_ok=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    v = json.loads(html.unescape(m.group(1))) if m and m.group(1) else ["EMPTY (is SGen running on :3000?)"]
    if not v[0].startswith("data:"):
        sys.exit(v[0][:600])
    import io
    from PIL import Image
    fresh = Image.open(io.BytesIO(base64.b64decode(v[0].split(",", 1)[1]))).convert("RGB")
    im = Image.open(approved).convert("RGB")
    if fresh.size != im.size:
        sys.exit(f"size mismatch {fresh.size} vs {im.size}")
    im.paste(fresh.crop((0, BAND[0], im.width, BAND[1])), (0, BAND[0]))
    im.save(out)
    print(v[1] if len(v) > 1 else ""); print(out)


if __name__ == "__main__":
    main()

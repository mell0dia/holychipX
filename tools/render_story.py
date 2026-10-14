#!/usr/bin/env python3
"""Render a full 3-panel story headlessly from a dialog file + four library bots.

    render_story.py content/HC048.dialog.md \
        --p1 "Chip 1/o005.b045.r054.m001.a093" "Chip 0/o217.b231.r015.m001.a110" \
        --p2 "Chip 1/o005.b095.r242.m001.a093" "Chip 0/o217.b257.r027.m001.a110" \
        [--out stories/HC048.png]

The dialog file is the Zettlr format (## HC048 -- title / *TITLE | Year: 2027 |
ID: HC048* / **Panel N:** / - **Left Bot:** TEXT). Bots are files in
~/holy-chip/characters/, given as "<dir>/<name>" (.png optional); p1 and p2
each take LEFT then RIGHT. Runs SGen's own generateComicImage (panels 1 & 2
composited and lettered by SGen, Gemini draws panel 3) on the dev server (:3000)
and saves HC###.png + HC###.json into the canonical stories dir, the same
shape SGen's Save writes, so the story opens in SGen's picker afterwards.
"""
import base64, html, json, re, subprocess, sys, time
from pathlib import Path

HC = Path.home() / "holy-chip"
STORIES = HC / "website" / "holy-chip-site" / "stories"
CHARS = HC / "characters"
SGEN = HC / "SGen"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def parse(md):
    banner, scenes, pre, panel = None, [], None, None
    for raw in md.splitlines():
        s = raw.strip()
        m = re.match(r"\*(.+?)\s*\|\s*Year:\s*(\d+)\s*\|\s*ID:\s*(HC\d{3})\*", s)
        if m:
            banner = {"title": m.group(1).strip().upper(), "year": m.group(2), "id": m.group(3)}; continue
        m = re.match(r"\*\*Panel (\d):\*\*", s)
        if m:
            panel = int(m.group(1)); scenes.append({"dialogs": []}); continue
        m = re.match(r"-\s*\*\*(Left|Right) Bot:?\*\*:?\s*(.+)", s)
        if m and panel:
            scenes[-1]["dialogs"].append({"speaker": f"{m.group(1)} Bot", "text": re.sub(r"\s+", " ", m.group(2)).strip()}); continue
        m = re.match(r"\*\*Pre image \((Left|Right) Bot\):\*\*\s*(.+)", s)
        if m:
            pre = {"bot": f"{m.group(1)} Bot", "text1": m.group(2).strip(), "text2": ""}
    if not banner or len(scenes) != 3:
        sys.exit(f"could not parse: banner={banner} panels={len(scenes)}")
    script = {"banner": banner, "scenes": scenes}
    if pre:
        script["preComic"] = pre
    return script


def bot(name):
    p = CHARS / (name if name.endswith(".png") else name + ".png")
    if not p.exists():
        sys.exit(f"no such bot: {p}")
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def main():
    a = sys.argv[1:]
    md = Path(a[0]); p1 = a[a.index("--p1") + 1: a.index("--p1") + 3]; p2 = a[a.index("--p2") + 1: a.index("--p2") + 3]
    script = parse(md.read_text())
    sid = script["banner"]["id"]
    out = Path(a[a.index("--out") + 1]) if "--out" in a else STORIES / f"{sid}.png"
    bots = {"p1Left": bot(p1[0]), "p1Right": bot(p1[1]), "p2Left": bot(p2[0]), "p2Right": bot(p2[1])}
    print(json.dumps(script, indent=1))

    page = SGEN / "zz-render-story.html"
    page.write_text(f"""<!doctype html><html><head><link rel="stylesheet" href="/src/index.css"></head><body><pre id="out"></pre>
<script type="module">
import {{ generateComicImage }} from '/src/services/gemini.ts';
const toData = src => new Promise((r, j) => {{ const i = new Image(); i.onload = () => {{ const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight; c.getContext('2d').drawImage(i,0,0); r(c.toDataURL()); }}; i.onerror = j; i.src = src; }});
const B = {json.dumps(bots)};
try {{
  const tpl = await toData('/images/template.png');
  let bub; try {{ bub = await toData('/images/bubbles.png'); }} catch (e) {{ bub = undefined; }}
  const r = await generateComicImage({json.dumps(script, ensure_ascii=False)}, tpl, bub, B.p1Left, B.p1Right, B.p2Left, B.p2Right, true);
  document.getElementById('out').textContent = JSON.stringify([r.image, r.prompt]);
}} catch (e) {{ document.getElementById('out').textContent = JSON.stringify(['ERR ' + (e && e.stack || e)]); }}
</script></body></html>""")
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=300000",
                              "--timeout=300000", "--dump-dom", "http://localhost:3000/zz-render-story.html"],
                             capture_output=True, text=True, timeout=360).stdout
    finally:
        page.unlink(missing_ok=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    v = json.loads(html.unescape(m.group(1))) if m and m.group(1) else ["EMPTY (is SGen running on :3000?)"]
    if not v[0] or not v[0].startswith("data:"):
        sys.exit(str(v[0])[:600])
    out.write_bytes(base64.b64decode(v[0].split(",", 1)[1]))
    if out.parent == STORIES:                      # the canonical save: PNG + the JSON SGen's picker reads
        (STORIES / f"{sid}.json").write_text(json.dumps({"id": 5, "timestamp": int(time.time() * 1000), "script": script,
                                                         "image": v[0], **bots, "prompt": v[1]}, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()

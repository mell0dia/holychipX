"""Re-letter ONE bubble of an approved comic, keeping everything else.

Measures the text already in the bubble (line baselines, ink widths, colour),
erases only the text, and has Chrome draw the new line through SGen's own font
setup ('bold "Chakra Petch"' on the dev server, so the synthetic-bold weight
matches the original lettering exactly). The font size is the one whose OLD
lines reproduce the measured ink widths.

    python3 reletter.py IMG X Y "NEW TEXT" "OLD TEXT"
(X, Y = a point of the bubble's fill, not on a letter). SGen must run on :3000.
"""
import base64, html, io, json, re, subprocess, sys
sys.path.insert(0, '/Users/rmello/holy-chip/content/pt-br/work')
from bubbles import analyse
from pathlib import Path
from PIL import Image, ImageDraw

SGEN = Path.home() / 'holy-chip' / 'SGen'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


def measure(im, x, y):
    dark, R, bb, body = analyse(im, (x, y))
    bx0, by0, bx1, by1 = body
    g = im.convert('L'); px = g.load()
    ink = (lambda v: v > 128) if dark else (lambda v: v < 128)
    m = 8
    rows = set(yy for yy in range(by0 + m, by1 - m) if any(ink(px[xx, yy]) for xx in range(bx0 + m, bx1 - m)))
    bands, s = [], None
    for yy in range(by0 + m, by1 - m + 1):
        on = yy in rows
        if on and s is None: s = yy
        if not on and s is not None: bands.append([s, yy - 1]); s = None
    lines = []                                   # fold accent slivers into their line
    for b in bands:
        if lines and (b[0] - lines[-1][1] <= 3 or lines[-1][1] - lines[-1][0] < 8):
            lines[-1][1] = b[1]
        else:
            lines.append(b)
    ext = []
    for a, b2 in lines:
        xs = [xx for xx in range(bx0 + m, bx1 - m) if any(ink(px[xx, yy]) for yy in range(a, b2 + 1))]
        ext.append((min(xs), max(xs)))
    return dict(dark=dark, body=body, lines=lines, ext=ext)


def chrome(job):
    page = SGEN / 'zz-reletter.html'
    page.write_text(f"""<!doctype html><html><head><link rel="stylesheet" href="/src/index.css"></head><body><pre id="out"></pre>
<script type="module">
const J = {json.dumps(job, ensure_ascii=False)};
await document.fonts.load('bold 40px "Chakra Petch"'); await document.fonts.ready;
const c = document.createElement('canvas'); c.width = J.W; c.height = J.H; const x = c.getContext('2d');
const F = px => `bold ${{px}}px "Chakra Petch"`;
const ink = s => {{ const m = x.measureText(s); return m.actualBoundingBoxRight + m.actualBoundingBoxLeft; }};
// size: the px whose old lines match the measured ink widths
let best = null;
for (let px = 16; px <= 48; px += 0.25) {{
  x.font = F(px);
  const err = J.old.reduce((a, l, i) => a + Math.abs(ink(l) - J.widths[i]), 0);
  if (!best || err < best[0]) best = [err, px];
}}
const px = best[1]; x.font = F(px);
const wrap = (t, maxw) => {{ const L = []; let cur = '';
  for (const w of t.split(' ')) {{ const nx = (cur + ' ' + w).trim(); if (cur && ink(nx) > maxw) {{ L.push(cur); cur = w; }} else cur = nx; }}
  return [...L, cur]; }};
let L = J.forced || wrap(J.text, J.maxw);
if (!J.forced && L.length > J.baselines.length) L = wrap(J.text, J.maxw2);
x.fillStyle = J.color; x.textBaseline = 'alphabetic';
const pitch = J.pitch || px;
let base;
if (L.length === J.baselines.length) base = J.baselines;
else {{ const mid = (J.baselines[0] + J.baselines[J.baselines.length - 1]) / 2;
        base = L.map((_, i) => mid + (i - (L.length - 1) / 2) * pitch); }}
L.forEach((l, i) => {{ const m = x.measureText(l);
  x.fillText(l, J.cx - (m.actualBoundingBoxRight - m.actualBoundingBoxLeft) / 2 + m.actualBoundingBoxLeft, base[i]); }});
document.getElementById('out').textContent = JSON.stringify({{px, err: best[0], lines: L, img: c.toDataURL()}});
</script></body></html>""")
    try:
        dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--virtual-time-budget=20000',
                              '--dump-dom', 'http://localhost:3000/zz-reletter.html'],
                             capture_output=True, text=True, timeout=120).stdout
    finally:
        page.unlink(missing_ok=True)
    return json.loads(html.unescape(re.search(r'<pre id="out">(.*?)</pre>', dom, re.S).group(1)))


def wrap_old(old, n, ext):
    """Split the old text into the n measured lines, by matching word counts to widths."""
    words = old.split()
    best = None
    def splits(ws, k):
        if k == 1: yield [' '.join(ws)]; return
        for i in range(1, len(ws) - k + 2):
            for rest in splits(ws[i:], k - 1): yield [' '.join(ws[:i])] + rest
    widths = [e[1] - e[0] for e in ext]
    for sp in splits(words, n):
        lens = [len(s) for s in sp]
        r = [w / max(1, l) for w, l in zip(widths, lens)]       # px per char should be ~constant
        err = max(r) - min(r)
        if best is None or err < best[0]: best = (err, sp)
    return best[1]


def main():
    path, x, y, new, old = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
    im = Image.open(path).convert('RGB'); W, H = im.size
    M = measure(im, x, y)
    bx0, by0, bx1, by1 = M['body']; lines, ext = M['lines'], M['ext']
    old_lines = old.split('|') if '|' in old else wrap_old(old, len(lines), ext)
    baselines = [b + 1 for a, b in lines]
    pitch = (baselines[-1] - baselines[0]) / (len(baselines) - 1) if len(baselines) > 1 else None
    tx0 = min(e[0] for e in ext); tx1 = max(e[1] for e in ext)
    margin = min(tx0 - bx0, bx1 - tx1)
    job = dict(W=W, H=H, old=old_lines, widths=[e[1] - e[0] for e in ext], text=new.replace('|', ' '),
               maxw=tx1 - tx0 + 4, maxw2=(bx1 - bx0) - 2 * max(12, margin - 6), baselines=baselines, pitch=pitch,
               cx=(bx0 + bx1) / 2, forced=new.split('|') if '|' in new else None, color='#ffffff' if M['dark'] else '#000000')
    r = chrome(job)
    fill = (0, 0, 0) if M['dark'] else im.getpixel((x, y))
    ImageDraw.Draw(im).rectangle((tx0 - 3, lines[0][0] - 3, tx1 + 3, lines[-1][1] + 3), fill=fill)
    layer = Image.open(io.BytesIO(base64.b64decode(r['img'].split(',', 1)[1]))).convert('RGBA')
    base = im.convert('RGBA'); base.alpha_composite(layer); base.convert('RGB').save(path)
    print(f"{path}: old {old_lines} -> {r['lines']}  px={r['px']} err={r['err']:.1f}")


if __name__ == '__main__':
    main()

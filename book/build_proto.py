#!/usr/bin/env python3
"""Coffee-table book prototype: a few stories as real-size spreads.

Cover, dedication, then each story: the full comic, then its origin essay in
one column across the next two pages. Comics are 896x1200 px, far too small for print, so
they are upscaled 4x and traced with potrace - the art is flat black on paper,
so the vector prints sharp at any size and keeps the pixel font's corners.

    python3 build_proto.py HC021 HC031      -> build/proto/book-proto.pdf
"""
import html, re, subprocess, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
STORIES = Path.home() / "holy-chip/website/holy-chip-site/stories"
FONTS = Path.home() / "holy-chip/SGen/public/fonts"
OUT = HERE / "build" / "proto"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Optional section openers before a story: {sid: (part title, line, bot)}.
# Empty: the book runs in story order, HC000 -> HC041 (user, 2026-10-02).
OPENERS = {}
HISTORY = Path.home() / "holy-chip/website/holy-chip-site/history/index.html"

# A black page every five stories (user, 2026-10-02): a bot on its cream tile
# and a line of effect, taken word for word from one of the five stories that
# follow, credited in small type. {before_sid: (bot, line, from_sid)}
INTERLUDES = {
    "HC005": ("Chip_110",   "The machine had the spark. It didn't have the weight.", "HC007"),
    "HC010": ("Chip_101",   "Knowing the water is deep doesn't mean you can swim.", "HC011"),
    "HC015": ("Chip_10001", "Sadness without consequence is just a sigh before the next spreadsheet opens.", "HC015"),
    "HC020": ("Chip_1001",  "Maybe the scary thing is not the AI. Maybe the scary thing is the human behind it.", "HC023"),
    "HC025": ("Chip_10011", "The scariest catastrophe isn't the one that hates you. It's the one that is genuinely trying to help.", "HC027"),
    "HC030": ("Chip_1010",  "The difference between you and the AI is that the people who love you fill the gap in your favor.", "HC031"),
    "HC035": ("Chip_1011",  "You cost a little more to run than anyone will pay you, and you show up tomorrow anyway.", "HC036"),
    "HC040": ("Chip_10100", "Anything that costs nothing to assert costs nothing to forge.", "HC041"),
}
CHARS = Path.home() / "holy-chip/website/holy-chip-site/characters"


def trace(sid, src=None):
    """HC###.png -> HC###.svg (vector). Upscale 4x first so curves come out smooth."""
    svg = OUT / f"{sid}.svg"
    im = Image.open(src or STORIES / f"{sid}.png").convert("RGBA")
    flat = Image.new("RGBA", im.size, "white"); flat.alpha_composite(im)
    im = flat.convert("L")
    big = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
    pbm = OUT / f"{sid}.pbm"
    big.point(lambda v: 0 if v < 140 else 255).convert("1").save(pbm)
    subprocess.run(["potrace", "-s", "--turdsize", "10", "--opttolerance", "0.4",
                    "-o", str(svg), str(pbm)], check=True)
    pbm.unlink()
    return svg.name


def trace_bot(bot, fill="#FFFFFF"):
    """A bot as two stacked SVGs: a white silhouette (so bots in front hide the
    ones behind) and the black line art on top."""
    im = Image.open(CHARS / f"{bot}.png").convert("RGBA")
    a = im.getchannel("A").resize((im.width * 4, im.height * 4), Image.LANCZOS)
    pbm = OUT / f"{bot}.sil.pbm"
    a.point(lambda v: 0 if v > 110 else 255).convert("1").save(pbm)
    sil = OUT / f"{bot}.sil.svg"
    subprocess.run(["potrace", "-s", "--turdsize", "10", "-o", str(sil), str(pbm)], check=True)
    pbm.unlink()
    sil.write_text(sil.read_text().replace('fill="#000000"', f'fill="{fill}"'))
    return sil.name, trace(bot, CHARS / f"{bot}.png")


def art_box(bot):
    """The bot's drawn area inside its square image, as fractions (x0, y0, x1, y1)."""
    im = Image.open(CHARS / f"{bot}.png").convert("RGBA")
    x0, y0, x1, y1 = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
    return x0 / im.width, y0 / im.height, x1 / im.width, y1 / im.height


def carousel(front, ring):
    """The cover's bots: `front` large in the middle, the `ring` around it on
    an ellipse going back - smaller, higher and fainter the further away.

    The front bot is never touched (user, 2026-10-01): any ring bot whose drawn
    area would come within GAP of it is pushed sideways, or - if it sits right
    behind it - up over its head. Ring bots may still overlap each other."""
    import math
    n = len(ring) + 1
    cx, base, GAP = 5.0, 7.2, 0.14        # inches: centre line, front bot's feet, clearance
    placed = []
    for k, bot in enumerate([front] + ring):
        if bot is None:
            continue
        th = 2 * math.pi * k / n
        d = (1 - math.cos(th)) / 2                 # 0 front .. 1 back
        w = 3.4 * (1 - 0.74 * d ** 0.6)
        x = cx + 3.6 * math.sin(th) - w / 2
        top = base - 2.55 * d ** 0.85 - w
        placed.append([k, bot, d, x, top, w, art_box(bot), math.sin(th)])

    def rect(p):
        _, _, _, x, top, w, (a, b, c, e), _ = p
        return x + a * w, top + b * w, x + c * w, top + e * w

    f = rect(placed[0])
    for p in placed[1:]:
        for _ in range(400):
            x0, y0, x1, y1 = rect(p)
            if x1 + GAP <= f[0] or x0 - GAP >= f[2] or y1 + GAP <= f[1] or y0 - GAP >= f[3]:
                break
            if abs(p[7]) > 0.35:            # off to one side: slide outward
                p[3] += 0.02 if p[7] > 0 else -0.02
            else:                           # right behind: rise over the head
                p[4] -= 0.02

    out = []
    for k, bot, d, x, top, w, _, _ in placed:
        # Progressive fade (user): ink thins and the white face sinks into the
        # cover's cream the further round the ring a bot sits.
        fade = d ** 0.55
        ink = 1 - 0.86 * fade
        face = tuple(round(255 + (c - 255) * fade) for c in (0xF6, 0xF3, 0xEA))
        sil, art = trace_bot(bot, "#%02X%02X%02X" % face)
        out.append((d, f'<div class="cbot" style="left:{x:.3f}in;top:{top:.3f}in;width:{w:.3f}in;'
                       f'z-index:{100 - round(d * 90)}"><img src="{sil}"><img src="{art}" '
                       f'style="opacity:{ink:.2f}"></div>'))
    return "".join(h for _, h in sorted(out, key=lambda t: -t[0]))


def smart(t):
    t = re.sub(r'(^|[\s(\[—-])"', r'\1“', t).replace('"', '”')
    t = re.sub(r"(^|[\s(\[—-])'", r"\1‘", t).replace("'", "’")
    return t


def inline(t):
    t = smart(html.escape(t, quote=False))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<i>\1</i>", t)
    return t.replace(" -- ", " — ").replace("--", "—")


def essay(sid):
    """Parse HC###.blog.md -> title, kicker, lede, paragraphs. The footer is
    dropped except an "Idea by ..." credit, which must travel with the story."""
    md = (STORIES / "analysis" / f"{sid}.blog.md").read_text()
    md, _, foot = md.partition("\n---")
    credit = next((l.strip().strip("*") for l in foot.splitlines() if "idea by" in l.lower()), "")
    lines = [l.rstrip() for l in md.splitlines()]
    title = next(l[2:] for l in lines if l.startswith("# "))
    kicker = next((l[3:] for l in lines if l.startswith("## ")), "")
    kicker = re.sub(r"^Holy Chip #(\d+)\s*-+\s*", r"HC\1 · ", kicker)
    paras, lede = [], ""
    for block in re.split(r"\n\s*\n", "\n".join(l for l in lines if not l.startswith("#"))):
        b = " ".join(block.split())
        if not b:
            continue
        if not lede and b.startswith("*") and b.endswith("*"):
            lede = b.strip("*")
            continue
        paras.append(b)
    if credit:
        paras.append("CREDIT:" + credit)
    return title, kicker, lede, paras


def intro_paragraphs():
    """PLACEHOLDER introduction: the website's History page (user: "it will not
    be that one, but just to position")."""
    src = re.sub(r"<(script|style)[\s\S]*?</\1>", "", HISTORY.read_text())
    body = src.split("History</h1>")[-1].split("Original Artwork")[0]
    paras = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", m)).split())
             for m in re.findall(r"<p[^>]*>([\s\S]*?)</p>", body)]
    return [p for p in paras if len(p) > 40]


# DRAFT - for the user to rewrite.
SHORTS_INTRO = [
    "Two frames. One bot talks; the other gets the last word.",
    "No setup, no essay, no time to look away. Some things are better said fast.",
]

COVER_BOT = "Chip_1"
# The ring behind it, in order round the carousel (front-left ... back ... front-right).
# None keeps a seat empty: the two at the very back spaced the ring out too
# much (user, 2026-10-01), but the others keep the angles they had.
COVER_RING = ["Chip_110", "Chip_1010", "Chip_1011", None, None,
              "Chip_10100", "Chip_10011", "Chip_1001"]   # no helmets: the space suit is Chip_1's alone (user)
DEDICATION = "To Zago and Luciano"


def page_html(sids):
    pages = []
    # Cover: the punchline bubble over a bot - the strip's own last panel.
    pages.append(f'<section class="page cover"><div class="bubble">HOLY CHIP !!</div>'
                 f'<div class="ring">{carousel(COVER_BOT, COVER_RING)}</div>'
                 f'<p class="sub">Comics from the age of thinking machines</p>'
                 f'<div class="by"><p class="author">by Ricardo Mello</p>'
                 f'<p class="chars">Characters by Junior Monteiro</p></div></section>')
    pages.append('<section class="page"></section>')
    pages.append(f'<section class="page dedication"><p>{inline(DEDICATION)}</p></section>')
    # The series introduction, facing a featured short story - both PLACEHOLDERS.
    pages.append('<section class="page featured"><div class="slot"><p class="tag">FEATURED SHORT STORY</p>'
                 '<p>[ placeholder — a short story will be chosen ]</p></div></section>')
    intro = "".join(f"<p>{inline(t)}</p>" for t in intro_paragraphs())
    pages.append(f'<section class="page intro"><div class="win"><p class="kicker">HOLY CHIP</p>'
                 f'<h2>Introduction</h2><p class="lede">[ placeholder text — the History page of the website ]</p>'
                 f'{intro}</div></section>')
    for sid in sids:
        if sid in INTERLUDES:
            bot, line, src = INTERLUDES[sid]
            pages.append(f'<section class="page opener interlude"><div><img class="obot" src="{trace(bot, CHARS / f"{bot}.png")}">'
                         f'<p class="quote">{inline(line)}</p><p class="from">{src}</p></div></section>')
        if sid in OPENERS:
            part, line, bot = OPENERS[sid]
            pages.append(f'<section class="page opener"><div><img class="obot" src="{trace(bot, CHARS / f"{bot}.png")}">'
                         f'<p class="part">PART</p><h1>{inline(part)}</h1><p class="tease">{inline(line)}</p></div></section>')
        title, kicker, lede, paras = essay(sid)
        body = "".join(
            f'<p class="credit">{inline(p[7:])}</p>' if p.startswith("CREDIT:") else
            f'<p class="end">{inline(p)}</p>' if p.rstrip(".!") == "Holy Chip" else f"<p>{inline(p)}</p>"
            for p in paras)
        flow = (f'<p class="kicker">{inline(kicker)}</p><h2>{inline(title)}</h2>'
                f'<p class="lede">{inline(lede)}</p>{body}')
        # The comic, then the origin essay in one column across the next two
        # pages. No pre-story teasers (user, 2026-10-01). Three pages a story,
        # so comics fall on alternating sides of the spread.
        pages.append(f'<section class="page comic"><img src="{trace(sid)}"><p class="num">{sid}</p></section>')
        pages.append(f'<section class="page essay" data-story="{sid}"><div class="win">'
                     f'<div class="flow">{flow}</div></div><p class="folio">{sid}</p></section>')
        pages.append(f'<section class="page essay" data-story="{sid}"><div class="win">'
                     f'<div class="flow"></div></div><p class="folio">{sid}</p></section>')
    # SHORTS (user, 2026-10-02): a short introduction, then every short, two to
    # a page, centred, nothing else. Any HC###.short.png on the site is included.
    shorts = sorted(STORIES.glob("HC[0-9][0-9][0-9].short.png"))
    if shorts:
        pages.append(f'<section class="page opener shorts-intro"><div><p class="part">SHORTS</p>'
                     f'<h1>Shorts</h1>{"".join(f"<p class=tease>{inline(t)}</p>" for t in SHORTS_INTRO)}</div></section>')
        imgs = [trace(p.name[:-4], p) for p in shorts]
        for i in range(0, len(imgs), 2):
            pages.append('<section class="page shorts">'
                         + "".join(f'<img src="{im}">' for im in imgs[i:i + 2]) + '</section>')
    # Tag each page with the side it really falls on. The cover is page 1, a
    # right-hand page, so after it even indexes are left pages. Margins and
    # folios mirror on that, not on the page's role.
    return [p.replace('class="page', f'class="page {"l" if i % 2 else "r"}', 1)
            for i, p in enumerate(pages)]


CSS = """
@font-face { font-family: Pixel; src: url('%(fonts)s/PressStart2P-Regular.ttf'); }
@page { size: 10in 10in; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; }
body { font-family: 'Iowan Old Style', Charter, Georgia, serif; color: #141414; }
.page { width: 10in; height: 10in; background: #F6F3EA; page-break-after: always;
        position: relative; overflow: hidden; }
.comic, .pre, .bot, .dedication { display: flex; align-items: center; justify-content: center; }
.comic img { height: 8.7in; display: block; }
.pre img { width: 8.4in; display: block; }
.bot img { width: 6.2in; }
.num, .folio { position: absolute; bottom: .45in; font: 7pt Pixel; letter-spacing: .12em;
               color: #8a877e; margin: 0; }
.num { left: 0; right: 0; text-align: center; }
.l .folio { left: 1.5in; }
.r .folio { right: 1.5in; }
/* mirror margins: wider outside, narrower at the gutter */
.essay .win { position: absolute; top: 1.15in; bottom: 1.2in; overflow: hidden; }
.essay.l .win { left: 1.5in; right: 1.15in; }
.essay.r .win { left: 1.15in; right: 1.5in; }
.essay .flow { height: 100%; column-fill: auto; font-size: var(--fs, 13pt); line-height: 1.55; }
.kicker { font: 7.5pt Pixel; letter-spacing: .1em; text-transform: uppercase; color: #8a877e; margin: 0 0 .3in; }
h2 { font-weight: 700; font-size: 34pt; line-height: 1.05; margin: 0 0 .25in; letter-spacing: -.01em; }
.lede { font-style: italic; color: #4a4843; margin: 0 0 .35in; }
.flow p { margin: 0 0 .75em; hyphens: auto; }
.flow .credit { font-style: italic; color: #6b685f; margin-top: .8em; }
.featured { display: flex; align-items: center; justify-content: center; }
.featured .slot { width: 8.2in; height: 4.6in; border: 2px dashed #b9b4a6; display: flex; flex-direction: column;
                  align-items: center; justify-content: center; color: #8a877e; font-style: italic; font-size: 14pt; }
.featured .tag { font: 8pt Pixel; letter-spacing: .2em; font-style: normal; margin: 0 0 .25in; }
.intro .win { position: absolute; top: 1.15in; bottom: 1.2in; left: 1.15in; right: 1.5in; font-size: 13.5pt; line-height: 1.6; }
.intro.l .win { left: 1.5in; right: 1.15in; }
.intro .win p { margin: 0 0 .8em; }
.flow .end { font: 9pt Pixel; letter-spacing: .08em; margin-top: 1.4em; }
.opener { display: flex; align-items: center; justify-content: center; text-align: center; background: #141414; color: #F6F3EA; }
.opener .obot { width: 3.2in; background: #F6F3EA; padding: .35in; border-radius: .28in; margin-bottom: .55in; display: inline-block; }
.interlude > div { width: 7.2in; }
.shorts-intro > div { width: 6.8in; }
.shorts-intro .tease { margin: 0 0 .15in; line-height: 1.4; }
.shorts { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .5in; }
.shorts img { width: 8.4in; display: block; }
.interlude .quote { font-style: italic; font-size: 24pt; line-height: 1.3; margin: 0 0 .35in; color: #F6F3EA; }
.interlude .from { font: 7.5pt Pixel; letter-spacing: .2em; color: #8a877e; margin: 0; }
.opener .part { font: 8pt Pixel; letter-spacing: .3em; color: #8a877e; margin: 0 0 .3in; }
.opener h1 { font-size: 46pt; margin: 0 0 .25in; font-weight: 700; }
.opener .tease { font-style: italic; font-size: 15pt; margin: 0; color: #cfcbbf; }
.dedication p { font-style: italic; font-size: 20pt; color: #141414; margin: 0 0 1.2in; }
.cover { display: flex; flex-direction: column; align-items: center; padding-top: 1.3in; }
.cover .bubble { position: relative; background: #141414; color: #F6F3EA; font: 36pt Pixel; white-space: nowrap;
                 padding: .4in .55in; border-radius: .2in; letter-spacing: 0; }
.cover .bubble::after { content: ''; position: absolute; left: 50%; bottom: -.42in; margin-left: -.25in;
                        border: .25in solid transparent; border-top: .45in solid #141414; border-bottom: 0; }
.cover .bubble { z-index: 200; }
.cover .ring { position: absolute; inset: 0; }
.cover .cbot { position: absolute; }
.cover .cbot img { position: absolute; left: 0; top: 0; width: 100%; }
.cover .sub { position: absolute; top: 7.55in; font-style: italic; font-size: 17pt; margin: 0; color: #4a4843; z-index: 200; }
.cover .by { position: absolute; bottom: .6in; text-align: center; }
.cover .by p { margin: 0; }
.cover .author { font-size: 15pt; letter-spacing: .02em; }
.cover .chars { font-style: italic; font-size: 11.5pt; color: #6b685f; margin-top: .08in !important; }
"""

# Each essay flows as ONE column across its two pages: the left page shows the
# first column of a multi-column box, the right page a copy of it shifted one
# column over. The type size is the largest that fits in those two columns.
FIT_JS = """
<script>
// Each essay flows as ONE column across its pages: page 1 shows column 1 of a
// multi-column box, the next pages a copy shifted one column at a time. Two
// pages at the largest size that fits (down to 11.5pt); if an essay cannot fit
// two pages at a readable size it gets a third page instead of smaller type.
const FS = 12.5;
document.fonts.ready.then(() => {
  const groups = {};
  for (const p of document.querySelectorAll('.essay')) (groups[p.dataset.story] ||= []).push(p);
  for (const [sid, [L, R]] of Object.entries(groups)) {
    const win = L.querySelector('.win'), f1 = L.querySelector('.flow');
    const W = win.clientWidth, G = 200;
    f1.style.width = W + 'px'; f1.style.columnWidth = W + 'px'; f1.style.columnGap = G + 'px';
    // ONE type size for the whole book (user wants consistency); the essay
    // takes as many pages as it needs at that size: 1, 2 or 3.
    L.style.setProperty('--fs', FS + 'pt');
    const n = Math.max(1, Math.round((f1.scrollWidth + G) / (W + G))), fs = FS;
    const pages = [L, R];
    if (n === 1) { R.remove(); pages.pop(); }
    for (let k = 3; k <= n; k++) { const X = R.cloneNode(true); pages[pages.length - 1].after(X); pages.push(X); }
    pages.slice(1).forEach((P, i) => {
      P.style.setProperty('--fs', fs + 'pt');
      const f = P.querySelector('.flow');
      f.innerHTML = f1.innerHTML;
      Object.assign(f.style, { width: W + 'px', columnWidth: W + 'px', columnGap: G + 'px',
                               transform: `translateX(${-(i + 1) * (W + G)}px)` });
    });
    L.dataset.fit = sid + ' ' + n + 'pages';
  }
  // Real sides and page numbers, now that the page count is final. The cover
  // is page 1, a right-hand page.
  document.querySelectorAll('.page').forEach((P, i) => {
    P.classList.remove('l', 'r'); P.classList.add(i % 2 ? 'l' : 'r');
    const f = P.querySelector('.folio, .num');
    if (f) f.textContent = f.textContent.split(' · ')[0] + ' · ' + (i + 1);
  });
  document.body.dataset.done = '1';
});
</script>
"""


def main():
    args = sys.argv[1:] or ["HC021", "HC031"]
    if args == ["all"]:      # the whole book, in story order
        args = sorted(p.stem for p in STORIES.glob("HC0[0-9][0-9].png"))
        args = [a for a in args if (STORIES / "analysis" / f"{a}.blog.md").exists()]
    sids = args
    OUT.mkdir(parents=True, exist_ok=True)
    pages = page_html(sids)
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS.replace('%(fonts)s', str(FONTS))}</style>"
           f"</head><body>{''.join(pages)}{FIT_JS}</body></html>")
    src = OUT / "book-proto.html"
    src.write_text(doc)
    pdf = OUT / ("book-review.pdf" if len(sids) > 2 else "book-proto.pdf")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=30000", f"--print-to-pdf={pdf}", f"file://{src}"],
                   check=True, capture_output=True)
    print(pdf)


if __name__ == "__main__":
    main()

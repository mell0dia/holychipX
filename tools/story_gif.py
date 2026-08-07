#!/usr/bin/env python3
"""story_gif.py — animated "build-up" GIF of a Holy Chip story.

The comic assembles itself in reading order:

    empty frame -> header -> bubble 1 + the bot who said it
                          -> bubble 2 + the bot who said it
                          -> ... every bubble, in order ...
                          -> footer

HOW IT WORKS
------------
The published HC###.png is a flat raster - the bubbles are not layers. But
HC###.json carries the script, so we know how many bubbles each panel should
have and who speaks each one. That turns "guess the regions" into "detect,
then check against ground truth".

  1. PAGE STRUCTURE. Panels are separated by thick solid-black rules. A rule is
     a run of near-100%-black rows with a white gutter touching it - that test
     rejects the false positives you get when a wide black bubble and both
     bots' bases happen to line up on the same rows. The qualifying rules are
     always [header bottom, divider..., footer top] = len(scenes)+1 of them.
     (Do NOT split panels on white gutters: HC012 panel 2 has a genuine
     full-width white gap inside it, between the bubble block and the bots.)

  2. ELEMENTS. Run-based connected components inside each panel. Big components
     in the middle are bubbles, ordered top-to-bottom = reading order; small
     components fully inside a bubble's box are its text and tail and get
     absorbed; whatever is left is bot art, split by which side it sits on.

  3. THE SCRIPT IS A HINT, NOT A LAW. Sometimes the art and the script disagree
     - HC011 panel 3 draws one bubble for two scripted lines. So bubbles are
     matched to dialogs when the counts agree, and grouped in reading order
     when they don't. --strict turns any mismatch into an error instead.

  4. REVEAL EXACT PIXELS, NEVER BOUNDING BOXES. In the last panel a bot's black
     base spans the full page width and runs behind the bubble, so a box reveal
     would leak the punchline early.

OUTPUTS  (both live in the gh-pages site repo, so they are publicly fetchable)
    anim/HC###.gif            looping GIF, for the website / embeds
    videos/HC###.buildup.mp4  1080x1920 Reel for FB + IG, fed to post_reel.py
                              -> https://holy-chip.com/videos/HC###.buildup.mp4
    stories/                  SOURCES ONLY - never write animation output here.

    NOT READY TO PUBLISH YET: a Reel needs real music. The mp4 currently
    carries a SILENT track, which only satisfies Meta's "must have an audio
    stream" rule - it is a placeholder, not a soundtrack.

USAGE
    story_gif.py HC030                 # -> anim/HC030.gif
    story_gif.py HC030 --reel          # + videos/HC030.buildup.mp4 (the Reel)
    story_gif.py HC030 --mp4           # also an mp4 at the GIF's own size
    story_gif.py HC030 --width 0       # native 896px wide instead of 720
    story_gif.py HC030 --pace 1.1 --beat 2500 --hold 8000   # tune the timing
    story_gif.py --check-all           # verify segmentation on every story
"""
import os, sys, json, argparse, subprocess, tempfile, shutil
from PIL import Image, ImageDraw

HC = os.path.expanduser("~/holy-chip")
STORIES = os.path.join(HC, "stories")
SITE = os.path.join(HC, "website/holy-chip-site")
ANIMDIR = os.path.join(SITE, "anim")      # looping GIF, for the web
VIDEODIR = os.path.join(SITE, "videos")   # Reels, fed to post_reel.py

# Reel canvas. Instagram wants 9:16; the comic is 0.747, so it is fitted to the
# full width and the rest is black. It sits high on the canvas because IG draws
# the caption and action buttons over the bottom of the frame - centring it
# would put the holy-chip.com footer underneath that UI.
REEL_W, REEL_H = 1080, 1920
REEL_TOP = 150
REEL_FPS = 30

BLACK = 128           # luma below this counts as ink
PAGE = 6              # width of the black page frame, measured from the art
SOLID = 0.85          # row ink fraction that counts as a solid rule
GUTTER = 0.05         # row ink fraction that counts as white gutter
MIN_RULE_ROWS = 3

MIN_BUBBLE_W = 70     # a bubble is never smaller than this
MIN_BUBBLE_H = 38
MAX_BUBBLE_WFRAC = 0.92    # ...nor as wide as the panel (that's a bot's base)
BOT_SIDE_FRAC = 0.08       # a bot hugs a side edge within this fraction...
BOT_FLOOR_FRAC = 0.18      # ...stands this close to the panel floor...
BOT_FILL_LO = 0.15         # ...and is line art, not a solid block or a thin
BOT_FILL_HI = 0.50         #    outline (see is_bot for the measured spread)
BOT_MAX_ASPECT = 1.8       # a bot is squarish; a bubble is wide
SIDE_ZONE_FRAC = 0.30      # how far in from a panel edge still counts as bot
                           # territory; past that, leftovers belong to a bubble

COVER_GAP = 46             # black between the .pre teaser and the last panel;
                           # the pair is centred as one block on the card
COVER_MS = 1400            # how long the cover card is held

EMPTY_MS = 550
HEADER_MS = 2450   # the title needs a real beat to read
FOOTER_MS = 2600
READ_BASE_MS = 700    # fixed cost: notice the bubble, see who is speaking
READ_PER_CHAR_MS = 48 # reading pace, ~205 characters/minute
READ_MIN_MS = 900
READ_MAX_MS = 3800    # must stay above BASE + pace * longest line, or long
                      # lines get clipped and the pace stops applying to them
BEAT_MS = 2000        # pause held before the punchline drops

# The last frame is the finished comic, and the two outputs want it held for
# very different lengths. The GIF is read on a web page, so it sits there. A
# Reel is judged on completion and replays, so a long frozen tail is where
# viewers swipe away - keep it short and let it loop round fast.
FOOTER_GIF_MS = 12600     # total hold on the last frame in the GIF
FOOTER_REEL_MS = 2500     # ...and in the Reel


class SegmentError(Exception):
    pass


# ---------------------------------------------------------------- primitives

class Element:
    """One revealable thing: a list of pixel runs plus a label."""

    def __init__(self, kind, runs, label=""):
        self.kind = kind          # frame|header|bubble|footer
        self.runs = runs          # [(y, x0, x1), ...]
        self.label = label
        self.ms = 0
        self.punch = False        # the punchline: last bubble of panel 2
        self.bubble_runs = []     # the bubble alone, without the bot art that
                                  # gets revealed alongside it (the cover card
                                  # needs to crop the bubble on its own)
        self.texts = []           # what is said on this frame, in order
        self.speakers = []        # "Left"/"Right" per text - a bubble can
                                  # carry several scripted lines


class Comp:
    """A connected component."""
    __slots__ = ("runs", "x0", "y0", "x1", "y1", "area")

    def __init__(self, runs):
        self.runs = runs
        self.x0 = min(r[1] for r in runs)
        self.x1 = max(r[2] for r in runs)
        self.y0 = min(r[0] for r in runs)
        self.y1 = max(r[0] for r in runs)
        self.area = sum(r[2] - r[1] + 1 for r in runs)

    @property
    def w(self):
        return self.x1 - self.x0 + 1

    @property
    def h(self):
        return self.y1 - self.y0 + 1

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    def inside(self, o):
        return (self.x0 >= o.x0 and self.x1 <= o.x1
                and self.y0 >= o.y0 and self.y1 <= o.y1)


def make_runs(px, W, H):
    """Row-runs of ink for the whole page."""
    rows = []
    for y in range(H):
        runs, x = [], 0
        while x < W:
            if px[x, y] < BLACK:
                s = x
                while x < W and px[x, y] < BLACK:
                    x += 1
                runs.append((s, x - 1))
            else:
                x += 1
        rows.append(runs)
    return rows


def subtract(spans, cuts):
    """Interval subtraction on one row: spans minus cuts."""
    out = []
    for s, e in spans:
        pieces = [(s, e)]
        for cs, ce in cuts:
            nxt = []
            for ps, pe in pieces:
                if ce < ps or cs > pe:
                    nxt.append((ps, pe))
                    continue
                if ps < cs:
                    nxt.append((ps, cs - 1))
                if pe > ce:
                    nxt.append((ce + 1, pe))
            pieces = nxt
        out.extend(pieces)
    return out


def components(rows, ya, yb, xa, xb):
    """Run-based connected components, 8-connected across rows."""
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    prev, store = [], {}
    nid = 0
    for y in range(ya, yb + 1):
        cur = []
        for (s, e) in rows[y]:
            if e < xa or s > xb:
                continue
            s, e = max(s, xa), min(e, xb)
            nid += 1
            parent[nid] = nid
            store[nid] = (y, s, e)
            for (ps, pe, pid) in prev:
                if ps <= e + 1 and s <= pe + 1:      # +1 => 8-connected
                    union(pid, nid)
            cur.append((s, e, nid))
        prev = cur

    groups = {}
    for nid, run in store.items():
        groups.setdefault(find(nid), []).append(run)
    return [Comp(v) for v in groups.values()]


# ----------------------------------------------------------- page structure

def bars(rows, dens, W, H, relaxed):
    """Runs of rows that cross the whole page in black.

    Strict = every row is one unbroken span from x0 to the far edge. That is
    what a printed rule looks like, and it rejects a wide black bubble, whose
    row only *reaches* both edges by way of the page frame either side of it.
    Relaxed additionally tolerates a nick in the bar (HC005 has one).
    """
    def full(y):
        r = rows[y]
        if not r or r[0][0] != 0 or r[-1][1] != W - 1:
            return False
        return len(r) == 1 or (relaxed and dens[y] >= 0.80)

    out, y = [], 0
    while y < H:
        if full(y):
            s = y
            while y < H and full(y):
                y += 1
            if y - s >= MIN_RULE_ROWS:
                out.append((s, y - 1))
        else:
            y += 1
    return out


def page_structure(rows, W, H, nscenes):
    """Split the page into header / panels / footer using the black rules.

    The header bar contributes TWO bars (above and below its text line), so the
    interior candidates are everything between the header and the footer rule.
    Some stories also have full-width black inside the last panel, so when there
    are too many candidates they are filtered on thickness and on having a white
    gutter nearby - a real divider always has panel margin next to it.
    """
    dens = [sum(b - a + 1 for a, b in r) / W for r in rows]

    def near_gutter(r, k=25):
        return (any(dens[y] <= GUTTER for y in range(max(0, r[0] - k), r[0]))
                or any(dens[y] <= GUTTER
                       for y in range(r[1] + 1, min(H, r[1] + 1 + k))))

    chosen = None
    for relaxed in (False, True):
        bs = bars(rows, dens, W, H, relaxed)
        if len(bs) < 2:
            continue
        head = [b for b in bs if b[0] < 120]
        if not head:
            continue
        hb, ft = head[-1][1], bs[-1][0]
        interior = [b for b in bs if b[0] > hb and b[1] < ft]
        good = [b for b in interior
                if near_gutter(b) and MIN_RULE_ROWS <= b[1] - b[0] + 1 <= 11]
        for pick in (interior, good):
            if len(pick) == nscenes - 1:
                chosen = (hb, ft, pick)
                break
        if chosen:
            break

    if not chosen:
        raise SegmentError(
            f"could not find {nscenes - 1} panel dividers on the page")

    hb, ft, div = chosen
    edges = [hb] + [d[1] for d in div]
    stops = [d[0] for d in div] + [ft]
    panels = [(edges[i] + 1, stops[i] - 1) for i in range(nscenes)]
    return (0, hb), panels, (bs[-1][1] + 1, H - 1)


# --------------------------------------------------------------- segmenting

def split_panel(rows, W, ya, yb, ndialogs, warn=None):
    """Return (bubble_runs[], left_runs, right_runs) for one panel."""
    comps = components(rows, ya, yb, PAGE, W - PAGE - 1)
    pw = W - 2 * PAGE
    ph = yb - ya + 1
    px0, px1 = PAGE, W - PAGE - 1

    def is_bot(c):
        """Is this component a bot rather than a speech bubble?

        Three signals, measured across every panel of every story:

        1. SIDE. A bot hugs one side of the panel. Required.
        2. FILL. A bot is line art - ink fills 0.15-0.50 of its box. Bubbles
           are either solid blocks (>0.55) or thin outlines (<0.15), so this
           is what keeps the big solid panel-3 punchline bubble out.
        3. SHAPE. A bot is roughly square: 171 of 180 measured bots fall in
           aspect 0.5-1.5, while bubbles cluster at 3.0-4.0. Bubbles are wide.

        Shape matters because the floor test alone is fragile - HC036's bots sit
        81px above the panel floor against a 79.6px threshold, so BOTH of them
        failed by 1.4 pixels, outranked the real bubbles on box area, and got
        animated as bubbles while two genuine bubbles were dropped. Floor is
        kept as an alternative to shape for the occasional wide bot base.
        """
        if min(c.x0 - px0, px1 - c.x1) > BOT_SIDE_FRAC * pw:
            return False
        fill = c.area / float(c.w * c.h)
        if not (BOT_FILL_LO <= fill <= BOT_FILL_HI):
            return False
        squarish = (c.w / float(c.h)) < BOT_MAX_ASPECT
        on_floor = (yb - c.y1) <= BOT_FLOOR_FRAC * ph
        return squarish or on_floor

    cand = [c for c in comps
            if c.w >= MIN_BUBBLE_W and c.h >= MIN_BUBBLE_H
            and c.w <= MAX_BUBBLE_WFRAC * pw
            and c.x0 > PAGE + 3 and c.x1 < W - PAGE - 4
            and not is_bot(c)]

    # of what is left, the speech bubbles are the big boxes - a filled block or
    # an outlined ring, either way dwarfing a glyph.
    cand.sort(key=lambda c: -(c.w * c.h))
    bubbles = cand[:ndialogs] if len(cand) > ndialogs else cand
    if not bubbles:
        raise SegmentError(f"panel y{ya}-{yb}: no bubbles found")
    for c in bubbles:
        if (min(c.x0 - px0, px1 - c.x1) <= BOT_SIDE_FRAC * pw
                and BOT_FILL_LO <= c.area / float(c.w * c.h) <= BOT_FILL_HI
                and (c.w / float(c.h)) < BOT_MAX_ASPECT and warn):
            warn(f"  ! panel y{ya}-{yb}: a chosen bubble looks like bot art "
                 f"(x{c.x0}-{c.x1} y{c.y0}-{c.y1}, aspect "
                 f"{c.w / float(c.h):.2f}) - check the bot thresholds")
    bubbles.sort(key=lambda c: c.y0)

    bub = [list(b.runs) for b in bubbles]
    leftovers = []
    for c in comps:
        if c in bubbles:
            continue
        for j, b in enumerate(bubbles):
            if c.inside(b):
                bub[j].extend(c.runs)
                break
        else:
            leftovers.append(c)

    # Bot art hugs its side of the panel. A leftover floating in the middle is
    # almost always a bubble's tail or trim, and handing it to a bot on nothing
    # more than "its centre is past the midline" makes it appear early - as a
    # few stray pixels on screen before the bubble it belongs to.
    mid = PAGE + pw / 2
    side_zone = SIDE_ZONE_FRAC * pw
    left, right = [], []
    for c in leftovers:
        if min(c.x0 - px0, px1 - c.x1) <= side_zone:
            (left if c.cx < mid else right).extend(c.runs)
            continue
        # nearest bubble by box distance, so tails travel with their bubble
        best, bd = None, None
        for j, b in enumerate(bubbles):
            dx = max(b.x0 - c.x1, c.x0 - b.x1, 0)
            dy = max(b.y0 - c.y1, c.y0 - b.y1, 0)
            d = dx * dx + dy * dy
            if bd is None or d < bd:
                best, bd = j, d
        if best is not None:
            bub[best].extend(c.runs)
        else:
            (left if c.cx < mid else right).extend(c.runs)

    # a side holding only specks is not a bot - fold it into the other side
    la = sum(e - s + 1 for _, s, e in left)
    ra = sum(e - s + 1 for _, s, e in right)
    if la and la < 0.08 * (la + ra):
        right, left = right + left, []
    elif ra and ra < 0.08 * (la + ra):
        left, right = left + right, []
    return bub, left, right


def pair_dialogs(bubbles, dialogs):
    """Map bubbles -> list of dialogs, in reading order, even when counts differ."""
    nb, nd = len(bubbles), len(dialogs)
    if nb == nd:
        return [[d] for d in dialogs]
    groups = [[] for _ in range(nb)]
    for i, d in enumerate(dialogs):          # spread lines over the bubbles drawn
        groups[min(nb - 1, i * nb // max(1, nd))].append(d)
    for g in groups:
        if not g:
            g.append({"speaker": "", "text": ""})
    return groups


def segment(im, script, strict=False, warn=print, pace=1.0, groups=None):
    W, H = im.size
    rows = make_runs(im.convert("L").load(), W, H)
    scenes = script["scenes"]
    hdr, panel_spans, ftr = page_structure(rows, W, H, len(scenes))

    def band(a, b):
        return [(y, s, e) for y in range(a, b + 1) for (s, e) in rows[y]]

    header = Element("header", band(*hdr), "header")
    footer = Element("footer", band(*ftr), "footer")

    seq = [None, header]                     # slot 0 filled in at the end
    assigned = {}                            # y -> [(x0,x1), ...]

    def claim(runs):
        for (y, s, e) in runs:
            assigned.setdefault(y, []).append((s, e))

    claim(header.runs)
    claim(footer.runs)

    for i, (a, b) in enumerate(panel_spans):
        dialogs = scenes[i]["dialogs"]
        bub, left, right = split_panel(rows, W, a, b, len(dialogs), warn)

        # If a bot speaks in this panel it must have art. Empty art means its
        # component was misread as a bubble - which is exactly how HC036 lost
        # both bots. The bubble COUNT alone cannot catch that, so check it here.
        panel_px = (b - a + 1) * (W - 2 * PAGE)
        for side, runs in (("Left", left), ("Right", right)):
            speaks = any(side in d.get("speaker", "") for d in dialogs)
            ink = sum(e - s2 + 1 for _, s2, e in runs)
            if speaks and ink < 0.004 * panel_px:
                warn(f"  ! panel {i + 1}: script has {side} bot speaking but no "
                     f"{side.lower()} bot is drawn here - art and script disagree")

        if len(bub) != len(dialogs):
            msg = (f"panel {i + 1}: {len(bub)} bubbles drawn but script has "
                   f"{len(dialogs)} lines - grouping them")
            if strict:
                raise SegmentError(msg)
            warn("  ! " + msg)

        # A per-story override can say which scripted lines share a bubble.
        # Needed when the art fuses a bubble to a bot: the bubble cannot be
        # revealed on its own, so its line has to be spoken with whatever else
        # that bot brings on screen. See voice/HC###.timing.json -> "groups".
        ov = (groups or {}).get(str(i + 1))
        if ov and len(ov) == len(bub):
            dgroups = [[dialogs[k] for k in idxs if k < len(dialogs)] for idxs in ov]
            warn(f"  · panel {i + 1}: using the grouping override "
                 f"{ov} from the timing file")
        else:
            if ov:
                warn(f"  ! panel {i + 1}: grouping override has {len(ov)} groups "
                     f"but {len(bub)} bubbles were found - ignoring it")
            dgroups = pair_dialogs(bub, dialogs)
        groups_local = dgroups
        sides = {"Left": left, "Right": right}
        shown = set()
        panel_start = len(seq)

        for j, (runs, group) in enumerate(zip(bub, groups_local)):
            runs = list(runs)
            texts, who = [], []
            for d in group:
                texts.append(d.get("text", ""))
                side = "Left" if "Left" in d.get("speaker", "") else "Right"
                if side not in shown and sides.get(side):
                    runs += sides[side]
                    shown.add(side)
                    who.append(side)
            label = " / ".join(t.replace("\n", " ").strip()[:44] for t in texts if t)
            if who:
                label += "  (+%s bot)" % "+".join(who)
            el = Element("bubble", runs, label or f"bubble {j + 1}")
            el.bubble_runs = list(bub[j])
            el.ms = read_ms(" ".join(texts), pace)
            # kept for the voice tools: what is said here, and by whom
            el.texts = [d.get("text", "") for d in group]
            el.speakers = ["Left" if "Left" in d.get("speaker", "") else "Right"
                           for d in group]
            seq.append(el)

        # a bot that never speaks in this panel still has to appear - bring it
        # in on the panel's last frame so the panel is never left half drawn
        silent = [r for s, r in sides.items() if r and s not in shown]
        if silent and len(seq) > panel_start:
            for r in silent:
                seq[-1].runs += r
            seq[-1].label += "  (+silent bot)"

        # The joke lands on the last bubble of the second-to-last panel; the
        # final panel is the reaction to it. Mark it so a beat can be held
        # before it drops.
        if i == len(panel_spans) - 2 and len(seq) > panel_start:
            seq[-1].punch = True

        for el in seq[panel_start:]:
            claim(el.runs)

    # the empty page = ink that belongs to nothing else: page frame + rules
    frame_runs = []
    for y in range(H):
        rest = subtract(rows[y], assigned.get(y, []))
        frame_runs.extend((y, s, e) for s, e in rest)
    seq[0] = Element("frame", frame_runs, "empty frame")
    seq[0].ms = EMPTY_MS
    header.ms = HEADER_MS
    footer.ms = FOOTER_MS
    seq.append(footer)
    return seq


# ---------------------------------------------------------------- rendering

def read_ms(text, pace=1.0):
    n = len(" ".join(text.split()))
    ms = READ_BASE_MS + n * READ_PER_CHAR_MS * pace
    return int(max(READ_MIN_MS, min(READ_MAX_MS * pace, ms)))


def apply_beat(seq, beat):
    """Hold the frame before the punchline, so the joke drops into a pause."""
    if beat <= 0:
        return
    for i, el in enumerate(seq):
        if el.punch and i > 0:
            seq[i - 1].ms += beat
            seq[i - 1].label += f"  [+{beat}ms beat]"
            return


def load_timing(story):
    """Per-story timing nudges from voice/HC###.timing.json, if present."""
    p = os.path.join(HC, "voice", story + ".timing.json")
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return {}


def apply_nudges(seq, nudges):
    """Add extra hold to named frames.

    Keys are 'frame', 'header', 'footer', or 'b1'..'bN' counting bubbles in
    reading order. Values are milliseconds to ADD. Lets a single long line get
    room to be spoken without slowing the whole story down.
    """
    if not nudges:
        return
    b = 0
    for el in seq:
        if el.kind == "bubble":
            b += 1
            key = "b%d" % b
        else:
            key = el.kind
        extra = int(nudges.get(key, 0))
        if extra:
            el.ms += extra
            el.label += "  [+%dms]" % extra


def apply_end_hold(seq, hold):
    """Set the last frame's total hold (used by the voice studio)."""
    for el in seq:
        if el.kind == "footer":
            el.ms = hold
            return


def durations(seq, footer_hold):
    """Per-frame ms with the last frame held for `footer_hold` total.

    Returned as a list rather than mutated onto the elements, because one run
    renders two outputs with different endings off the same frames.
    """
    return [footer_hold if el.kind == "footer" else el.ms for el in seq]


def build_frames(im, seq, width):
    W, H = im.size
    mask = Image.new("1", (W, H), 0)
    draw = ImageDraw.Draw(mask)
    white = Image.new("RGB", (W, H), (255, 255, 255))

    frames = []
    for el in seq:
        for (y, x0, x1) in el.runs:
            draw.line([(x0, y), (x1, y)], fill=1)
        f = Image.composite(im, white, mask)
        if width and width != W:
            f = f.resize((width, round(H * width / W)), Image.LANCZOS)
        frames.append(f.convert("L"))
    return frames


def save_gif(frames, durs, out, colors=16):
    """Write the GIF on one explicit grayscale palette shared by every frame.

    Do NOT use quantize(palette=...) here - it remaps indices and silently
    inverts the artwork (white page, black ink -> black page, white ink).
    The comic is grayscale anyway, so an evenly spaced ramp is exact and keeps
    the palette identical frame to frame, which is what makes the GIF small.
    """
    n = max(2, min(256, colors))
    pal = []
    for i in range(n):
        v = round(i * 255 / (n - 1))
        pal += [v, v, v]
    pal += [0, 0, 0] * (256 - n)

    q = []
    for f in frames:
        idx = f.point(lambda v, n=n: min(n - 1, v * n // 256))
        p = Image.frombytes("P", f.size, idx.tobytes())
        p.putpalette(pal)
        q.append(p)

    q[0].save(out, save_all=True, append_images=q[1:], duration=durs,
              loop=0, optimize=True, disposal=1)


def build_cover(im, seq, story=None, nscenes=3, size=None):
    """Title card for the first frame - which is what FB and IG use as the cover.

    Two real assets, nothing drawn fresh: the .pre teaser at the top (its header
    carries the #HC number, the place and the year, and it holds the big chip
    face), and the WHOLE of the last panel flush along the bottom, bringing its
    own white background, the reacting bot and the HOLY CHIP bubble. Setup on
    top, payoff at the foot, black between them doing the separating.

    `size` builds the card at that exact canvas - pass the Reel's 1080x1920 so
    it fills the frame edge to edge instead of being letterboxed like the comic
    pages. Omit it for the GIF, which wants the page's own geometry.

    Without a cover the Reel opens on the blank page, and that is what Meta
    grabs for the thumbnail.
    """
    W, H = im.size
    CW, CH = size or (W, H)
    page = Image.new("RGB", (CW, CH), (0, 0, 0))

    pre = None
    if story:
        pp = os.path.join(STORIES, story + ".pre.png")
        if os.path.exists(pp):
            try:
                pre = Image.open(pp).convert("RGB")
            except Exception:
                pre = None

    # the last panel, full width, exactly as it sits on the page
    panel = None
    try:
        rows = make_runs(im.convert("L").load(), W, H)
        _, panels, _ = page_structure(rows, W, H, nscenes)
        y0, y1 = panels[-1]
        panel = im.crop((0, y0, W, y1 + 1))
    except Exception:
        bub = [e for e in seq if e.kind == "bubble"]
        if bub:
            b = bub[-1]
            y0 = min(r[0] for r in b.runs)
            y1 = max(r[0] for r in b.runs)
            panel = im.crop((0, max(0, y0 - 12), W, min(H, y1 + 13)))

    # Both bands sit as one centred block. Pinning the panel to the bottom edge
    # left a wide dead gap through the middle of the frame, which read as two
    # unrelated pictures rather than one card.
    bands = []
    if pre is not None:
        bands.append(pre.resize((CW, round(pre.height * CW / pre.width)),
                                Image.LANCZOS))
    if panel is not None:
        bands.append(panel.resize((CW, round(panel.height * CW / panel.width)),
                                  Image.LANCZOS))

    total = sum(b.height for b in bands) + COVER_GAP * max(0, len(bands) - 1)
    y = max(0, (CH - total) // 2)
    for b in bands:
        page.paste(b, (0, y))
        y += b.height + COVER_GAP

    return page


def reel_canvas(f):
    """Fit a frame onto the 1080x1920 Reel canvas."""
    h = round(f.height * REEL_W / f.width)
    c = Image.new("RGB", (REEL_W, REEL_H), (0, 0, 0))
    c.paste(f.convert("RGB").resize((REEL_W, h), Image.LANCZOS), (0, REEL_TOP))
    return c


def save_mp4(frames, durs, out, reel=False, fps=REEL_FPS):
    """Encode the frames as h264.

    Each distinct frame is written once and then SYMLINKED as many times as it
    needs to be held, so ffmpeg's image2 demuxer sees an exact constant-rate
    sequence. Do not switch this to the concat demuxer with `duration`
    directives - measured, it drops the last entry's duration and overshoots
    the total by ~2s.

    A SILENT AUDIO TRACK IS NOT OPTIONAL - Instagram rejects a Reel with no
    audio stream, which is why story_video.py adds one too.
    """
    tmp = tempfile.mkdtemp(prefix="hcgif")
    try:
        n = 0
        for i, (f, ms) in enumerate(zip(frames, durs)):
            if reel:
                # the cover card is already built at the reel canvas; fitting it
                # again would letterbox it a second time
                f = f if f.size == (REEL_W, REEL_H) else reel_canvas(f)
            else:
                w, h = f.size
                f = f.convert("RGB").crop((0, 0, w - w % 2, h - h % 2))
            src = os.path.join(tmp, f"src{i:03d}.png")
            f.save(src)
            for _ in range(max(1, round(fps * ms / 1000.0))):
                os.symlink(src, os.path.join(tmp, f"f{n:06d}.png"))
                n += 1

        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-framerate", str(fps), "-i", os.path.join(tmp, "f%06d.png"),
             "-f", "lavfi", "-i",
             "anullsrc=channel_layout=stereo:sample_rate=44100",
             "-c:v", "libx264", "-profile:v", "high", "-level", "4.0",
             "-pix_fmt", "yuv420p", "-r", str(fps),
             "-c:a", "aac", "-b:a", "128k", "-shortest",
             "-movflags", "+faststart", out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------- main

def load(hc):
    im = Image.open(os.path.join(STORIES, hc + ".png")).convert("RGB")
    with open(os.path.join(STORIES, hc + ".json")) as fh:
        return im, json.load(fh)["script"]


def story_ids():
    return sorted(f[:-5] for f in os.listdir(STORIES)
                  if f.endswith(".json") and f.startswith("HC")
                  and ".pre" not in f
                  and os.path.exists(os.path.join(STORIES, f[:-5] + ".png")))


def check_all(strict=False):
    ok = warned = bad = 0
    for hc in story_ids():
        notes = []
        try:
            im, script = load(hc)
            seq = segment(im, script, strict=strict, warn=notes.append)
            nb = sum(1 for e in seq if e.kind == "bubble")
            nd = sum(len(s["dialogs"]) for s in script["scenes"])
            tag = "OK  " if not notes else "WARN"
            print(f"  {tag} {hc}  {len(seq):2d} frames, {nb} bubbles / {nd} lines")
            for n in notes:
                print(n)
            ok += 1
            warned += 1 if notes else 0
        except Exception as e:
            print(f"  FAIL {hc}  {e}")
            bad += 1
    print(f"\n{ok} usable ({warned} with warnings), {bad} failed, "
          f"{ok + bad} total")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", nargs="?", help="e.g. HC030")
    ap.add_argument("--out")
    ap.add_argument("--width", type=int, default=720, help="0 = native")
    ap.add_argument("--colors", type=int, default=16)
    ap.add_argument("--mp4", action="store_true",
                    help="also write an mp4 at the GIF's size")
    ap.add_argument("--no-cover", action="store_true",
                    help="skip the title card and open on the blank page")
    ap.add_argument("--reel", action="store_true",
                    help="write a 1080x1920 Reel mp4 for FB/IG into videos/")
    ap.add_argument("--nudge", action="append", default=[], metavar="KEY=MS",
                    help="add hold to one frame, e.g. --nudge b3=1000 "
                         "--nudge header=500 (also read from "
                         "voice/HC###.timing.json)")
    ap.add_argument("--hold", type=int, default=FOOTER_GIF_MS,
                    help="total ms held on the last frame in the GIF")
    ap.add_argument("--reel-hold", type=int, default=FOOTER_REEL_MS,
                    help="total ms held on the last frame in the Reel")
    ap.add_argument("--pace", type=float, default=1.0,
                    help="multiply the per-character reading time")
    ap.add_argument("--beat", type=int, default=BEAT_MS,
                    help="ms held before the punchline drops (0 = off)")
    ap.add_argument("--strict", action="store_true",
                    help="fail instead of grouping when art and script disagree")
    ap.add_argument("--check-all", action="store_true")
    a = ap.parse_args()

    if a.check_all:
        sys.exit(check_all(a.strict))
    if not a.story:
        ap.error("give a story id, e.g. HC030")

    hc = a.story.upper()
    im, script = load(hc)
    nudges = load_timing(hc)
    seq = segment(im, script, strict=a.strict, pace=a.pace,
                  groups=nudges.get("groups"))
    for spec in a.nudge:
        k, _, v = spec.partition("=")
        nudges[k.strip()] = int(v)
    apply_nudges(seq, nudges)
    apply_beat(seq, a.beat)
    durs = durations(seq, a.hold)                 # GIF ending
    reel_durs = durations(seq, a.reel_hold)       # Reel ending

    print(f"{hc}: {len(seq)} frames   gif {sum(durs) / 1000:.1f}s   "
          f"reel {sum(reel_durs) / 1000:.1f}s")
    for el, dg, dr in zip(seq, durs, reel_durs):
        mark = "  <- PUNCHLINE" if el.punch else ""
        if dg != dr:
            print(f"  {dg:5d}ms  {el.kind:7s} {el.label}"
                  f"   [reel: {dr}ms]{mark}")
        else:
            print(f"  {dg:5d}ms  {el.kind:7s} {el.label}{mark}")

    frames = build_frames(im, seq, a.width or im.size[0])

    if not a.no_cover:
        # frame 0 is what Meta uses as the thumbnail, so it must not be blank
        gif_cover = build_cover(im, seq, hc, len(script["scenes"]))
        gif_cover = gif_cover.resize(frames[0].size, Image.LANCZOS).convert("L")
        reel_cover = build_cover(im, seq, hc, len(script["scenes"]),
                                 size=(REEL_W, REEL_H)).convert("L")
        frames = [gif_cover] + frames
        reel_frames = [reel_cover] + frames[1:]
        durs = [COVER_MS] + durs
        reel_durs = [COVER_MS] + reel_durs
        os.makedirs(ANIMDIR, exist_ok=True)
        cov = os.path.join(ANIMDIR, hc + ".cover.jpg")
        build_cover(im, seq, hc, len(script["scenes"]),
                    size=(REEL_W, REEL_H)).save(cov, quality=92)
        print(f"  cover -> {cov}")
    else:
        reel_frames = frames
    os.makedirs(ANIMDIR, exist_ok=True)
    out = a.out or os.path.join(ANIMDIR, hc + ".gif")
    save_gif(frames, durs, out, a.colors)
    print(f"\n-> {out}  ({os.path.getsize(out) / 1024:.0f} KB, "
          f"{frames[0].size[0]}x{frames[0].size[1]})")

    if a.mp4:
        mp4 = out.rsplit(".", 1)[0] + ".mp4"
        save_mp4(frames, durs, mp4)
        print(f"-> {mp4}  ({os.path.getsize(mp4) / 1024:.0f} KB)")

    if a.reel:
        os.makedirs(VIDEODIR, exist_ok=True)
        reel = os.path.join(VIDEODIR, hc + ".buildup.mp4")
        save_mp4(reel_frames, reel_durs, reel, reel=True)
        print(f"-> {reel}  ({os.path.getsize(reel) / 1024:.0f} KB, "
              f"{REEL_W}x{REEL_H} @{REEL_FPS}fps + silent audio)")
        print(f"   public: https://holy-chip.com/videos/{hc}.buildup.mp4")


if __name__ == "__main__":
    main()

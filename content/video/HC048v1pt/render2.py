"""Holy Chip 1-minute documentary (v2): deep narrator ABOUT the joke + origin
excerpts; a story bot in front, AI-painted backgrounds changing with the narrative.
Free stack: Kokoro voice, local SDXL backgrounds, synthesized score, PIL -> ffmpeg.

    ~/holy-chip/venv/video/bin/python render2.py   -> HC023_doc.mp4
"""
import json, math, random, subprocess
import numpy as np, soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 48000
HC = '/Users/rmello/holy-chip'
F_CHAKRA = HC + '/content/pt-br/work/ChakraPetch-Bold.ttf'
F_PIXEL = HC + '/SGen/public/fonts/PressStart2P-Regular.ttf'
GOLD = (232, 186, 64)
fnt = lambda p, s: ImageFont.truetype(p, s)
ease = lambda x: 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, x)))
random.seed(23)

beats = json.load(open('beats.json'))
lines = json.load(open('audio/lines.json'))
comic = Image.open(HC + '/website/holy-chip-site/stories/HC023.png').convert('RGB')
PANELS = [comic.crop((0, 0, 896, 510)), comic.crop((0, 510, 896, 907)), comic.crop((0, 900, 896, 1200))]


def cutout(im):
    from collections import deque
    im = im.convert('RGBA'); px = im.load(); w, h = im.size
    q = deque([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]); seen = set(q)
    while q:
        x, y = q.popleft(); r, g, b, a = px[x, y]
        if a < 20 or (r > 200 and g > 200 and b > 190):
            px[x, y] = (0, 0, 0, 0)
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= n[0] < w and 0 <= n[1] < h and n not in seen:
                    seen.add(n); q.append(n)
    im.putalpha(im.getchannel('A').point(lambda v: 255 if v > 128 else 0))
    return im.crop(im.getbbox())


def with_glow(bot, target_w):
    """Bot scaled to target width, with a soft white rim and a dark drop shadow."""
    s = target_w / bot.width; b = bot.resize((target_w, int(bot.height * s)), Image.LANCZOS)
    pad = 60; c = Image.new('RGBA', (b.width + 2 * pad, b.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new('L', c.size, 0); a.paste(b.getchannel('A'), (pad, pad))
    sh = a.filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.75))
    c.paste(Image.new('RGBA', c.size, (0, 0, 0, 255)), (14, 22), sh)
    rim = a.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.9))
    c.alpha_composite(Image.merge('RGBA', [Image.new('L', c.size, 255)] * 3 + [rim]))
    c.alpha_composite(b, (pad, pad))
    return c


SRC = {k: Image.open(f'assets/{k}.png') for k in ('p1Left', 'p2Left', 'p3')}   # the episode's own chip (assets/ in the workspace)
BOT = {k: with_glow(cutout(v), 700) for k, v in SRC.items()}

def cover(im):
    s = max(W / im.width, H / im.height) * 1.12
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
# the sketch sits SMALL in the CENTRE, between the words (top) and the chip (bottom) - user, 2026-10-09
PAPER = (246, 243, 234)
BOX = 940; BOX_CY = 1010                      # bigger scene image now that the chip is a small corner signature
CHIP_SCALE = 0.36                              # chip = small side image (user, 2026-10-13)
_imgs = {b.get('img', b['id']) for b in beats} | {sh['img'] for b in beats for sh in b.get('shots', [])}
BG = {k: Image.open(f"bg/{k}.png").convert('RGB').resize((BOX + 50, BOX + 50), Image.LANCZOS) for k in _imgs}
SHADE = Image.new('RGBA', (W, H)); sd = ImageDraw.Draw(SHADE)
for y in range(H):        # dark at top (captions) and bottom (bot), clear in the middle
    v = max(0, 1 - y / 520) * 0.85 + max(0, (y - 1300) / 620) * 0.35
    sd.line([(0, y), (W, y)], fill=(250, 248, 242, int(255 * min(0.92, v))))

# ---------------------------------------------------------------- timeline
SCENE_GAP = 1.0                                     # silence between scenes (user, 2026-10-14)
t = 0.6; seq = []   # (start, end, beat_index, line)
for bi, b in enumerate(beats):
    if bi: t += SCENE_GAP
    for k, _ in enumerate(b['say']):
        l = next(x for x in lines if x['beat'] == b['id'] and x['k'] == k)
        if b.get('punch') and k == len(b['say']) - 1: t += 0.55          # beat before "Holy chip."
        t += l.get('pre', 0)                                                # (pause) tag
        seq.append((t, t + l['dur'], bi, l)); t += l["dur"] + 0.05           # one-shot narration: the pauses are already in the clips

outro_l = next(x for x in lines if x['beat'] == 'outro')
LAST_HOLD, FADE = 3.0, 2.0                   # user (2026-10-15): the last scene stays ~3 s longer and fades slowly into the card
OUT0 = t + 0.2 + LAST_HOLD; seq_out = (OUT0, OUT0 + outro_l['dur']); TOTAL = OUT0 + outro_l['dur'] + 1.6
# END ON THE STORY (test, user 2026-10-13): after the closing card, fade to the comic itself and hold it
END_HOLD = 7.0; STORY0 = TOTAL; TOTAL = STORY0 + END_HOLD
STORY = Image.open(HC + '/website/holy-chip-site/stories/pt/HC048.png').convert('RGBA')
BEAT_T = [(min(s for s, e, bi, l in seq if bi == i), max(e for s, e, bi, l in seq if bi == i)) for i in range(len(beats))]
cuts = [0.0] + [BEAT_T[i][0] - 0.15 - SCENE_GAP / 2 for i in range(1, len(beats))] + [OUT0 + 0.5]
# image timeline: the scene's image at its start, then any line-level "Image:" at that line's start
SHOTS = []
for i, b in enumerate(beats):
    SHOTS.append((cuts[i], b.get('img', b['id'])))
    for sh in b.get('shots', []):
        st = next(s_ for s_, e_, bi_, l_ in seq if bi_ == i and l_['k'] == sh['line'])
        SHOTS.append((st - 0.15, sh['img']))
SHOTS.sort(key=lambda x: x[0])
SHOT_T = [x[0] for x in SHOTS] + [OUT0 + 0.5]
beats[-1]['punch'] = True                          # RULE (user, 2026-10-13): the punchline is ALWAYS the last phrase
PUNCH = next(s for s, e, bi, l in seq if bi == len(beats) - 1 and l['k'] == len(beats[-1]['say']) - 1)
HAS_PUNCH = True
print(f'duration {TOTAL:.1f}s, punch at {PUNCH:.1f}s' if HAS_PUNCH else f'duration {TOTAL:.1f}s, no punchline')

# ---------------------------------------------------------------- sound
def load(fn):
    a, sr = sf.read(fn); a = a.mean(1) if a.ndim > 1 else a
    return np.interp(np.linspace(0, len(a), int(len(a) * SR / sr), endpoint=False), np.arange(len(a)), a)
N = int((TOTAL + 0.3) * SR); tt = np.arange(N) / SR
voice = np.zeros(N)
for s, e, bi, l in seq + [(OUT0, 0, -1, outro_l)]:
    a = load(l['file']); i = int(s * SR); voice[i:i + len(a)] += a[:N - i]
score = np.zeros(N)
import os
if os.path.exists('music.wav'):                       # generated track (ACE-Step, MIT)
    m = load('music.wav'); m = np.tile(m, int(np.ceil(N / len(m))))[:N] if len(m) < N else m[:N]
    m = m / max(1e-6, np.abs(m).max())
    # "more spacial, really in the background" (user, 2026-10-13): soften the treble, add a room tail, then half the level
    k = np.exp(-np.arange(int(0.0006 * SR)) / (0.00025 * SR)); m = np.convolve(m, k / k.sum(), 'same')      # gentle low-pass
    ir = np.random.RandomState(7).randn(int(1.6 * SR)) * np.exp(-np.arange(int(1.6 * SR)) / (0.45 * SR))  # 1.6 s reverb tail
    import numpy.fft as _f; L = len(m) + len(ir); Nf = 1 << (L - 1).bit_length()
    wet = _f.irfft(_f.rfft(m, Nf) * _f.rfft(ir, Nf), Nf)[:len(m)]; wet = wet / max(1e-6, np.abs(wet).max())
    m = 0.55 * m + 0.45 * wet
    score += m / max(1e-6, np.abs(m).max()) * 0.04     # half again (was 0.08)
# punchline: a soft cartoon "boing" + ding (no whooshes anywhere - user, 2026-10-08)
if HAS_PUNCH:
    i = int(PUNCH * SR); n = int(0.6 * SR); x = np.arange(n) / SR
    score[i:i + n] += (np.sin(2 * np.pi * (180 + 120 * np.sin(2 * np.pi * 9 * x)) * x) * np.exp(-x * 4) * 0.22)[:N - i]
if HAS_PUNCH:
    n = int(1.2 * SR); x = np.arange(n) / SR; j = int((PUNCH + 0.12) * SR)
    score[j:j + n] += ((np.sin(2 * np.pi * 1568 * x) + 0.5 * np.sin(2 * np.pi * 2093 * x)) * np.exp(-x * 3) * 0.08)[:N - j]
env = np.convolve((np.abs(voice) > 0.01).astype(float), np.ones(SR // 4) / (SR // 4), 'same')
mix = voice + score * (1 - 0.55 * np.clip(env * 3, 0, 1))
mix *= np.clip(tt / 0.8, 0, 1) * np.clip((TOTAL + 0.3 - tt) / 1.4, 0, 1)
sf.write('mix.wav', (mix / np.abs(mix).max() * 0.9).astype(np.float32), SR)

# ---------------------------------------------------------------- picture
from PIL import ImageChops
_F = Image.new('L', (BOX, BOX), 0)                    # soft-edged mask: the sketch dissolves into the paper
ImageDraw.Draw(_F).rounded_rectangle((70, 70, BOX - 70, BOX - 70), radius=120, fill=255)
FEATHER = _F.filter(ImageFilter.GaussianBlur(55))
LEVELS = [0 if v < 0 else (255 if v > 255 else v) for v in (int((v - 0) * 255 / 225) for v in range(256))]

CLIPS = {}
def clip_frame(k, dt):
    """Wan clip (clips/K.mp4, made on the M5) in place of the still, ping-ponged to fill any shot length."""
    if k not in CLIPS:
        f = f"clips/{k}.mp4"
        if not os.path.exists(f): CLIPS[k] = None
        else:
            w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height',
                                            '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip().split(','))
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
            n = len(raw) // (w * h * 3)
            CLIPS[k] = (16, [Image.frombuffer('RGB', (w, h), raw[j * w * h * 3:(j + 1) * w * h * 3]) for j in range(n)])
            print(f'  clip {k}: {n} frames', flush=True)
    if not CLIPS[k]: return None
    fps, fr = CLIPS[k]; n = len(fr); j = int(max(0, dt) * fps) % max(1, 2 * n - 2)
    j = j if j < n else 2 * n - 2 - j                      # forward, then backward: no jump at the loop
    return fr[j].resize((BOX + 50, BOX + 50), Image.BILINEAR)

def bg_at(i, t):                                   # i = index into SHOTS
    s0, s1 = SHOT_T[i], SHOT_T[i + 1]
    p = (t - s0) / max(0.1, s1 - s0); im = clip_frame(SHOTS[i][1], t - s0) or BG[SHOTS[i][1]]
    z = 1.0 + 0.05 * p                                   # subtle push-in
    w = int(im.width * z); r = im.resize((w, w), Image.BILINEAR)
    o = (w - BOX) // 2; r = r.crop((o, o, o + BOX, o + BOX)).point(LEVELS * 3)   # near-white paper -> white
    frame_ = Image.new('RGB', (W, H), PAPER)
    x0, y0 = (W - BOX) // 2, BOX_CY - BOX // 2
    patch = frame_.crop((x0, y0, x0 + BOX, y0 + BOX))
    inked = ImageChops.multiply(patch, r)
    frame_.paste(Image.composite(inked, patch, FEATHER), (x0, y0))
    return frame_

def wrap(s, f, mw):
    out, cur = [], ''
    for w_ in s.split():
        n = (cur + ' ' + w_).strip()
        if cur and f.getlength(n) > mw: out.append(cur); cur = w_
        else: cur = n
    return out + [cur]

def captions(im, t):
    cur = None
    for s, e, bi, l in seq:
        if s - 0.1 <= t <= e + 0.25: cur = (s, e, l)
    if not cur: return
    s, e, l = cur; f = fnt(F_CHAKRA, 72)
    words = l['text'].upper().split(); n_chars = sum(len(w_) for w_ in words)
    prog = (t - s) / max(0.1, e - s); acc = 0; spoken = 0
    for w_ in words:
        acc += len(w_)
        if acc / n_chars <= prog + 0.02: spoken += 1
    rows = wrap(' '.join(words), f, 920); d = ImageDraw.Draw(im); y = 250; wi = 0
    for row in rows:
        rw = f.getlength(row); x = (W - rw) / 2
        for w_ in row.split():
            col = (176, 120, 20) if wi == spoken else ((20, 20, 20) if wi < spoken else (20, 20, 20, 90))
            d.text((x, y), w_, font=f, fill=(250, 248, 242), stroke_width=7, stroke_fill=(250, 248, 242))
            d.text((x, y), w_, font=f, fill=col, stroke_width=2, stroke_fill=col)            # bold
            x += f.getlength(w_ + ' '); wi += 1
        y += 90

def comic_card(im, t, b, bi):
    if 'comic' not in b: return
    s0, s1 = BEAT_T[bi]; panels = b['comic']
    if b.get('punch'):
        s0 = PUNCH - 0.05                       # the punchline card waits for "Holy chip." - no spoiler
    if not (s0 - 0.2 <= t <= s1 + 0.3): return
    k = min(len(panels) - 1, int((t - s0) / max(0.1, (s1 - s0)) * len(panels)))
    p = PANELS[panels[k]]; a = (1.0 if b.get('punch') else ease((t - s0 + 0.2) / 0.5)) * ease((s1 + 0.3 - t) / 0.4)
    cw = 820; ch = int(p.height * cw / p.width)
    card = Image.new('RGBA', (cw + 28, ch + 28), (255, 255, 255, 255)); card.paste(p.resize((cw, ch), Image.LANCZOS), (14, 14))
    pop = 1.0
    if b.get('punch') and t >= PUNCH: pop = 1.0 + 0.18 * (1 - ease((t - PUNCH) / 0.35))
    card = card.rotate(-2.5 if k % 2 == 0 else 2.0, expand=True, resample=Image.BICUBIC)
    card = card.resize((int(card.width * pop), int(card.height * pop)), Image.LANCZOS)
    card.putalpha(card.getchannel('A').point(lambda v: int(v * a)))
    im.alpha_composite(card, (int((W - card.width) / 2), int(760 - card.height / 2 + (1 - a) * 60)))

def bot_layer(im, t, bi):
    b = beats[bi]; key = b['bot']; prev = beats[bi - 1]['bot'] if bi > 0 else key
    s0 = cuts[bi]; mix_ = ease((t - s0) / 0.5)
    breathe = 1 + 0.012 * math.sin(t * 2.2); bob = 7 * math.sin(t * 1.4); tilt = 1.3 * math.sin(t * 0.9)
    shake = (0, 0)
    if t >= PUNCH and t - PUNCH < 0.45: shake = (random.uniform(-16, 16), random.uniform(-10, 10))
    big = 1.0
    if bi == len(beats) - 1: big = 1.0 + 0.25 * ease((t - s0) / 2.5)        # "Watch the human": push in
    def put(k, alpha):
        if alpha <= 0.01: return
        g = BOT[k]; s = breathe * big * CHIP_SCALE
        r = g.resize((int(g.width * s), int(g.height * s)), Image.BILINEAR).rotate(tilt, resample=Image.BICUBIC)
        if alpha < 1: r.putalpha(r.getchannel('A').point(lambda v: int(v * alpha)))
        im.alpha_composite(r, (int(W - r.width - 50 + shake[0]), int(H - r.height - 70 + bob * 0.5 + shake[1])))   # small, bottom-right corner
    if key != prev and mix_ < 1: put(prev, 1 - mix_)
    put(key, mix_ if key != prev else 1)

def story_frame(t):
    im = Image.new('RGBA', (W, H), (246, 243, 234, 255))
    z = 1.0 + 0.04 * min(1, (t - STORY0) / END_HOLD)                  # slow push-in
    sw = int(1000 * z); r = STORY.resize((sw, int(STORY.height * sw / STORY.width)), Image.LANCZOS)
    im.alpha_composite(r, (int(W / 2 - r.width / 2), int(H / 2 - r.height / 2)))
    return im

def frame(t):
    if t >= STORY0:
        card = outro_frame(STORY0 - 0.001)
        return Image.blend(card, story_frame(t), ease((t - STORY0) / 0.8)) if t - STORY0 < 0.8 else story_frame(t)
    return outro_frame(t)

def outro_frame(t):
    if t >= OUT0 - FADE:                                  # slow crossfade: last scene -> closing card
        card = card_frame(t)
        return Image.blend(scene_frame(t), card, ease((t - OUT0 + FADE) / FADE)) if t < OUT0 else card
    return scene_frame(t)

def card_frame(t):
    if True:
        im = Image.new('RGBA', (W, H), (246, 243, 234, 255)); d = ImageDraw.Draw(im); k = ease((t - OUT0 + FADE) / FADE)
        bw = 840; bx = (W - bw) / 2
        d.rounded_rectangle((bx, 300, bx + bw, 470), radius=30, fill=(0, 0, 0), outline=(255, 255, 255), width=4)
        d.polygon([(W / 2 - 30, 468), (W / 2 + 30, 468), (W / 2, 520)], fill=(0, 0, 0))
        d.text((W / 2, 387), 'HOLY CHIP !!', font=fnt(F_PIXEL, 58), fill=(255, 255, 255), anchor='mm')
        g = BOT['p1Left']; s = 0.62 * (0.85 + 0.15 * k)
        r = g.resize((int(g.width * s), int(g.height * s)), Image.LANCZOS); im.alpha_composite(r, (int(W / 2 - r.width / 2), 560))
        y0 = 1140; OJ = json.load(open('outro.json'))
        d.text((W / 2, y0), OJ['label'], font=fnt(F_PIXEL, 44), fill=(176, 120, 20), anchor='mm')
        d.text((W / 2, y0 + 110), OJ['line1'], font=fnt(F_CHAKRA, 62), fill=(30, 30, 30), anchor='mm')
        if t > OUT0 + 2.2:                                   # the joke lands with the voice
            a2 = int(255 * ease((t - OUT0 - 2.2) / 0.5))
            d.text((W / 2, y0 + 210), OJ['line2'], font=fnt(F_CHAKRA, 62), fill=(30, 30, 30, a2), anchor='mm')
        if t > OUT0 + 3.4:
            a3 = int(255 * ease((t - OUT0 - 3.4) / 0.5))
            d.rounded_rectangle((110, y0 + 290, W - 110, y0 + 420), radius=26, fill=GOLD + (a3,))
            d.text((W / 2, y0 + 355), OJ['button'], font=fnt(F_CHAKRA, 52), fill=(20, 20, 20, a3), anchor='mm')
        d.text((W / 2, y0 + 520), OJ['site'], font=fnt(F_CHAKRA, 66), fill=(30, 30, 30), anchor='mm')
        return im

def scene_frame(t):
    bi = max(i for i in range(len(beats)) if cuts[i] <= t)
    si = max(k for k in range(len(SHOTS)) if SHOT_T[k] <= t)
    base = bg_at(si, t).convert('RGBA')
    if si > 0 and t - SHOT_T[si] < 0.6:                                   # crossfade from the previous image
        base = Image.blend(bg_at(si - 1, t).convert('RGBA'), base, ease((t - SHOT_T[si]) / 0.6))
    comic_card(base, t, beats[bi], bi)
    bot_layer(base, t, bi)
    if t >= PUNCH and t - PUNCH < 0.14:
        base = Image.blend(base, Image.new('RGBA', (W, H), (255, 255, 255, 255)), 0.8 * (1 - (t - PUNCH) / 0.14))
    d = ImageDraw.Draw(base)
    d.text((W / 2, 120), 'HOLY CHIP #048', font=fnt(F_PIXEL, 26), fill=(30, 30, 30, 220), anchor='mm')
    captions(base, t)
    return base

GRAIN = [Image.effect_noise((W // 2, H // 2), 26).resize((W, H)).convert('L') for _ in range(4)]
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                       '-i', 'mix.wav', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
                       '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', 'HC048_sketch.mp4'], stdin=subprocess.PIPE)
nf = int(TOTAL * FPS)
for fi in range(nf):
    im = frame(fi / FPS).convert('RGB')
    im = Image.blend(im, Image.merge('RGB', [GRAIN[fi % 4]] * 3), 0.015)
    ff.stdin.write(im.tobytes())
    if fi % 450 == 0: print(f'  frame {fi}/{nf}', flush=True)
ff.stdin.close(); ff.wait(); print('HC048_sketch.mp4', f'{TOTAL:.1f}s')

#!/usr/bin/env python3
"""Channel intro prototypes (~5 s) ending on the HOLY - beep - CHIIIP!! voice.

    intro_build.py A|B|C|D|A2|D2 [--out intro_A.mp4] [--vertical]   (A2/D2 = cutout shout of Chip 1)

A  "roll call": faces flash one after another, slow then faster and faster,
   each with a rising blip; the last one freezes big and shouts HOLY CHIP!!
B  "the wall": a wall of faces; the camera dives into one of them; it goes
   wide-eyed and shouts.
C  "three panels": an empty strip; faces slam into panel 1, then 2, faster
   and faster; panel 3 gets the one who shouts.
Faces: nft/collection/assets/*.png (640 RGBA). Voice: reel_vo.build_chip_vo.
"""
import os, random, subprocess, sys, tempfile, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HC = Path.home() / "holy-chip"
sys.path.insert(0, str(HC / "tools"))
FACES = sorted((p for p in (HC / "nft" / "collection" / "assets").glob("*.png") if p.stem.isdigit()), key=lambda p: int(p.stem))
PAPER = (246, 243, 234); INK = (20, 20, 20)
FPS = 30
F_PIXEL = str(HC / "SGen" / "public" / "fonts" / "PressStart2P-Regular.ttf")
F_CHAKRA = str(HC / "SGen" / "public" / "fonts" / "ChakraPetch-Bold.woff2")
F_CHAKRA_TTF = str(HC / "content" / "pt-br" / "work" / "ChakraPetch-Bold.ttf")


def font(path, size):
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.truetype(F_CHAKRA_TTF, size)


def ease_in(t): return t * t * t


def face(i, size):
    im = Image.open(FACES[i % len(FACES)]).convert("RGBA"); im.thumbnail((size, size), Image.LANCZOS); return im


def paste_center(bg, im, cx, cy):
    bg.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def bubble(bg, text, cx, top, scale=1.0, font_size=96, full=None):
    """Black rounded bubble with white text, tail pointing down. `full` sizes the
    bubble for the complete line while only `text` (its first words) is drawn, so
    the bubble never changes size when the rest of the words appear."""
    f = font(F_CHAKRA_TTF, int(font_size * scale)); d = ImageDraw.Draw(bg)
    full = full or text; tw = d.textlength(full, font=f); pad = int(40 * scale); w = tw + 2 * pad; h = int(font_size * scale) + 2 * pad
    x0 = cx - w / 2; y0 = top
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=int(34 * scale), fill=INK)
    d.polygon([(cx - 28 * scale, y0 + h - 2), (cx + 28 * scale, y0 + h - 2), (cx, y0 + h + 40 * scale)], fill=INK)
    d.text((x0 + pad, y0 + h / 2), text, font=f, fill=(255, 255, 255), anchor="lm")


def write_video(frames, audio_parts, out, size, fade=0.0):
    """frames: list of PIL RGB; audio_parts: [(wav, start_s)] mixed over silence;
    fade: seconds of fade-to-paper (and audio fade-out) at the end."""
    tmp = tempfile.mkdtemp(); W, H = size
    if fade:                                                  # iris: a paper circle grows from the centre and eats the picture
        nf = int(fade * FPS); R = math.hypot(W, H) / 2
        for i in range(nf):
            k = len(frames) - nf + i; r = R * ((i + 1) / nf) ** 0.8
            fr = frames[k].convert("RGB"); ImageDraw.Draw(fr).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=PAPER); frames[k] = fr
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", os.path.join(tmp, "v.mp4")], stdin=subprocess.PIPE)
    for fr in frames: ff.stdin.write(fr.convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    dur = len(frames) / FPS
    ins, fc, labels = [], [], []
    for i, (wav, st) in enumerate(audio_parts):
        ins += ["-i", wav]; fc.append(f"[{i+1}:a]adelay={int(st*1000)}|{int(st*1000)}[a{i}]"); labels.append(f"[a{i}]")
    af = f",afade=t=out:st={dur - fade:.3f}:d={fade:.3f}" if fade else ""
    fc.append("".join(labels) + f"amix=inputs={len(audio_parts)}:normalize=0,apad,atrim=0:{dur:.3f}{af}[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(tmp, "v.mp4"), *ins, "-filter_complex", ";".join(fc),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
    return out


def chip_voice(tmp):
    import reel_vo
    wav, dur = reel_vo.build_chip_vo(tmp); return wav, dur


def tone(tmp, hz, dur, name):
    p = os.path.join(tmp, name)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={hz}:duration={dur}:sample_rate=48000",
                    "-af", f"afade=t=in:d=0.004,afade=t=out:st=0.02:d={dur-0.02:.3f},volume=-16dB", "-ac", "2", p], check=True)
    return p


FADE = 2.0


def modem(tmp, dur=FADE):
    """An old dial-up handshake, synthesised: answer tone, warble, probing chirps, then
    the hiss (user, 2026-10-17: under the iris wipe)."""
    import numpy as np
    sr = 48000; t = np.arange(int(sr * dur)) / sr; y = np.zeros_like(t)
    def seg(a, b): return (t >= a) & (t < b)
    y += seg(0.0, 0.40) * np.sin(2 * np.pi * 2100 * t) * 0.5                                    # answer tone
    m = seg(0.40, 0.80); y += m * np.sin(2 * np.pi * np.where((t * 12).astype(int) % 2 == 0, 1300, 2100) * t) * 0.5   # warble
    for k in range(5):                                                                             # probing chirps, 500 -> 2800 Hz
        a = 0.80 + k * 0.12; mm = seg(a, a + 0.11); tt = (t - a)
        y += mm * np.sin(2 * np.pi * (500 * tt + (2300 / 0.11 / 2) * tt ** 2)) * 0.45
    rng = np.random.default_rng(7); noise = rng.standard_normal(len(t))
    noise = np.convolve(noise, np.ones(6) / 6, mode="same")                                        # dull the hiss a little
    y += seg(1.40, dur) * noise * 0.35 * np.clip((dur - t) / (dur - 1.40), 0, 1)                    # hiss dies with the picture
    y = np.clip(y, -1, 1) * 0.7; out = os.path.join(tmp, "modem.wav")
    import wave
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); pcm = (y * 32767).astype("<i2"); w.writeframes(np.repeat(pcm, 2).tobytes())
    return out


def title_card(bg, W, H, scale=1.0):
    d = ImageDraw.Draw(bg); f = font(F_PIXEL, int(0.04 * H * scale))
    d.text((W / 2, H * 0.90), "HOLY-CHIP  AI HUMOUR", font=f, fill=INK, anchor="mm")


def intro_A(size, tmp, seed=7):
    W, H = size; random.seed(seed); order = random.sample(range(len(FACES)), 40)
    voice, vdur = chip_voice(tmp)
    shout_at = 2.8; total = shout_at + vdur + 0.25          # 2.8 s of faces, then the whole voice
    # face switch times: accelerating from 0.45 s apart to 0.06 s apart until shout_at
    times, t, gap = [], 0.0, 0.45
    while t < shout_at - 0.05:
        times.append(t); t += gap; gap = max(0.055, gap * 0.82)
    frames, audio = [], [(voice, shout_at)]
    fsize = int(H * 0.62)
    for k, st in enumerate(times):
        audio.append((tone(tmp, 500 + k * 55, 0.06, f"b{k}.wav"), st))
    n = int(total * FPS)
    for fi in range(n):
        tt = fi / FPS; bg = Image.new("RGBA", size, PAPER + (255,))
        if tt < shout_at:
            k = max(i for i, st in enumerate(times) if st <= tt)
            im = face(order[k], fsize); paste_center(bg, im, W / 2, H * 0.52)
        else:
            p = min(1.0, (tt - shout_at) / 0.12); im = face(order[len(times) - 1], int(fsize * (1 + 0.12 * p)))
            paste_center(bg, im, W / 2, H * 0.56)
            if tt - shout_at > 0.45:                       # the bubble pops on CHIP
                bubble(bg, "HOLY CHIP !!", W / 2, H * 0.08, scale=min(1.0, (tt - shout_at - 0.45) / 0.1 + 0.6) * (H / 1080))
        title_card(bg, W, H)
        frames.append(bg)
    return frames, audio


def intro_B(size, tmp, seed=11):
    W, H = size; random.seed(seed); n_side = 10; cell = max(W, H) // n_side + 1
    voice, vdur = chip_voice(tmp); shout_at = 2.8; total = shout_at + vdur + 0.25
    idx = random.sample(range(len(FACES)), n_side * n_side); target = (n_side // 2, n_side // 2)
    wall = Image.new("RGBA", (cell * n_side, cell * n_side), PAPER + (255,))
    for r in range(n_side):
        for c in range(n_side):
            paste_center(wall, face(idx[r * n_side + c], int(cell * 0.86)), c * cell + cell / 2, r * cell + cell / 2)
    tx, ty = target[1] * cell + cell / 2, target[0] * cell + cell / 2
    frames, audio = [], [(voice, shout_at)]
    for k in range(10): audio.append((tone(tmp, 420 + k * 70, 0.06, f"w{k}.wav"), shout_at * k / 10))
    for fi in range(int(total * FPS)):
        tt = fi / FPS; bg = Image.new("RGBA", size, PAPER + (255,))
        p = ease_in(min(1.0, tt / shout_at)); zoom = 1.0 + p * (n_side * 0.95 - 1.0)    # from the whole wall to one cell
        vw, vh = wall.width / zoom, wall.height / zoom
        cx = (wall.width / 2) * (1 - p) + tx * p; cy = (wall.height / 2) * (1 - p) + ty * p
        crop = wall.crop((int(cx - vw / 2), int(cy - vh / 2), int(cx + vw / 2), int(cy + vh / 2))).resize(size, Image.LANCZOS)
        bg.alpha_composite(crop)
        if tt >= shout_at:
            im = face(idx[target[0] * n_side + target[1]], int(H * 0.7)); paste_center(bg, im, W / 2, H * 0.56)
            if tt - shout_at > 0.45: bubble(bg, "HOLY CHIP !!", W / 2, H * 0.08, scale=H / 1080)
        title_card(bg, W, H)
        frames.append(bg)
    return frames, audio


def intro_C(size, tmp, seed=3):
    W, H = size; random.seed(seed); voice, vdur = chip_voice(tmp); shout_at = 2.8; total = shout_at + vdur + 0.25
    order = random.sample(range(len(FACES)), 30)
    pw = int(W * 0.28); gap = int(W * 0.04); x0 = (W - 3 * pw - 2 * gap) / 2; py = H * 0.22; ph = int(H * 0.56)
    times, t, g = [], 0.0, 0.5
    while t < shout_at - 0.05: times.append(t); t += g; g = max(0.06, g * 0.8)
    frames, audio = [], [(voice, shout_at)]
    for k, st in enumerate(times): audio.append((tone(tmp, 480 + k * 50, 0.06, f"c{k}.wav"), st))
    for fi in range(int(total * FPS)):
        tt = fi / FPS; bg = Image.new("RGBA", size, PAPER + (255,)); d = ImageDraw.Draw(bg)
        for i in range(3):
            x = x0 + i * (pw + gap); d.rectangle((x, py, x + pw, py + ph), outline=INK, width=6)
        k = max([i for i, st in enumerate(times) if st <= tt] or [0])
        for i in range(2):                                     # panels 1 and 2 flip faces, alternating
            j = k - (1 - i)
            if j >= 0 and (j % 2 == i or tt >= shout_at):
                paste_center(bg, face(order[j], int(pw * 0.8)), x0 + i * (pw + gap) + pw / 2, py + ph / 2)
        if tt >= shout_at:
            paste_center(bg, face(order[-1], int(pw * 0.9)), x0 + 2 * (pw + gap) + pw / 2, py + ph / 2 + 10)
            if tt - shout_at > 0.45: bubble(bg, "HOLY CHIP !!", x0 + 2 * (pw + gap) + pw / 2, py - H * 0.16, scale=0.62 * H / 1080)
        title_card(bg, W, H)
        frames.append(bg)
    return frames, audio


def intro_D(size, tmp, seed=1):
    """A pencil draws one of the comic's own bots stroke by stroke (ink revealed in
    drawing order: top to bottom, left to right within a band), then it shouts."""
    W, H = size; voice, vdur = chip_voice(tmp); draw_s = 2.6; total = draw_s + vdur + 0.25     # the voice is never cut
    art = Image.open(HC / "characters" / "Chip 1" / "o005.b095.r242.m001.a093.png").convert("RGBA")
    art = art.resize((int(H * 0.62), int(H * 0.62)), Image.LANCZOS)
    g = art.convert("L"); px = g.load(); AW, AH = art.size
    ink = [(x, y) for y in range(AH) for x in range(AW) if px[x, y] < 128]
    band = 14                                              # drawing order: horizontal bands, left->right in each
    ink.sort(key=lambda q: (q[1] // band, q[0] if (q[1] // band) % 2 == 0 else -q[0]))
    n_ink = len(ink); ox, oy = int(W / 2 - AW / 2), int(H * 0.56 - AH / 2)
    pencil = Image.new("RGBA", (260, 40), (0, 0, 0, 0)); pd = ImageDraw.Draw(pencil)
    pd.polygon([(0, 20), (40, 4), (260, 4), (260, 36), (40, 36)], fill=(240, 196, 60, 255)); pd.polygon([(0, 20), (40, 4), (40, 36)], fill=(60, 60, 60, 255))
    pd.rectangle((230, 4, 260, 36), fill=(230, 120, 120, 255))
    pencil = pencil.rotate(35, expand=True, resample=Image.BICUBIC)
    frames, audio = [], [(voice, draw_s)]
    scratch = tone(tmp, 180, 0.05, "scratch.wav")
    for k in range(int(draw_s / 0.11)): audio.append((scratch, k * 0.11))
    for fi in range(int(total * FPS)):
        tt = fi / FPS; bg = Image.new("RGBA", size, PAPER + (255,))
        p = min(1.0, (tt / draw_s) ** 0.9)
        shown = int(n_ink * p); layer = Image.new("RGBA", art.size, (0, 0, 0, 0)); lp = layer.load()
        for (x, y) in ink[:shown]: lp[x, y] = (20, 20, 20, 255)
        bg.alpha_composite(layer, (ox, oy))
        if tt < draw_s and shown:
            tipx, tipy = ink[shown - 1]; bg.alpha_composite(pencil, (ox + tipx - 8, oy + tipy - pencil.height + 8))
        if tt >= draw_s + 0.45: bubble(bg, "HOLY CHIP !!", W / 2, H * 0.08, scale=H / 1080)
        title_card(bg, W, H)
        frames.append(bg)
    return frames, audio




# ------------------------------------------------------------- M5 versions ---
# The hand in D2 is a Qwen-Image sprite drawn on the M5 (assets/hand.png). The shout
# is a cutout animation of Chip 1 (characters/Chip 1, ten mouth variants): the Wan
# I2V clips of the shout (clips/hero*.mp4) were tried and rejected (2026-10-17).
INTRO = HC / "content" / "video" / "intro"
T_CHIP = 1.72            # "CHIP" starts 1.72 s into the voice (HOLY + beep before it)


def key_white(im, thr=228):
    """White (tile / paper) -> transparent. Keeps the ink and the greys."""
    im = im.convert("RGBA"); px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and min(r, g, b) > thr: px[x, y] = (r, g, b, 0)
    return im


def face_k(i, size):
    return key_white(face(i, size))


CHIP1 = HC / "characters" / "Chip 1"
MOUTH = {"smile": "b195", "open": "b095", "line": "b042", "wide": "b329", "small": "b002", "rect": "b045"}
FACE_W = 340            # inner width of Chip 1's face in the 640 art
# voice beats inside build_chip_vo (measured): HOLY 0-0.60, beep 0.75-1.50, CHIIIP 1.72-3.84
T_HOLY_END, T_BEEP, T_BEEP_END, T_CHIP_END = 0.60, 0.75, 1.50, 3.84


_EYES = None


def _components(mouth, region, lo, hi):
    """Dark connected components of a Chip 1 variant inside region whose box is lo..hi px."""
    im = Image.open(CHIP1 / f"o005.{MOUTH[mouth]}.r242.m001.a093.png").convert("L"); px = im.load()
    X0, Y0, X1, Y1 = region; seen = set(); boxes = []
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            if px[x, y] < 128 and (x, y) not in seen:
                q = [(x, y)]; seen.add((x, y)); pts = []
                while q:
                    cx, cy = q.pop(); pts.append((cx, cy))
                    for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                        if X0 <= nx < X1 and Y0 <= ny < Y1 and (nx, ny) not in seen and px[nx, ny] < 128:
                            seen.add((nx, ny)); q.append((nx, ny))
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; b = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
                if lo <= b[2] - b[0] <= hi and lo <= b[3] - b[1] <= hi: boxes.append((len(pts), b))
    return [b for _, b in sorted(boxes, reverse=True)]


def eye_boxes():
    global _EYES
    if not _EYES: _EYES = sorted(_components("open", (120, 150, 520, 360), 40, 100)[:2])
    return _EYES


_MOUTH = {}


def mouth_box(mouth):
    if mouth not in _MOUTH: _MOUTH[mouth] = _components(mouth, (140, 330, 500, 500), 30, 220)[0]
    return _MOUTH[mouth]


def pop(im, box, f, fy=None, anchor="center"):
    """Redraw the part inside box f times bigger (fy vertically) over a white patch;
    anchor="bottom" keeps the bottom edge in place (the mouth grows up, not into the body)."""
    x0, y0, x1, y1 = box; part = im.crop(box); w, h = part.size; cx = (x0 + x1) / 2
    ew, eh = int(w * f), int(h * (fy or f)); big = part.resize((ew, eh), Image.LANCZOS)
    top = y1 - eh if anchor == "bottom" else (y0 + y1) / 2 - eh / 2
    ImageDraw.Draw(im).rectangle((min(x0, cx - ew / 2) - 2, min(y0, top) - 2, max(x1, cx + ew / 2) + 2, max(y1, top + eh) + 2), fill=(255, 255, 255, 255))   # hides the original even when shrinking
    im.alpha_composite(big, (int(cx - ew / 2), int(top)))


def chip1(mouth, size, eyes=2.0, mouth_w=None):
    """mouth_w: draw the CHIIIIP mouth as a rectangle this wide (640-art px) in place of the variant's mouth."""
    none = mouth == "none"; mouth = "rect" if none else mouth                 # "none": the rect variant with its mouth painted out
    im = Image.open(CHIP1 / f"o005.{MOUTH[mouth]}.r242.m001.a093.png").convert("RGBA")
    if none:
        x0, y0, x1, y1 = mouth_box(mouth); ImageDraw.Draw(im).rectangle((x0 - 2, y0 - 2, x1 + 2, y1 + 2), fill=(255, 255, 255, 255))
    if mouth_w:
        x0, y0, x1, y1 = mouth_box(mouth); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; h = (y1 - y0) / 2      # half the variant's height (user, 2026-10-17)
        d = ImageDraw.Draw(im); d.rectangle((x0 - 2, y0 - 2, x1 + 2, y1 + 2), fill=(255, 255, 255, 255))
        d.rectangle((cx - mouth_w / 2, cy - h / 2, cx + mouth_w / 2, cy + h / 2), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=9)
    if eyes < 2.0 and EYES == "chevron":                   # squint (user, 2026-10-17): the round eyes become "> <" chevrons,
        d = ImageDraw.Draw(im); e = max(0.0, min(1.0, eyes))   # then the chevron angle closes (eyes 1 -> 0) for the deeper squint
        for i, (x0, y0, x1, y1) in enumerate(eye_boxes()):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; hw = 20; hh = 8 + 22 * e
            d.rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), fill=(255, 255, 255, 255))
            S4 = 4; L = (x1 - x0 + 8) * S4; lay = Image.new("RGBA", (L, L), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)   # drawn 4x and downsampled: sub-pixel smooth
            lc = L / 2
            if i == 0: pts = [(lc - hw * S4, lc - hh * S4), (lc + hw * S4, lc), (lc - hw * S4, lc + hh * S4)]       # left eye  >
            else: pts = [(lc + hw * S4, lc - hh * S4), (lc - hw * S4, lc), (lc + hw * S4, lc + hh * S4)]            # right eye <
            ld.line(pts, fill=(0, 0, 0, 255), width=13 * S4, joint="curve")
            lay = lay.resize((L // S4, L // S4), Image.LANCZOS); im.alpha_composite(lay, (int(cx - L / S4 / 2), int(cy - L / S4 / 2)))
    elif eyes < 2.0:                                      # "minus" style (saved, 2026-10-17): the plus loses its vertical arm, then the minus tilts
        d = ImageDraw.Draw(im); arm = max(0.0, min(1.0, eyes - 1)); ang = (1 - max(0.0, min(1.0, eyes))) * 28
        for i, (x0, y0, x1, y1) in enumerate(eye_boxes()):
            w, h = x1 - x0, y1 - y0; ax0, ax1 = x0 + 0.38 * w, x0 + 0.60 * w
            top0, top1, bot0, bot1 = y0 + 0.18 * h, y0 + 0.40 * h, y0 + 0.60 * h, y0 + 0.82 * h
            cut = (1 - arm) * (top1 - top0)
            if cut > 0:
                d.rectangle((ax0, top0, ax1, top0 + cut), fill=(0, 0, 0, 255)); d.rectangle((ax0, bot1 - cut, ax1, bot1), fill=(0, 0, 0, 255))
            if ang > 0:
                pad = 6; box = (x0 - pad, y0 - pad, x1 + pad, y1 + pad); eye = im.crop(box)
                eye = eye.rotate(-ang if i == 0 else ang, resample=Image.BICUBIC, fillcolor=(255, 255, 255, 255)); im.paste(eye, box)
    im = im.resize((size, size), Image.LANCZOS); return key_white(im)


ASTRO = HC / "website" / "holy-chip-site" / "characters" / "Chip_1.png"    # the smiling store astronaut: FIRST face of the roll call (user, 2026-10-17)


EYES = "chevron"         # "chevron" (> <, angle closes) or "minus" (plus -> minus -> tilted); --eyes minus
T_GROW, T_COLLAPSE = 1.5, 0.35        # slow growth; back to the square right as the note dies (user, 2026-10-17)


def shout_pose(t):
    """Cutout shout, t = seconds since the voice started -> (mouth, eyes, scale, dx, dy, mouth_w).
    HOLY: the round mouth opens, small punch. Beep: mouth shut. CHIIIIP: a rectangular
    mouth grows slowly sideways to ~60% of the face while the eyes squint, then collapses back
    and the face ends on the same small square it started from (user, 2026-10-17)."""
    if t < T_HOLY_END:
        punch = 1 + 0.06 * (1 - min(1, t / 0.08)) if t < 0.08 else 1.02 + 0.02 * math.exp(-(t - 0.08) * 6)
        return "open", 2.0, punch, 0, 0, None
    if t < T_CHIP: return "rect", 2.0, 1.02, 0, 0, (mouth_box("rect")[3] - mouth_box("rect")[1]) / 2   # a small square, same height as the rect mouth that opens (user, 2026-10-17)
    u = t - T_CHIP
    x0, y0, x1, y1 = mouth_box("rect"); w0 = (y1 - y0) / 2               # starts as the square (the drawn mouth is half the variant height)
    if u < T_GROW:
        eyes = (1.0 - (u / T_GROW) ** 0.8) if EYES == "chevron" else 2.0 - 2.0 * (u / T_GROW)   # chevron: circle -> closing "> <" on the first CHIP frame; minus: plus -> minus -> tilt
        w = w0 + (0.6 * FACE_W - w0) * (u / T_GROW)                                   # slow, steady widening to 60% of the face
        scale = (1.02 + 0.16 * (u / 0.07)) if u < 0.07 else 1.18 - 0.05 * min(1, (u - 0.07) / 0.5)
        amp = 12 * math.exp(-u * 3.5) if u < 1.0 else 0
        return "rect", eyes, scale, amp * math.sin(2 * math.pi * 23 * u), 0.4 * amp * math.sin(2 * math.pi * 31 * u), w
    v = (u - T_GROW) / T_COLLAPSE
    if v < 1:
        return "rect", ((v if v < 0.8 else 2.0) if EYES == "chevron" else 2.0 * v), 1.13 - 0.11 * v, 0, 0, 0.6 * FACE_W - (0.6 * FACE_W - w0) * v ** 0.6
    return "rect", 2.0, 1.02, 0, 0, w0                                     # ends on the same small square it started from (user, 2026-10-17)


def shout_frame(bg, t, base_size, cx, cy, cache):
    mouth, eyes, scale, dx, dy, mw = shout_pose(t); sz = int(base_size * scale); eyes = round(eyes, 3); mw = mw and int(mw)
    key = (mouth, eyes, sz, mw)
    if key not in cache: cache[key] = chip1(mouth, sz, eyes, mw)
    paste_center(bg, cache[key], cx + dx, cy + dy)


def intro_A2(size, tmp, seed=7):
    """Roll call of the NFT faces (white tiles keyed out), faster and faster; it lands
    on Chip 1, the comic's own bot, who shouts HOLY CHIP!! as a cutout animation."""
    W, H = size; random.seed(seed); order = random.sample(range(len(FACES)), 40)
    voice, vdur = chip_voice(tmp); shout_at = 2.8; total = shout_at + vdur + 2.6      # the face returns to normal, holds ~1 s, then the 2 s iris wipe
    times, t, gap = [], 0.0, 0.45
    while t < shout_at - 0.05: times.append(t); t += gap; gap = max(0.055, gap * 0.82)
    frames, audio = [], [(voice, shout_at), (modem(tmp), total - FADE)]       # the modem plays under the iris wipe
    fsize = int(H * 0.62); cache = {}
    for k, st in enumerate(times): audio.append((tone(tmp, 500 + k * 55, 0.06, f"b{k}.wav"), st))
    for fi in range(int(total * FPS)):
        tt = fi / FPS; bg = Image.new("RGBA", size, PAPER + (255,))
        if tt < shout_at - 0.25:
            k = max(i for i, st in enumerate(times) if st <= tt)
            if k not in cache:
                if k == 0:                                             # the roll call opens on the smiling store astronaut
                    im = Image.open(ASTRO).convert("RGBA"); bg_ = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg_.alpha_composite(im)
                    bg_.thumbnail((fsize, fsize), Image.LANCZOS); cache[k] = key_white(bg_)
                else: cache[k] = face_k(order[k], fsize)
            paste_center(bg, cache[k], W / 2, H * 0.52)
        elif tt < shout_at:                                   # lands on Chip 1, smiling, a beat before the voice
            if "smile" not in cache: cache["smile"] = chip1("smile", fsize)
            paste_center(bg, cache["smile"], W / 2, H * 0.52)
        else:
            shout_frame(bg, tt - shout_at, fsize, W / 2, H * 0.52, cache)
            u = tt - shout_at                                   # the bubble in two phases (user, 2026-10-17): "HOLY" on HOLY, "HOLY CHIP !!" on CHIP
            if tt >= total - FADE: pass                                                                 # the bubble leaves the moment the iris wipe starts (user, 2026-10-17)
            elif u >= T_CHIP: bubble(bg, "HOLY CHIP !!", W / 2, H * 0.05, scale=H / 1080, full="HOLY CHIP !!")   # the words complete; the bubble does not move
            elif u >= 0: bubble(bg, "HOLY...", W / 2, H * 0.05, scale=min(1.0, u / 0.1 + 0.6) * (H / 1080), full="HOLY CHIP !!")   # "HOLY..." in the full-size bubble
        frames.append(bg)                                   # no title line (user, 2026-10-17)
    return frames, audio


def intro_D2(size, tmp, seed=1):
    """Chip 1 draws itself, stroke by stroke, no hand, no pencil (user, 2026-10-17);
    then the drawing shouts HOLY CHIP!! (cutout animation)."""
    W, H = size; voice, vdur = chip_voice(tmp); draw_s = 2.8; total = draw_s + vdur + 0.25
    AW = AH = int(H * 0.62)
    art = Image.open(CHIP1 / f"o005.{MOUTH['smile']}.r242.m001.a093.png").convert("RGBA").resize((AW, AH), Image.LANCZOS)
    g = art.convert("L"); px = g.load()
    ink = [(x, y) for y in range(AH) for x in range(AW) if px[x, y] < 128]
    band = 14; ink.sort(key=lambda q: (q[1] // band, q[0] if (q[1] // band) % 2 == 0 else -q[0]))
    n_ink = len(ink); cx, cy = W / 2, H * 0.52; ox, oy = int(cx - AW / 2), int(cy - AH / 2)
    frames, audio = [], [(voice, draw_s)]
    scratch = tone(tmp, 180, 0.05, "scratch.wav")
    for k in range(int(draw_s / 0.11)): audio.append((scratch, k * 0.11))
    layer = Image.new("RGBA", art.size, (0, 0, 0, 0)); lp = layer.load(); drawn = 0; cache = {}
    for fi in range(int(total * FPS)):
        tt = fi / FPS; bg = Image.new("RGBA", size, PAPER + (255,))
        p = min(1.0, (tt / draw_s) ** 0.9); shown = int(n_ink * p)
        for (x, y) in ink[drawn:shown]: lp[x, y] = (20, 20, 20, 255)
        drawn = max(drawn, shown)
        if tt < draw_s: bg.alpha_composite(layer, (ox, oy))
        else:
            shout_frame(bg, tt - draw_s, AW, cx, cy, cache)
            if tt >= draw_s + T_CHIP: bubble(bg, "HOLY CHIP !!", W / 2, H * 0.05, scale=H / 1080)
        title_card(bg, W, H); frames.append(bg)
    return frames, audio


if __name__ == "__main__":
    which = sys.argv[1].upper(); vertical = "--vertical" in sys.argv
    if "--eyes" in sys.argv: EYES = sys.argv[sys.argv.index("--eyes") + 1]
    size = (1080, 1920) if vertical else (1920, 1080)
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else str(HC / "content" / "video" / "intro" / f"intro_{which}{'_v' if vertical else ''}.mp4")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp()
    frames, audio = {"A": intro_A, "B": intro_B, "C": intro_C, "D": intro_D, "A2": intro_A2, "D2": intro_D2}[which](size, tmp)
    print(write_video(frames, audio, out, size, fade=FADE if which == "A2" else 0.0))

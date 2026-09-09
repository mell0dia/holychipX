#!/usr/bin/env python3
"""reel_vo.py - build a Reel with the approved voice-over format.

Four audio elements and nothing else:

  1. a TTS header read over the title card ("A G I Headquarters. Twenty
     twenty six.")
  2. the music bed, alone, through the whole build-up
  3. a short tone on every bubble reveal in panels 1 and 2 - "blip" for a
     white bubble, "blop" for a black one
  4. a dramatic TTS "HOLY - beep - CHIIIP!!" on the final bubble

THIS IS THE OFFICIAL FORMAT as of 2026-08-20, signed off by the user after a
round of auditions. All 39 Reels were rebuilt to it that day. The pieces that
were chosen by ear, and must not be "tidied" without asking:

  - TWO VOICES, not one. Daniel + a light machine treatment reads the title;
    Fred delivers the punchline. Zarvox did both and was too robotic up front.
  - THE PUNCHLINE RISES. Only the last word: HOLY stays at Fred's floor,
    CHIIIP is lifted to pbas 80.
  - THE VOWEL IS STRETCHED, NOT SPELLED. See CHIP_WORD below.
  - THE BEEP HAS AIR EITHER SIDE. 0.18s, "short, just to notice".
  - TONES ON PANELS 1 AND 2 ONLY. The last panel stays dry under the voice.

Usage:
    reel_vo.py HC017                  # one story  -> videos/HC017.reel.mp4
    reel_vo.py --all                  # every story that has assets
    reel_vo.py --all --skip-existing  # only the ones not built yet
    reel_vo.py HC017 --music-lufs=-34 # louder bed (default -38)

WHY THE HEADER HOLD IS COMPUTED, NOT FIXED. The title card is HEADER_MS
(2450ms) by default, but the spoken header runs 3.4-4.0s depending on how long
the title is. We measure the TTS first and stretch the card to fit it, so a
long title like "AI PERSONAL ASSISTANT" does not get its voice cut off. A flat
--nudge header=1500 works for a two-word title and silently truncates a longer
one.

WHY OFFSETS ARE COMPUTED FRAME-BY-FRAME. save_mp4 rounds EACH element to a
whole number of frames independently, so a cumulative millisecond total drifts
against the real video - about two frames by the end of a 27s Reel, which is
enough to land the punchline voice on the wrong panel. verify_offsets() checks
our frame math against the encoded file and refuses to mix if they disagree.
"""
import argparse, array, math, os, re, subprocess, sys, tempfile, wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_gif as sg
from PIL import Image

HC = os.path.expanduser("~/holy-chip")
MUSIC = os.path.join(HC, "audio", "robotz.mp4")

# --- the two voices, chosen by the user 2026-08-20 -----------------------
# The reel speaks twice and the two lines want opposite things, so they no
# longer share a voice. Zarvox did both and was too robotic for the title.
#
# TITLE CARD: Daniel, a natural voice, with a light machine treatment on top
# (formant shift down, gentle flanger). Human phrasing, just enough metal.
#
# PUNCHLINE: Fred, the classic synthetic computer voice. It has to carry
# "HOLY - beep - CHIP!!" and it is deliberately more of a machine than the
# header. It also HAS to be an old-style voice - see below.
HDR_VOICE = "Daniel"
HDR_FX = ("asetrate=48000*0.94,aresample=48000,atempo=1.0638,"
          "flanger=delay=2:depth=3:regen=12:speed=0.4,"
          "aecho=0.9:0.9:55:0.18")
CHIP_VOICE = "Fred"

# DO NOT put a modern voice on the punchline. The low, dramatic delivery comes
# from the [[pbas]]/[[pmod]] commands in say(), and only the old synthesis
# voices (Fred, Ralph, Junior, Zarvox...) honour them. Modern ones such as
# Daniel silently ignore them - verified: identical audio with and without, so
# nothing is read aloud, but nothing is pitched either, and the punch lands
# flat on the DRAMA chain alone. The header can be modern precisely because it
# never relied on those commands for its character.

# --- levels: the mix the user approved on 2026-08-18 --------------------
MUSIC_LUFS = -38.0   # absolute, NOT a relative -12dB trim: robotz already
                     # sits near -16 LUFS, so a -12dB trim lands on -28 and
                     # changes nothing. Ask for the target you actually want.
HDR_LUFS = -13.0
CHIP_LUFS = -11.0
DUCK = "sidechaincompress=threshold=0.02:ratio=12:attack=15:release=340"
DRAMA = ("asetrate=48000*0.93,aresample=48000,"
         "aecho=0.85:0.88:130|340|620:0.32|0.20|0.10,"
         "acompressor=threshold=-18dB:ratio=3:attack=5:release=180,"
         "loudnorm=I=-13:TP=-1.5")
AF = ("aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo")

HDR_PAD_S = 0.35     # silence left at the end of the title card after the VO

# THE BEEP IS CENSORING A SWEAR WORD, so it has to last as long as the word it
# is covering. At 0.34s it read as a bleep of punctuation - a blip between two
# words rather than something hiding one. A broadcast censor tone also butts
# straight up against the surrounding speech; the silences that used to sit
# either side of it were what made it sound detached. Lengthened and tightened
# 2026-08-19. Note DRAMA slows everything ~7%, so the tone lands near 0.75s.
BEEP_S = 0.70
BEEP_DB = -9
# Widened again 2026-08-20: with Fred on the punchline the censor tone stopped
# reading clearly at 0.05/0.07. The brief for these is "short, just to notice" -
# enough air either side to hear the tone as its own event, not so much that it
# floats free of the words. Note DRAMA slows everything ~7%, so what is heard is
# nearer 0.19s than 0.18s.
BEEP_GAP_BEFORE = 0.18   # after HOLY, before the tone
BEEP_GAP_AFTER = 0.18    # after the tone, before CHIP

# --- "CHIIIP" ------------------------------------------------------------
# The punchline holds its vowel: "HOLY - beep - CHIIIP!!". It is produced by
# time-stretching the vowel of a normally spoken "CHIP!!", NOT by spelling it
# that way. Fred reads any doubled vowel in caps as letters - "CHIIIP!!" comes
# out "C-H-I-I-I-P" and runs 1.85s of spelling. Verified across spellings:
# CHIIIP/CHEEEP/CHIIP all spell out; CHIP/CHEEP/CHEAP/chip are spoken.
#
# CHIP_PBAS RAISED FROM 18 TO 80. Fred's pitch floor is about 44: pbas 0, 18, 30
# and 40 render byte-identical audio, so the old 18 was doing nothing at all and
# the line simply sat at Fred's lowest pitch. 80 is a real, audible lift.
# (HOLY keeps its low setting deliberately - only the last word rises.)
CHIP_WORD = "CHIP!!"
CHIP_PBAS = 80
CHIP_HOLD_S = 1.80       # target length for the whole stretched word
VOWEL_MIN_S = 0.10       # sanity floor for the detected vowel - see stretch_vowel
STRETCH_MAX = 10.0       # beyond this, time-stretch turns metallic

# --- bubble-reveal tones, added 2026-08-19 ------------------------------
# One tone per bubble as it appears, in PANELS 1 AND 2 ONLY. The last panel is
# left dry: that is where the punchline voice lands and a tone under it fights
# the joke. Every story is a 3-panel strip, so this is "every bubble except the
# final panel's" - but it is written as an explicit panel set, because the day
# a 4-panel strip shows up the right answer is to look at it, not to inherit a
# silent third panel by accident.
SFX_PANELS = {1, 2}
BLIP_HZ, BLIP_S = 1200.0, 0.07     # white bubble
BLOP_HZ, BLOP_S = 420.0, 0.11      # black bubble - lower AND longer, because
                                   # low-and-short reads as a thud, not a blop
BLIP_DB = BLOP_DB = -14.0          # ABSOLUTE peak dBFS - see tone()

# WHICH BUBBLES ARE BLACK IS MEASURED, NOT LOOKED UP. Nothing in the script
# records it, and a Left/Right rule would invert on any story whose palette
# fix_bubble_colors has flipped. Measure ink per row INSIDE the bubble's own
# silhouette - not its bounding box. The bounding box measure is not separable:
# across all 39 strips its widest natural gap is 0.046, because a black bubble
# packed with white lettering sinks to meet a white bubble packed with black
# lettering. Per-row silhouette ink leaves a 0.222-wide empty band at 0.548,
# with nothing between 0.437 and 0.659, and the bubbles either side of that gap
# were eyeballed against the art to confirm which is which.
INK_BLACK = 0.548


# THE PUNCHLINE VOICE IS ALWAYS AND ONLY "HOLY - beep - CHIP!!".
# Some final panels carry extra words (POOR FISHIES..., UNBEATABLE, DISGUSTING,
# BEING IS HARD!). We used to speak them; the TTS performs them badly - it reads
# them flat, right after a line that has been pitched and drenched in echo, so
# the tail undercuts the punch it is supposed to land. The words stay ON SCREEN
# where they read fine. Rule set by the user 2026-08-18: ignore them all.

SPOKEN = {"AGI": "A G I", "AI": "A I", "HQ": "Headquarters",
          "DEPTO": "Department", "INC": "Incorporated",
          "HEADQUARTER": "Headquarters"}
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
        "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path])
    return float(r.stdout.strip())


def two_digits(n):
    return ONES[n] if n < 20 else (TENS[n // 10] +
                                   ("" if n % 10 == 0 else " " + ONES[n % 10]))


def spoken_year(year):
    """2026 -> 'twenty twenty six'. Falls back to digits for anything odd."""
    s = str(year).strip()
    if not re.fullmatch(r"\d{4}", s):
        return s
    hi, lo = int(s[:2]), int(s[2:])
    return f"{two_digits(hi)} {two_digits(lo)}" if lo else f"{two_digits(hi)} hundred"


def spoken_title(title):
    return " ".join(SPOKEN.get(w.upper(), w.capitalize()) for w in title.split())


def header_text(script):
    b = script["banner"]
    return f"{spoken_title(b.get('title', ''))}. {spoken_year(b.get('year', ''))}."


# --------------------------------------------------------------- TTS ---
def say(text, out, rate, pbas, pmod, tmp, voice=None):
    aiff = os.path.join(tmp, os.path.basename(out) + ".aiff")
    run(["say", "-v", voice or CHIP_VOICE, "-r", str(rate),
         f"[[pbas {pbas}]][[pmod {pmod}]][[volm 1.0]] {text}", "-o", aiff])
    run(["ffmpeg", "-y", "-v", "error", "-i", aiff, "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02:"
         "stop_periods=-1:stop_threshold=-45dB:stop_duration=0.06," + AF, out])
    return out


def build_header_vo(script, tmp):
    """Spoken title card: HDR_VOICE, then HDR_FX.

    THE TREATMENT IS BAKED IN BEFORE THE LENGTH IS MEASURED. The title card is
    stretched to fit this clip (see the module docstring), and HDR_FX changes
    the duration - asetrate slows it and atempo pulls it back, which do not
    cancel to the sample. Measuring the dry take would size the card to the
    wrong number and clip the end of the voice.
    """
    out = os.path.join(tmp, "hdr.wav")
    aiff = os.path.join(tmp, "hdr.aiff")
    run(["say", "-v", HDR_VOICE, "-r", "145",
         f"[[pbas 40]] {header_text(script)}", "-o", aiff])
    # AF COMES BEFORE HDR_FX, NOT AFTER. `say` writes AIFF at 22050Hz, and
    # asetrate sets an ABSOLUTE rate - so asetrate=48000*0.94 on a 22050 stream
    # plays it 2.05x FASTER rather than 1.06x slower. That cut the spoken title
    # to 1.14s, and because the card is sized from this measurement the whole
    # reel shrank with it. AF normalises to 48000 first, which is the rate the
    # 0.94 factor is written against.
    run(["ffmpeg", "-y", "-v", "error", "-i", aiff, "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:"
         "stop_periods=-1:stop_threshold=-45dB:stop_duration=0.3,"
         + AF + "," + HDR_FX + "," + AF, out])
    return out, probe(out)


def vowel_span(path, tmp):
    """(start, end) of the longest sustained high-energy run: the vowel.

    Measured rather than hardcoded, because the window moves with the pitch -
    at pbas 50 the vowel starts at 0.160s, at pbas 80 at 0.225s.
    """
    mono = os.path.join(tmp, "vowel.probe.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", path, "-ac", "1", "-ar", "48000",
         "-c:a", "pcm_s16le", mono])
    w = wave.open(mono)
    sr = w.getframerate()
    d = array.array("h")
    d.frombytes(w.readframes(w.getnframes()))
    w.close()

    step = int(sr * 0.005)
    prof = [math.sqrt(sum(x * x for x in d[i:i + step]) / step)
            for i in range(0, len(d) - step, step)]
    if not prof or max(prof) <= 0:
        return None
    thr = 0.5 * max(prof)
    best = (0, 0, 0)
    i = 0
    while i < len(prof):
        if prof[i] >= thr:
            j = i
            while j < len(prof) and prof[j] >= thr:
                j += 1
            if j - i > best[0]:
                best = (j - i, i, j)
            i = j
        else:
            i += 1
    return (best[1] * 0.005, best[2] * 0.005) if best[0] else None


def atempo_chain(factor):
    """atempo accepts 0.5-100 per instance; chain for anything slower."""
    out = []
    while factor < 0.5:
        out.append(0.5)
        factor /= 0.5
    out.append(factor)
    return ",".join(f"atempo={x:.4f}" for x in out)


def stretch_vowel(src, dst, target, tmp):
    """Hold the vowel so "CHIP" becomes "CHIIIP", leaving the ch and p intact.

    atempo is pitch-preserving, so the vowel SUSTAINS instead of sagging - which
    is the whole point; asetrate would drop the pitch we just raised.

    GUARDED, because the detector can misfire. On one audition it caught only an
    80ms window and asked for a 15.5x stretch, which smears into a metallic
    warble. A vowel shorter than VOWEL_MIN_S, or a factor past STRETCH_MAX, means
    the measurement is not to be trusted: stretch as far as is safe and carry on
    rather than shipping a warble. Returns the factor actually used.
    """
    span = vowel_span(src, tmp)
    if not span or (span[1] - span[0]) < VOWEL_MIN_S:
        return None
    v0, v1 = span
    vlen = v1 - v0
    mult = min(STRETCH_MAX, (vlen + max(0.0, target - probe(src))) / vlen)
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex",
         f"[0:a]atrim=0:{v0},asetpts=N/SR/TB[a];"
         f"[0:a]atrim={v0}:{v1},asetpts=N/SR/TB,{atempo_chain(1.0 / mult)}[b];"
         f"[0:a]atrim={v1},asetpts=N/SR/TB[c];"
         f"[a][b][c]concat=n=3:v=0:a=1,{AF}[o]", "-map", "[o]", dst])
    return mult


def build_chip_vo(tmp):
    """HOLY - 1kHz censor beep - CHIP!!, then the drama chain. Nothing else.

    Identical for every story: the final panel's extra words are never spoken.
    """
    say("HOLY", os.path.join(tmp, "holy.wav"), 135, 20, 160, tmp)

    dry = say(CHIP_WORD, os.path.join(tmp, "chip.dry.wav"), 95, CHIP_PBAS,
              175, tmp)
    chip = os.path.join(tmp, "chip.wav")
    if stretch_vowel(dry, chip, CHIP_HOLD_S, tmp) is None:
        # detector failed - ship the unstretched word rather than a warble
        chip = dry

    beep = os.path.join(tmp, "beep.wav")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         f"sine=frequency=1000:duration={BEEP_S}:sample_rate=48000", "-af",
         f"afade=t=in:d=0.012,afade=t=out:st={BEEP_S - 0.012:.3f}:d=0.012,"
         f"volume={BEEP_DB}dB", "-ac", "2", beep])

    ins, parts, n = [], [], 0
    for src, pad in ((os.path.join(tmp, "holy.wav"), BEEP_GAP_BEFORE),
                     (beep, BEEP_GAP_AFTER), (chip, 0.0)):
        ins += ["-i", src]
        parts.append(f"[{n}:a]{AF}" + (f",apad=pad_dur={pad}" if pad else "") +
                     f"[p{n}];")
        n += 1

    labels = "".join(f"[p{i}]" for i in range(n))
    out = os.path.join(tmp, "chipline.wav")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex",
         "".join(parts) + f"{labels}concat=n={n}:v=0:a=1,{DRAMA}[o]",
         "-map", "[o]", out])
    return out, probe(out)


# -------------------------------------------------------- reveal tones ---
def peak_db(path):
    """Measured peak of a file in dBFS, or None.

    astats reports on stderr at INFO level, so this cannot use run(): that
    passes -v error everywhere else and would hand back an empty string.
    """
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "astats",
                        "-f", "null", "-"], capture_output=True, text=True)
    peaks = [float(l.split(":")[-1]) for l in (r.stderr or "").splitlines()
             if "Peak level dB" in l]
    return max(peaks) if peaks else None


def tone(path, hz, dur, db, tmp):
    """One sine with a fast attack and a long decay, so it plucks.

    `db` IS THE ABSOLUTE PEAK WANTED, and it is reached by measuring, not by
    trimming. `volume=-14dB` on the lavfi sine does NOT give a -14dBFS tone:
    ffmpeg emits sine at -18.06dBFS (amplitude ~1/8, the same at any duration)
    and loses a further 3dB rematrixing mono to stereo. The first cut of this
    asked for -20dB, got -41dB, and was inaudible - the music bed sits near
    -35dB RMS. Both losses belong to the ffmpeg build, so they are measured and
    cancelled rather than baked in as a magic 21dB.

    The same trap is live in BEEP_DB above, which reads -9dB and delivers about
    -30dBFS. It happens not to matter: DRAMA ends in loudnorm, so the punchline
    is renormalised as a whole and the beep keeps its level relative to HOLY and
    CHIP. Worth knowing before anyone "corrects" that number.
    """
    hold = dur * 0.25
    raw = os.path.join(tmp, os.path.basename(path) + ".raw.wav")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         f"sine=frequency={hz}:duration={dur}:sample_rate=48000", "-af",
         f"afade=t=in:d=0.004,afade=t=out:st={hold:.4f}:d={dur - hold:.4f},"
         + AF, "-ac", "2", raw])

    got = peak_db(raw)
    trim = 0.0 if got is None else db - got
    run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
         f"volume={trim:.2f}dB,{AF}", path])

    # a tone that is present but 21dB too quiet looks right everywhere except
    # the ear, so this is checked rather than assumed.
    final = peak_db(path)
    if final is not None and abs(final - db) > 0.5:
        raise SystemExit(f"  tone {hz:.0f}Hz asked for {db}dB peak, measures "
                         f"{final:.1f}dB after a {trim:+.1f}dB correction")
    return path


def bubble_is_black(el):
    """Ink per row inside the bubble's own silhouette. See INK_BLACK."""
    rows = {}
    for (y, s, e) in el.bubble_runs:
        rows.setdefault(y, []).append((s, e))
    if not rows:
        return False, 0.0
    ink = span = 0
    for rr in rows.values():
        ink += sum(e - s + 1 for s, e in rr)
        span += max(e for _, e in rr) - min(s for s, _ in rr) + 1
    frac = ink / span
    return frac > INK_BLACK, frac


def panel_of(el, panel_spans):
    """Which panel a bubble sits in, by the top of its bubble art."""
    runs = el.bubble_runs or el.runs
    y0 = min(r[0] for r in runs)
    for k, (a, b) in enumerate(panel_spans):
        if a <= y0 <= b:
            return k + 1
    return None


def sfx_events(im, script, seq, starts, blip, blop):
    """[(when, wav)] for every bubble revealed in SFX_PANELS, plus a log."""
    W, H = im.size
    rows = sg.make_runs(im.convert("L").load(), W, H)
    _, panel_spans, _ = sg.page_structure(rows, W, H, len(script["scenes"]))

    events, log = [], []
    for i, el in enumerate(seq):
        if el.kind != "bubble":
            continue
        p = panel_of(el, panel_spans)
        if p not in SFX_PANELS:
            continue
        black, frac = bubble_is_black(el)
        # starts[] is indexed over ["cover"] + seq, hence the +1
        events.append((starts[i + 1], blop if black else blip))
        log.append(f"      panel {p}  {starts[i + 1]:5.2f}s  ink {frac:.2f}  "
                   f"{'blop' if black else 'blip'}")
    return events, log


def build_sfx_track(events, dur, tmp):
    """One full-length track carrying every tone at its reveal time."""
    ins, parts = [], []
    for i, (t, wav) in enumerate(events):
        ins += ["-i", wav]
        parts.append(f"[{i}:a]{AF},adelay={max(0, round(t * 1000))}:all=1[s{i}];")
    labels = "".join(f"[s{i}]" for i in range(len(events)))
    out = os.path.join(tmp, "sfx.wav")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex",
         "".join(parts) + f"{labels}amix=inputs={len(events)}:duration=longest:"
         f"normalize=0,apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[o]",
         "-map", "[o]", out])
    return out


# ------------------------------------------------------------- video ---
def frame_starts(durs, fps=sg.REEL_FPS):
    """Replicate save_mp4's per-element rounding. Returns (starts_s, total_s)."""
    starts, n = [], 0
    for ms in durs:
        starts.append(n / fps)
        n += max(1, round(fps * ms / 1000.0))
    return starts, n / fps


def plan(hc, header_extra, footer_extra=0):
    """Segment and time the Reel WITHOUT encoding it.

    Encoding is the slow part (~800 frames at 1080x1920), and we need the
    timeline before we can know how much room the punchline voice has. So the
    cheap half runs first and the caller encodes once, with the final numbers.

    Ten of the 39 strips draw two script lines inside one bubble, which
    --strict refuses. That is a real drawing/script mismatch, not a bug, and
    story_gif's grouping fallback handles it correctly - the two lines simply
    reveal together. We try strict, fall back, and report which is which.
    """
    im, script = sg.load(hc)
    nudges = sg.load_timing(hc)
    grouped = False
    try:
        seq = sg.segment(im, script, strict=True, warn=lambda *a: None,
                         groups=nudges.get("groups"))
    except sg.SegmentError:
        seq = sg.segment(im, script, strict=False, warn=lambda *a: None,
                         groups=nudges.get("groups"))
        grouped = True
    nudges["header"] = max(int(nudges.get("header", 0)), header_extra)
    sg.apply_nudges(seq, nudges)
    sg.apply_beat(seq, sg.BEAT_MS)
    reel_durs = sg.durations(seq, sg.FOOTER_REEL_MS + footer_extra)
    return im, script, seq, [sg.COVER_MS] + reel_durs, grouped


def build_reel(hc, im, script, seq, durs):
    """Encode the silent Reel. Mirrors story_gif.main()'s --reel path."""
    frames = sg.build_frames(im, seq, 720)
    cover = sg.build_cover(im, seq, hc, len(script["scenes"]),
                           size=(sg.REEL_W, sg.REEL_H)).convert("L")
    os.makedirs(sg.ANIMDIR, exist_ok=True)
    sg.build_cover(im, seq, hc, len(script["scenes"]),
                   size=(sg.REEL_W, sg.REEL_H)).save(
                       os.path.join(sg.ANIMDIR, hc + ".cover.jpg"), quality=92)

    out = os.path.join(sg.VIDEODIR, hc + ".buildup.mp4")
    os.makedirs(sg.VIDEODIR, exist_ok=True)
    sg.save_mp4([cover] + frames, durs, out, reel=True)
    return out


def verify_offsets(video, total_s):
    real = probe(video)
    if abs(real - total_s) > 1.0 / sg.REEL_FPS:
        raise SystemExit(f"  frame math disagrees with the encode: computed "
                         f"{total_s:.3f}s, file is {real:.3f}s")
    return real


# --------------------------------------------------------------- mix ---
def mix(video, dur, hdr_wav, hdr_at, chip_wav, chip_at, out, music, music_lufs,
        sfx_wav=None):
    """Bed + both voices (+ the reveal tones), ducked and normalised.

    The tones are added AFTER the sidechain, never into it: they are 70-110ms
    long, and letting them key the ducker makes the bed flutter on every bubble
    for no gain - they already sit ~20dB over it.
    """
    sfx = f"[4:a]{AF}[sfx];" if sfx_wav else ""
    tail = "[musd][vox1][sfx]amix=inputs=3" if sfx_wav else "[musd][vox1]amix=inputs=2"
    fc = (
        f"[1:a]{AF},atrim=0:{dur:.3f},asetpts=N/SR/TB,"
        f"loudnorm=I={music_lufs}:TP=-6[mus];"
        f"[2:a]{AF},loudnorm=I={HDR_LUFS}:TP=-1.5,"
        f"adelay={round(hdr_at * 1000)}:all=1[hdr];"
        f"[3:a]{AF},loudnorm=I={CHIP_LUFS}:TP=-1.5,"
        f"adelay={round(chip_at * 1000)}:all=1[chip];"
        + sfx +
        f"[hdr][chip]amix=inputs=2:duration=longest:normalize=0,"
        f"apad=whole_dur={dur:.3f},asplit=2[vox1][vox2];"
        f"[mus][vox2]{DUCK}:makeup=1[musd];"
        + tail +
        f":duration=first:normalize=0,"
        f"alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5[a]"
    )
    run(["ffmpeg", "-y", "-v", "error", "-i", video,
         "-stream_loop", "-1", "-i", music, "-i", hdr_wav, "-i", chip_wav,
         *(["-i", sfx_wav] if sfx_wav else []),
         "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", out])
    return out


def one(hc, music, music_lufs, out_dir, sfx=True):
    with tempfile.TemporaryDirectory(prefix="reelvo") as tmp:
        _, script = sg.load(hc)

        # Both voices are generated first: their lengths decide how long the
        # title card and the footer need to be, so the video is encoded once
        # with the final timings rather than encoded and then patched.
        hdr_wav, hdr_len = build_header_vo(script, tmp)
        chip_wav, chip_len = build_chip_vo(tmp)

        need = max(0, math.ceil((hdr_len + HDR_PAD_S) * 1000) - sg.HEADER_MS)

        im, script, seq, durs, grouped = plan(hc, need)
        starts, total = frame_starts(durs)
        kinds = ["cover"] + [el.kind for el in seq]
        chip_i = max(i for i, k in enumerate(kinds) if k == "bubble")
        room = total - starts[chip_i]

        # Kept as a guard even though the punchline is now a fixed ~2.7s: a
        # short final bubble on a future story could still leave less room than
        # the line needs, and clipping the punch is never the right answer.
        grow = 0
        if chip_len > room:
            grow = math.ceil((chip_len - room + 0.3) * 1000)
            im, script, seq, durs, grouped = plan(hc, need, footer_extra=grow)
            starts, total = frame_starts(durs)
            room = total - starts[chip_i]

        sfx_wav, ev_log = None, []
        if sfx:
            blip = tone(os.path.join(tmp, "blip.wav"), BLIP_HZ, BLIP_S,
                        BLIP_DB, tmp)
            blop = tone(os.path.join(tmp, "blop.wav"), BLOP_HZ, BLOP_S,
                        BLOP_DB, tmp)
            events, ev_log = sfx_events(im, script, seq, starts, blip, blop)
            if events:
                sfx_wav = build_sfx_track(events, total, tmp)
            else:
                ev_log = [f"      ! no bubbles in panels "
                          f"{sorted(SFX_PANELS)} - no tones"]

        video = build_reel(hc, im, script, seq, durs)
        verify_offsets(video, total)
        hdr_at, chip_at = starts[kinds.index("header")], starts[chip_i]

        out = os.path.join(out_dir, hc + ".reel.mp4")
        mix(video, total, hdr_wav, hdr_at, chip_wav, chip_at, out,
            music, music_lufs, sfx_wav)

        notes = "".join([f"  +{grow}ms footer" if grow else "",
                         "  [grouped]" if grouped else "",
                         f"  {len(ev_log)} tones" if sfx_wav else ""])
        print(f"  {hc}  {total:5.1f}s   header {hdr_at:5.2f}s ({hdr_len:.2f}s "
              f"vo, +{need}ms card)   chip {chip_at:5.2f}s "
              f"({chip_len:.2f}s/{room:.2f}s room){notes}")
        for line in ev_log:
            print(line)
        return out, grouped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--music", default=MUSIC)
    ap.add_argument("--music-lufs", type=float, default=MUSIC_LUFS)
    ap.add_argument("--out-dir", default=sg.VIDEODIR)
    ap.add_argument("--no-sfx", action="store_true",
                    help="skip the blip/blop bubble-reveal tones")
    a = ap.parse_args()

    ids = sg.story_ids() if a.all else [a.story.upper()] if a.story else None
    if not ids:
        ap.error("give a story id or --all")

    os.makedirs(a.out_dir, exist_ok=True)
    ok, skipped, failed, grouped = [], [], [], []
    for hc in ids:
        dst = os.path.join(a.out_dir, hc + ".reel.mp4")
        if a.skip_existing and os.path.exists(dst):
            skipped.append(hc); continue
        try:
            _, grp = one(hc, os.path.expanduser(a.music), a.music_lufs,
                         a.out_dir, sfx=not a.no_sfx)
            ok.append(hc)
            if grp:
                grouped.append(hc)
        except Exception as e:
            failed.append((hc, str(e).strip().splitlines()[-1][:120]))
            print(f"  {hc}  FAILED: {failed[-1][1]}")

    print(f"\nbuilt {len(ok)}   skipped {len(skipped)}   failed {len(failed)}")
    if grouped:
        print(f"  two script lines share one bubble (revealed together) on: "
              f"{' '.join(grouped)}")
    for hc, err in failed:
        print(f"  {hc}: {err}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

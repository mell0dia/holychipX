#!/usr/bin/env python3
"""reel_vo.py - build a Reel with the approved voice-over format.

Three audio elements and nothing else:

  1. a TTS header read over the title card ("A G I Headquarters. Twenty
     twenty six.")
  2. the music bed, alone, through the whole build-up
  3. a dramatic TTS "HOLY - beep - CHIP!!" on the final bubble

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
import argparse, math, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_gif as sg
from PIL import Image

HC = os.path.expanduser("~/holy-chip")
MUSIC = os.path.join(HC, "audio", "robotz.mp4")
VOICE = "Zarvox"

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
def say(text, out, rate, pbas, pmod, tmp):
    aiff = os.path.join(tmp, os.path.basename(out) + ".aiff")
    run(["say", "-v", VOICE, "-r", str(rate),
         f"[[pbas {pbas}]][[pmod {pmod}]][[volm 1.0]] {text}", "-o", aiff])
    run(["ffmpeg", "-y", "-v", "error", "-i", aiff, "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02:"
         "stop_periods=-1:stop_threshold=-45dB:stop_duration=0.06," + AF, out])
    return out


def build_header_vo(script, tmp):
    out = os.path.join(tmp, "hdr.wav")
    aiff = os.path.join(tmp, "hdr.aiff")
    run(["say", "-v", VOICE, "-r", "145",
         f"[[pbas 40]] {header_text(script)}", "-o", aiff])
    run(["ffmpeg", "-y", "-v", "error", "-i", aiff, "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:"
         "stop_periods=-1:stop_threshold=-45dB:stop_duration=0.3," + AF, out])
    return out, probe(out)


def build_chip_vo(tmp):
    """HOLY - 1kHz censor beep - CHIP!!, then the drama chain. Nothing else.

    Identical for every story: the final panel's extra words are never spoken.
    """
    say("HOLY", os.path.join(tmp, "holy.wav"), 135, 20, 160, tmp)
    say("CHIP!!", os.path.join(tmp, "chip.wav"), 95, 18, 175, tmp)
    beep = os.path.join(tmp, "beep.wav")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=1000:duration=0.34:sample_rate=48000", "-af",
         "afade=t=in:d=0.012,afade=t=out:st=0.328:d=0.012,volume=-9dB",
         "-ac", "2", beep])

    ins, parts, n = [], [], 0
    for src, pad in ((os.path.join(tmp, "holy.wav"), 0.18),
                     (beep, 0.22), (os.path.join(tmp, "chip.wav"), 0.0)):
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
def mix(video, dur, hdr_wav, hdr_at, chip_wav, chip_at, out, music, music_lufs):
    fc = (
        f"[1:a]{AF},atrim=0:{dur:.3f},asetpts=N/SR/TB,"
        f"loudnorm=I={music_lufs}:TP=-6[mus];"
        f"[2:a]{AF},loudnorm=I={HDR_LUFS}:TP=-1.5,"
        f"adelay={round(hdr_at * 1000)}:all=1[hdr];"
        f"[3:a]{AF},loudnorm=I={CHIP_LUFS}:TP=-1.5,"
        f"adelay={round(chip_at * 1000)}:all=1[chip];"
        f"[hdr][chip]amix=inputs=2:duration=longest:normalize=0,"
        f"apad=whole_dur={dur:.3f},asplit=2[vox1][vox2];"
        f"[mus][vox2]{DUCK}:makeup=1[musd];"
        f"[musd][vox1]amix=inputs=2:duration=first:normalize=0,"
        f"alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5[a]"
    )
    run(["ffmpeg", "-y", "-v", "error", "-i", video,
         "-stream_loop", "-1", "-i", music, "-i", hdr_wav, "-i", chip_wav,
         "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", out])
    return out


def one(hc, music, music_lufs, out_dir):
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

        video = build_reel(hc, im, script, seq, durs)
        verify_offsets(video, total)
        hdr_at, chip_at = starts[kinds.index("header")], starts[chip_i]

        out = os.path.join(out_dir, hc + ".reel.mp4")
        mix(video, total, hdr_wav, hdr_at, chip_wav, chip_at, out,
            music, music_lufs)

        notes = "".join([f"  +{grow}ms footer" if grow else "",
                         "  [grouped]" if grouped else ""])
        print(f"  {hc}  {total:5.1f}s   header {hdr_at:5.2f}s ({hdr_len:.2f}s "
              f"vo, +{need}ms card)   chip {chip_at:5.2f}s "
              f"({chip_len:.2f}s/{room:.2f}s room){notes}")
        return out, grouped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--music", default=MUSIC)
    ap.add_argument("--music-lufs", type=float, default=MUSIC_LUFS)
    ap.add_argument("--out-dir", default=sg.VIDEODIR)
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
                         a.out_dir)
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

#!/usr/bin/env python3
"""story_mix.py — lay the recorded voice-over and a music bed onto the Reel.

    story_mix.py HC030
    story_mix.py HC030 --music ~/Downloads/track.mp3
    story_mix.py HC030 --music-start 39 --music-db -12 --duck-db -11

Inputs
    videos/HC###.buildup.mp4   the silent Reel from story_gif.py --reel
    voice/HC###.vo.(m4a|wav)   the take chosen in voice_studio.py
    voice/HC###.vo.json        the timing that take was performed to
    --music                    any audio file; used from --music-start

Output
    videos/HC###.reel.mp4      1080x1920, voice + ducked music, ready to post

ALIGNMENT. Two offsets, both derived, never assumed:

  - the studio records a lead-in (blanked to silence) before the animation's
    first frame, so the voice file's t=lead is the animation's t=0. Read from
    the .vo.json and trimmed here.
  - the Reel now opens on a title card, so the animation no longer starts at
    video t=0. The card's length is (video duration - the animation length the
    take was performed to), and the voice is delayed by exactly that. Get this
    wrong and every line lands early.

MUSIC LEVEL. Flat by default. Sidechain ducking is available via --duck, but it
is NOT the default: pulling the bed down under each line means it swells back up
in every pause between lines, which reads as the music surging at you whenever
you stop talking. A constant bed set at the ducked level is steadier and keeps
the dialogue just as clear.
"""
import os, sys, json, argparse, subprocess

HC = os.path.expanduser("~/holy-chip")
SITE = os.path.join(HC, "website/holy-chip-site")
VIDEODIR = os.path.join(SITE, "videos")
VOICE = os.path.join(HC, "voice")
SR = 44100


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + r.stderr[-1500:])
    return r


def probe(path, entry="format=duration"):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", entry,
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return r.stdout.strip()


def find_voice(story):
    for ext in (".m4a", ".wav"):
        p = os.path.join(VOICE, story + ".vo" + ext)
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--music")
    ap.add_argument("--music-start", type=float, default=0.0,
                    help="seconds into the track to start (default 0)")
    # -10 is where the bed actually sat while the voice was present under the old
    # ducking setup (-4 bed, -6 duck). Holding it there constantly removes the
    # swell in the gaps without making the music any louder over the dialogue.
    # Pass negative values as --music-db=-12 (with the equals sign) - argparse
    # reads a bare -12 as a flag.
    # Settled by ear over several passes: -10 too loud, -22 too faint, -18 close,
    # -15 is the touch-up. Sits ~14 dB under the voice - clearly present, still
    # never competing with the dialogue.
    ap.add_argument("--music-db", type=float, default=-15.0,
                    help="music level, constant (default -15 - a bed, not a duet)")
    ap.add_argument("--duck", action="store_true",
                    help="duck the music under the voice instead of a flat bed")
    ap.add_argument("--duck-db", type=float, default=-6.0,
                    help="with --duck: extra reduction while the voice plays")
    ap.add_argument("--fade-in", type=float, default=0.4)
    ap.add_argument("--fade-out", type=float, default=1.8)
    ap.add_argument("--out")
    a = ap.parse_args()

    story = a.story.upper()
    video = os.path.join(VIDEODIR, story + ".buildup.mp4")
    if not os.path.exists(video):
        sys.exit(f"no {video} - run: story_gif.py {story} --reel")
    voice = find_voice(story)
    if not voice:
        sys.exit(f"no {VOICE}/{story}.vo.* - pick a take in voice_studio.py")

    vdur = float(probe(video))
    lead = 3.0
    meta_p = os.path.join(VOICE, story + ".vo.json")
    if os.path.exists(meta_p):
        try:
            with open(meta_p) as fh:
                lead = json.load(fh).get("lead", 3000) / 1000.0
        except Exception:
            pass

    # the take was performed to the animation alone; anything the video has
    # beyond that is the title card in front of it
    anim = 0.0
    if os.path.exists(meta_p):
        try:
            with open(meta_p) as fh:
                anim = sum(c["ms"] for c in json.load(fh).get("cues", [])) / 1000.0
        except Exception:
            anim = 0.0
    cover = max(0.0, round(vdur - anim, 3)) if anim else 0.0

    print(f"{story}")
    print(f"  video  {vdur:6.2f}s   {video}")
    if cover:
        print(f"  cover  {cover:6.2f}s   title card in front - voice delayed to match")
    print(f"  voice  {float(probe(voice)):6.2f}s   {voice}   (lead {lead:.2f}s trimmed)")

    ins = ["-i", video, "-i", voice]
    # voice: drop the lead so t=0 lines up with the first frame, then fit the video
    delay_ms = int(round(cover * 1000))
    fc = [f"[1:a]atrim=start={lead:.3f},asetpts=N/SR/TB,"
          f"aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,"
          # reset the timestamps AFTER the delay: adelay shifts PTS, and the
          # atrim window below is measured on PTS, so without this it swallows
          # exactly the delay and the track comes up short by the cover length
          + (f"adelay={delay_ms}|{delay_ms},asetpts=N/SR/TB," if delay_ms else "")
          + f"apad,atrim=0:{vdur:.3f},asetpts=N/SR/TB[vo]"]

    if a.music:
        music = os.path.expanduser(a.music)
        if not os.path.exists(music):
            sys.exit(f"no such music file: {music}")
        mdur = float(probe(music))
        print(f"  music  {mdur:6.2f}s   {music}")
        print(f"         using {a.music_start:.1f}s -> {a.music_start + vdur:.1f}s "
              f"at a constant {a.music_db:+.0f} dB"
              if not a.duck else
              f"         using {a.music_start:.1f}s -> {a.music_start + vdur:.1f}s "
              f"at {a.music_db:+.0f} dB, ducking {a.duck_db:+.0f} dB under the voice")
        ins += ["-i", music]
        fc.append(
            f"[2:a]atrim=start={a.music_start:.3f}:"
            f"end={a.music_start + vdur:.3f},asetpts=N/SR/TB,"
            f"aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad,atrim=0:{vdur:.3f},asetpts=N/SR/TB,"
            # The track's own dynamics swing ~20 dB across a 27s window, which
            # reads as the bed surging even with the gain held constant. Compress
            # it hard so the bed sits still underneath the voice; THEN set level.
            # NB makeup is a LINEAR multiplier here, not dB - makeup=6 is ~+15 dB
            # and drove the whole mix into the limiter.
            f"acompressor=threshold=-24dB:ratio=6:attack=25:release=350:makeup=2,"
            f"volume={a.music_db}dB,"
            f"afade=t=in:st=0:d={a.fade_in},"
            f"afade=t=out:st={max(0, vdur - a.fade_out):.3f}:d={a.fade_out}[mu]")
        if a.duck:
            # split the voice: one copy to hear, one to key the ducking
            fc.append("[vo]asplit=2[vo1][key]")
            fc.append(
                f"[mu][key]sidechaincompress=threshold=0.015:ratio=12:"
                f"attack=8:release=320:makeup=1:level_sc=1[muD]")
            fc.append(f"[muD]volume={a.duck_db}dB[muQ]")
        else:
            # no sidechain at all - the bed never moves
            fc.append("[vo]anull[vo1]")
            fc.append("[mu]anull[muQ]")
        fc.append("[vo1][muQ]amix=inputs=2:duration=first:normalize=0,"
                  "alimiter=limit=0.95[aout]")
    else:
        print("  music  (none)")
        fc.append("[vo]alimiter=limit=0.95[aout]")

    out = a.out or os.path.join(VIDEODIR, story + ".reel.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", *ins,
         "-filter_complex", ";".join(fc),
         "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", out])

    print(f"\n-> {out}  ({os.path.getsize(out) / 1024:.0f} KB, "
          f"{float(probe(out)):.2f}s)")
    print(f"   public: https://holy-chip.com/videos/{story}.reel.mp4")


if __name__ == "__main__":
    main()

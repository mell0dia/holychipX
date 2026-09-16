#!/usr/bin/env python3
"""reel_static.py - the simple Reel: one still image, two spoken lines.

Replaces the frame-by-frame build-up (reel_vo.py) with what the user asked for
on 2026-09-09:

    show the full comic, say the header, wait 18 seconds, say HOLY CHIP.

Nothing reveals, nothing animates. The viewer reads the strip at their own pace
during the hold, and the punchline voice lands at the end.

    reel_static.py HC040                  # one story
    reel_static.py --all                  # every story that has artwork
    reel_static.py HC040 --hold 20        # longer reading pause

WHAT THIS DROPS, and why none of it is missed: panel segmentation, per-element
frame timing, the frame-by-frame offset verification, and the blip/blop bubble
tones. All of that existed to reveal bubbles one at a time. With a static image
there are no reveals, so HC040's panel-2 segmentation trouble - fused bubbles
and a mouth read as a bubble - stops mattering entirely. It is not fixed, it is
irrelevant here.

WHAT IT KEEPS: both voices (Daniel + treatment on the header, Fred on the
punchline), the music bed, the ducking, and the final loudness. Those are
reel_vo's and are imported rather than copied.

THE FIRST FRAME IS THE THUMBNAIL. Meta grabs it for the feed, which is why the
old build-up opened on the .pre teaser instead of the comic - opening on the
full strip puts HOLY CHIP in the thumbnail and spoils the joke before anyone
taps. --cover pre uses the teaser for the opening seconds where one exists.
"""
import argparse, math, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_gif as sg
import reel_vo as rv
from PIL import Image

HOLD_S = 18.0            # reading pause between the header and the punchline
TAIL_S = 0.6             # air after the punchline so it does not cut dead
COVER_S = 1.6            # how long the .pre teaser holds, when used


def canvas(img, top=None, w=sg.REEL_W, h=sg.REEL_H):
    """Fit the page onto the Reel canvas on black, matching the old builder.

    The comic is 896x1200 (3:4) and the Reel is 1080x1920 (9:16), so it scales
    to the width and leaves bars. Black is deliberate: the page already carries
    a black frame, so the bars read as part of the artwork.

    VERTICAL PLACEMENT IS NOT CENTRED FOR THE COMIC. story_gif.reel_canvas
    pastes it at REEL_TOP=150, which leaves 324px clear at the bottom - that is
    where Instagram lays its caption, handle and buttons over the video. Centring
    it (237px each side) pushes the last panel down under that furniture. The
    teaser IS centred, matching build_cover, because it is a short wide band.
    """
    page = Image.new("RGB", (w, h), (0, 0, 0))
    iw, ih = img.size
    s = min(w / iw, h / ih)
    r = img.convert("RGB").resize((int(iw * s), int(ih * s)), Image.LANCZOS)
    y = (h - r.height) // 2 if top is None else top
    page.paste(r, ((w - r.width) // 2, y))
    return page


def build_video(hc, total, cover, tmp):
    """A still held for `total` seconds - optionally opening on the teaser.

    THE SILENT INTERMEDIATE MUST STAY IN tmp. It used to be written to
    sg.VIDEODIR/HC###.reel.mp4, which is the SAME PATH the finished Reel is
    written to whenever --out-dir is left at its default. ffmpeg cannot read and
    write one file in a single pass, so the mix failed on every story - and the
    silent intermediate was already sitting at the destination, leaving all 40
    Reels on disk with no audio track at all. Instagram rejects those outright.
    It only ever worked under test because --out-dir pointed somewhere else.
    """
    im, _ = sg.load(hc)
    main = os.path.join(tmp, "main.png")
    canvas(im, top=sg.REEL_TOP).save(main)

    out = os.path.join(tmp, hc + ".silent.mp4")

    pre_path = os.path.join(sg.STORIES, hc + ".pre.png")
    use_pre = cover == "pre" and os.path.exists(pre_path)
    if use_pre:
        first = os.path.join(tmp, "cover.png")
        canvas(Image.open(pre_path)).save(first)   # centred, as build_cover does
        rv.run(["ffmpeg", "-y", "-v", "error",
                "-loop", "1", "-t", f"{COVER_S:.3f}", "-i", first,
                "-loop", "1", "-t", f"{total - COVER_S:.3f}", "-i", main,
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-r", str(sg.REEL_FPS),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out])
    else:
        rv.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", main,
                "-t", f"{total:.3f}", "-r", str(sg.REEL_FPS),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out])
    return out, use_pre


def one(hc, music, music_lufs, hold, cover, out_dir):
    with tempfile.TemporaryDirectory(prefix="reelstatic") as tmp:
        _, script = sg.load(hc)
        hdr_wav, hdr_len = rv.build_header_vo(script, tmp)
        chip_wav, chip_len = rv.build_chip_vo(tmp)

        chip_at = hdr_len + hold
        total = chip_at + chip_len + TAIL_S

        silent, used_pre = build_video(hc, total, cover, tmp)
        out = os.path.join(out_dir, hc + ".reel.mp4")
        rv.mix(silent, total, hdr_wav, 0.0, chip_wav, chip_at, out,
               music, music_lufs)

        print(f"  {hc}  {total:5.1f}s   header 0.00-{hdr_len:.2f}s   "
              f"hold {hold:.0f}s   chip {chip_at:.2f}-{chip_at + chip_len:.2f}s"
              + ("   [.pre cover]" if used_pre else "   [opens on the comic]"))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--hold", type=float, default=HOLD_S)
    ap.add_argument("--cover", choices=("pre", "comic"), default="pre",
                    help="'pre' opens on the teaser where one exists so the "
                         "punchline is not the feed thumbnail")
    ap.add_argument("--music", default=rv.MUSIC)
    ap.add_argument("--music-lufs", type=float, default=rv.MUSIC_LUFS)
    ap.add_argument("--out-dir", default=sg.VIDEODIR)
    a = ap.parse_args()

    ids = sg.story_ids() if a.all else [a.story.upper()] if a.story else None
    if not ids:
        ap.error("give a story id or --all")
    os.makedirs(a.out_dir, exist_ok=True)

    ok, failed = [], []
    for hc in ids:
        try:
            one(hc, os.path.expanduser(a.music), a.music_lufs, a.hold,
                a.cover, a.out_dir)
            ok.append(hc)
        except Exception as e:
            failed.append((hc, str(e).strip().splitlines()[-1][:120]))
            print(f"  {hc}  FAILED: {failed[-1][1]}")
    print(f"\nbuilt {len(ok)}   failed {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Make a short FB/Instagram Reels pan/zoom video of a Holy Chip story image.

Output: 1080x1920 (9:16 vertical Reel). The sharp comic pans/zooms in the
centre over a blurred fill background. Camera path (~5s):
  pan in on the title -> ease out -> pan down through panels 1 & 2 ->
  zoom into panel 3 -> pull back to the full story (letterboxed on blur).

  story_video.py HC035 [out.mp4] [--seconds 5] [--fps 30]

Renders frames with PIL (precise camera control), encodes with ffmpeg (h264).
"""
import os, sys, shutil, subprocess, tempfile
from PIL import Image, ImageFilter, ImageEnhance

HC = os.path.expanduser("~/holy-chip")
STORIES = os.path.join(HC, "website/holy-chip-site/stories")
OUTDIR = os.path.join(HC, "website/holy-chip-site/videos")

CW, CH = 1080, 1920                      # Reel canvas (9:16)

# Camera keyframes: (t_seconds, zoom, cy)
#   zoom = multiplier on the fit-to-width base scale (1.0 = whole comic width
#          fills 1080 -> full comic visible, letterboxed top/bottom on the blur)
#   cy   = comic y-fraction that sits at the canvas vertical centre
# Total duration = the last keyframe's time.
KEYFRAMES = [
    (0.0,  1.00, 0.50),   # START on the full story
    (1.0,  1.90, 0.07),   # zoom in to the title / header
    (2.0,  1.90, 0.07),   # hold 1s on the title
    (3.0,  1.20, 0.85),   # move to panel 3
    (4.0,  1.20, 0.85),   # hold 1s on panel 3
    (5.0,  1.00, 0.50),   # bring the whole story back into frame
    (35.0, 1.00, 0.50),   # hold 30s on the full story
]


def smoothstep(a):
    return a * a * (3 - 2 * a)


def camera_at(t):
    """t in seconds -> (zoom, cy), smooth-eased between keyframes."""
    for i in range(len(KEYFRAMES) - 1):
        t0, z0, y0 = KEYFRAMES[i]
        t1, z1, y1 = KEYFRAMES[i + 1]
        if t0 <= t <= t1:
            a = smoothstep((t - t0) / (t1 - t0)) if t1 > t0 else 0.0
            return (z0 + (z1 - z0) * a, y0 + (y1 - y0) * a)
    return KEYFRAMES[-1][1:]


def make_background(img):
    """Blurred, darkened cover-fill of the comic for the Reel backdrop."""
    W, H = img.size
    scale = max(CW / W, CH / H)
    bw, bh = int(W * scale) + 2, int(H * scale) + 2
    bg = img.resize((bw, bh), Image.LANCZOS).crop(
        ((bw - CW) // 2, (bh - CH) // 2, (bw - CW) // 2 + CW, (bh - CH) // 2 + CH))
    bg = bg.filter(ImageFilter.GaussianBlur(45))
    return ImageEnhance.Brightness(bg).enhance(0.55)


def render(sid, out_path, fps):
    src = os.path.join(STORIES, f"{sid}.png")
    if not os.path.exists(src):
        sys.exit(f"not found: {src}")
    img = Image.open(src).convert("RGB")
    W, H = img.size
    base = CW / W                        # fit-to-width scale
    bg = make_background(img)
    seconds = KEYFRAMES[-1][0]           # total duration = last keyframe time
    nframes = int(round(seconds * fps))
    tmp = tempfile.mkdtemp(prefix=f"{sid}_reel_")
    try:
        for f in range(nframes):
            t = f / fps
            z, cy = camera_at(t)
            k = base * z
            dw, dh = max(1, int(W * k)), max(1, int(H * k))
            comic = img.resize((dw, dh), Image.LANCZOS)
            frame = bg.copy()
            ox = (CW - dw) // 2                    # horizontally centred
            oy = int(round(CH / 2 - cy * dh))      # cy point at canvas centre
            frame.paste(comic, (ox, oy))
            frame.save(os.path.join(tmp, f"f{f:04d}.png"))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-framerate", str(fps),
            "-i", os.path.join(tmp, "f%04d.png"),
            # silent stereo audio track — Instagram Reels reject videos with no audio
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-movflags", "+faststart", out_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("ffmpeg failed:\n" + r.stderr[-800:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out_path} ({os.path.getsize(out_path)//1024} KB, "
          f"{seconds}s @ {fps}fps, {CW}x{CH})")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("usage: story_video.py HC### [out.mp4] [--seconds N] [--fps N]")
    sid = args[0]
    out = args[1] if len(args) > 1 else os.path.join(OUTDIR, f"{sid}.mp4")

    def opt(name, default):
        if name in sys.argv:
            return type(default)(sys.argv[sys.argv.index(name) + 1])
        return default
    render(sid, out, opt("--fps", 30))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Animate every scene image of a video on the M5 (Wan 2.2).   animate.py HC023v5 [--frames 81] [--only ID]

Reads DIR/motion.json ({bg id: motion prompt, "_suffix": style tail}), sends DIR/bg/ID.png,
writes DIR/clips/ID.mp4. Existing clips are kept (delete one to redo it). render2 uses a clip
in place of the still whenever DIR/clips/ID.mp4 exists.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from m5_video import animate

D = Path(__file__).parent / sys.argv[1]
opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
M = json.loads((D / "motion.json").read_text()); suffix = M.pop("_suffix", "")
only = opt("--only", ""); frames = opt("--frames", 81)
(D / "clips").mkdir(exist_ok=True)
todo = [k for k in M if (not only or k == only) and not (D / "clips" / f"{k}.mp4").exists()]
for i, k in enumerate(todo, 1):
    print(f"[{i}/{len(todo)}] {k}: {M[k][:70]}", flush=True)
    tmp = D / "clips" / f"{k}.part.mp4"
    animate(D / "bg" / f"{k}.png", M[k] + suffix, str(tmp), frames=frames)
    tmp.rename(D / "clips" / f"{k}.mp4")
print("done")

#!/usr/bin/env python3
"""Rebuild a video.md's Narration blocks from a narration file (EN or PT), keeping the
visual blocks (Bot/Comic/Background/Color/Image) of the template. Images attach to the
LAST n lines of their scene (n = number of Image shots in the scene).
    sync_narration.py TEMPLATE.video.md NARRATION.md OUT.video.md VOICE"""
import re, sys
tpl, nar, out, voice = sys.argv[1:5]
T = open(tpl).read(); N = open(nar).read()
head = T.split('\n## Scene', 1)[0]
head = re.sub(r'^- Voice: .*$', f'- Voice: {voice}', head, flags=re.M)
scenes = re.split(r'^## (?=Scene|Ending)', T, flags=re.M)[1:]
nsc = re.split(r'^## (?=Scene|Cena|Ending)', N, flags=re.M)[1:]
vis, ending_t = [], None
for sec in scenes:
    h, body = sec.split('\n', 1)
    if h.startswith('Ending'): continue
    pre = [l for l in body.split('\n') if re.match(r'^- (Bot|Comic|Background|Color|Punchline):', l)]
    imgs = [l.strip()[2:].strip() for l in body.split('\n') if l.strip().startswith('- Image:')]
    vis.append((h.strip(), pre, imgs))
nlines, nend = [], None
for sec in nsc:
    h, body = sec.split('\n', 1)
    if h.startswith('Ending'): nend = body.strip('\n'); continue
    nlines.append([l[2:].strip() for l in body.split('\n') if l.startswith('- ')])
assert len(vis) == len(nlines), (len(vis), len(nlines))
parts = [head.rstrip('\n')]
for (h, pre, imgs), lines in zip(vis, nlines):
    blk = [f'## {h}'] + pre + ['- Narration:']
    k0 = len(lines) - len(imgs)
    for i, ln in enumerate(lines):
        blk.append(f'  - {ln}')
        if imgs and i >= k0: blk.append(f'      - {imgs[i - k0]}')
    parts.append('\n'.join(blk))
parts.append('## Ending\n' + nend)
open(out, 'w').write('\n\n'.join(parts) + '\n'); print('wrote', out, len(vis), 'scenes')

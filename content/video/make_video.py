#!/usr/bin/env python3
"""Screenplay -> video. Reads <dir>/<SID>.video.md (edited by the user in Zettlr):

    ~/holy-chip/venv/video/bin/python make_video.py HC023v4 HC023

Only what changed is regenerated: a background is redrawn when its description
changes (cache: bg/meta.json); music is generated only for a new "new: <mood>".
Voice is always re-made (fast). Then render2.py builds <SID>_sketch.mp4."""
import hashlib, json, re, subprocess, sys
from pathlib import Path

VID = Path(__file__).parent
D = VID / sys.argv[1]; SID = sys.argv[2]
PY = str(Path.home() / 'holy-chip/venv/video/bin/python')
BOTS = {'calm': 'p1Left', 'thinking': 'p2Left', 'surprised': 'p3'}

md = (Path(sys.argv[sys.argv.index('--md') + 1]) if '--md' in sys.argv else D / f'{SID}.video.md').read_text()   # --md: check another copy
sections = re.split(r'^## ', md, flags=re.M)[1:]
settings, beats, outro, chars = {}, [], {}, {}
old = {b['id']: b for b in json.loads((D / 'beats.json').read_text())} if (D / 'beats.json').exists() else {}
old_list = list(old.values())
for sec in sections:
    head, body = sec.split('\n', 1)
    head = re.sub(r'^[^A-Za-z]+', '', head)               # "## **Scene 2" -> "Scene 2"
    kv = dict(re.findall(r'^- ([A-Za-z ]+?):\s*(.*)$', body, re.M))
    if head.startswith('Settings'):
        settings = {k.strip(): (v.split('   (')[0] if k.strip() == 'Style reference' else v.split('(')[0]).strip() for k, v in kv.items()}
    elif head.startswith('Characters'):
        chars = {k.strip(): v.strip() for k, v in kv.items()}
    elif head.startswith('Scene'):                       # "## Scene" - any number/title is ignored; order = file order
        n = len(beats) + 1
        say, shots = [], []
        for ln in body.split('- Narration:', 1)[1].split('\n'):        # 2-space items = lines; deeper = Image/Color for that line
            m = re.match(r'^(\s*)- (.+)$', ln)        # unindented "- line" counts too (it was silently dropped before 2026-10-13)
            if not m or (not m.group(1) and re.match(r'^(Bot|Comic|Background|Punchline|Narration)\s*:', m.group(2))): continue
            ind, txt = len(m.group(1)), m.group(2).strip()
            sub = re.match(r'^(Image|Color)\s*:\s*(.*)$', txt, re.I)
            if ind >= 4 and sub and say:
                if sub.group(1).lower() == 'image':
                    shots.append({'line': len(say) - 1, 'prompt': sub.group(2).strip(), 'color': ''})
                elif shots and shots[-1]['line'] == len(say) - 1:
                    shots[-1]['color'] = sub.group(2).strip()
            elif not sub:
                say.append(txt)
        b = {'id': f's{n:02d}', 'bot': BOTS[kv.get('Bot', 'calm').strip().lower()],
             'prompt': kv['Background'].strip(), 'color': kv.get('Color', '').strip(), 'say': say, 'shots': shots}
        c = kv.get('Comic', 'none').strip().lower()
        if c not in ('', 'none'):
            b['comic'] = [int(x) - 1 for x in re.findall(r'\d', c)]
        if kv.get('Punchline', '').strip().lower().startswith('y'):
            b['punch'] = True
        beats.append(b)
    elif head.startswith('Ending'):
        outro = {'narration': kv.get('Narration', '').strip(), 'label': kv.get('Card label', '').strip(),
                 'line1': kv.get('Card line 1', '').strip(), 'line2': kv.get('Card line 2', '').strip(),
                 'button': kv.get('Button', '').strip(), 'site': kv.get('Site', 'holy-chip.com').strip()}
(D / 'beats.json').write_text(json.dumps(beats, indent=1, ensure_ascii=False))
(D / 'outro.json').write_text(json.dumps(outro, indent=1, ensure_ascii=False))
print(f'{len(beats)} scenes; music={settings.get("Music")}; voice={settings.get("Voice")}')

# backgrounds: one image per (description + colour + style + characters), stored by content
STYLE = settings.get('Style', 'simple ink sketch on cream paper')
STYLE_REF = settings.get('Style reference', 'auto')
def expand(p):                                            # [Name] -> ACTION FIRST, then the character's description
    used = re.findall(r'\[([^\]]+)\]', p)                 # (the model reads ~77 tokens: a long description first cut the action)
    known = [n for n in used if n in chars]
    for n in used: p = p.replace(f'[{n}]', f'the {n.lower()}' if n in chars else n)
    if known: p = p + '. ' + ' '.join(f'The {n.lower()}: {chars[n]}.' for n in known)
    return p, known
key = lambda p, c, extra='': f"{p} || color: {c} || style: {STYLE} || ref: {STYLE_REF} {extra} || v6"
H = lambda k: hashlib.md5(k.encode()).hexdigest()[:10]
metaf = D / 'bg' / 'meta.json'
allimgs, jobs = [], []
anchor = None
if STYLE_REF == 'auto' and beats:
    # "the artist": a sheet of small pen sketches that SHOWS the stroke (a scene can come out too pale to copy)
    p0 = "many small cartoon doodles scattered on white: little people walking, two boxy robots, a dog, a bicycle, a tree, a cat"
    anchor = f"_anchor_{H(key(p0, '', 'sheet'))}"
    jobs.append({'id': anchor, 'prompt': p0, 'color': '', 'seed': 7, 'style': STYLE, 'kind': 'anchor'})
style_img = f"bg/{anchor}.png" if anchor else STYLE_REF
portraits = {}; AVOID = {}; LOOK = {}
for n, desc in list(chars.items()):
    parts = [x.strip() for x in desc.split('|')]
    chars[n] = parts[0]; f = {}
    for x in parts[1:]:
        if ':' in x: k_, v_ = x.split(':', 1); f[k_.strip().lower()] = v_.strip()
    AVOID[n] = f.get('avoid', ''); LOOK[n] = f.get('look', '')
    if f.get('ref'):                                       # casting: locked to a chosen picture
        portraits[n] = f['ref']; continue
    cid = f"_char_{H(key(desc, '', 'char'))}"; portraits[n] = f"bg/{cid}.png"
    jobs.append({'id': cid, 'prompt': f"full-length portrait of {chars[n]}, standing, simple pose", 'color': '', 'seed': 5,
                 'style': STYLE, 'kind': 'char', 'ref': style_img, 'avoid': AVOID.get(n, '')})
def plan(item):
    p, used = expand(item['prompt']); c = item.get('color', '')
    ref = portraits[used[0]] if used else style_img
    item['img'] = f"h_{H(key(p, c, ref))}"; item['seed'] = int(H(key(p, c))[:6], 16) % 100000
    jobs.append({'id': item['img'], 'prompt': p, 'color': c, 'seed': item['seed'], 'style': STYLE, 'kind': 'scene', 'ref': ref, 'char': bool(used),
                 'avoid': ', '.join(AVOID.get(u, '') for u in used if AVOID.get(u)),
                 'rednose': any('rednose' in LOOK.get(u, '') for u in used)})
    allimgs.append(item)
for b in beats:
    plan(b)
    for sh in b.get('shots', []): plan(sh)

# ---- Image engine: m5 -> every image is drawn by Qwen-Image on the M5 (user rule, 2026-10-13: "if images change, M5") ----
ENGINE = settings.get('Image engine', 'm5').split()[0].lower()   # RULE (user, 2026-10-13): images are ALWAYS drawn on the M5; if it fails, stop and ask
M5_URL = "https://ricardos-macbook-pro.tailfb1456.ts.net:8443/v1/images/generations"
if ENGINE == 'm5':
    ROBOT = re.split(r'\s{2,}\(', chars.get('Robot', ''))[0].strip()
    jobs = []
    def m5plan(item):
        p, _ = expand(item['prompt']); c = item.get('color', '')
        if ROBOT and re.search(r'\brobots?\b', p, re.I): p += f". Each robot is {ROBOT}"
        if c: p += f", with {c} in color"
        p += f". Style: {STYLE}"
        item['img'] = 'm5_' + hashlib.md5(p.encode()).hexdigest()[:10]
        jobs.append({'id': item['img'], 'prompt': p, 'kind': 'm5'})
    for b in beats:
        m5plan(b)
        for sh in b.get('shots', []): m5plan(sh)
    if '--seed-from' in sys.argv:                          # one-time: approved images -> cache (only where the description is unchanged)
        import shutil
        src_dir = Path(sys.argv[sys.argv.index('--seed-from') + 1]); expect = json.loads((src_dir / 'descriptions.json').read_text())
        order = [x for b in beats for x in [b] + b.get('shots', [])]
        (D / 'bg').mkdir(exist_ok=True)
        by_text = {v.strip(): k for k, v in expect.items()}          # match by DESCRIPTION, wherever the scene now sits
        for n, it in enumerate(order, 1):
            k = by_text.get(it['prompt'].strip())
            if k and not (D / 'bg' / f"{it['img']}.png").exists():
                shutil.copy(src_dir / f'{int(k):02d}.png', D / 'bg' / f"{it['img']}.png"); print(f'image {n}: reused approved #{k}')
            elif not k: print(f'image {n}: new/changed description -> M5')

# ---- image-by-image choice: --options N ["twist"]  /  --pick N K ----
scene_jobs = [j for j in jobs if j['kind'] == 'scene']
if '--options' in sys.argv or '--pick' in sys.argv:
    from PIL import Image, ImageDraw, ImageFont
    a = sys.argv[sys.argv.index('--options' if '--options' in sys.argv else '--pick') + 1:]
    N = int(a[0]); base = scene_jobs[N - 1]
    if '--pick' in sys.argv:                               # lock the chosen option as THE image
        import shutil; k = int(a[1])
        shutil.copy(D / 'bg' / f'opt_{N}_{k}.png', D / 'bg' / f"{base['id']}.png"); print(f'image {N} = option {k} (locked)')
        subprocess.run([PY, __file__, sys.argv[1], sys.argv[2], '--images'], check=False)   # refresh the full drawings sheet
        sys.exit(0)
    twist = a[1] if len(a) > 1 and not a[1].startswith('--') else ''
    opts = []
    for k in range(1, 5):
        j = dict(base); j['id'] = f'opt_{N}_{k}'; j['seed'] = base['seed'] + 1000 * k
        if twist: j['prompt'] = twist + ', ' + base['prompt']           # the twist goes FIRST (77-token cut)
        opts.append(j)
    deps = [j for j in jobs if j['kind'] in ('anchor', 'char') and not (D / 'bg' / f"{j['id']}.png").exists()]
    for batch in (deps, [o for o in opts if not o.get('char')], [o for o in opts if o.get('char')]):
        if not batch: continue
        (D / 'jobs.json').write_text(json.dumps(batch, ensure_ascii=False))
        r = subprocess.run([PY, 'sd.py', 'jobs.json'], cwd=D, capture_output=True, text=True)
        if r.returncode: sys.exit(r.stderr[-1500:])
    F = ImageFont.truetype(str(Path.home() / 'holy-chip/content/pt-br/work/ChakraPetch-Bold.ttf'), 26)
    sheet = Image.new('RGB', (5 * 400, 470), 'white'); d = ImageDraw.Draw(sheet)
    d.text((8, 6), f"IMAGE {N} - current (C) and 4 options" + (f"   twist: {twist[:70]}" if twist else ''), font=F, fill='black')
    cur = D / 'bg' / f"{base['id']}.png"
    for i, (fn, lab) in enumerate([(cur, 'C')] + [(D / 'bg' / f'opt_{N}_{k}.png', str(k)) for k in range(1, 5)]):
        if fn.exists(): sheet.paste(Image.open(fn).resize((390, 390)), (i * 400 + 5, 50))
        d.text((i * 400 + 12, 56), lab, font=F, fill=(200, 30, 30), stroke_width=3, stroke_fill='white')
    out = D / f'options_{N}.png'; sheet.save(out); subprocess.run(['open', str(out)]); print('options:', out); sys.exit(0)
todo = [j for j in jobs if not (D / 'bg' / f"{j['id']}.png").exists()]
if '--plan' in sys.argv:                                   # dry run: show the plan, draw/render nothing
    for j in jobs: print(f"  {j['kind']:6s} {j['id'][:18]:18s} ref={str(j.get('ref', '-'))[:22]:22s} {j['prompt'][:70]}")
    print(f"{len(set(j['id'] for j in todo))} image(s) would be drawn"); sys.exit(0)
todo_ids = {j['id'] for j in todo}
seen = set(); todo = [j for j in todo if not (j['id'] in seen or seen.add(j['id']))]
m5todo = [j for j in todo if j['kind'] == 'm5']; todo = [j for j in todo if j['kind'] != 'm5']
for j in m5todo:                                           # draw on the M5 (~10 s each)
    import base64, urllib.request
    body = {"model": "local/qwen-image-2.1-turbo", "prompt": j['prompt'], "size": "1024x1024", "response_format": "b64_json", "seed": 42}
    for attempt in range(4):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(M5_URL, data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer unused"}), timeout=900)); break
        except Exception as e:
            if attempt == 3: sys.exit(f"M5 image failed ({e}). Is Tailscale on and the M5 image model loaded?")
            import time; time.sleep(20)
    (D / 'bg').mkdir(exist_ok=True); (D / 'bg' / f"{j['id']}.png").write_bytes(base64.b64decode(r["data"][0]["b64_json"]))
    print('M5 drew', j['id'], flush=True)
if todo:
    print('drawing', len(todo), 'image(s):', ', '.join(sorted({j['kind'] for j in todo})), flush=True)
    for batch in ([j for j in todo if not j.get('char')], [j for j in todo if j.get('char')]):   # character scenes use the face adapter: own batch
        if not batch: continue
        (D / 'jobs.json').write_text(json.dumps(batch, ensure_ascii=False))
        r = subprocess.run([PY, 'sd.py', 'jobs.json'], cwd=D, capture_output=True, text=True)
        if r.returncode: sys.exit(r.stderr[-1500:])
if '--images' in sys.argv:                                 # approval sheet: drawings in order, no voice/video
    from PIL import Image, ImageDraw, ImageFont
    F = ImageFont.truetype(str(Path.home() / 'holy-chip/content/pt-br/work/ChakraPetch-Bold.ttf'), 22)
    seqi = []
    for n, b in enumerate(beats, 1):
        seqi.append((b['img'], f"Scene {n}", b['say'][0] if b['say'] else ''))
        for sh in b.get('shots', []):
            seqi.append((sh['img'], f"Scene {n} - line {sh['line'] + 1}", b['say'][sh['line']]))
    def wrapt(t, w=34):
        out, cur = [], ''
        for x in re.sub(r'^\([^)]*\)\s*', '', t).split():
            if len(cur) + len(x) > w: out.append(cur); cur = x
            else: cur = (cur + ' ' + x).strip()
        return (out + [cur])[:3]
    C, TW = 4, 360
    sheet = Image.new('RGB', (C * TW, ((len(seqi) + C - 1) // C) * (TW + 110) + 10), 'white'); d = ImageDraw.Draw(sheet)
    for i, (img, lab, line) in enumerate(seqi):
        x, y = (i % C) * TW + 5, (i // C) * (TW + 110) + 5
        sheet.paste(Image.open(D / 'bg' / f'{img}.png').resize((TW - 10, TW - 10)), (x, y))
        d.text((x + 6, y + 4), f"{i + 1}. {lab}", font=F, fill=(200, 30, 30), stroke_width=3, stroke_fill='white')
        for k, ln in enumerate(wrapt(line)): d.text((x, y + TW - 4 + k * 26), ln, font=F, fill='black')
    out = D / f'{SID}_drawings.png'; sheet.save(out); print('sheet:', out)
    subprocess.run(['open', str(out)]); sys.exit(0)
metaf.write_text(json.dumps({b['img']: b['prompt'] for b in allimgs}, indent=1, ensure_ascii=False))
(D / 'beats.json').write_text(json.dumps(beats, indent=1, ensure_ascii=False))

# music
m = settings.get('Music', 'A_synthpop')
if m.lower().startswith('new:'):
    mood = m.split(':', 1)[1].strip(); name = 'custom_' + hashlib.md5(mood.encode()).hexdigest()[:8]
    if not (VID / 'music' / f'{name}.wav').exists():
        print('composing music:', mood, flush=True)
        subprocess.run([str(Path.home() / '.local/bin/uv'), 'run', 'python', str(VID / 'music' / 'gen_music.py'), name, mood],
                       cwd=Path.home() / 'holy-chip/vendor/ACE-Step-1.5', check=True, capture_output=True)
    m = name
(D / 'music.wav').unlink(missing_ok=True)
(D / 'music.wav').symlink_to(VID / 'music' / f'{m}.wav')

(D / 'audio').mkdir(exist_ok=True)
print('voice...', flush=True)
subprocess.run([PY, 'tts2.py', settings.get('Voice', 'eleven:Lily')], cwd=D, check=True, capture_output=True)   # standard voices (user, 2026-10-14): EN eleven:Lily, PT eleven:Yasmin
print('render...', flush=True)
r = subprocess.run([PY, 'render2.py'], cwd=D, capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1] if r.returncode == 0 else r.stderr[-800:])

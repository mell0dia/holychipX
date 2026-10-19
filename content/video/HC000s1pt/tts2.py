import json, os, numpy as np, soundfile as sf, subprocess, sys
from kokoro import KPipeline
VOICE = sys.argv[1] if len(sys.argv) > 1 else 'am_onyx'
CLOUD = VOICE.startswith(('gemini:', 'eleven:'))
pipe = None if CLOUD else KPipeline(lang_code=VOICE[0], device='cpu')     # a=US, b=UK, p=Brazilian Portuguese (pm_alex, pm_santa, pf_dora)
SR = 24000
FLT = ("asetrate=22560,aresample=24000,atempo=1.0638,"          # ~6% lower, same speed
       "equalizer=f=110:t=q:w=1:g=4,equalizer=f=3500:t=q:w=1:g=2,"
       "acompressor=threshold=-20dB:ratio=3:attack=5:release=120,"
       "aecho=0.8:0.5:40|70:0.12|0.08,highpass=f=50")
import re
ASK = False
TAGS = {   # tag -> (speed, pitch, gain)   speed/pitch are multipliers, gain linear
    'slow': (0.84, 1, 1), 'fast': (1.10, 1, 1), 'low': (1, 0.93, 1), 'high': (1, 1.06, 1),
    'soft': (1, 1, 0.6), 'loud': (1, 1, 1.35), 'whisper': (0.92, 1, 0.5), 'dramatic': (0.80, 0.94, 1.15),
    'angry': (1.04, 1.03, 1.0), 'rage': (1.08, 1.06, 1.0)}
# energy chains added after the voice filter (user, 2026-10-09: "more energy, almost rage")
ENERGY = {
    'angry': "equalizer=f=2800:t=q:w=1.2:g=5,acompressor=threshold=-26dB:ratio=6:attack=2:release=60:makeup=4,volume=1.35",
    'rage':  "equalizer=f=3000:t=q:w=1.2:g=8,equalizer=f=180:t=q:w=1:g=3,acompressor=threshold=-30dB:ratio=9:attack=1:release=50,"
             "asoftclip=type=tanh:threshold=0.6"}
ENERGY_ON = None
def parse(line):
    """'(slow, low, pause) Watch the human.' -> text, speed, pitch, gain, pause_before"""
    m = re.match(r'^\(([^)]*)\)\s*(.*)$', line.strip())
    tags, text = ([t.strip().lower() for t in m.group(1).split(',')], m.group(2)) if m else ([], line.strip())
    sp, pi, ga, pause = 1.0, 1.0, 1.0, 0.0
    global ASK, ENERGY_ON; ASK = 'ask' in tags
    ENERGY_ON = 'rage' if 'rage' in tags else ('angry' if 'angry' in tags else None)
    for t in tags:
        if t.startswith('pause'):
            n = re.findall(r'[\d.]+', t); pause += float(n[0]) if n else 0.8
        elif t in TAGS:
            a, b, c = TAGS[t]; sp *= a; pi *= b; ga *= c
    return text, sp, pi, ga, pause
QWORDS = ('what', 'who', 'whom', 'whose', 'why', 'how', 'where', 'when', 'which')
def stress_question(text):
    """Primary stress (+2) on the question word, else on the first word; a word the
    author already marked as [word](+n) is left alone."""
    if re.search(r'\]\([+-]?[\d.]+\)', text): return text
    words = list(re.finditer(r"[A-Za-z']+", text))
    if not words: return text
    SKIP = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'do', 'does', 'did', 'so', 'and', 'or', 'but', 'of', 'to', 'it', 'its', 'this', 'that'}
    content = [m for m in words if m.group(0).lower() not in SKIP] or words
    w = next((m for m in words if m.group(0).lower() in QWORDS), content[0])
    return text[:w.start()] + f'[{w.group(0)}](+2)' + text[w.end():]
import base64, hashlib, time, urllib.request, urllib.error
DIRECTION = {'angry': 'com raiva, firme', 'rage': 'gritando de raiva', 'dramatic': 'de forma dramática e pausada',
             'ask': 'como uma pergunta, com entonação interrogativa clara', 'whisper': 'sussurrando', 'soft': 'baixinho',
             'loud': 'com força', 'slow': 'devagar', 'fast': 'um pouco mais rápido', 'low': 'com voz mais grave', 'high': 'com voz mais aguda'}
BASE_STYLE = ("Fale em português do Brasil, com sotaque brasileiro natural, como um narrador de documentário de voz grave, "
              "envolvente e com um toque de humor")
def _env():
    e = {}
    for l in open(os.path.expanduser('~/claude-agent/.env')):
        if '=' in l and not l.lstrip().startswith('#'):
            k, v = l.split('=', 1); e[k.strip()] = v.strip().strip('"').strip("'")
    return e
def gemini_say(text, tags, voice, out_wav):
    """Gemini TTS (gemini-2.5-pro-preview-tts). Tags -> spoken direction. Cached by text+tags+voice."""
    style = BASE_STYLE + ''.join(', ' + DIRECTION[t] for t in tags if t in DIRECTION)
    prompt = f"{style}: {text}"
    os.makedirs('audio/cache', exist_ok=True)
    key = hashlib.md5((voice + '|' + prompt).encode()).hexdigest()[:16]; cached = f'audio/cache/{key}.wav'
    if not os.path.exists(cached):
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-tts:generateContent?key={_env()['GEMINI_API_KEY']}"
        for attempt in range(8):
            try:
                r = json.load(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'}), timeout=180)); break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503) and attempt < 7: time.sleep(15 * (attempt + 1)); continue
                raise
        pcm = base64.b64decode(r['candidates'][0]['content']['parts'][0]['inlineData']['data'])
        open(cached + '.pcm', 'wb').write(pcm)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', cached + '.pcm',
                        '-af', 'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse',
                        cached], check=True)
        os.remove(cached + '.pcm')
    import shutil; shutil.copy(cached, out_wav)
ELEVEN_TAGS = {'angry': '[angry]', 'rage': '[shouting][angry]', 'dramatic': '[dramatic tone]', 'whisper': '[whispers]',
               'soft': '[softly]', 'loud': '[loudly]', 'slow': '[slowly]', 'fast': '[quickly]'}   # ElevenLabs v3 audio tags
def eleven_voice_id(name):
    """A voice in the account whose name starts with `name` (e.g. 'Yasmin', 'Daniel', 'Marcelo Costa'). Cached."""
    os.makedirs('audio/cache', exist_ok=True); cf = 'audio/cache/eleven_voices.json'
    m = json.load(open(cf)) if os.path.exists(cf) else {}
    if name not in m:
        r = json.load(urllib.request.urlopen(urllib.request.Request('https://api.elevenlabs.io/v2/voices?page_size=100',
                      headers={'xi-api-key': _env()['ELEVENLABS_API_KEY']}), timeout=60))
        hit = [v for v in r['voices'] if v['name'].lower().startswith(name.lower())]
        if not hit: raise SystemExit(f'ElevenLabs: no voice named {name!r} in the account')
        m[name] = hit[0]['voice_id']; json.dump(m, open(cf, 'w'))
    return m[name]
def eleven_say(text, tags, voice, out_wav):
    """ElevenLabs v3 TTS. Tags -> v3 audio tags in front of the line. Cached by voice+tags+text."""
    spoken = ''.join(ELEVEN_TAGS[t] for t in tags if t in ELEVEN_TAGS) + ' ' + text
    key = hashlib.md5(('eleven|' + voice + '|' + spoken).encode()).hexdigest()[:16]; cached = f'audio/cache/{key}.wav'
    if not os.path.exists(cached):
        body = {"text": spoken.strip(), "model_id": "eleven_v3",
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}}
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id(voice)}?output_format=mp3_44100_128"
        for attempt in range(6):
            try:
                mp3 = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(),
                        headers={'xi-api-key': _env()['ELEVENLABS_API_KEY'], 'Content-Type': 'application/json'}), timeout=180).read(); break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503) and attempt < 5: time.sleep(10 * (attempt + 1)); continue
                raise
        open(cached + '.mp3', 'wb').write(mp3)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', cached + '.mp3', '-ac', '1', '-ar', '24000',
                        '-af', 'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse',
                        cached], check=True)
        os.remove(cached + '.mp3')
    import shutil; shutil.copy(cached, out_wav)
def cloud_say(text, tags, out_wav):
    eng, name = VOICE.split(':', 1)
    (gemini_say if eng == 'gemini' else eleven_say)(text, tags, name, out_wav)
def eleven_script(beats, voice):
    """ONE-SHOT narration (user, 2026-10-14: line-by-line requests broke the flow).
    The whole script goes to ElevenLabs in a single request (scenes as paragraphs),
    with character timestamps; the recording is then cut at the natural pauses
    between lines, so the pipeline keeps its per-line clips (captions, image
    switches) but the performance is continuous. Cached by voice+script."""
    parts, spans, text = [], [], ''
    for b in beats:
        for k, line0 in enumerate(b['say']):
            tags = TAGS_OF(line0); line = re.sub(r'^\([^)]*\)\s*', '', line0.strip())
            line = re.sub(r'\[([^\]]+)\]\([+-]?[\d.]+\)', r'\1', line)
            spoken = ''.join(ELEVEN_TAGS[t] for t in tags if t in ELEVEN_TAGS) + say_fix(line)
            if text: text += ('\n\n' if k == 0 else ' ')
            spans.append((b['id'], k, len(text), len(text) + len(spoken), line, tags)); text += spoken
    os.makedirs('audio/cache', exist_ok=True)
    key = hashlib.md5(('eleven-script|' + voice + '|' + text).encode()).hexdigest()[:16]; cached = f'audio/cache/{key}'
    if not os.path.exists(cached + '.json'):
        vid = eleven_voice_id(voice); last = None
        for model in ('eleven_v3', 'eleven_multilingual_v2'):
            body = {"text": text, "model_id": model, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}}
            if model == 'eleven_multilingual_v2': body["language_code"] = 'pt' if voice.split()[0] in ('Will', 'Marcelo', 'Yasmin') else 'en'
            try:
                r = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128",
                        data=json.dumps(body).encode(), headers={'xi-api-key': _env()['ELEVENLABS_API_KEY'], 'Content-Type': 'application/json'}), timeout=300).read())
                print('  one-shot via', model, flush=True); break
            except urllib.error.HTTPError as e:
                last = e.read()[:200]; r = None
        if r is None: raise SystemExit(f'ElevenLabs one-shot failed: {last}')
        open(cached + '.mp3', 'wb').write(base64.b64decode(r['audio_base64']))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', cached + '.mp3', '-ac', '1', '-ar', '24000', cached + '.wav'], check=True)
        json.dump(r['alignment'], open(cached + '.json', 'w'))
    al = json.load(open(cached + '.json')); st, en = al['character_start_times_seconds'], al['character_end_times_seconds']
    chars = al['characters']; assert ''.join(chars) == text, 'alignment/text mismatch'
    def first_sound(a, b):
        for i in range(a, b):
            if not chars[i].isspace(): return st[i]
        return st[a]
    def last_sound(a, b):
        for i in range(b - 1, a - 1, -1):
            if not chars[i].isspace(): return en[i]
        return en[b - 1]
    starts = [first_sound(a, b) for _, _, a, b, _, _ in spans]; ends = [last_sound(a, b) for _, _, a, b, _, _ in spans]
    total = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', cached + '.wav'], capture_output=True, text=True).stdout)
    out = []
    for i, (bid, k, a, b, line, tags) in enumerate(spans):
        c0 = 0.0 if i == 0 else (ends[i - 1] + starts[i]) / 2            # cut in the middle of the natural pause
        c1 = total if i == len(spans) - 1 else (ends[i] + starts[i + 1]) / 2
        fn = f"audio/{bid}_{k}.wav"
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{c0:.3f}', '-to', f'{c1:.3f}', '-i', cached + '.wav',
                        '-af', 'highpass=f=60,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=150,aecho=0.8:0.5:40:0.06', fn], check=True)
        pause = 0.0
        for t in tags:
            if t.startswith('pause'):
                n = re.findall(r'[\d.]+', t); pause += float(n[0]) if n else 0.8
        out.append({'beat': bid, 'k': k, 'text': line, 'file': fn, 'dur': round(c1 - c0, 3), 'pre': pause}); print(' ', bid, k, round(c1 - c0, 2), flush=True)
    return out
SAY = {'Nagu': 'Nagú', 'IA': 'I.A.'}                                   # pronunciation fixes: spoken text only, captions unchanged (user picked na-GÚ)
def say_fix(t):
    for a, b in SAY.items(): t = re.sub(rf'\b{a}\b', b, t)
    return t
TAGS_OF = lambda line0: [t.strip().lower() for t in re.match(r'^\(([^)]*)\)', line0.strip()).group(1).split(',')] if line0.strip().startswith('(') else []
beats = json.load(open('beats.json')); out = []
ONE_SHOT = VOICE.startswith('eleven:') and os.environ.get('ELEVEN_LINES') != '1'
if ONE_SHOT: out = eleven_script(beats, VOICE.split(':', 1)[1])
for b in ([] if ONE_SHOT else beats):
    for k, line0 in enumerate(b['say']):
        line, sp, pi, ga, pause = parse(line0)
        spoken = stress_question(line) if (ASK and VOICE[0] in 'ab') else line   # stress markup is English-only (espeak voices ignore it)      # (ask): Kokoro stress, same voice (user picked option 2)
        line = re.sub(r'\[([^\]]+)\]\([+-]?[\d.]+\)', r'\1', line)   # captions: plain words
        if CLOUD:                                             # cloud TTS (Gemini / ElevenLabs): tags become direction, no pitch tricks
            fn = f"audio/{b['id']}_{k}.wav"; raw = fn + '.raw.wav'
            cloud_say(say_fix(line), TAGS_OF(line0), raw)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', 'highpass=f=60,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=150,aecho=0.8:0.5:40:0.06', fn], check=True)
            d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', fn], capture_output=True, text=True).stdout)
            out.append({'beat': b['id'], 'k': k, 'text': line, 'file': fn, 'dur': round(d, 3), 'pre': pause}); print(' ', b['id'], k, flush=True); continue
        a = np.concatenate([c.numpy() for _, _, c in pipe(spoken, voice=VOICE, speed=0.95 * sp)])
        raw = f"audio/{b['id']}_{k}.raw.wav"; fn = f"audio/{b['id']}_{k}.wav"; sf.write(raw, a, SR)
        f2 = FLT if pi == 1 else FLT.replace('asetrate=22560', f'asetrate={int(22560 * pi)}').replace('atempo=1.0638', f'atempo={1.0638 / pi:.4f}')
        if ga != 1: f2 += f',volume={ga}'
        if ENERGY_ON: f2 += ',' + ENERGY[ENERGY_ON]
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', f2, fn], check=True)
        if ENERGY_ON:                             # same loudness as the plain narration (user, 2026-10-09)
            ref = fn + '.ref.wav'
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', f2.split(',' + ENERGY[ENERGY_ON])[0], ref], check=True)
            def rms(path):
                v, _ = sf.read(path); v = v.mean(1) if v.ndim > 1 else v; v = v[np.abs(v) > 0.01]
                return float(np.sqrt(np.mean(v ** 2))) if len(v) else 1e-6
            y, sr_ = sf.read(fn); g = min(rms(ref) / rms(fn), 4.0)   # same loudness as the plain line
            y = np.clip(y * g, -0.99, 0.99); sf.write(fn, y, sr_); os.remove(ref)
        d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', fn], capture_output=True, text=True).stdout)
        out.append({'beat': b['id'], 'k': k, 'text': line, 'file': fn, 'dur': round(d, 3), 'pre': pause})
out.append({'beat': 'outro', 'k': 0, 'text': json.load(open("outro.json"))["narration"], 'file': None, 'dur': 0})
if CLOUD:
    cloud_say(json.load(open("outro.json"))["narration"], [], 'audio/outro.raw.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'audio/outro.raw.wav', '-af', 'highpass=f=60,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=150,aecho=0.8:0.5:40:0.06', 'audio/outro.wav'], check=True)
else:
    a = np.concatenate([c.numpy() for _, _, c in pipe(json.load(open("outro.json"))["narration"], voice=VOICE, speed=0.95)])
    sf.write('audio/outro.raw.wav', a, SR); subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'audio/outro.raw.wav', '-af', FLT, 'audio/outro.wav'], check=True)
out[-1].update(file='audio/outro.wav', dur=round(float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', 'audio/outro.wav'], capture_output=True, text=True).stdout), 3))
json.dump(out, open('audio/lines.json', 'w'), indent=1)
print(VOICE, round(sum(o['dur'] for o in out), 1), 's of narration')

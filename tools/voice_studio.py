#!/usr/bin/env python3
"""voice_studio.py — perform the whole voice-over to picture, in the browser.

Press Record: it arms, counts 3-2-1, then starts the animation and the mic
together. You read each line as its bubble lands, with a teleprompter showing
the current line and a bar counting down to the next. Stop, listen back against
the picture, keep the take you like.

Why a server and not an .html file: browser mic capture needs a secure context.
127.0.0.1 counts as one; file:// does not.

The animation is played as individual PNG frames driven by JS from the exact
duration list story_gif computes, NOT as the GIF - a GIF cannot be restarted or
scrubbed reliably, and we need the audio and the picture to start on the same
tick. The pace slider scales the speaking frames live, so you can find a
comfortable delivery speed before committing; whatever pace you record at is
saved with the take and is what the final render should use.

Takes are NEVER silence-trimmed here (unlike voice_record.py) - the leading
silence IS the sync. The lead-in offset is recorded in the take's JSON.

    voice_studio.py HC030
    voice_studio.py HC030 --port 8899 --width 560
"""
import os, sys, json, argparse, subprocess, shutil, http.server, socketserver
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_gif as G

HC = os.path.expanduser("~/holy-chip")
VOICE = os.path.join(HC, "voice")
SR = 44100

# Bring every take to a usable level before anything else touches it, so
# playback is audible and the robot chain gets a healthy input signal.
# -13 LUFS, not the -16 broadcast norm: the music bed sits at -2 dB, so the
# voice needs the extra headroom to stay clearly on top of it.
NORMALISE = "loudnorm=I=-13:TP=-1.5:LRA=11"

ROBOTS = {
    "none": "anull",
    "subtle": ("asetrate={sr}*0.94,aresample={sr},atempo=1.064,"
               "flanger=delay=2:depth=2:speed=0.4,"
               "highpass=f=160,lowpass=f=7200,alimiter=limit=0.9"),
    "machine": ("asetrate={sr}*0.90,aresample={sr},atempo=1.111,"
                "tremolo=f=55:d=0.30,acrusher=bits=7:mode=log:aa=1,"
                "flanger=delay=3:depth=3:speed=0.5,"
                "highpass=f=170,lowpass=f=6500,alimiter=limit=0.9"),
    "heavy": ("asetrate={sr}*0.84,aresample={sr},atempo=1.190,"
              "tremolo=f=48:d=0.45,acrusher=bits=6:mode=log:aa=1,"
              "flanger=delay=4:depth=4:speed=0.4,aecho=0.8:0.7:60:0.25,"
              "highpass=f=150,lowpass=f=6000,alimiter=limit=0.9"),
}

STATE = {}          # story, dir, cues, frames


def ff(*a):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + list(a),
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-600:])


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()), 2)
    except ValueError:
        return 0.0


def list_takes():
    """Existing takes on disk, so they survive a studio restart."""
    takes = os.path.join(STATE["dir"], "takes")
    out = []
    for n in sorted({int(f[4:6]) for f in os.listdir(takes)
                     if f.startswith("take") and f[4:6].isdigit()}):
        base = os.path.join(takes, f"take{n:02d}")
        if not os.path.exists(base + ".wav"):
            continue
        files = {"none": f"take{n:02d}.wav"}
        for name in ROBOTS:
            if name == "none":
                continue
            if os.path.exists(f"{base}.{name}.m4a"):
                files[name] = f"take{n:02d}.{name}.m4a"
        lead = 3000
        if os.path.exists(base + ".json"):
            try:
                lead = json.load(open(base + ".json")).get("lead", 3000)
            except Exception:
                pass
        meta = {}
        if os.path.exists(base + ".json"):
            try:
                meta = json.load(open(base + ".json"))
            except Exception:
                meta = {}
        out.append({"n": n, "dur": dur(base + ".wav"), "files": files,
                    "lead": lead, "pace": meta.get("pace", 1.0),
                    "cues": meta.get("cues", [])})
    return out


def prepare(story, width):
    """Segment the story, write the frame PNGs, build the cue list."""
    im, script = G.load(story)
    # the timing file carries BOTH the per-frame nudges and any grouping
    # override, and the studio must honour the same ones story_gif renders with
    # or the teleprompter shows a different story to the picture
    timing = G.load_timing(story)
    seq = G.segment(im, script, groups=timing.get("groups"))
    G.apply_nudges(seq, timing)
    G.apply_beat(seq, G.BEAT_MS)
    G.apply_end_hold(seq, G.FOOTER_REEL_MS)   # perform to the Reel ending
    frames = G.build_frames(im, seq, width)

    # Regenerate the frames but NEVER touch takes/ - restarting the studio must
    # not destroy recordings.
    d = os.path.join(VOICE, "studio", story)
    os.makedirs(os.path.join(d, "takes"), exist_ok=True)
    for old in os.listdir(d):
        if old.startswith("f") and old.endswith(".png"):
            os.remove(os.path.join(d, old))

    cues = []
    for i, (el, f) in enumerate(zip(seq, frames)):
        name = f"f{i:02d}.png"
        f.convert("RGB").save(os.path.join(d, name))
        cues.append({
            "i": i, "img": name, "ms": el.ms, "kind": el.kind,
            "punch": el.punch,
            "lines": [{"who": w, "text": " ".join(t.split())}
                      for w, t in zip(getattr(el, "speakers", []),
                                      getattr(el, "texts", []))],
        })
    STATE.update(story=story, dir=d, cues=cues,
                 size=[frames[0].size[0], frames[0].size[1]])
    return cues


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<title>__STORY__ — voice studio</title>
<style>
:root{--bg:#14161a;--bg2:#1b1e24;--bg3:#23272f;--line:#2f343d;--txt:#e6e9ef;
      --dim:#8b93a1;--acc:#ffcf2d;--acc2:#4ad0ff;--rec:#ff5c5c;--ok:#7ddb8f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);padding:20px 22px 50px;
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
h1{font-size:17px;margin:0 0 3px}h1 b{color:var(--acc)}
.sub{color:var(--dim);font-size:12px;margin-bottom:16px}
.wrap{display:flex;gap:24px;align-items:flex-start}
.left{flex:0 0 auto;position:relative}
#stage{display:block;background:#fff;border-radius:3px;
  box-shadow:0 8px 34px rgba(0,0,0,.55)}
#count{position:absolute;inset:0;display:none;align-items:center;justify-content:center;
  background:rgba(0,0,0,.72);font:800 130px/1 -apple-system,sans-serif;color:var(--acc);
  border-radius:3px}
.right{flex:1 1 auto;min-width:320px;max-width:560px}
.bar{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
button{font:inherit;cursor:pointer;border-radius:7px;border:1px solid var(--line);
  background:var(--bg3);color:var(--txt);padding:9px 15px}
button:hover{background:#2c313a}button:disabled{opacity:.4;cursor:default}
#rec{background:var(--rec);border-color:var(--rec);color:#1a1a1a;font-weight:700;
  min-width:172px;font-size:15px;padding:11px 16px}
#rec.on{background:var(--ok);border-color:var(--ok)}
#meter{flex:1;min-width:110px;height:9px;background:#0f1114;border:1px solid var(--line);
  border-radius:5px;overflow:hidden}
#lvl{height:100%;width:0;background:linear-gradient(90deg,#4ad0ff,#ffcf2d,#ff5c5c)}
.pace{display:flex;align-items:center;gap:8px;color:var(--dim);font-size:12px}
input[type=range]{width:130px;accent-color:var(--acc)}
#now{background:var(--bg2);border-left:3px solid var(--acc);border-radius:4px;
  padding:14px 16px;min-height:96px;margin-bottom:6px}
#who{font:700 11px/1 -apple-system,sans-serif;letter-spacing:1.2px;text-transform:uppercase;
  color:var(--acc2);margin-bottom:8px}
#who.right{color:var(--acc)}
#say{font-size:20px;line-height:1.35;letter-spacing:.3px}
#say.small{font-size:15px;color:var(--dim)}
#prog{height:4px;background:#0f1114;border-radius:3px;overflow:hidden;margin-bottom:16px}
#pfill{height:100%;width:0;background:var(--acc)}
#next{color:var(--dim);font-size:12px;margin-bottom:16px;min-height:18px}
#next b{color:var(--txt)}
table{border-collapse:collapse;width:100%;font-size:12px}
th{text-align:left;font-size:10px;letter-spacing:.8px;text-transform:uppercase;color:var(--dim);
  padding:0 6px 6px;border-bottom:1px solid var(--line)}
td{padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:middle}
td.n{color:var(--acc);font-weight:700;width:20px}
td.d{color:var(--dim);width:44px;font-variant-numeric:tabular-nums}
audio{height:30px;width:150px}
select{background:var(--bg3);color:var(--txt);border:1px solid var(--line);
  border-radius:5px;padding:4px 6px;font:inherit;font-size:12px}
.use{background:transparent;border-color:var(--acc);color:var(--acc);padding:5px 9px;font-size:11px}
.use.chosen{background:var(--acc);color:#1a1a1a;font-weight:700}
.del{background:transparent;border-color:var(--line);color:var(--dim);
  padding:5px 9px;font-size:11px;margin-left:5px}
.del:hover{border-color:var(--rec);color:var(--rec);background:#2a1a1a}
.hint{color:var(--dim);font-size:11.5px;line-height:1.7;margin-top:14px}
kbd{background:#0f1114;border:1px solid var(--line);border-radius:3px;padding:1px 5px;font-size:10.5px}
#err{color:var(--rec);font-size:12px;margin-top:8px}
.script{margin-top:16px}
.script div{padding:4px 0;color:var(--dim);border-bottom:1px solid #21252c}
.script div.cur{color:var(--txt)}
.script span{color:var(--acc2);font-weight:600;font-size:10.5px;letter-spacing:.8px;
  display:inline-block;width:44px}
.script div.r span{color:var(--acc)}
</style></head><body>
<h1>__STORY__ — <b>voice studio</b></h1>
<div class="sub">Record starts the animation and the mic on the same tick. Read each line as its bubble lands.</div>
<div class="wrap">
  <div class="left">
    <img id="stage" width="__W__" height="__H__">
    <div id="count"></div>
  </div>
  <div class="right">
    <div class="bar">
      <button id="rec">● Record</button>
      <button id="play" disabled>▶ Preview</button>
      <div id="meter"><div id="lvl"></div></div>
    </div>
    <div class="bar">
      <div class="pace">pace <input type="range" id="pace" min="0.7" max="2.2" step="0.05" value="1">
        <span id="pv">1.00×</span></div>
      <div class="pace">total <b id="tot" style="color:var(--txt)">—</b></div>
    </div>
    <div id="now"><div id="who">ready</div><div id="say" class="small">Press Record. You get a 3-2-1 count, then the comic starts building.</div></div>
    <div id="prog"><div id="pfill"></div></div>
    <div id="next"></div>
    <table id="tbl"><tr><th class="n">#</th><th class="d">len</th><th>take</th>
      <th>effect</th><th></th></tr></table>
    <div id="err"></div>
    <div id="diag" style="color:#5c6472;font-size:10.5px;margin-top:6px"></div>
    <div class="hint">
      <kbd>space</kbd> record / stop &nbsp;·&nbsp; <kbd>p</kbd> preview.
      Nothing is overwritten — record as many takes as you like.
      The pace slider stretches only the speaking frames; whatever you record at is saved with the take.
      Recording continues 2.5s past the last frame so the final word is never clipped.
    </div>
    <div class="script" id="script"></div>
  </div>
</div>
<script>
const CUES = __CUES__, STORY = "__STORY__", LEAD = 3000;
// Keep recording after the last frame. Tying the stop to the end of the
// animation clipped the final word mid-syllable.
const POSTROLL = 2500;
const stage=document.getElementById('stage'), count=document.getElementById('count'),
      recBtn=document.getElementById('rec'), playBtn=document.getElementById('play'),
      lvl=document.getElementById('lvl'), who=document.getElementById('who'),
      say=document.getElementById('say'), pfill=document.getElementById('pfill'),
      nxt=document.getElementById('next'), tbl=document.getElementById('tbl'),
      err=document.getElementById('err'), paceEl=document.getElementById('pace'),
      pv=document.getElementById('pv'), tot=document.getElementById('tot'),
      scriptEl=document.getElementById('script');

const imgs = CUES.map(c => { const i = new Image(); i.src = '/f/' + c.img; return i; });
let mr, chunks=[], takeN=0, on=false, analyser, raf, timer, tickRaf, tailTimer;

function pace(){ return parseFloat(paceEl.value); }
function ms(c){ return c.kind === 'bubble' ? Math.round(c.ms * pace()) : c.ms; }
function total(){ return CUES.reduce((s,c) => s + ms(c), 0); }
function fmt(m){ return (m/1000).toFixed(1) + 's'; }
function refresh(){ pv.textContent = pace().toFixed(2)+'×'; tot.textContent = fmt(total()); }
paceEl.oninput = refresh; refresh();

// script list
CUES.forEach((c,i) => { c.lines.forEach(l => {
  const d = document.createElement('div');
  d.className = (l.who === 'Right' ? 'r ' : '') + 'cue' + i;
  d.innerHTML = '<span>' + (l.who === 'Left' ? 'LEFT' : 'RIGHT') + '</span>' + l.text;
  scriptEl.appendChild(d); }); });

function show(i){
  stage.src = imgs[i].src;
  const c = CUES[i];
  document.querySelectorAll('.script div').forEach(d => d.classList.remove('cur'));
  document.querySelectorAll('.cue'+i).forEach(d => d.classList.add('cur'));
  if(c.lines.length){
    who.textContent = c.lines.map(l => l.who === 'Left' ? 'LEFT BOT' : 'RIGHT BOT').join(' + ')
                      + (c.punch ? '   ← PUNCHLINE' : '');
    who.className = c.lines[0].who === 'Right' ? 'right' : '';
    say.className = ''; say.textContent = c.lines.map(l => l.text).join('  /  ');
  } else {
    who.textContent = c.kind; who.className = '';
    say.className = 'small';
    say.textContent = c.kind === 'footer' ? '(hold — nothing to say)' : '(no line)';
  }
  const f = CUES[i+1];
  nxt.innerHTML = f ? ('next: <b>' + (f.lines.map(l=>l.text).join(' / ') || '(' + f.kind + ')') + '</b>') : '';
}

function run(onDone){
  let i = 0, t0 = performance.now(), acc = 0;
  const step = () => {
    show(i);
    const d = ms(CUES[i]);
    acc += d;
    timer = setTimeout(() => { i++; if(i < CUES.length) step(); else { stopTick(); onDone && onDone(); } }, d);
  };
  const tick = () => {
    const el = performance.now() - t0;
    let start = 0;
    for(let k=0;k<i;k++) start += ms(CUES[k]);
    const d = ms(CUES[i]) || 1;
    pfill.style.width = Math.min(100, Math.max(0,(el-start)/d*100)) + '%';
    tickRaf = requestAnimationFrame(tick);
  };
  step(); tick();
}
function stopTick(){ clearTimeout(timer); cancelAnimationFrame(tickRaf); pfill.style.width='0'; }

// The mic is requested on the first click, NOT at page load: getUserMedia is far
// more reliable when it runs inside a user gesture, and a failed probe must never
// leave the Record button dead with no explanation.
let stream, mime = '';
async function ensureMic(){
  if(mr) return true;
  if(!window.isSecureContext){
    err.textContent = 'Not a secure context ('+location.origin+') — mic is blocked. '
      + 'Use http://127.0.0.1 or http://localhost, not a file:// page or a LAN IP.';
    return false;
  }
  if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
    err.textContent = 'This browser exposes no getUserMedia.'; return false;
  }
  try{
    stream = await navigator.mediaDevices.getUserMedia({audio:{
      echoCancellation:false, noiseSuppression:false, autoGainControl:false}});
  }catch(e){
    err.innerHTML = 'Microphone blocked: <b>'+e.name+'</b> — '+e.message
      + '<br>macOS: System Settings → Privacy &amp; Security → Microphone → enable '
      + 'Google Chrome, then reload this page. Also check the 🔒 icon in the address bar.';
    return false;
  }
  if(!window.MediaRecorder){ err.textContent = 'No MediaRecorder in this browser.'; return false; }
  const cands = ['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'];
  mime = cands.find(t => MediaRecorder.isTypeSupported(t)) || '';
  try{ mr = mime ? new MediaRecorder(stream,{mimeType:mime}) : new MediaRecorder(stream); }
  catch(e){ err.textContent = 'MediaRecorder failed: '+e.message; return false; }
  mr.ondataavailable = e => chunks.push(e.data);
  mr.onstop = save;
  try{
    const ctx = new AudioContext();
    if(ctx.state === 'suspended') await ctx.resume();
    analyser = ctx.createAnalyser(); analyser.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(analyser);
    meter();
  }catch(e){ /* level meter is optional - recording still works */ }
  err.textContent = '';
  return true;
}
async function init(){
  show(0);
  try{
    const old = await (await fetch('/takes')).json();
    old.forEach(row);
    if(old.length){ takeN = Math.max(...old.map(t => t.n)); playBtn.disabled = false; }
  }catch(e){}
  const bits = ['secure: '+window.isSecureContext,
                'getUserMedia: '+!!(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia),
                'MediaRecorder: '+!!window.MediaRecorder];
  document.getElementById('diag').textContent = bits.join('   ·   ');
}
function meter(){
  const b = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(b);
  let pk=0; for(const v of b) pk = Math.max(pk, Math.abs(v-128));
  lvl.style.width = Math.min(100, pk/128*140)+'%';
  raf = requestAnimationFrame(meter);
}

function start(){
  if(!mr) return;
  chunks = []; mr.start(); on = true;
  recBtn.textContent = '■ Stop'; recBtn.classList.add('on'); playBtn.disabled = true;
  // record through the count-in; the offset is saved so audio can be aligned
  let n = 3;
  count.style.display = 'flex'; count.textContent = n;
  const iv = setInterval(() => {
    n--;
    if(n > 0){ count.textContent = n; }
    else { clearInterval(iv); count.style.display = 'none';
           run(() => {
             if(!on) return;
             who.textContent = 'STILL RECORDING — finish the line';
             who.className = '';
             say.className = 'small';
             say.textContent = 'auto-stops in ' + (POSTROLL/1000) + 's, or hit space';
             tailTimer = setTimeout(() => { if(on) stop(); }, POSTROLL);
           }); }
  }, 1000);
}
function stop(){ if(!on) return; on = false; clearTimeout(tailTimer); stopTick();
  recBtn.textContent = '● Record'; recBtn.classList.remove('on'); mr.stop(); }
recBtn.onclick = async () => { if(on) return stop();
  if(await ensureMic()) start(); };
playBtn.onclick = () => run(null);
document.addEventListener('keydown', e => {
  if(e.target.tagName === 'INPUT') return;
  if(e.code === 'Space'){ e.preventDefault();
    if(on) stop(); else ensureMic().then(ok => { if(ok) start(); }); }
  if(e.key === 'p'){ e.preventDefault(); run(null); }
});

async function save(){
  const blob = new Blob(chunks, {type: mime || 'audio/webm'});
  takeN++;
  const meta = {lead: LEAD, pace: pace(),
                cues: CUES.map(c => ({i:c.i, ms:ms(c), kind:c.kind}))};
  const fd = new FormData();
  fd.append('meta', JSON.stringify(meta));
  fd.append('audio', blob, 'take.' + ((mime||'').includes('mp4') ? 'm4a' : 'webm'));
  const r = await fetch(`/take?story=${STORY}&n=${takeN}`, {method:'POST', body:fd});
  if(!r.ok){ err.textContent = 'Save failed: ' + await r.text(); return; }
  row(await r.json());
  playBtn.disabled = false;
}
const ALL_AUDIO = [];

// Follow the audio element's own clock instead of running a parallel timer, so
// picture and sound stay locked through play, pause and scrubbing. Uses the cue
// timing stored WITH the take - the take was performed at that pace, which may
// not be where the slider sits now.
function bindSync(au, t){
  const cues = (t.cues && t.cues.length) ? t.cues
             : CUES.map(c => ({i: c.i, ms: ms(c)}));
  const starts = []; let acc = 0;
  for(const c of cues){ starts.push(acc); acc += c.ms; }
  let raf = null, last = -2;
  function follow(){
    const el = au.currentTime * 1000 - (t.lead || 0);
    let i = cues.length - 1;
    if(el < 0){ i = 0; }
    else for(let k = 0; k < cues.length; k++){
      if(el < starts[k] + cues[k].ms){ i = k; break; }
    }
    if(i !== last){ show(i); last = i; }
    const d = cues[i].ms || 1;
    pfill.style.width = Math.min(100, Math.max(0, (el - starts[i]) / d * 100)) + '%';
    raf = requestAnimationFrame(follow);
  }
  const halt = () => { if(raf){ cancelAnimationFrame(raf); raf = null; } };
  au.onplay = () => {
    ALL_AUDIO.forEach(o => { if(o !== au) o.pause(); });   // one at a time
    stopTick(); halt(); last = -2; follow();
  };
  au.onpause = halt;
  au.onended = () => { halt(); pfill.style.width = '0'; };
  au.onseeking = () => { last = -2; };
}

function row(t){
  const tr = tbl.insertRow(-1);
  const c1 = tr.insertCell(-1); c1.className='n'; c1.textContent = t.n;
  const c2 = tr.insertCell(-1); c2.className='d'; c2.textContent = t.dur+'s';
  const c3 = tr.insertCell(-1);
  const au = document.createElement('audio'); au.controls = true; au.preload='metadata';
  au.src = '/m/'+t.files.none; c3.appendChild(au);
  const c4 = tr.insertCell(-1);
  const sel = document.createElement('select');
  for(const k of Object.keys(t.files)){
    const o = document.createElement('option'); o.value=k; o.textContent=k; sel.appendChild(o); }
  sel.onchange = () => { au.src = '/m/'+t.files[sel.value]; au.play(); };
  c4.appendChild(sel);
  const c5 = tr.insertCell(-1);
  const b = document.createElement('button'); b.className='use'; b.textContent='Use this';
  b.onclick = async () => {
    await fetch(`/choose?story=${STORY}&n=${t.n}&fx=${sel.value}`, {method:'POST'});
    document.querySelectorAll('.use').forEach(x=>x.classList.remove('chosen'));
    b.classList.add('chosen'); b.textContent='✓ in use';
  };
  const del = document.createElement('button');
  del.className = 'del'; del.textContent = '✕'; del.title = 'delete this take';
  del.onclick = async () => {
    if(!confirm('Delete take ' + t.n + '? This cannot be undone.')) return;
    au.pause();
    await fetch(`/delete?story=${STORY}&n=${t.n}`, {method:'POST'});
    const i = ALL_AUDIO.indexOf(au); if(i >= 0) ALL_AUDIO.splice(i, 1);
    tr.remove();
  };
  c5.appendChild(b); c5.appendChild(del);
  bindSync(au, t);
  ALL_AUDIO.push(au);
}
init();
</script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        """Serve a file, honouring Range.

        Chrome's <audio> element issues Range requests and expects 206 with a
        Content-Range. Answering every request with a plain 200 makes playback
        and seeking unreliable.
        """
        if not os.path.exists(path):
            return self._send(404, "no", "text/plain")
        size = os.path.getsize(path)
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            spec = rng.split("=", 1)[1].split(",")[0]
            s, _, e = spec.partition("-")
            start = int(s) if s.strip() else 0
            end = int(e) if e.strip() else size - 1
            end = min(end, size - 1)
            if start > end or start >= size:
                start, end = 0, size - 1
            with open(path, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        with open(path, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            page = (PAGE.replace("__CUES__", json.dumps(STATE["cues"]))
                        .replace("__STORY__", STATE["story"])
                        .replace("__W__", str(STATE["size"][0]))
                        .replace("__H__", str(STATE["size"][1])))
            return self._send(200, page, "text/html; charset=utf-8")
        if u.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if u.path == "/takes":
            return self._send(200, json.dumps(list_takes()))
        if u.path.startswith("/f/"):
            return self._file(os.path.join(STATE["dir"], os.path.basename(u.path[3:])),
                              "image/png")
        if u.path.startswith("/m/"):
            n = os.path.basename(u.path[3:])
            ct = "audio/mp4" if n.endswith(".m4a") else "audio/wav"
            return self._file(os.path.join(STATE["dir"], "takes", n), ct)
        self._send(404, "no", "text/plain")

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        n = int(q.get("n", ["1"])[0])
        d = STATE["dir"]
        takes = os.path.join(d, "takes")

        if u.path == "/take":
            # The server picks the number, not the client: if the highest take
            # is deleted the browser's counter would otherwise reuse a number
            # that still belongs to a surviving take.
            used = {int(f[4:6]) for f in os.listdir(takes)
                    if f.startswith("take") and f[4:6].isdigit()}
            n = (max(used) + 1) if used else 1
            ln = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(ln)
            ctype = self.headers.get("Content-Type", "")
            bound = ctype.split("boundary=")[-1].encode()
            meta, audio = {}, b""
            for part in body.split(b"--" + bound):
                if b"\r\n\r\n" not in part:
                    continue
                head, data = part.split(b"\r\n\r\n", 1)
                data = data.rstrip(b"\r\n")
                if b'name="meta"' in head:
                    meta = json.loads(data.decode())
                elif b'name="audio"' in head:
                    audio = data
            if not audio:
                return self._send(400, "no audio", "text/plain")

            base = os.path.join(takes, f"take{n:02d}")
            with open(base + ".webm", "wb") as fh:
                fh.write(audio)
            # The recorder is armed DURING the 3-2-1 count, because
            # MediaRecorder takes a moment to spin up and starting it on the
            # animation's first frame clips the opening syllable. So the count-in
            # is captured - and then replaced here with true digital silence.
            #
            # Net effect: real audio begins exactly when the animation begins,
            # the file keeps its full length, and t=lead still lines up with
            # frame 0. Level is normalised on the SPOKEN part only, so 3s of
            # room noise cannot drag the measurement around.
            lead_s = max(0, int(meta.get("lead", 3000))) / 1000.0
            src = base + ".webm"
            if lead_s > 0:
                ff("-i", src, "-filter_complex",
                   f"[0:a]atrim=start={lead_s:.3f},asetpts=N/SR/TB,"
                   f"{NORMALISE}[sp];"
                   f"anullsrc=r={SR}:cl=mono:d={lead_s:.3f}[sil];"
                   f"[sil][sp]concat=n=2:v=0:a=1[o]",
                   "-map", "[o]", "-ar", str(SR), "-ac", "1", base + ".wav")
            else:
                ff("-i", src, "-af", NORMALISE, "-ar", str(SR), "-ac", "1",
                   base + ".wav")
            files = {}
            for name, chain in ROBOTS.items():
                if name == "none":
                    files[name] = os.path.basename(base + ".wav")
                    continue
                out = f"{base}.{name}.m4a"
                ff("-i", base + ".wav", "-af", chain.format(sr=SR),
                   "-ar", str(SR), "-ac", "2", out)
                files[name] = os.path.basename(out)
            with open(base + ".json", "w") as fh:
                json.dump(meta, fh, indent=1)
            info = {"n": n, "dur": dur(base + ".wav"), "files": files,
                    "lead": meta.get("lead", 3000),
                    "pace": meta.get("pace", 1.0),
                    "cues": meta.get("cues", [])}
            print(f"  take {n:2d}  {info['dur']:6.2f}s  pace {meta.get('pace')}  "
                  f"-> {base}.wav")
            return self._send(200, json.dumps(info))

        if u.path == "/delete":
            base = os.path.join(takes, f"take{n:02d}")
            gone = 0
            for ext in (".webm", ".wav", ".json", ".m4a"):
                for f in os.listdir(takes):
                    fp = os.path.join(takes, f)
                    if f.startswith(f"take{n:02d}.") and f.endswith(ext):
                        os.remove(fp)
                        gone += 1
            print(f"  deleted take {n}  ({gone} files)")
            return self._send(200, json.dumps({"ok": True, "removed": gone}))

        if u.path == "/choose":
            fx = q.get("fx", ["none"])[0]
            src = os.path.join(takes, f"take{n:02d}" +
                               (".wav" if fx == "none" else f".{fx}.m4a"))
            os.makedirs(VOICE, exist_ok=True)
            dst = os.path.join(VOICE, f"{STATE['story']}.vo" +
                               os.path.splitext(src)[1])
            shutil.copy(src, dst)
            shutil.copy(os.path.join(takes, f"take{n:02d}.json"),
                        os.path.join(VOICE, f"{STATE['story']}.vo.json"))
            print(f"  chose take {n} ({fx}) -> {dst}")
            return self._send(200, json.dumps({"ok": True, "dst": dst}))

        self._send(404, "no", "text/plain")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--width", type=int, default=560)
    a = ap.parse_args()

    cues = prepare(a.story.upper(), a.width)
    spoken = sum(1 for c in cues if c["lines"])
    print(f"{a.story.upper()}: {len(cues)} frames, {spoken} speaking, "
          f"{sum(c['ms'] for c in cues) / 1000:.1f}s at pace 1.0")
    print(f"studio -> http://127.0.0.1:{a.port}")
    print(f"takes  -> {os.path.join(STATE['dir'], 'takes')}")
    print("ctrl-c to stop")

    class Srv(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    with Srv(("127.0.0.1", a.port), H) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()

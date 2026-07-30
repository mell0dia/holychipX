#!/usr/bin/env python3
"""voice_record.py — record a voice-over take in the browser, robotise it instantly.

Built for the HOLY CHIP moment: macOS `say` cannot perform a held vowel (see
story_gif/story_voice notes - repeated letters normalise away and phoneme mode
is dead), so that line is performed by a human and put through the same robot
chain as the synthetic bot dialogue.

Serves a page on http://127.0.0.1:8899 . Browser mic capture needs a secure
context, and 127.0.0.1 counts as one - a file:// page does NOT, which is why
this is a server and not just an .html file.

Each take is saved raw, auto-trimmed of leading/trailing silence, and rendered
through three robot treatments so you can A/B them on your own voice
immediately. "Use this take" copies it to the canonical path.

    voice_record.py                    # record the HOLY CHIP catchphrase
    voice_record.py --slot hc030_l1    # record some other line
    voice_record.py --port 9000

Takes land in ~/holy-chip/voice/takes/ ; the chosen one in ~/holy-chip/voice/.
"""
import os, sys, json, argparse, subprocess, shutil, http.server, socketserver, urllib.parse

HC = os.path.expanduser("~/holy-chip")
VOICE = os.path.join(HC, "voice")
TAKES = os.path.join(VOICE, "takes")
SR = 44100

# Trim silence off both ends so the clip starts exactly on the word - essential
# for lining the audio up with the frame it belongs to.
TRIM = ("silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB:"
        "detection=peak,areverse,"
        "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB:"
        "detection=peak,areverse")

ROBOTS = {
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


def ff(*a):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + list(a),
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-500:])


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()), 2)
    except ValueError:
        return 0.0


def process(webm, slot, n):
    """raw webm -> trimmed wav + one m4a per robot treatment."""
    base = os.path.join(TAKES, f"{slot}_{n:02d}")
    wav = base + ".wav"
    ff("-i", webm, "-af", TRIM, "-ar", str(SR), "-ac", "1", wav)
    out = {"n": n, "raw": os.path.basename(wav), "dur": dur(wav), "robots": {}}
    for name, chain in ROBOTS.items():
        m4a = f"{base}.{name}.m4a"
        ff("-i", wav, "-af", chain.format(sr=SR), "-ar", str(SR), "-ac", "2", m4a)
        out["robots"][name] = os.path.basename(m4a)
    return out


PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Holy Chip — voice recorder</title>
<style>
:root{--bg:#14161a;--bg2:#1b1e24;--line:#2f343d;--txt:#e6e9ef;--dim:#8b93a1;
      --acc:#ffcf2d;--acc2:#4ad0ff;--rec:#ff5c5c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);padding:28px 24px 70px;max-width:1000px;
  font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
h1{font-size:20px;margin:0 0 4px}h1 b{color:var(--acc)}
.sub{color:var(--dim);font-size:13px;margin-bottom:20px}
.script{background:var(--bg2);border-left:3px solid var(--acc);border-radius:4px;
  padding:14px 18px;margin-bottom:20px;font-size:17px;letter-spacing:.4px}
.script i{color:var(--acc2);font-style:normal}
.bar{display:flex;align-items:center;gap:14px;margin-bottom:8px}
button{font:inherit;cursor:pointer;border-radius:7px;border:1px solid var(--line);
  background:#23272f;color:var(--txt);padding:9px 16px}
button:hover{background:#2c313a}
button:disabled{opacity:.4;cursor:default}
#rec{background:var(--rec);border-color:var(--rec);color:#1a1a1a;font-weight:700;
  min-width:190px;font-size:15px;padding:12px 18px}
#rec.on{background:#7ddb8f;border-color:#7ddb8f}
#meter{flex:1;height:10px;background:#0f1114;border:1px solid var(--line);
  border-radius:6px;overflow:hidden}
#lvl{height:100%;width:0;background:linear-gradient(90deg,#4ad0ff,#ffcf2d,#ff5c5c)}
.hint{color:var(--dim);font-size:12px;margin-bottom:22px}
kbd{background:#0f1114;border:1px solid var(--line);border-radius:3px;padding:1px 6px;font-size:11px}
table{border-collapse:collapse;width:100%}
th{text-align:left;font-size:11px;letter-spacing:.8px;text-transform:uppercase;color:var(--dim);
  padding:0 8px 8px;border-bottom:1px solid var(--line);font-weight:600}
td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:hover{background:var(--bg2)}
td.n{color:var(--acc);font-weight:700;width:26px}
td.d{color:var(--dim);font-size:11.5px;width:52px;font-variant-numeric:tabular-nums}
audio{height:32px;width:180px;vertical-align:middle}
.lab{color:var(--dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;
  display:block;margin-bottom:2px}
.use{background:transparent;border-color:var(--acc);color:var(--acc);padding:6px 11px;font-size:12px}
.use.chosen{background:var(--acc);color:#1a1a1a;font-weight:700}
#err{color:var(--rec);font-size:12px;margin-top:10px}
</style></head><body>
<h1>Holy Chip — <b>voice recorder</b></h1>
<div class="sub">Records in the browser, trims the silence, and robotises every take instantly.</div>
<div class="script">__SCRIPT__</div>
<div class="bar">
  <button id="rec">● Record</button>
  <div id="meter"><div id="lvl"></div></div>
</div>
<div class="hint">Hit <kbd>space</kbd> to start and stop. Record as many takes as you like —
  nothing is overwritten. Then pick one with <b>Use this</b>.</div>
<table id="tbl"><tr><th class="n">#</th><th class="d">len</th><th>raw</th>
  <th>subtle</th><th>machine</th><th>heavy</th><th></th></tr></table>
<div id="err"></div>
<script>
const slot = "__SLOT__";
let mr, chunks = [], n = 0, on = false, ctx, analyser, raf;
const recBtn = document.getElementById('rec'), lvl = document.getElementById('lvl'),
      tbl = document.getElementById('tbl'), err = document.getElementById('err');

async function init(){
  try{
    const s = await navigator.mediaDevices.getUserMedia({audio:{
      echoCancellation:false, noiseSuppression:false, autoGainControl:false}});
    mr = new MediaRecorder(s, {mimeType:'audio/webm'});
    mr.ondataavailable = e => chunks.push(e.data);
    mr.onstop = save;
    ctx = new AudioContext();
    analyser = ctx.createAnalyser(); analyser.fftSize = 512;
    ctx.createMediaStreamSource(s).connect(analyser);
    meter();
  }catch(e){ err.textContent = 'Microphone blocked: ' + e.message; recBtn.disabled = true; }
}
function meter(){
  const b = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(b);
  let pk = 0; for(const v of b) pk = Math.max(pk, Math.abs(v-128));
  lvl.style.width = Math.min(100, pk/128*140) + '%';
  raf = requestAnimationFrame(meter);
}
function toggle(){
  if(!mr) return;
  if(on){ mr.stop(); on = false; recBtn.textContent = '● Record'; recBtn.classList.remove('on'); }
  else{ chunks = []; mr.start(); on = true;
        recBtn.textContent = '■ Stop'; recBtn.classList.add('on'); }
}
recBtn.onclick = toggle;
document.addEventListener('keydown', e => {
  if(e.code === 'Space' && e.target.tagName !== 'BUTTON'){ e.preventDefault(); toggle(); }
});
async function save(){
  const blob = new Blob(chunks, {type:'audio/webm'});
  n++;
  const r = await fetch(`/take?slot=${slot}&n=${n}`, {method:'POST', body:blob});
  if(!r.ok){ err.textContent = 'Save failed: ' + await r.text(); return; }
  row(await r.json());
}
function row(t){
  const tr = tbl.insertRow(-1);
  const cell = (h, c) => { const d = tr.insertCell(-1); d.innerHTML = h; if(c) d.className = c; };
  cell(t.n, 'n'); cell(t.dur + 's', 'd');
  cell(`<audio controls preload="metadata" src="/media/${t.raw}"></audio>`);
  for(const k of ['subtle','machine','heavy'])
    cell(`<audio controls preload="metadata" src="/media/${t.robots[k]}"></audio>`);
  const d = tr.insertCell(-1);
  const b = document.createElement('button');
  b.className = 'use'; b.textContent = 'Use this';
  b.onclick = async () => {
    await fetch(`/choose?slot=${slot}&n=${t.n}`, {method:'POST'});
    document.querySelectorAll('.use').forEach(x => x.classList.remove('chosen'));
    b.classList.add('chosen'); b.textContent = '✓ In use';
  };
  d.appendChild(b);
  tr.scrollIntoView({block:'nearest'});
}
init();
</script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    slot = "holychip"
    script = 'HOOOOOOly &nbsp;<i>—</i>&nbsp; [bleep] &nbsp;<i>—</i>&nbsp; CHIIIIIP!'
    takes = 0

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

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            page = (PAGE.replace("__SLOT__", H.slot)
                        .replace("__SCRIPT__", H.script))
            return self._send(200, page, "text/html; charset=utf-8")
        if u.path.startswith("/media/"):
            name = os.path.basename(u.path[len("/media/"):])
            p = os.path.join(TAKES, name)
            if not os.path.exists(p):
                return self._send(404, "no")
            ct = "audio/mp4" if name.endswith(".m4a") else "audio/wav"
            with open(p, "rb") as fh:
                return self._send(200, fh.read(), ct)
        self._send(404, "no")

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        slot = q.get("slot", [H.slot])[0]
        n = int(q.get("n", ["1"])[0])

        if u.path == "/take":
            ln = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(ln)
            tmp = os.path.join(TAKES, f"{slot}_{n:02d}.webm")
            with open(tmp, "wb") as fh:
                fh.write(raw)
            try:
                info = process(tmp, slot, n)
            except Exception as e:
                return self._send(500, str(e), "text/plain")
            print(f"  take {n:2d}  {info['dur']:5.2f}s  -> {info['raw']}")
            return self._send(200, json.dumps(info))

        if u.path == "/choose":
            src = os.path.join(TAKES, f"{slot}_{n:02d}.wav")
            dst = os.path.join(VOICE, f"{slot}.wav")
            shutil.copy(src, dst)
            for name in ROBOTS:
                s2 = os.path.join(TAKES, f"{slot}_{n:02d}.{name}.m4a")
                if os.path.exists(s2):
                    shutil.copy(s2, os.path.join(VOICE, f"{slot}.{name}.m4a"))
            print(f"  chose take {n} -> {dst}")
            return self._send(200, json.dumps({"ok": True}))

        self._send(404, "no")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="holychip")
    ap.add_argument("--script", default=None)
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()

    os.makedirs(TAKES, exist_ok=True)
    H.slot = a.slot
    if a.script:
        H.script = a.script

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", a.port), H) as srv:
        print(f"recorder for '{a.slot}' -> http://127.0.0.1:{a.port}")
        print(f"takes: {TAKES}")
        print("ctrl-c to stop")
        srv.serve_forever()


if __name__ == "__main__":
    main()

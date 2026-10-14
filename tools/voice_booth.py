#!/usr/bin/env python3
"""Voice booth: record the narration of a Holy Chip video yourself, line by line.

    python3 tools/voice_booth.py            # http://localhost:8890

Pick an episode (any content/video/<dir> with audio/lines.json), see its
scenes with the drawing and every narration line, press RECORD, read, press
STOP. Each take is saved as 48 kHz mono WAV at

    content/video/<dir>/audio/rec/<beat>_<k>.wav      (same key as the TTS line)

so the video pipeline can pick it up in place of the TTS line (and a speech-
to-speech engine can re-voice it). PLAY hears your take; TTS hears the current
machine line for timing reference. Re-recording overwrites; the old take is
kept once as .prev.wav. Keys: R record/stop, SPACE play my take, T play TTS,
arrows previous/next line.
"""
import json, re, subprocess, time
from pathlib import Path
from flask import Flask, request, send_file, jsonify, Response, abort

VIDEO = Path.home() / "holy-chip" / "content" / "video"
PORT = 8890
app = Flask(__name__)


def episodes():
    out = []
    # newest episode first (the one being worked on), so it is the default
    for d in sorted((x for x in VIDEO.iterdir() if (x / "audio" / "lines.json").exists()),
                    key=lambda x: (x / "audio" / "lines.json").stat().st_mtime, reverse=True):
        lines = json.loads((d / "audio" / "lines.json").read_text())
        if lines and isinstance(lines[0], dict) and "beat" in lines[0]:      # the screenplay format only (not the first pilot)
            n = len(lines)
            rec = len(list((d / "audio" / "rec").glob("*.wav"))) if (d / "audio" / "rec").exists() else 0
            rec = len([p for p in (d / "audio" / "rec").glob("*.wav") if not p.name.endswith(".prev.wav")]) if rec else 0
            out.append({"dir": d.name, "lines": n, "recorded": rec})
    return out


def safe_dir(name):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not (VIDEO / name / "audio" / "lines.json").exists():
        abort(404)
    return VIDEO / name


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.get("/api/episodes")
def api_episodes():
    return jsonify(episodes())


@app.get("/api/lines")
def api_lines():
    d = safe_dir(request.args.get("dir", ""))
    lines = json.loads((d / "audio" / "lines.json").read_text())
    beats = {}
    try:                                   # older pilots keep beats in other shapes; the drawing is optional
        raw = json.loads((d / "beats.json").read_text())
        for b in (raw if isinstance(raw, list) else raw.values()):
            if isinstance(b, dict) and b.get("id"):
                beats[b["id"]] = {"img": b.get("img"), "prompt": b.get("prompt", "")}
    except Exception:
        pass
    rec = d / "audio" / "rec"
    for l in lines:
        key = f"{l['beat']}_{l['k']}"
        l["key"] = key
        l["rec"] = (rec / f"{key}.wav").exists()
        l["img"] = beats.get(l["beat"], {}).get("img")
    return jsonify({"dir": d.name, "lines": lines, "title": d.name})


@app.get("/media/<name>/<path:rel>")
def media(name, rel):
    d = safe_dir(name)
    p = (d / rel).resolve()           # PT workspaces symlink bg/ and clips/ to the EN one: stay inside content/video
    if not str(p).startswith(str(VIDEO.resolve())) or not p.exists():
        abort(404)
    return send_file(p, max_age=0)


@app.post("/api/save")
def api_save():
    d = safe_dir(request.args.get("dir", ""))
    key = request.args.get("key", "")
    if not re.fullmatch(r"s[0-9A-Za-z.]+_\d+|[A-Za-z0-9.]+_\d+", key):
        abort(400)
    rec = d / "audio" / "rec"; rec.mkdir(parents=True, exist_ok=True)
    raw = rec / f"{key}.upload"; raw.write_bytes(request.get_data())
    out = rec / f"{key}.wav"
    if out.exists():
        out.replace(rec / f"{key}.prev.wav")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-ac", "1", "-ar", "48000",
                        "-sample_fmt", "s16", str(out)], capture_output=True, text=True)
    raw.unlink(missing_ok=True)
    if r.returncode != 0 or not out.exists():
        return jsonify({"ok": False, "error": r.stderr[-300:]}), 500
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout.strip() or 0)
    return jsonify({"ok": True, "file": f"audio/rec/{key}.wav", "dur": round(dur, 2)})


@app.delete("/api/take")
def api_delete():
    d = safe_dir(request.args.get("dir", "")); key = request.args.get("key", "")
    p = d / "audio" / "rec" / f"{key}.wav"
    if p.exists():
        p.replace(d / "audio" / "rec" / f"{key}.prev.wav")
    return jsonify({"ok": True})


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Holy Chip · Voice Booth</title>
<style>
  :root { --ink:#141414; --paper:#f8f9f2; --red:#c0392b; --green:#1e8449; --grey:#888; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family: "Chakra Petch", -apple-system, Helvetica, sans-serif; }
  header { display:flex; align-items:center; gap:18px; padding:14px 22px; background:var(--ink); color:#fff; }
  header h1 { font-size:16px; letter-spacing:.18em; text-transform:uppercase; margin:0; }
  select { font: inherit; padding:6px 10px; }
  .wrap { display:grid; grid-template-columns: 1fr 360px; gap:0; height: calc(100vh - 58px); }
  .lines { overflow:auto; padding:18px 22px; }
  .scene { font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:var(--grey); margin:22px 0 6px; }
  .line { display:grid; grid-template-columns: 28px 1fr auto; gap:12px; align-items:center; padding:10px 12px; border:2px solid transparent; border-radius:8px; cursor:pointer; }
  .line.active { border-color: var(--ink); background:#fff; }
  .line .n { color:var(--grey); font-size:12px; }
  .line .t { font-size:18px; line-height:1.35; }
  .line .s { font-size:11px; color:var(--grey); white-space:nowrap; }
  .line.rec .s { color:var(--green); }
  .side { border-left:2px solid var(--ink); padding:18px; display:flex; flex-direction:column; gap:14px; background:#fff; }
  .side img { width:100%; border:1px solid #ddd; border-radius:6px; background:#fff; }
  .big { font-size:22px; line-height:1.35; min-height:3em; }
  .btns { display:grid; grid-template-columns: 1fr 1fr; gap:10px; }
  button { font: inherit; font-weight:700; letter-spacing:.08em; text-transform:uppercase; padding:14px 10px; border:2px solid var(--ink); background:#fff; border-radius:8px; cursor:pointer; }
  button:disabled { opacity:.35; cursor:default; }
  #recbtn { grid-column: 1 / -1; font-size:18px; padding:20px; }
  #recbtn.on { background:var(--red); color:#fff; border-color:var(--red); }
  .meter { height:8px; background:#eee; border-radius:4px; overflow:hidden; } .meter i { display:block; height:100%; width:0; background:var(--green); }
  .status { font-size:12px; color:var(--grey); min-height:1.2em; }
  .help { font-size:11px; color:var(--grey); line-height:1.6; margin-top:auto; }
  .count { font-size:12px; color:var(--grey); }
</style></head><body>
<header><h1>Holy Chip · Voice Booth</h1><select id="ep"></select><span class="count" id="count"></span></header>
<div class="wrap">
  <div class="lines" id="lines"></div>
  <div class="side">
    <img id="img" alt="">
    <div class="big" id="big">Pick a line.</div>
    <div class="meter"><i id="meter"></i></div>
    <div class="btns">
      <button id="recbtn">● Record</button>
      <button id="playbtn" disabled>▶ My take</button>
      <button id="ttsbtn" disabled>▶ TTS line</button>
      <button id="prevbtn">◀ Prev</button>
      <button id="nextbtn">Next ▶</button>
      <button id="delbtn" disabled>✕ Delete take</button>
    </div>
    <div class="status" id="status"></div>
    <div class="help">R = record / stop · SPACE = play my take · T = play TTS line · ↑ ↓ = previous / next<br>
      Takes are saved as 48 kHz WAV in <code>content/video/&lt;episode&gt;/audio/rec/</code>, one file per line.<br>
      Leave a beat of silence before and after each line; the pipeline trims it.</div>
  </div>
</div>
<script>
let DIR=null, LINES=[], cur=-1, media=null, rec=null, chunks=[], recording=false, player=new Audio(), ctx=null, analyser=null;
const $=id=>document.getElementById(id);
async function loadEpisodes(){
  const eps=await (await fetch('/api/episodes')).json();
  $('ep').innerHTML=eps.map(e=>`<option value="${e.dir}">${e.dir} — ${e.recorded}/${e.lines} recorded</option>`).join('');
  const want=localStorage.getItem('booth-dir'); if(want && eps.some(e=>e.dir===want)) $('ep').value=want;
  await loadLines($('ep').value);
}
async function loadLines(dir){
  DIR=dir; localStorage.setItem('booth-dir',dir);
  const d=await (await fetch('/api/lines?dir='+encodeURIComponent(dir))).json(); LINES=d.lines;
  let html='', beat=null;
  LINES.forEach((l,i)=>{ if(l.beat!==beat){ beat=l.beat; html+=`<div class="scene">Scene ${beat}</div>`; }
    html+=`<div class="line${l.rec?' rec':''}" id="L${i}" onclick="select(${i})"><span class="n">${i+1}</span><span class="t">${esc(l.text)}</span><span class="s">${l.rec?'✓ recorded':''}</span></div>`; });
  $('lines').innerHTML=html; updateCount();
  select(Math.max(0, LINES.findIndex(l=>!l.rec)));
}
function esc(s){ return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function updateCount(){ const n=LINES.filter(l=>l.rec).length; $('count').textContent=`${n} / ${LINES.length} recorded`; }
function select(i){
  if(recording) return;
  cur=i; const l=LINES[i]; if(!l) return;
  document.querySelectorAll('.line').forEach(e=>e.classList.remove('active')); $('L'+i).classList.add('active'); $('L'+i).scrollIntoView({block:'nearest'});
  $('big').textContent=l.text; $('img').src=l.img?`/media/${DIR}/bg/${l.img}.png`:''; $('img').style.display=l.img?'block':'none';
  $('playbtn').disabled=!l.rec; $('delbtn').disabled=!l.rec; $('ttsbtn').disabled=!l.file; $('status').textContent=l.rec?'Take saved. Record again to replace it.':'No take yet.';
}
async function toggleRecord(){
  if(cur<0) return;
  if(!recording){
    if(!media){ media=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
      ctx=new AudioContext(); analyser=ctx.createAnalyser(); ctx.createMediaStreamSource(media).connect(analyser); meter(); }
    chunks=[]; rec=new MediaRecorder(media); rec.ondataavailable=e=>chunks.push(e.data);
    rec.onstop=async()=>{ const blob=new Blob(chunks,{type:rec.mimeType}); $('status').textContent='Saving…';
      const r=await (await fetch(`/api/save?dir=${encodeURIComponent(DIR)}&key=${LINES[cur].key}`,{method:'POST',body:blob})).json();
      if(r.ok){ LINES[cur].rec=true; $('L'+cur).classList.add('rec'); $('L'+cur).querySelector('.s').textContent='✓ recorded'; updateCount(); select(cur); $('status').textContent=`Saved ${r.file} (${r.dur}s)`; }
      else $('status').textContent='Save failed: '+r.error; };
    rec.start(); recording=true; $('recbtn').textContent='■ Stop'; $('recbtn').classList.add('on'); $('status').textContent='Recording… read the line, then stop.';
  } else { rec.stop(); recording=false; $('recbtn').textContent='● Record'; $('recbtn').classList.remove('on'); }
}
function meter(){ const a=new Uint8Array(analyser.fftSize); (function f(){ analyser.getByteTimeDomainData(a); let m=0; for(const v of a) m=Math.max(m,Math.abs(v-128)); $('meter').style.width=Math.min(100,m/128*160)+'%'; requestAnimationFrame(f); })(); }
function playTake(){ const l=LINES[cur]; if(!l||!l.rec) return; player.src=`/media/${DIR}/audio/rec/${l.key}.wav?t=${Date.now()}`; player.play(); }
function playTTS(){ const l=LINES[cur]; if(!l||!l.file) return; player.src=`/media/${DIR}/${l.file}`; player.play(); }
async function delTake(){ const l=LINES[cur]; if(!l||!l.rec) return; await fetch(`/api/take?dir=${encodeURIComponent(DIR)}&key=${l.key}`,{method:'DELETE'}); l.rec=false; $('L'+cur).classList.remove('rec'); $('L'+cur).querySelector('.s').textContent=''; updateCount(); select(cur); }
$('recbtn').onclick=toggleRecord; $('playbtn').onclick=playTake; $('ttsbtn').onclick=playTTS; $('delbtn').onclick=delTake;
$('prevbtn').onclick=()=>select(Math.max(0,cur-1)); $('nextbtn').onclick=()=>select(Math.min(LINES.length-1,cur+1));
$('ep').onchange=e=>loadLines(e.target.value);
document.addEventListener('keydown',e=>{ if(e.target.tagName==='SELECT') return;
  if(e.key==='r'||e.key==='R'){ e.preventDefault(); toggleRecord(); }
  else if(e.key===' '){ e.preventDefault(); playTake(); } else if(e.key==='t'||e.key==='T'){ playTTS(); }
  else if(e.key==='ArrowDown'||e.key==='ArrowRight'){ e.preventDefault(); select(Math.min(LINES.length-1,cur+1)); }
  else if(e.key==='ArrowUp'||e.key==='ArrowLeft'){ e.preventDefault(); select(Math.max(0,cur-1)); } });
loadEpisodes();
</script></body></html>"""

if __name__ == "__main__":
    print(f"Voice booth: http://localhost:{PORT}  (episodes: {', '.join(e['dir'] for e in episodes())})")
    app.run(host="127.0.0.1", port=PORT, debug=False)

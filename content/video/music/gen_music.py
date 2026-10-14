"""Free, local, MIT-licensed music for the videos: ACE-Step 1.5 (turbo DiT, no LM)."""
import sys, os, shutil
sys.path.insert(0, '/Users/rmello/holy-chip/vendor/ACE-Step-1.5')
os.chdir('/Users/rmello/holy-chip/vendor/ACE-Step-1.5')
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music
OUT = '/Users/rmello/holy-chip/content/video/music'
dit = AceStepHandler()
print(dit.initialize_service(project_root=os.getcwd(), config_path="acestep-v15-turbo", device="mps"))
llm = LLMHandler()
TRACKS = {
 "A_synthpop": "playful futuristic synth pop instrumental, curious and optimistic, bubbly arpeggios, soft analog synthesizers, light electronic drums, whimsical and cinematic",
 "B_chiptune": "retro futuristic electronic instrumental, cheerful chiptune melody over warm synth pads, gentle beat, quirky, positive, cartoon",
 "C_dreamy":   "futuristic lo-fi electronic instrumental, dreamy synths, light groove, optimistic, wonder and curiosity, space age",
}
if len(sys.argv) > 2:                       # make_video.py: one custom track "name mood"
    TRACKS = {sys.argv[1]: sys.argv[2] + ", instrumental"}
for name, cap in TRACKS.items():
    p = GenerationParams(caption=cap, lyrics="[Instrumental]", instrumental=True, bpm=100, duration=100,
                         thinking=False, inference_steps=8, seed=23)
    r = generate_music(dit, llm, p, GenerationConfig(batch_size=1, audio_format="wav"), save_dir=OUT + '/tmp')
    if not r.success:
        print(name, 'ERROR', r.error); continue
    shutil.move(r.audios[0]['path'], f'{OUT}/{name}.wav'); print(name, 'ok', flush=True)

"""Local, free images (SDXL + LCM-LoRA on MPS) with a consistent 'artist' and characters.

jobs.json: [{id, prompt, color, seed, style, kind, ref}]
  kind 'anchor'  : drawn from the style text alone -> becomes the style reference ("the artist")
  kind 'char'    : a character portrait, in the artist's style (IP-Adapter style-only)
  kind 'scene'   : a scene; ref = style image (style-only) or a character portrait (0.55, content+style)
Content goes to CLIP-L (prompt), style + composition to OpenCLIP-G (prompt_2): neither is cut at 77 tokens."""
import os, sys, json, time, torch
from diffusers import DiffusionPipeline, LCMScheduler
from PIL import Image
from transformers import CLIPVisionModelWithProjection
jobs0 = json.load(open(sys.argv[1]))
FACE = any(j.get('char') for j in jobs0)          # character scenes: face-locked reference (IP-Adapter Plus Face)
enc = CLIPVisionModelWithProjection.from_pretrained("h94/IP-Adapter", subfolder="models/image_encoder", torch_dtype=torch.float16) if FACE else None
pipe = DiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", image_encoder=enc, torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
pipe.load_lora_weights("latent-consistency/lcm-lora-sdxl"); pipe.fuse_lora()
pipe.to("mps")
COMPOSE = "whole scene visible, centered, generous empty paper margins, nothing cut off, no text, no letters"
NEG = "extra limbs, extra arms, extra hands, extra legs, deformed anatomy, newspapers, stacks of paper, documents, books, top hat, thick lines, heavy black shading, dark, scary, cluttered, busy, 3d render, photo, realistic, anime, cropped, cut off, text, letters, words, watermark, logo"
STYLE_ONLY = {"up": {"block_0": [0.0, 0.4, 0.0]}}      # InstantStyle at HALF: stroke without erasing the scene (1.0 wiped content)
CHAR_SCALE = float(os.environ.get('CHAR_SCALE', 0.7))   # face lock strength (lower = actions come through)
jobs = json.load(open(sys.argv[1]))
adapter = False
def draw(j, ref=None, scale=None):
    global adapter
    c = j.get('color', '').strip()
    accent = f", soft watercolor touch on {c}" if c else ""
    kw = dict(prompt=j['prompt'] + accent, prompt_2=j['prompt'] + accent + ", " + j['style'] + ", " + COMPOSE, negative_prompt=NEG + (', ' + j['avoid'] if j.get('avoid') else ''),   # content in BOTH encoders (was style-only: scenes ignored the text)
              num_inference_steps=6, guidance_scale=1.5, width=1024, height=1024,
              generator=torch.Generator("cpu").manual_seed(j.get('seed', 7)))
    if ref is not None:
        if not adapter:
            pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models",
                                 weight_name="ip-adapter-plus-face_sdxl_vit-h.safetensors" if FACE else "ip-adapter_sdxl.bin"); adapter = True
        pipe.set_ip_adapter_scale(scale); kw['ip_adapter_image'] = Image.open(ref).convert('RGB')
    t = time.time(); pipe(**kw).images[0].save(f"bg/{j['id']}.png")
    if j.get('rednose'):                                  # character look: black and white, only the red nose
        from rednose import red_nose_only; red_nose_only(f"bg/{j['id']}.png", f"bg/{j['id']}.png")
    print(f"bg/{j['id']}.png {j['kind']} {time.time()-t:.1f}s", flush=True)
order = {'anchor': 0, 'char': 1, 'scene': 2}
for j in sorted(jobs, key=lambda j: order[j['kind']]):
    if j['kind'] in ('anchor', 'char'):                 # artist sheet + character portraits: from the text alone
        draw(j)
    elif j['kind'] == 'char' or not (j.get('ref', '').startswith('bg/_char') or j.get('char')):
        draw(j, j['ref'], STYLE_ONLY)
    else:
        draw(j, j['ref'], CHAR_SCALE)

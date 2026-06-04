#!/usr/bin/env node

/**
 * Create animated GIF: 25 random NFT images (slow→fast) + brand image (5s hold)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const CHARS_DIR = path.join(__dirname, 'Characters');
const BRAND = path.join(__dirname, '..', 'website', 'holy-chip-site', 'assets', 'brand.png');
const OUT = path.join(__dirname, 'holy-chip-animation.gif');
const TMP = '/tmp/hc-gif-frames';

// Clean and create temp dir
if (fs.existsSync(TMP)) fs.rmSync(TMP, { recursive: true });
fs.mkdirSync(TMP, { recursive: true });

// Pick 25 random images
const allImages = fs.readdirSync(CHARS_DIR).filter(f => f.endsWith('.png'));
const shuffled = allImages.sort(() => Math.random() - 0.5);
const picked = shuffled.slice(0, 25);

console.log(`Selected 25 images from ${allImages.length} total\n`);

// Generate frame durations: 800ms → 80ms (gentler exponential decay)
const durations = [];
for (let i = 0; i < 25; i++) {
  durations.push(Math.round(800 * Math.exp(-i * 0.095)));
}

// Resize all frames to 500x500
console.log('Creating frames...');
for (let i = 0; i < picked.length; i++) {
  const src = path.join(CHARS_DIR, picked[i]);
  const dst = path.join(TMP, `frame_${String(i).padStart(3, '0')}.png`);
  execSync(`ffmpeg -y -loglevel error -i "${src}" -vf "scale=250:250:force_original_aspect_ratio=decrease,pad=250:250:(ow-iw)/2:(oh-ih)/2:white" "${dst}"`);
  console.log(`  Frame ${i + 1}: ${picked[i]} (${durations[i]}ms)`);
}

// Brand image as final frame — flatten transparency onto white background
const brandDst = path.join(TMP, 'frame_025.png');
execSync(`ffmpeg -y -loglevel error -f lavfi -i "color=white:250x250" -i "${BRAND}" -filter_complex "[1:v]scale=250:250:force_original_aspect_ratio=decrease[scaled];[0:v][scaled]overlay=(W-w)/2:(H-h)/2:shortest=1" -frames:v 1 "${brandDst}"`);
console.log('  Brand: 5000ms\n');

// Use Python/Pillow to build GIF with per-frame delays (more reliable than ffmpeg concat for GIFs)
console.log('Building GIF...');

const pyScript = path.join(TMP, 'build_gif.py');
const frames = [];
for (let i = 0; i < 25; i++) {
  frames.push({ file: path.join(TMP, `frame_${String(i).padStart(3, '0')}.png`), delay: durations[i] });
}
frames.push({ file: path.join(TMP, 'frame_025.png'), delay: 5000 });

const pyCode = `
from PIL import Image
import sys

frames_data = ${JSON.stringify(frames)}
images = []
delays = []

for f in frames_data:
    img = Image.open(f['file']).convert('RGBA')
    # Flatten onto white background
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.paste(img, (0, 0), img)
    images.append(bg.convert('P', palette=Image.ADAPTIVE, colors=128))
    delays.append(f['delay'])

images[0].save(
    '${OUT.replace(/'/g, "\\'")}',
    save_all=True,
    append_images=images[1:],
    duration=delays,
    loop=0,
    optimize=False
)
print(f"Saved {len(images)} frames")
`;

fs.writeFileSync(pyScript, pyCode);

try {
  const result = execSync(`python3 "${pyScript}"`, { encoding: 'utf8' });
  console.log(result.trim());
} catch (err) {
  // If Pillow not installed, try installing it
  console.log('Installing Pillow...');
  execSync('pip3 install Pillow --quiet');
  const result = execSync(`python3 "${pyScript}"`, { encoding: 'utf8' });
  console.log(result.trim());
}

const size = (fs.statSync(OUT).size / 1024 / 1024).toFixed(1);
console.log(`\nDone! ${OUT} (${size} MB)`);

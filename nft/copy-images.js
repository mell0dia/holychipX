#!/usr/bin/env node

/**
 * NFT Image Consolidation Script
 *
 * Copies images from Google Drive PERSONAGENS/{CHARACTER}/_nft/ folders
 * to HolyChip/nft/Characters/ with natural binary filenames (0, 1, 10, 11, 100...).
 * Images are RANDOMLY SHUFFLED so consecutive binary IDs come from different characters.
 * Incremental: reads existing manifest.json and only copies NEW images.
 * Generates/updates manifest.json for traceability.
 */

const fs = require('fs');
const path = require('path');

const GDRIVE = path.join(
  process.env.HOME,
  'Library/CloudStorage/GoogleDrive-rico.duoba@gmail.com/My Drive/HC-BIG-MARKETING-STRATEGY/PERSONAGENS'
);
const DEST = path.join(__dirname, 'Characters');
const ORIGINALS = path.join(__dirname, 'nft_original_name');
const MANIFEST_PATH = path.join(__dirname, 'Characters', 'manifest.json');

// Ensure destination folders exist
if (!fs.existsSync(DEST)) {
  fs.mkdirSync(DEST, { recursive: true });
}
if (!fs.existsSync(ORIGINALS)) {
  fs.mkdirSync(ORIGINALS, { recursive: true });
}

// Load existing manifest (for incremental runs)
let manifest = {};
let nextId = 0;
const alreadyCopied = new Set();

if (fs.existsSync(MANIFEST_PATH)) {
  manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
  for (const entry of Object.values(manifest)) {
    alreadyCopied.add(`${entry.character}/${entry.original}`);
    if (entry.id >= nextId) {
      nextId = entry.id + 1;
    }
  }
  console.log(`Existing manifest: ${alreadyCopied.size} images (next ID: ${nextId})\n`);
}

// Get all character folders with _nft subfolders
const characters = fs.readdirSync(GDRIVE).filter(dir => {
  const nftPath = path.join(GDRIVE, dir, '_nft');
  return fs.existsSync(nftPath) && fs.statSync(nftPath).isDirectory();
}).sort();

console.log(`Found ${characters.length} characters with _nft folders`);

// Collect only NEW images
const newImages = [];

for (const character of characters) {
  const nftDir = path.join(GDRIVE, character, '_nft');
  const images = fs.readdirSync(nftDir)
    .filter(f => f.toLowerCase().endsWith('.png'))
    .sort();

  let newCount = 0;
  for (const originalName of images) {
    const key = `${character}/${originalName}`;
    if (alreadyCopied.has(key)) continue;

    const baseName = originalName.replace('.png', '');
    const parts = baseName.split('.');
    const attributes = {};
    for (const part of parts) {
      const letter = part.charAt(0);
      const code = parseInt(part.substring(1), 10);
      if (!isNaN(code)) {
        attributes[letter] = code;
      }
    }

    newImages.push({
      character,
      original: originalName,
      srcPath: path.join(nftDir, originalName),
      attributes
    });
    newCount++;
  }

  console.log(`${character}: ${images.length} total, ${newCount} new`);
}

if (newImages.length === 0) {
  console.log('\nNo new images to copy. Everything is up to date.');
  process.exit(0);
}

console.log(`\nNew images to copy: ${newImages.length}`);
console.log('Shuffling new images randomly...\n');

// Fisher-Yates shuffle (only new images)
for (let i = newImages.length - 1; i > 0; i--) {
  const j = Math.floor(Math.random() * (i + 1));
  [newImages[i], newImages[j]] = [newImages[j], newImages[i]];
}

// Copy in shuffled order with natural binary names (0, 1, 10, 11, 100, ...)
for (let i = 0; i < newImages.length; i++) {
  const img = newImages[i];
  const id = nextId + i;
  const binaryName = id.toString(2) + '.png';

  fs.copyFileSync(img.srcPath, path.join(DEST, binaryName));
  fs.copyFileSync(img.srcPath, path.join(ORIGINALS, img.original));

  manifest[id.toString(2)] = {
    id,
    binary: id.toString(2),
    character: img.character,
    original: img.original,
    attributes: img.attributes
  };

  console.log(`${binaryName} <- ${img.character} / ${img.original}`);
}

// Write manifest
fs.writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2));

const lastId = nextId + newImages.length - 1;
console.log(`\n--- DONE ---`);
console.log(`New images copied: ${newImages.length}`);
console.log(`Total images in collection: ${Object.keys(manifest).length}`);
console.log(`Binary range: 0.png to ${lastId.toString(2)}.png`);
console.log(`Manifest written to: ${MANIFEST_PATH}`);

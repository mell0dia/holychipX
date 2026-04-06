#!/usr/bin/env node

import { GoogleGenAI } from "@google/genai";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── Help ─────────────────────────────────────────────────────────────────────

const HELP = `
sgen-pre — Holy Chip pre-comic image generator

USAGE:
  sgen-pre --bot <image> --text <phrase> --title <title> --year <year> --id <id> --out <file>

REQUIRED:
  --bot <path>       Path to the bot character image (PNG)
  --text <string>    Speech bubble text
  --title <string>   Story title (banner center)
  --year <string>    Story year (banner right)
  --id <string>      Story ID, e.g. HC042 (banner left)
  --out <path>       Output file path (PNG)

OPTIONAL:
  --side <left|right> Which side the bot appears on (default: left)
  --template <path>  Custom template image (default: bundled template.png)
  --bubbles <path>   Bubble style reference image
  --key <string>     Gemini API key (or set GEMINI_API_KEY env var)
  -h, --help         Show this help

EXAMPLES:
  sgen-pre --bot ./astronaut.png --text "Houston, we have a chip" --title "Space Chips" --year 2026 --id HC042 --out output.png
  sgen-pre --bot ./robot.png --text "Hello world" --side right --title "Binary" --year 2026 --id HC099 --out story.png

ENV:
  GEMINI_API_KEY     Google Gemini API key (alternative to --key flag)
`;

// ── Parse Args ───────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h" || arg === "--h") {
      console.log(HELP);
      process.exit(0);
    }
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const val = argv[i + 1];
      if (!val || val.startsWith("--")) {
        console.error(`Missing value for ${arg}`);
        process.exit(1);
      }
      args[key] = val;
      i++;
    }
  }
  return args;
}

function require(args, key, label) {
  if (!args[key]) {
    console.error(`Missing required argument: --${key} (${label})`);
    console.error(`Run 'sgen-pre --help' for usage.`);
    process.exit(1);
  }
  return args[key];
}

// ── Image Helpers ────────────────────────────────────────────────────────────

function fileToInlinePart(filePath) {
  const abs = path.resolve(filePath);
  if (!fs.existsSync(abs)) {
    console.error(`File not found: ${abs}`);
    process.exit(1);
  }
  const data = fs.readFileSync(abs).toString("base64");
  const ext = path.extname(abs).toLowerCase();
  const mimeMap = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };
  const mimeType = mimeMap[ext] || "image/png";
  return { inlineData: { mimeType, data } };
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs(process.argv);

  if (process.argv.length <= 2) {
    console.log(HELP);
    process.exit(0);
  }

  // Required args
  const botPath   = require(args, "bot", "bot character image");
  const text      = require(args, "text", "speech bubble text");
  const title     = require(args, "title", "story title");
  const year      = require(args, "year", "story year");
  const id        = require(args, "id", "story ID");
  const outPath   = require(args, "out", "output file path");

  // Optional args
  const side          = args.side || "left";
  const templatePath  = args.template || path.join(__dirname, "assets", "template.png");
  const bubblesPath   = args.bubbles || null;
  const referencePath = path.join(__dirname, "assets", "reference.png");
  const apiKey        = args.key || process.env.GEMINI_API_KEY || "AIzaSyC0Pb1-TfjpT9sbpgkpYNIOVZLtrT4phCg";

  if (!apiKey) {
    console.error("No Gemini API key. Set GEMINI_API_KEY env var or pass --key <key>");
    process.exit(1);
  }

  // Validate side
  if (side !== "left" && side !== "right") {
    console.error(`--side must be 'left' or 'right', got '${side}'`);
    process.exit(1);
  }

  const botLabel = side === "left" ? "Left Bot" : "Right Bot";
  const speakerSide = side === "left" ? "LEFT" : "RIGHT";
  const speakerLabel = side === "left" ? "LEFT BOT" : "RIGHT BOT";

  console.log(`\n  sgen-pre — generating pre-comic image`);
  console.log(`  ──────────────────────────────────────`);
  console.log(`  ID:       #${id}`);
  console.log(`  Title:    ${title}`);
  console.log(`  Year:     ${year}`);
  console.log(`  Bot:      ${botPath} (${speakerSide} side)`);
  console.log(`  Text:     "${text}"`);
  console.log(`  Output:   ${outPath}`);
  console.log();

  // ── Build prompt ─────────────────────────────────────────────────────────

  const oppositeSide = side === "left" ? "RIGHT" : "LEFT";

  const prompt = `
GENERATE A SINGLE-PANEL PRE-COMIC IMAGE. Match the REFERENCE image style EXACTLY.

IMAGE ROLES:
- REFERENCE image -> THE STYLE TO COPY. Match this layout, proportions, border style, font style, bubble style, and overall feel pixel-for-pixel. This is the gold standard.
- BOT image -> the ONLY character. Copy it pixel-for-pixel. Do NOT change expression, shape, colors, or any feature.
${templatePath ? "- TEMPLATE image -> panel border reference." : ""}
${bubblesPath ? "- BUBBLE STYLE image -> additional bubble shape reference." : ""}

FORMAT (match REFERENCE exactly):
- Aspect ratio: 16:9.
- Solid BLACK border around the entire image (top, bottom, left, right edges).
- Banner at top: solid black bar, approximately 15-19% of total height.
- One panel below: fills the remaining height.

BANNER (solid black bar, white text):
- All text in UPPERCASE white pixel/bitmap font — same style as the REFERENCE image.
- LEFT-ALIGNED: "#${id}"
- CENTERED: "${title.toUpperCase()}"
- RIGHT-ALIGNED: "${year}"
- Font must match the REFERENCE banner font exactly — blocky, pixel-art style, ALL CAPS.

PANEL:
- Background color: #F8F9F2 (very light sage/cream — match the REFERENCE).
- Show ONLY the ${botLabel} character on the ${speakerSide} side of the panel.
- Character should be LARGE — fill most of the panel height (similar proportions to the REFERENCE).
- Reproduce the BOT image exactly — zero changes to expression, shape, colors, line weight, or any feature.
- Black border along the bottom edge of the panel (like the REFERENCE).

SPEECH BUBBLE (CRITICAL — match REFERENCE style):
- Solid BLACK filled rectangle with sharp square corners — NO rounded corners, NO outline-only bubbles.
- Positioned on the ${oppositeSide} side of the panel (opposite the character).
- The bubble should be LARGE — fill most of the horizontal space not occupied by the character.
- Vertically centered in the panel or slightly above center.
- Speech TAIL: solid black triangular tail pointing from the bubble toward the ${botLabel} character.
- Text inside the bubble: WHITE, ALL UPPERCASE, large blocky pixel/bitmap font — same style as the REFERENCE.
- Text should be LARGE and fill the bubble well — maximize readability.
- ONE bubble only.
- Text: "${text.toUpperCase()}"

NO FOOTER. The image ends at the bottom panel border.

QUALITY: Match the REFERENCE image quality exactly — clean pixel art, solid fills, hard edges, no anti-aliasing, no gradients, no noise.
`;

  // ── Build parts ──────────────────────────────────────────────────────────

  const parts = [];

  // Reference image FIRST — this is the style gold standard
  if (fs.existsSync(referencePath)) {
    parts.push(fileToInlinePart(referencePath));
    parts.push({ text: "↑ REFERENCE — THIS IS THE EXACT STYLE TO COPY. Match layout, banner font, bubble style, proportions, and overall feel. The character in this image is NOT the character to use — use the BOT image below instead." });
  }

  // Template
  if (fs.existsSync(templatePath)) {
    parts.push(fileToInlinePart(templatePath));
    parts.push({ text: "↑ TEMPLATE — panel border reference." });
  } else {
    console.warn(`Warning: template not found at ${templatePath}, proceeding without.`);
  }

  // Bot image
  parts.push(fileToInlinePart(botPath));
  parts.push({ text: `↑ ${speakerLabel} — the ONLY character to draw. Copy pixel-for-pixel, zero changes. Place on the ${speakerSide} side.` });

  // Bubbles (optional)
  if (bubblesPath) {
    parts.push(fileToInlinePart(bubblesPath));
    parts.push({ text: "↑ BUBBLE STYLE — additional bubble shape reference." });
  }

  // Prompt
  parts.push({ text: prompt });

  // ── Call Gemini ──────────────────────────────────────────────────────────

  console.log("  Calling Gemini API...");
  const ai = new GoogleGenAI({ apiKey });

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash-exp",
      contents: [{ role: "user", parts }],
      config: { responseModalities: ["Text", "Image"] },
    });

    for (const part of response.candidates?.[0]?.content?.parts || []) {
      if (part.inlineData) {
        const buffer = Buffer.from(part.inlineData.data, "base64");
        const outAbs = path.resolve(outPath);
        fs.mkdirSync(path.dirname(outAbs), { recursive: true });
        fs.writeFileSync(outAbs, buffer);
        console.log(`  Done! Image saved to: ${outAbs}`);
        console.log(`  Size: ${(buffer.length / 1024).toFixed(1)} KB\n`);
        return;
      }
    }

    console.error("  Error: Gemini returned no image data.");
    console.error("  Response:", JSON.stringify(response.candidates?.[0]?.content, null, 2));
    process.exit(1);
  } catch (err) {
    console.error(`  Error calling Gemini: ${err.message}`);
    if (err.message?.includes("API key")) {
      console.error("  Check your GEMINI_API_KEY is valid.");
    }
    process.exit(1);
  }
}

main();

# sgen-pre — Holy Chip Pre-Comic Image Generator

Standalone CLI tool to generate Holy Chip pre-comic images using Google Gemini.

## Requirements

- Node.js 20+
- Google Gemini API key

## Install on any machine

```bash
# 1. Copy the cli/ folder to the target machine
# 2. Run setup:
cd cli
./setup.sh
```

That's it. The setup script installs dependencies, links the global command, and checks your environment.

Or manually:

```bash
cd cli
npm install
npm link          # makes 'sgen-pre' available globally
```

## Setup API key

```bash
export GEMINI_API_KEY=your-key-here
```

Or pass it per-run with `--key YOUR_KEY`.

## Usage

```bash
sgen-pre --bot <image> --text <phrase> --title <title> --year <year> --id <id> --out <file>
```

Run `sgen-pre -h` for full help.

### Required

| Flag | Description |
|------|-------------|
| `--bot` | Path to bot character image (PNG) |
| `--text` | Speech bubble text |
| `--title` | Story title (banner center) |
| `--year` | Story year (banner right) |
| `--id` | Story ID, e.g. HC042 (banner left) |
| `--out` | Output file path (PNG) |

### Optional

| Flag | Default | Description |
|------|---------|-------------|
| `--side` | left | Bot position: `left` or `right` |
| `--template` | bundled | Custom template image |
| `--bubbles` | — | Bubble style reference image |
| `--key` | env var | Gemini API key |
| `-h` | — | Show help |

## Examples

```bash
# Bot on the left (default)
sgen-pre \
  --bot ./astronaut.png \
  --text "Houston, we have a chip" \
  --title "Space Chips" \
  --year 2026 \
  --id HC042 \
  --out output.png

# Bot on the right
sgen-pre \
  --bot ./robot.png \
  --text "Hello world" \
  --side right \
  --title "Binary Dreams" \
  --year 2026 \
  --id HC099 \
  --out story.png
```

## What's in the box

```
cli/
  index.js          # CLI entry point
  package.json      # Dependencies (@google/genai)
  setup.sh          # One-step install script
  .env.example      # API key template
  README.md         # This file
  assets/
    template.png    # Default panel layout template
    reference.png   # Style reference (HC018 pre-comic)
```

## Output

- 16:9 PNG image
- Black banner: #ID | TITLE | YEAR (white pixel font)
- Single panel: bot character + speech bubble (black rect, white text)
- Background: #F8F9F2
- Style matches the bundled reference image

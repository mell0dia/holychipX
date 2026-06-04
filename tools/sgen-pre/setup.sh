#!/bin/bash
# sgen-pre — one-step setup for any machine
# Requirements: Node.js 20+ and a Gemini API key

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  sgen-pre — setup"
echo "  ────────────────"

# Check Node.js
if ! command -v node &> /dev/null; then
  echo "  ERROR: Node.js not found. Install Node.js 20+ first."
  exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
  echo "  ERROR: Node.js $NODE_VERSION found, but 20+ is required."
  exit 1
fi
echo "  Node.js $(node -v) — OK"

# Install deps
echo "  Installing dependencies..."
npm install --silent

# Make executable
chmod +x index.js

# Link globally
echo "  Linking 'sgen-pre' command globally..."
npm link --silent 2>/dev/null || {
  echo "  Note: 'npm link' failed (may need sudo). You can still run directly:"
  echo "    node $SCRIPT_DIR/index.js --help"
}

# Check API key
if [ -z "$GEMINI_API_KEY" ]; then
  echo ""
  echo "  WARNING: GEMINI_API_KEY not set."
  echo "  Set it before running:"
  echo "    export GEMINI_API_KEY=your-key-here"
  echo "  Or pass --key on each run."
else
  echo "  GEMINI_API_KEY — OK"
fi

echo ""
echo "  Ready! Run: sgen-pre --help"
echo ""

#!/bin/bash
# Daily auto-commit and push to GitHub
# Skips if nothing changed

cd ~/holy-chip || exit 1

# Check for changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "No changes to commit"
    exit 0
fi

DATE=$(date +"%Y-%m-%d %H:%M")

git add -A
git commit -m "Auto-commit: $DATE"
git push origin main

echo "Committed and pushed at $DATE"

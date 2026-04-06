#!/bin/bash
# Holy Chip .PRE Phrase Cron Poster
# Runs every 4 hours to post up to 5 new .PRE phrases

# Make sure we're in the project directory
cd ~/holy-chip/tools

# Post the next batch of phrases
python3 pre-poster.py --batch 5
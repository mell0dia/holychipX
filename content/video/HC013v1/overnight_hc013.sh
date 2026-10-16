#!/bin/bash
# HC013: clips on the M5 (one by one), then EN + PT builds. Run after the user approves the images.
cd /Users/rmello/holy-chip/content/video; PY=/Users/rmello/holy-chip/venv/video/bin/python
echo "=== batch start $(date '+%H:%M')"
$PY -u animate.py HC013v1 --frames 81 2>&1 | grep -E "^\[|succeeded|failed|Traceback|Error|out of memory"
echo "=== batch end $(date '+%H:%M'): $(ls HC013v1/clips/m5_*.mp4 2>/dev/null | wc -l | tr -d ' ') clips"
echo "=== EN build $(date '+%H:%M')"; $PY make_video.py HC013v1 HC013 2>&1 | grep -vE "^\s*$" | tail -2
echo "=== PT build $(date '+%H:%M')"; $PY make_video.py HC013v1pt HC013 2>&1 | grep -vE "^\s*$" | tail -2
[ -f HC013v1pt/HC013_sketch.mp4 ] && mv -f HC013v1pt/HC013_sketch.mp4 HC013v1pt/HC013_sketch_PT.mp4
echo "=== done $(date '+%H:%M')"; ls -la HC013v1/HC013_sketch.mp4 HC013v1pt/HC013_sketch_PT.mp4 2>&1 | awk '{print $5,$9}'

#!/bin/bash
# Create animated GIF: 25 random NFT images (slow→fast) + brand image (5s hold)
# Uses ffmpeg with variable frame durations

CHARS_DIR="/Users/wakanda2/Desktop/4D Documents/Claude/HolyChip/nft/Characters"
BRAND="/Users/wakanda2/Desktop/4D Documents/Claude/HolyChip/website/holy-chip-site/assets/brand.png"
OUT="/Users/wakanda2/Desktop/4D Documents/Claude/HolyChip/nft/holy-chip-animation.gif"
TMP="/tmp/hc-gif-frames"

rm -rf "$TMP"
mkdir -p "$TMP"

# Pick 25 random NFT images
IMAGES=($(ls "$CHARS_DIR"/*.png | shuf -n 25))

# Generate frame durations: slow to fast
# Frame 1: 800ms, gradually decreasing to frame 25: ~40ms
# Using exponential curve
DURATIONS=()
for i in $(seq 0 24); do
  # Exponential decay from 800ms to 40ms
  dur=$(python3 -c "import math; print(int(800 * math.exp(-$i * 0.12)))")
  DURATIONS+=($dur)
done

echo "Creating frames..."

# Resize all NFT images to 500x500 (square, white bg) and copy to temp
FRAME=0
for img in "${IMAGES[@]}"; do
  printf -v padded "%03d" $FRAME
  ffmpeg -y -loglevel error \
    -i "$img" \
    -vf "scale=500:500:force_original_aspect_ratio=decrease,pad=500:500:(ow-iw)/2:(oh-ih)/2:white" \
    "$TMP/frame_${padded}.png"
  FRAME=$((FRAME + 1))
done

# Add brand image as final frame (resized to same 500x500)
printf -v padded "%03d" $FRAME
ffmpeg -y -loglevel error \
  -i "$BRAND" \
  -vf "scale=500:500:force_original_aspect_ratio=decrease,pad=500:500:(ow-iw)/2:(oh-ih)/2:white" \
  "$TMP/frame_${padded}.png"

echo "Building GIF with variable timing..."

# Build ffmpeg concat demuxer file with per-frame durations
CONCAT="$TMP/concat.txt"
> "$CONCAT"
for i in $(seq 0 24); do
  printf -v padded "%03d" $i
  dur_sec=$(python3 -c "print(${DURATIONS[$i]} / 1000.0)")
  echo "file 'frame_${padded}.png'" >> "$CONCAT"
  echo "duration $dur_sec" >> "$CONCAT"
done
# Brand image: 5 seconds
printf -v padded "%03d" 25
echo "file 'frame_${padded}.png'" >> "$CONCAT"
echo "duration 5" >> "$CONCAT"
# ffmpeg concat needs last file repeated without duration
echo "file 'frame_${padded}.png'" >> "$CONCAT"

# Create GIF via palette for quality
ffmpeg -y -loglevel error \
  -f concat -safe 0 -i "$CONCAT" \
  -vf "fps=25,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer" \
  -loop 0 \
  "$OUT"

SIZE=$(du -h "$OUT" | cut -f1)
echo ""
echo "Done! $OUT ($SIZE)"
echo ""
echo "Frame timing (ms):"
for i in $(seq 0 24); do
  echo "  Frame $((i+1)): ${DURATIONS[$i]}ms"
done
echo "  Brand: 5000ms"

# Cleanup
rm -rf "$TMP"

#!/usr/bin/env bash
# Generate pre-rendered earpiece audio clips for PitchPilot.
# Run once on macOS from the repo root: bash data/cue_bank/generate_clips.sh
set -euo pipefail

BANK_DIR="$(dirname "$0")"

declare -a CUES=(
  "slow down"
  "compliance risk"
  "clarify differentiation"
  "define problem first"
  "ROI question likely"
  "mention privacy"
  "add disclaimer"
  "cite evidence"
  "soften claim"
  "bridge transition"
  "simplify this"
  "needs evidence"
  "expect question"
  "differentiation unclear"
  "mention on-device"
  "pause for effect"
  "name the benchmark"
  "privacy question incoming"
  "expect ROI pushback"
  "strong point"
  "mention GDPR"
)

echo "Generating ${#CUES[@]} earpiece cue clips in ${BANK_DIR}/ ..."
count=0
for CUE in "${CUES[@]}"; do
  SLUG=$(echo "$CUE" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
  OUT="${BANK_DIR}/${SLUG}.aiff"
  if [ -f "$OUT" ]; then
    echo "  skip (exists): ${SLUG}.aiff"
    continue
  fi
  say -r 190 -o "$OUT" "$CUE" && echo "  generated: ${SLUG}.aiff" && ((count++)) || echo "  FAILED: $CUE"
done
echo "Done. ${count} new clips generated."

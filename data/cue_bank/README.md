# PitchPilot Earpiece Cue Bank

Pre-rendered audio clips for the TTSService. Each file is a short (~0.5-1.5 s) AIFF or WAV clip of a spoken earpiece cue.

## Naming convention

Files are named with underscores replacing spaces:

```
slow_down.aiff
compliance_risk.aiff
clarify_differentiation.aiff
define_problem_first.aiff
ROI_question_likely.aiff
mention_privacy.aiff
add_disclaimer.aiff
cite_evidence.aiff
soften_claim.aiff
bridge_transition.aiff
simplify_this.aiff
needs_evidence.aiff
expect_question.aiff
differentiation_unclear.aiff
mention_on_device.aiff
pause_for_effect.aiff
```

TTSService loads these at startup and uses them for sub-100 ms audio delivery. Novel cues fall back to macOS `say -r 200`.

## Generating the clip bank on macOS

Run this script once to pre-render all common cues:

```bash
#!/usr/bin/env bash
# Run from repo root
mkdir -p data/cue_bank
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
)
for CUE in "${CUES[@]}"; do
  SLUG=$(echo "$CUE" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
  say -r 190 -o "data/cue_bank/${SLUG}.aiff" "$CUE"
  echo "Generated: data/cue_bank/${SLUG}.aiff"
done
echo "Done. $(ls data/cue_bank/*.aiff | wc -l) clips generated."
```

## Cross-platform (Piper)

For non-macOS deployment, drop Piper ONNX model files here and set `PITCHPILOT_TTS_ENGINE=piper`. See https://github.com/rhasspy/piper for model downloads.

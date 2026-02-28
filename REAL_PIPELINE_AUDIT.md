# Real Pipeline Audit — `USE_MOCK_PIPELINE=false`

## How Mock Mode Currently Works

The app has **two independent mock toggles** that must both be disabled to exercise the real pipeline:

| Layer | Variable | Location | Meaning |
|-------|----------|----------|---------|
| Backend | `PITCHPILOT_MOCK_MODE` | `.env.local` | When `true`, all LLM calls return deterministic stubs; routes to `_run_mock_pipeline` |
| Frontend | `VITE_USE_MOCK` | `frontend/.env.local` | When `true` (or unset), both `useSession` and `useLiveSession` never call the backend API |

When either is `true`, the app **never exercises the real code path**.

---

## Bugs Found and Fixed

### BUG 1 (CRITICAL) — Wrong env var name, wrong env file
**Root cause:** `config.py` read `PITCHPILOT_MOCK_MODE` from `.env`, but `.env.local` set `USE_MOCK_PIPELINE`.  
**Effect:** Setting `USE_MOCK_PIPELINE=false` had zero effect. Mock mode was always `True`.  
**Fix:** Updated `config.py` `env_file` to read `.env.local` first. Updated `.env.local` to use `PITCHPILOT_MOCK_MODE=false`.

### BUG 2 (CRITICAL) — Frontend mock flags hardcoded to `true`
**Root cause:** Both `useSession.ts` and `useLiveSession.ts` had `const USE_MOCK = true;` as a compile-time constant.  
**Effect:** Frontend always used mock data regardless of backend mode. No API calls were ever made.  
**Fix:** Changed to `import.meta.env.VITE_USE_MOCK !== 'false'`. Created `frontend/.env.local` with `VITE_USE_MOCK=false`.

### BUG 3 (CRITICAL) — `_run_real_pipeline` called `report_gen.generate()` with wrong kwargs
**Root cause:** `main.py` called `report_gen.generate(session_id=..., orchestrator_result=..., ingestion_result=...)` but the method signature is `generate(result: OrchestratorResult, context: PipelineContext)`.  
**Effect:** `TypeError` on every real pipeline run — session always failed.  
**Fix:** Rewrote `_run_real_pipeline` to properly call `report_gen.generate(result=orch_result, context=context)`.

### BUG 4 (CRITICAL) — `PipelineContext` built with wrong types and forbidden kwarg
**Root cause:** `main.py` passed `data_models.Claim` / `data_models.TranscriptSegment` / `data_models.OCRBlock` directly to `PipelineContext`, which expects `schemas.Claim` / `schemas.TranscriptSegment` / `schemas.SlideOCR` (different dataclasses). Also passed `full_transcript=...` which is a `@property`, not a constructor field.  
**Effect:** `TypeError` at construction time.  
**Fix:** Added explicit conversion helpers to map each `data_models` type to the corresponding `schemas` type before building `PipelineContext`.

### BUG 5 (MODERATE) — `_map_report` used wrong attribute names for `schemas.ReadinessReport`
**Root cause:** `_map_report` tried to access `report.score.overall` but `schemas.ReadinessReport` uses `report.overall_score` (no nested `score` object). Tried `.detail` on `schemas.Finding` but the field is `.description`. Used `score_obj.dimensions` as a list but it's a `dict[str, DimensionScore]`.  
**Effect:** Report score silently fell back to 75; no findings detail shown; dimension scores missing.  
**Fix:** Rewrote `_map_report` to correctly handle `schemas.ReadinessReport` field layout.

### BUG 6 (MODERATE) — `useSession.ts` checked `status === 'error'` (never true)
**Root cause:** Backend sends `status: 'failed'` (from `SessionStatus.FAILED`), but frontend checked `s.status === 'error'`.  
**Effect:** Failed sessions never triggered the error state — UI stayed stuck on "analyzing".  
**Fix:** Changed to check `s.status === 'failed'` and use `s.error_message` (not `s.error`).

### BUG 7 (MODERATE) — `useSession.ts` imported wrong type for status
**Root cause:** Imported `StatusResponse` from `@/types/api` (maps to internal `schemas.py` fields like `current_step`, `error`) but the API returns `SessionStatusResponse` (fields: `progress_message`, `error_message`).  
**Effect:** `s.current_step` was always `undefined` in the UI; error messages never showed.  
**Fix:** Changed import to `SessionStatusResponse` from `@/types` (correct for `api_schemas.py`).

### BUG 8 (MODERATE) — Polling stops on first transient network error
**Root cause:** Any exception in `startRealPolling` immediately called `stopPolling()`.  
**Effect:** One bad network request (backend restart, slow response) permanently killed polling.  
**Fix:** Added 3-consecutive-error tolerance before giving up.

### BUG 9 (CLEANUP) — Duplicate field definitions in `config.py`
**Root cause:** `Settings` class defined `cue_min_interval_seconds`, `tts_engine`, `tts_cue_bank_path`, `teleprompter_update_interval` twice each; module-level constants also duplicated.  
**Effect:** Confusing; pydantic silently used the last definition. `tts_cue_bank_path` default was `""` from first set, overridden to `"data/cue_bank/"` from second.  
**Fix:** Removed the first (less-detailed) set of duplicate definitions.

---

## Remaining Known Risks in Real Mode

| Risk | Severity | Status |
|------|----------|--------|
| Ollama not running — `Orchestrator.initialize()` logs warning but doesn't fail startup | Low | By design; auto-fallback available |
| First Ollama request may timeout if model not loaded (`ollama pull` not run) | High | Mitigated by retry in `ollama_post()` (3 attempts) |
| `FunctionGemmaRouter` uses rule-based routing if LoRA adapter not present (`ROUTER_USE_RULES=true`) | Low | Config default is safe |
| Audio chunk transcription — browser sends WebM/Opus but backend writes `.webm` and passes to Whisper/Gemma3n; format support depends on ffmpeg build | Medium | Test before demo |
| Live session `TranscriptionPipeline.transcribe()` doesn't validate `audio_bytes` are non-empty; silent empty transcript possible | Low | Already guarded with `if not audio_bytes: return []` |

---

## Manual Test Plan — Before a Live Hackathon Demo

### Prerequisites
```bash
# 1. Start Ollama and pull models
ollama serve
ollama pull gemma3:4b
ollama pull gemma-3n:e4b

# 2. Set env vars (already done by .env.local with our fix)
#    PITCHPILOT_MOCK_MODE=false  ← .env.local
#    VITE_USE_MOCK=false         ← frontend/.env.local
```

### Test 1: Backend readiness check
```bash
curl http://localhost:8000/api/readiness
# Expected: {"mock_mode": false, "ollama_available": true, ...}
# If ollama_available is false, run 'ollama serve' first
```

### Test 2: Upload mode (review flow)
1. Start backend: `uvicorn backend.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to `http://localhost:5173`
4. Upload a short video (5–10 min rehearsal)
5. Wait for analysis to complete (~60–180s depending on GPU)
6. Verify:
   - [ ] Progress bar advances through all 7 stages
   - [ ] Status never stays on "pending" indefinitely
   - [ ] Report page shows real findings (not the "3× faster" demo finding)
   - [ ] Score dimensions populate correctly
   - [ ] Timeline has annotations

### Test 3: Live In-Room mode
1. Click "Live In-Room" in the UI
2. Allow camera + microphone permissions
3. Start speaking a pitch (~30 seconds)
4. Verify:
   - [ ] Transcript updates appear in real time (every ~2s)
   - [ ] Findings appear after ~10–15s of talking
   - [ ] (Optional) Earpiece cue audio plays for critical findings
5. Click "End Session"
6. Verify:
   - [ ] "Finalizing..." state shows
   - [ ] Full report loads within 30s
   - [ ] Findings reflect actual speech content

### Test 4: Live Remote mode
1. Click "Live Remote" in the UI
2. Share a screen with slides
3. Start presenting
4. Verify:
   - [ ] Teleprompter points update on slide changes
   - [ ] Overlay cards appear for compliance/coach findings
   - [ ] Objection prep sidebar shows likely questions
5. End session and verify report

### Test 5: Failure handling
1. Start a session, then kill Ollama mid-way
2. Verify:
   - [ ] Session transitions to `failed` state (not stuck on `processing`)
   - [ ] Frontend shows error message (not spinner)
   - [ ] Error message is human-readable
3. Restart Ollama, start new session → should succeed

### Test 6: Demo mode still works (mock)
```bash
# Verify mock mode still works after our changes
PITCHPILOT_MOCK_MODE=true uvicorn backend.main:app --reload
# In frontend/.env.local: VITE_USE_MOCK=true
```
Or use the dedicated demo server:
```bash
bash scripts/run_demo.sh
```
Should produce instant results with demo data.

---

## Quick Startup Diagnostic
```bash
# Check what mode the backend is in
curl -s http://localhost:8000/api/readiness | python3 -m json.tool

# Check Ollama has the required models
curl -s http://localhost:11434/api/tags | python3 -c "
import json, sys
data = json.load(sys.stdin)
names = [m['name'] for m in data.get('models', [])]
for required in ['gemma3:4b', 'gemma-3n:e4b']:
    status = '✓' if any(required in n for n in names) else '✗ MISSING'
    print(f'{status}  {required}')
"

# Run the smoke test suite (no Ollama needed)
pytest tests/test_smoke.py -v
```

---

## Summary of Changes Made

| File | Change |
|------|--------|
| `backend/config.py` | Fixed `env_file` to read `.env.local`; removed duplicate field definitions |
| `.env.local` | Renamed `USE_MOCK_PIPELINE` → `PITCHPILOT_MOCK_MODE=false` |
| `.env.example` | Same rename |
| `backend/main.py` | Fixed `_run_real_pipeline`: correct type conversions, correct `report_gen.generate()` call, added `/api/readiness` endpoint, startup log |
| `backend/live_ws.py` | Explicitly use `session_mode.value` in `session_created` message |
| `frontend/src/hooks/useSession.ts` | Removed hardcoded `USE_MOCK=true`; use `VITE_USE_MOCK` env var; fix `'failed'` status check; fix type imports; add retry on network errors |
| `frontend/src/hooks/useLiveSession.ts` | Removed hardcoded `USE_MOCK=true`; use `VITE_USE_MOCK` env var |
| `frontend/.env.local` | New file: `VITE_USE_MOCK=false` |
| `tests/test_smoke.py` | Added 5 new smoke tests for real pipeline path |

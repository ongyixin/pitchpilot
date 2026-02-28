# PitchPilot — Presentation Mode Architecture

> For teammates jumping in: this document explains **why** three modes exist,
> how they differ at the data and UI layers, and how live findings converge
> back into the same report format used by review mode.

---

## 1. The Three Modes

```
┌──────────────────┬──────────────────────┬──────────────────────────────┐
│ Mode             │ SessionMode value     │ Trigger                      │
├──────────────────┼──────────────────────┼──────────────────────────────┤
│ Review           │ "review" / "upload"  │ POST /api/session/start      │
│ Live In-Room     │ "live_in_room"        │ WS /api/session/live +       │
│                  │                      │   mode:"live_in_room" init   │
│ Live Remote      │ "live_remote"         │ WS /api/session/live +       │
│                  │                      │   mode:"live_remote" init    │
└──────────────────┴──────────────────────┴──────────────────────────────┘
```

Legacy values `"upload"` and `"live"` remain valid for backward compatibility
and map to Review and a generic live session respectively.

---

## 2. How Modes Differ

### 2A. Review Mode

```
Upload video ──► IngestionPipeline ──► Orchestrator ──► ReadinessReport
                 (frames + audio)        (FunctionGemma     (stored in session,
                                          → agents)          retrieved via REST)
```

- **Input:** Video file + optional policy PDFs
- **Processing:** Batch — all frames extracted at 1 fps, full audio transcribed, all claims extracted and routed
- **Latency:** Minutes (full pipeline)
- **Output channel:** REST `GET /api/session/{id}/report`
- **Frontend:** `SetupPage → AnalyzingPage → ResultsPage`
- **Relevant backend file:** `backend/main.py:start_session`, `backend/ingestion.py`

### 2B. Live In-Room Mode

```
Mic chunks ──► LivePipeline ──► Orchestrator ──► CueSynthesizer ──► TTSService
(2s audio)      (incremental                     (rate-limited,       (base64 WAV
                 transcription)                   priority gated)      or text-only)
                                                        │
                                               WebSocket: earpiece_cue
                                                        │
                                               Frontend: audio.play()
```

- **Input:** Device microphone (required); camera optional
- **Processing:** Streaming — 2-second audio chunks, claim extraction every 5 seconds
- **Latency budget:** ~5–8 seconds from utterance to earpiece cue
- **Output channel:** WebSocket `earpiece_cue` messages → frontend plays audio through earpiece output
- **Cue delivery rules:**
  - Max 1 cue per 15 seconds (configurable `CUE_MIN_INTERVAL`)
  - Only `warning` / `critical` severity findings produce cues; `info` deferred to report
  - Duplicate categories suppressed within a 60-second window (`CUE_DEDUP_WINDOW`)
  - Cue text: 3–6 words, sourced from `Finding.cue_hint` → `CueSynthesizer._CUE_BANK` → truncated title
- **Frontend:** `SetupPage → InRoomModePage → ResultsPage`
  - `InRoomModePage` is intentionally dark and minimal (device sits on a podium)
- **Relevant backend files:** `backend/pipeline/cue_synth.py`, `backend/services/tts.py`

### 2C. Live Remote Mode

```
Screen capture ──► LivePipeline ──► Orchestrator ──► CueSynthesizer ──► WebSocket
Mic chunks         (frame OCR +                       (ScriptSuggestion   ┌─ teleprompter
                    transcription)                     + overlay cards)    ├─ objection_prep
                                                                           ├─ script_suggestion
                                                                           └─ finding / nudge
```

- **Input:** Screen capture frames (required) + device microphone (required); webcam optional
- **Processing:** Same streaming pipeline as In-Room, plus periodic teleprompter + objection prep generation
- **Output channels:**
  - `teleprompter` — 2-3 talking points refreshed every 20 seconds or on slide change
  - `objection_prep` — likely audience questions with suggested answers, refreshed every 30 seconds
  - `script_suggestion` — inline alternative wording when a compliance/clarity issue is detected (auto-dismiss 12s)
  - `finding` / `nudge` — same as legacy live mode (still emitted)
- **Frontend:** `SetupPage → RemoteModePage → ResultsPage`
  - `RemoteModePage` has a two-zone layout: left = shared-safe webcam, right = presenter-only overlay
  - Right panel is **not** in the shared screen region — presenter controls window placement
- **Relevant backend files:** `backend/prompts/teleprompter.txt`, `backend/prompts/objection_prep.txt`

---

## 3. WebSocket Protocol Extension

The `init` message now carries a `mode` field:

```json
{
  "type": "init",
  "mode": "live_in_room",
  "personas": ["Skeptical Investor", "Technical Reviewer"],
  "policy_text": "...",
  "title": "Q3 Board Demo"
}
```

The server responds with `session_created` including the resolved mode:

```json
{ "type": "session_created", "session_id": "...", "mode": "live_in_room" }
```

### New outbound message types

| Type               | Mode        | Key fields                                              |
|--------------------|-------------|----------------------------------------------------------|
| `earpiece_cue`     | in_room     | `text`, `audio_b64`, `priority`, `category`, `elapsed`  |
| `teleprompter`     | remote      | `points[]`, `slide_context`, `elapsed`                  |
| `objection_prep`   | remote      | `questions[]` (each: `question`, `suggested_answer`, `persona`, `difficulty`) |
| `script_suggestion`| remote      | `original`, `alternative`, `reason`, `agent`, `elapsed` |

All existing message types (`transcript_update`, `finding`, `nudge`, `session_complete`) continue to be emitted in all live modes.

---

## 4. New REST Endpoint

```
POST /api/session/start-live
Body: { "mode": "live_in_room", "personas": [...], "policy_text": "...", "title": "..." }

Response: {
  "session_id": "uuid",
  "ws_url": "ws://localhost:8000/api/session/live",
  "mode": "live_in_room",
  "status": "pending",
  "message": "Session pre-registered..."
}
```

This pre-registers a session before the WebSocket is opened, so REST polling
endpoints (`/status`, `/report`, `/findings`, `/timeline`) work immediately.
The client connects to `ws_url` and sends the `init` message to start streaming.

---

## 5. How Live Findings Become a Reviewable Report

All three modes converge into the same `ReadinessReport` schema:

```
Live Session
    │
    ├── Findings accumulated in LivePipeline._all_findings
    ├── Transcript in LivePipeline._transcript_segments
    ├── Slide OCR in LivePipeline._slide_ocr
    │
    └── on end_session:
            ├── pipeline.finalize() → runs comprehensive agent pass on all context
            ├── ReadinessReportGenerator.generate() → scores dimensions, builds timeline
            └── session.report = api_report  (stored in _sessions dict)
                      │
                      └── retrievable via GET /api/session/{id}/report
                               │
                               └── Frontend: ResultsPage (identical to Review mode)
```

Key properties of post-live reports:
- All findings that were deferred during live delivery (info-level, deduped) are **included** in the final report
- Earpiece cues are **not** stored — only the underlying `Finding` objects are persisted
- The `Finding.live = True` flag marks which findings were produced in real time (useful for post-session filtering)
- Timeline annotations work the same as Review mode (timestamps = seconds elapsed from session start)

---

## 6. Schema Additions (backward compatible)

### `SessionMode` enum (`backend/api_schemas.py`)

```python
UPLOAD = "upload"       # legacy
LIVE = "live"           # legacy
REVIEW = "review"       # canonical review mode
LIVE_IN_ROOM = "live_in_room"
LIVE_REMOTE = "live_remote"
```

### `Finding` model

New optional field: `cue_hint: Optional[str]` — a pre-compressed 3-6 word phrase for earpiece delivery, populated by agents or by `CueSynthesizer`.

### New Pydantic models

`EarpieceCue`, `TeleprompterUpdate`, `ObjectionPrepUpdate`, `ScriptSuggestion`,
`LiveSessionStartRequest`, `LiveSessionStartResponse` — all in `backend/api_schemas.py`.

---

## 7. New Files

| File | Purpose |
|------|---------|
| `backend/pipeline/cue_synth.py` | `CueSynthesizer` — rate-limited cue compression, `process_for_in_room()` / `process_for_remote()` |
| `backend/services/tts.py` | `TTSService` — tiered on-device TTS (clip bank → macOS say → piper) |
| `backend/prompts/teleprompter.txt` | Prompt for generating 2-3 talking points from slide OCR + transcript |
| `backend/prompts/objection_prep.txt` | Prompt for generating likely audience questions + suggested answers |
| `frontend/src/pages/InRoomModePage.tsx` | Dark minimal UI for earpiece coaching |
| `frontend/src/pages/RemoteModePage.tsx` | Two-zone presenter overlay for remote demos |
| `docs/ARCHITECTURE_MODES.md` | This document |

---

## 8. Config Knobs (all in `backend/config.py`)

| Setting | Default | Effect |
|---------|---------|--------|
| `cue_min_interval_seconds` | 15.0 | Minimum gap between earpiece cues |
| `cue_dedup_window_seconds` | 60.0 | Suppresses repeat cue categories within this window |
| `tts_engine` | `"system"` | TTS backend: `system` (macOS say), `piper`, `prerendered` |
| `tts_cue_bank_path` | `"data/cue_bank/"` | Pre-rendered audio clips directory |
| `teleprompter_update_interval` | 20.0 | Seconds between teleprompter regenerations |
| `objection_prep_update_interval` | 30.0 | Seconds between objection prep refreshes |
| `live_extract_interval_seconds` | 5.0 | Claim extraction frequency during live sessions |
| `slide_change_ocr_diff_threshold` | 0.25 | OCR text diff fraction that triggers a slide-change event |

---

## 9. Demo Flow (3 modes in sequence)

```
1. Review Mode  → load demo_pitch.mp4 → ResultsPage (existing)
2. Live In-Room → start earpiece session → speak 30s → show cues appearing
3. Live Remote  → start overlay → screen share slide deck → show teleprompter
                → show compliance card → end → same ResultsPage
```

The transition from live session → `ResultsPage` is automatic (state `complete`).
No extra navigation logic required — the existing `ResultsPage` renders
all findings, timeline, and score from whichever mode produced the report.

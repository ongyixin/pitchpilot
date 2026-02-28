# PitchPilot

> On-device multi-agent pitch rehearsal copilot — powered by Gemma 3n, FunctionGemma, and Gemma 3.

PitchPilot analyses a recorded rehearsal and answers one question: **are you ready to demo under scrutiny?**

Three specialised agents run entirely on your machine:
- **Presentation Coach** — evaluates clarity, structure, and narrative flow
- **Compliance Reviewer** — cross-checks claims against your policy documents
- **Audience Persona Simulator** — generates tough questions from stakeholder personas

---

## Table of Contents

- [Quick Start (Hackathon Demo)](#quick-start-hackathon-demo)
- [Full Local Setup](#full-local-setup)
- [Running the Backend](#running-the-backend)
- [Running the Frontend](#running-the-frontend)
- [Seeding Demo Data](#seeding-demo-data)
- [Running Tests](#running-tests)
- [Architecture](#architecture)
- [Demo Script (3 minutes)](#demo-script-3-minutes)
- [Project Structure](#project-structure)

---

## Quick Start (Hackathon Demo)

The fastest path to a working demo — no models, no Ollama, no file upload needed.

```bash
# 1. Clone and enter the project
cd instalily

# 2. Install Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] python-multipart pydantic pydantic-settings httpx pytest

# 3. Install frontend deps
cd frontend && npm install && cd ..

# 4. Launch everything
bash scripts/run_demo.sh
```

This starts:
- **Backend** → http://localhost:8000 (demo server with mock pipeline)
- **Frontend** → http://localhost:5173 (React + Vite)
- Opens the browser automatically

In the browser, click **"Load Demo Session"** to skip file upload and see the full analysis view instantly.

### Fast mode (instant results, no stage animation)

```bash
bash scripts/run_demo.sh --fast
```

### Stop all servers

```bash
bash scripts/run_demo.sh --stop
```

---

## Full Local Setup

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Tested on 3.12 |
| Node.js | 18+ | For the frontend |
| Ollama | latest | Only needed for real inference |
| Apple Silicon | M1+ | For `mlx-whisper` audio fallback |

### Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

### (Optional) Pull Gemma models for real inference

```bash
ollama pull gemma-3n:e4b   # multimodal processing
ollama pull gemma3:4b       # agent reasoning
```

### (Optional) Environment variables

Copy and edit the example env file:

```bash
cp .env.example .env
```

Key settings:

| Variable | Default | Description |
|---|---|---|
| `PITCHPILOT_MOCK_MODE` | `true` | Use mock inference (no Ollama needed) |
| `PITCHPILOT_DEMO_DELAY` | `1.5` | Seconds between pipeline stage updates |
| `PITCHPILOT_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `PITCHPILOT_GEMMA3N_MODEL` | `gemma-3n:e4b` | Gemma 3n model tag |
| `PITCHPILOT_GEMMA3_MODEL` | `gemma3:4b` | Gemma 3 model tag |

---

## Running the Backend

### Demo server (always works, no models needed)

```bash
uvicorn backend.demo_server:app --reload --port 8000
```

This is the recommended backend for demos and development. It:
- Accepts video file uploads (multipart form)
- Runs a realistic mock pipeline with progressive stage updates
- Returns rich demo data matching the frontend's expected API shape
- Has a `/api/session/demo` endpoint for instant results without uploading

### Real inference server (requires Ollama + models)

```bash
uvicorn backend.main:app --reload --port 8000
```

This runs the full multi-agent orchestrator with Gemma 3n, FunctionGemma, and Gemma 3.
Requires all models to be pulled and Ollama running on port 11434.

### API Documentation

Browse the interactive API docs at:  
http://localhost:8000/docs

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/session/start` | Upload video + optional policy docs, start analysis |
| `POST` | `/api/session/demo` | Start instant demo session (no upload required) |
| `GET` | `/api/session/{id}/status` | Poll processing progress (0–100%) |
| `GET` | `/api/session/{id}/report` | Full readiness report |
| `GET` | `/api/session/{id}/timeline` | Timestamped timeline annotations |
| `GET` | `/api/session/{id}/findings` | Agent findings and persona questions |
| `GET` | `/health` | Health check |

---

## Running the Frontend

```bash
cd frontend
npm run dev
```

Opens at http://localhost:5173. The Vite dev server proxies `/api/*` to `localhost:8000`.

The frontend has two paths to the results view:

1. **Upload a video** — select a .mp4/.mov/.webm file and click "Start Analysis"
2. **Load Demo Session** — click the button below the main CTA to skip upload and see pre-built results instantly

### Demo mode toggle

In `frontend/src/hooks/useSession.ts`:

```typescript
const USE_MOCK = true;  // flip to false to call the real backend
```

When `USE_MOCK = true`, no backend is required — the frontend replays the mock status sequence from `src/lib/mock-data.ts`.

---

## Seeding Demo Data

Programmatically create a demo session in the running backend:

```bash
# Basic — just create the session and print the ID
python scripts/seed_demo.py

# Wait for completion and print a summary
python scripts/seed_demo.py --poll

# Dump the full report as JSON
python scripts/seed_demo.py --poll --json

# Point at a different server
python scripts/seed_demo.py --base-url http://localhost:9000 --poll
```

Sample policy documents for the Compliance agent are in `data/sample_policies/`:

| File | Contents |
|---|---|
| `enterprise_data_policy.txt` | §3.2 human oversight, §1.1 privacy disclosure, SLA limits |
| `approved_messaging_guide.txt` | Approved/prohibited phrasing for sales pitches |

---

## Seeding Live Session Demos

Live sessions (in-room or remote) produce the same readiness report as review mode, but with additional provenance fields (`session_mode`, `session_duration_seconds`, `live_cues_count`, `live_session_summary`). The `ResultsPage` detects these and renders a live-session info panel instead of a video player.

### Instant completed live session via API

```bash
# Live in-room session (5:22 duration, 6 earpiece cues)
curl -s -X POST "http://localhost:8000/api/session/demo-live?mode=live_in_room" | python3 -m json.tool

# Live remote session (8:15 duration, 8 overlay cards)
curl -s -X POST "http://localhost:8000/api/session/demo-live?mode=live_remote" | python3 -m json.tool
```

Poll `/api/session/{id}/status` until `"status": "complete"`, then fetch the full report:

```bash
SESSION_ID="<id from above>"

# Poll
curl "http://localhost:8000/api/session/$SESSION_ID/status"

# Full report (includes session_mode, live_cues_count, live findings with cue_hint)
curl "http://localhost:8000/api/session/$SESSION_ID/report" | python3 -m json.tool

# Timeline annotations (same format as review mode)
curl "http://localhost:8000/api/session/$SESSION_ID/timeline" | python3 -m json.tool

# Agent findings
curl "http://localhost:8000/api/session/$SESSION_ID/findings" | python3 -m json.tool
```

### Register a pending live session (WebSocket handshake)

```bash
curl -s -X POST http://localhost:8000/api/session/start-live \
  -H "Content-Type: application/json" \
  -d '{"mode": "live_in_room", "personas": ["Skeptical Investor"], "policy_text": ""}' \
  | python3 -m json.tool
```

Returns `session_id` and `ws_url` for the WebSocket connection.

### Static fixtures for offline testing

Two pre-built completed live session fixtures live in `data/fixtures/`:

| File | Mode | Duration | Cues |
|---|---|---|---|
| `live_inroom_session.json` | `live_in_room` | 5:22 | 6 earpiece cues |
| `live_remote_session.json` | `live_remote` | 8:15 | 8 overlay cards |

Both use the same `ReadinessReport` shape as `demo_session.json`. All findings carry `"live": true` and `cue_hint` on actionable items.

### Live mode in the frontend demo flow

When `USE_MOCK = true` in `useLiveSession.ts` (the default):

1. Select **Live In-Room** or **Live Remote** on the SetupPage
2. Click **Start** — the mock session begins immediately (no real microphone needed)
3. Findings and earpiece cues arrive over the mock interval
4. Click **End Session** — the finalizer runs for 2 seconds then transitions to **Results**
5. `ResultsPage` shows the mode-specific report with the **LIVE IN-ROOM** / **LIVE REMOTE** badge, session duration, and cue count

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Smoke tests only (no server needed, < 1 second)
pytest tests/test_smoke.py -v

# API tests (spins up FastAPI in-process)
pytest tests/test_api.py -v

# Live session tests only
pytest tests/test_api.py -v -k "live"
pytest tests/test_smoke.py -v -k "live"

# Specific test
pytest tests/test_api.py -v -k "test_demo_session_full_cycle"
```

Test coverage:
- **`test_smoke.py`** — imports, schema validation, fixture file shape, demo data quality, **live fixture validation** (cue_hints, live=true, duration fields)
- **`test_api.py`** — full HTTP cycle via TestClient: start → poll → report → timeline → findings, **live session registration**, **demo-live in-room and remote full cycles**, **live report provenance fields**, **shared endpoint compatibility**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Inputs                                                     │
│  ┌─────────────┐  ┌──────────────────┐                     │
│  │ Rehearsal   │  │ Policy / Compliance│                     │
│  │ Video (.mp4)│  │ Documents (.pdf)  │                     │
│  └──────┬──────┘  └────────┬─────────┘                     │
│         │                  │                                 │
│  ┌──────▼──────────────────▼──────────────────────────────┐ │
│  │  Multimodal Processing — Gemma 3n E4B                  │ │
│  │  Frame extraction (OpenCV) · OCR · Audio transcription  │ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                             │                                │
│  ┌──────────────────────────▼──────────────────────────────┐ │
│  │  Claim Extraction — Gemma 3n                            │ │
│  │  Identifies product, compliance, comparison claims      │ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                             │                                │
│  ┌──────────────────────────▼──────────────────────────────┐ │
│  │  Agent Router — FunctionGemma 270M (fine-tuned LoRA)    │ │
│  │  Dispatches claims to the right agent(s)                │ │
│  └───────┬────────────────────────────┬────────────────────┘ │
│          │                            │                       │
│  ┌───────▼──────┐ ┌────────────────┐ ┌▼──────────────────┐  │
│  │ Coach Agent  │ │Compliance Agent│ │ Persona Simulator  │  │
│  │ Gemma 3 4B   │ │ Gemma 3 4B     │ │ Gemma 3 4B         │  │
│  └───────┬──────┘ └───────┬────────┘ └┬──────────────────┘  │
│          └───────────┬────┘           │                      │
│                      │◄───────────────┘                      │
│  ┌───────────────────▼──────────────────────────────────────┐ │
│  │  Readiness Report Generator                              │ │
│  │  Score · Findings · Timeline · Priority Fixes            │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Model roles

| Model | Role | Serving |
|---|---|---|
| Gemma 3n E4B | Multimodal processing: OCR, audio transcription, claim extraction | Ollama |
| FunctionGemma 270M | Agent routing: classifies claims → dispatches to agents | HuggingFace transformers + LoRA |
| Gemma 3 4B | Agent reasoning: coach, compliance, persona | Ollama |

### Fine-tuning

FunctionGemma 270M is fine-tuned on a custom dataset of ~100 examples mapping pitch-specific intents to 6 tool functions:

```python
extract_claims(text, claim_types)     → list[Claim]
check_compliance(claim, policy)       → ComplianceResult
coach_presentation(text, context)     → CoachFeedback
simulate_persona(persona, context)    → list[Question]
score_readiness(findings)             → ReadinessScore
tag_timestamp(timestamp, category)    → Annotation
```

Training data: `fine_tuning/function_gemma/dataset.jsonl`  
Training script: `fine_tuning/function_gemma/train.py`

---

## Demo Script (3 minutes)

### The meta-demo: PitchPilot analyses your own hackathon pitch

**Act 1 — Review Mode (0:00–1:30)**

1. **(0:00)** "PitchPilot helps teams stress-test pitches before high-stakes audiences. Everything runs on-device — pitches contain confidential material."

2. **(0:30)** Upload a pre-recorded 2-min rehearsal and the sample policy docs in `data/sample_policies/`. Or click **"Load Demo Session"** to skip the upload.

3. **(0:45)** Show the pipeline running: frame extraction → OCR → transcription → claim extraction → FunctionGemma routing → agents.

4. **(1:00)** Click the **Compliance** tab: highlight the "fully automated" finding and read the policy reference aloud.

5. **(1:20)** Click a **timeline marker** — the timestamp shows exactly where the issue occurred in the video. Show the **Readiness Score** (72/100) and one **Priority Fix**.

**Act 2 — Live In-Room Mode (1:30–2:15)**

6. **(1:30)** Click **New Session**, select **Live In-Room** on the SetupPage. "Now imagine we're in the meeting room right now."

7. **(1:40)** Click Start. The dark minimal UI appears — designed to be invisible to the audience. Deliver 20 seconds of pitch into the microphone.

8. **(1:55)** Show earpiece cues appearing: **"compliance risk"** → **"slow down"** → **"ROI question likely"**. "Each cue arrived within 5–8 seconds of the problematic statement."

9. **(2:05)** Click **End Session**. The finalizer runs. ResultsPage appears — same quality report, same findings, same timeline. But now see the **LIVE IN-ROOM** badge, **5:22 duration**, **6 cues** panel.

**Act 3 — Close (2:15–2:30)**

10. **(2:15)** "Three modes, one product. Review a recording before the meeting. Get coached during it. Review what happened after. All on-device, all private. This is what real-time persuasion support looks like."

### Showing a completed live session without a real device

```bash
# Seed a completed live in-room session
curl -s -X POST "http://localhost:8000/api/session/demo-live?mode=live_in_room" | python3 -m json.tool
# then visit ResultsPage for that session ID to show the full live-mode results view
```

---

## Project Structure

```
instalily/
├── README.md
├── requirements.txt
├── .env.example                    # Copy to .env and edit
│
├── backend/
│   ├── api_schemas.py              # Pydantic API models (Enums + response types)
│   ├── config.py                   # Settings (pydantic-settings, env vars)
│   ├── data_models.py              # Ingestion pipeline Pydantic models
│   ├── demo_server.py              # ← Demo backend (start here for hackathon)
│   ├── main.py                     # Full orchestrator backend (requires models)
│   ├── schemas.py                  # Internal dataclass contracts (pipeline ↔ agents)
│   ├── ingestion.py                # Video ingestion entry point
│   ├── models/
│   │   ├── gemma3n.py              # Gemma 3n Ollama client (multimodal)
│   │   ├── gemma3.py               # Gemma 3 4B Ollama client (reasoning)
│   │   └── function_gemma.py       # FunctionGemma router (fine-tuned LoRA)
│   ├── pipeline/
│   │   ├── video.py                # Frame extraction + keyframe detection
│   │   ├── transcribe.py           # Audio transcription (Gemma 3n / mlx-whisper)
│   │   ├── ocr.py                  # Slide OCR (Gemma 3n vision)
│   │   └── claims.py               # Claim extraction from transcript + OCR
│   ├── agents/
│   │   ├── orchestrator.py         # FunctionGemma routing + parallel dispatch
│   │   ├── coach.py                # Presentation Coach agent
│   │   ├── compliance.py           # Compliance Reviewer agent
│   │   └── persona.py              # Audience Persona Simulator
│   ├── reports/
│   │   └── readiness.py            # Report aggregation + scoring
│   └── prompts/                    # System prompts for each agent
│
├── frontend/                       # React 19 + Vite + Tailwind
│   └── src/
│       ├── App.tsx                 # Root — routes setup / analyzing / results views
│       ├── hooks/
│       │   └── useSession.ts       # Session state machine + polling
│       ├── lib/
│       │   ├── api.ts              # Typed API client
│       │   ├── demo-data.ts        # ← Static demo fixture (index.ts types)
│       │   └── mock-data.ts        # Mock status sequence + report (api.ts types)
│       ├── pages/
│       │   ├── SetupPage.tsx       # Upload + persona config + Load Demo button
│       │   ├── AnalyzingPage.tsx   # Progress view with pipeline stages
│       │   └── ResultsPage.tsx     # Three-panel results (video / findings / timeline)
│       ├── components/
│       │   ├── VideoPlayer.tsx     # HTML5 video with VideoPlayerHandle ref API
│       │   ├── FindingsPanel.tsx   # Tabbed agent findings (Coach/Compliance/Persona)
│       │   ├── ReadinessScore.tsx  # SVG dial + dimension bars
│       │   ├── TimelinePanel.tsx   # ← Interactive timeline strip
│       │   ├── ReportSummary.tsx   # ← Priority fixes + persona questions
│       │   ├── AnalysisResults.tsx # ← Alternative results layout (index.ts types)
│       │   └── Timeline.tsx        # ← Standalone timeline (index.ts types)
│       └── types/
│           ├── index.ts            # Types matching backend api_schemas.py
│           └── api.ts              # Types used by current UI components
│
├── data/
│   ├── fixtures/
│   │   └── demo_session.json       # ← Complete demo session fixture
│   ├── sample_policies/
│   │   ├── enterprise_data_policy.txt   ← Load this in the compliance demo
│   │   └── approved_messaging_guide.txt ← Approved/prohibited phrasing guide
│   └── sessions/                   # Runtime: per-session working directories
│
├── fine_tuning/
│   └── function_gemma/
│       ├── generate_dataset.py     # Generates training examples
│       ├── dataset.jsonl           # Training data (~100 examples)
│       └── train.py                # LoRA fine-tuning with Unsloth
│
├── scripts/
│   ├── run_demo.sh                 # ← One-command demo launcher
│   └── seed_demo.py                # ← Seed a demo session via API
│
└── tests/
    ├── test_smoke.py               # ← Import + schema + fixture tests (fast)
    └── test_api.py                 # ← Full HTTP cycle tests (TestClient)
```

---

## Troubleshooting

### Backend won't start

```bash
# Check for port conflicts
lsof -i :8000

# Check Python version
python3 --version  # needs 3.11+

# Re-install deps
pip install -r requirements.txt --upgrade
```

### Frontend blank or "Cannot connect to backend"

1. Check the demo server is running: `curl http://localhost:8000/health`
2. Check Vite's proxy config in `frontend/vite.config.ts` — it proxies `/api` to port 8000
3. Try hard-refreshing the browser (Cmd+Shift+R)

### Demo session takes too long

Set the delay to 0 for instant results:

```bash
PITCHPILOT_DEMO_DELAY=0 uvicorn backend.demo_server:app --port 8000
# or
bash scripts/run_demo.sh --fast
```

### Ollama models not loading (for real inference)

```bash
ollama list                          # check what's pulled
ollama pull gemma-3n:e4b             # ~4 GB
ollama pull gemma3:4b                # ~3 GB
curl http://localhost:11434/api/tags # verify Ollama is running
```

---

## Performance Tuning + Recommended Settings for Mac

PitchPilot has been optimized for local, on-device inference on Apple Silicon Macs with 16 GB RAM.  Below are the key knobs and their recommended values depending on your hardware.

### Configuration reference

All settings can be set via environment variables or in `.env` (prefix `PITCHPILOT_`):

| Setting | Default | Fast-mode | Description |
|---|---|---|---|
| `PITCHPILOT_FAST_MODE` | `false` | `true` | Trade accuracy for speed; reduces FPS, skips persona agent, caps claims at 15 |
| `PITCHPILOT_EXTRACTION_FPS` | `1.0` | `0.5` | Frame sample rate. Lower = fewer frames, fewer OCR calls |
| `PITCHPILOT_FRAME_MAX_DIMENSION` | `1920` | `768` | Downscale frames before OCR. Smaller = faster base64 + faster model |
| `PITCHPILOT_KEYFRAME_DIFF_THRESHOLD` | `0.3` | `0.2` | Scene-change sensitivity. Lower = more keyframes |
| `PITCHPILOT_OCR_CONCURRENCY` | `2` | `1` | Max parallel OCR calls to Ollama. Ollama is serial on GPU — keep ≤ 2 |
| `PITCHPILOT_AGENT_CONCURRENCY` | `3` | `2` | Max parallel agent LLM calls |
| `PITCHPILOT_RETAIN_ARTIFACTS` | `false` | `false` | Keep extracted frames/audio after session. Set `true` for debugging |
| `PITCHPILOT_OLLAMA_TIMEOUT_SECONDS` | `120` | `60` | Per-request Ollama timeout |
| `PITCHPILOT_WHISPER_MODEL` | `base` | `tiny` | Whisper model size for transcription fallback |
| `PITCHPILOT_MAX_CLAIMS_PER_SESSION` | `50` | `15` | Hard cap on claims extracted |

### Recommended profiles

**Standard quality (default — 16 GB Mac M2/M3):**
```bash
PITCHPILOT_MOCK_MODE=false
PITCHPILOT_EXTRACTION_FPS=1.0
PITCHPILOT_OCR_CONCURRENCY=2
PITCHPILOT_AGENT_CONCURRENCY=3
PITCHPILOT_FRAME_MAX_DIMENSION=1280
PITCHPILOT_RETAIN_ARTIFACTS=false
```

**Fast mode (~50% faster, slight accuracy tradeoff):**
```bash
PITCHPILOT_MOCK_MODE=false
PITCHPILOT_FAST_MODE=true
PITCHPILOT_FRAME_MAX_DIMENSION=768
PITCHPILOT_OCR_CONCURRENCY=1
PITCHPILOT_WHISPER_MODEL=tiny
```

**Debug / retain artifacts:**
```bash
PITCHPILOT_RETAIN_ARTIFACTS=true
PITCHPILOT_MOCK_MODE=false
```

### What was optimized

The following optimizations reduce end-to-end latency:

1. **Single-pass frame extraction + keyframe detection** — OpenCV loop now computes pixel diff in one pass instead of two (saves one full re-read of all frames from disk).
2. **Only keyframes saved to disk** — non-keyframe frames are used only for diff computation then discarded, reducing disk I/O by 60–90% for static slide decks.
3. **Frame downscaling** — frames are resized to `FRAME_MAX_DIMENSION` before JPEG encoding and OCR, reducing base64 payload size and model inference time.
4. **Perceptual hash OCR cache** — near-identical frames (Hamming distance ≤ 5) reuse the previous OCR result, eliminating duplicate LLM calls for repeated slides.
5. **Bounded LLM concurrency** — `OCR_CONCURRENCY` and `AGENT_CONCURRENCY` semaphores prevent unbounded Ollama request queues. Since Ollama processes requests serially on the GPU, firing 30 concurrent requests just builds a queue and wastes RAM.
6. **Shared httpx.AsyncClient** — all Ollama calls share one connection-pooled HTTP client with automatic retry on transient errors (3 attempts, exponential backoff).
7. **`keep_alive=10m`** — sent with every Ollama request to prevent model unloading between back-to-back pipeline calls.
8. **Scoped OCR text per claim window** — each transcript window only sees temporally-nearby OCR blocks, reducing prompt token count by 40–70% for longer videos.
9. **`format=json` on all model calls** — eliminates markdown-fence stripping fallback, speeds up parsing.
10. **Audio + frame extraction in parallel** — ffmpeg audio extraction runs concurrently with frame processing.
11. **Async event loop unblocked** — all CPU-bound video work (OpenCV) runs in `asyncio.to_thread()` so the FastAPI event loop remains responsive.
12. **Session artifact cleanup** — extracted frames, audio, and video files are deleted after report generation (unless `RETAIN_ARTIFACTS=true`), preventing disk fill-up in production.

### Running the benchmark

```bash
# Mock mode (no models required, measures pipeline overhead only)
python scripts/benchmark_session.py

# Real models, single run
PITCHPILOT_MOCK_MODE=false \
python scripts/benchmark_session.py --video /path/to/rehearsal.mp4

# 3 runs, real models, fast mode
PITCHPILOT_MOCK_MODE=false PITCHPILOT_FAST_MODE=true \
python scripts/benchmark_session.py --video /path/to/rehearsal.mp4 --runs 3

# Keep artifacts for inspection
python scripts/benchmark_session.py --no-cleanup

# Output JSON metrics
python scripts/benchmark_session.py --json
python scripts/benchmark_session.py --out metrics_run1.json
```

Sample output:

```
PitchPilot Benchmark
────────────────────────────────────────
  mock_mode:        False
  fast_mode:        False
  extraction_fps:   1.0
  ocr_concurrency:  2
  agent_concurrency:3
  frame_max_dim:    1280
  retain_artifacts: False

  Video:   /tmp/rehearsal.mp4
  Runs:    1

════════════════════════════════════════════════════════════
  PitchPilot Benchmark Summary
════════════════════════════════════════════════════════════
  Total time:     87.42s
  Peak memory:    412.3 MB
  Claims:         12
  Findings:       18
  Keyframes:      8
  OCR blocks:     24
  LLM calls:      0

  Stage breakdown (run #1):
    agent_coach                     32.10s   36.7%  ███████
    agent_compliance                28.44s   32.5%  ██████
    ocr_frames                      14.22s   16.3%  ███
    transcription                    7.81s    8.9%  █
    claim_extraction                 3.18s    3.6%
    frame_extraction                 1.02s    1.2%
    audio_extraction                 0.44s    0.5%
════════════════════════════════════════════════════════════
```

### Expected performance on Apple Silicon

| Scenario | Video length | Expected time | Notes |
|---|---|---|---|
| Mock mode | any | 1–3s | Pipeline overhead only, no model calls |
| Fast mode (real models) | 5 min | 60–90s | Persona skipped, fewer OCR calls |
| Standard mode (real models) | 5 min | 90–150s | All agents, 1 fps sampling |
| Standard mode (real models) | 2 min | 40–70s | Short pitch deck |

> **Note:** LLM call latency dominates. At ~4 tok/s for Gemma 3 4B on M2, a single agent call with a 500-token response takes ~7s. Reducing call count is more effective than any other optimization.

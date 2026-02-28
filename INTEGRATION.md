# PitchPilot — Integration Contracts & Developer Notes

This document explains how the backend modules plug together and what contracts
each component must honour.  Read this before touching any pipeline or agent code.

---

## 1. The Data Flow

```
POST /api/session/start
        │
        ▼
  [pipeline/video.py]      extract_frames() → list[VideoFrame]
  [pipeline/video.py]      extract_audio()  → wav_path
        │
        ├──▶ [pipeline/ocr.py]       ocr_frames()      → list[SlideText]
        └──▶ [pipeline/transcribe.py] transcribe()     → str
        │
        ▼
  [pipeline/claims.py]     extract_claims() → list[Claim]       ← schema.Claim
        │
        ▼
  [agents/orchestrator.py] orchestrate()   → list[Finding]      ← schema.Finding
        │  (routes via FunctionGemma → Coach / Compliance / Persona)
        ▼
  [reports/readiness.py]   build_report()  → ReadinessReport    ← schema.ReadinessReport
        │
        ▼
  stored in _sessions[id]  ← Session object (in-memory)
        │
        ▼
  GET /api/session/{id}/report | /timeline | /findings
```

---

## 2. Schema Contracts

**Single source of truth:** `backend/schemas.py` + `frontend/src/types/index.ts`

- Every field that exists in Python must exist with the same name in TypeScript.
- UUID fields are `str` on the frontend (JSON serialises UUIDs as strings).
- Enums (`AgentType`, `Severity`, `SessionStatus`, etc.) are string literals on both sides.
- When you add a field to a Pydantic model, add it to the TS interface immediately.

---

## 3. How to Plug In a Real Pipeline Module

Replace mock logic by setting `settings.use_mock_pipeline = False` in `.env`, then:

### 3a. Video pipeline (`backend/pipeline/video.py`)
- `extract_frames(video_path, fps)` → `list[VideoFrame]`
- `extract_audio(video_path)` → `str` (path to wav)
- No Pydantic dependencies — returns local dataclasses.  Convert to schemas only at the
  claims step.

### 3b. OCR (`backend/pipeline/ocr.py`)
- `ocr_frames(frames)` → `list[SlideText]`
- Calls `gemma3n_client.ocr_frame()` per frame (parallelised with asyncio.Semaphore).
- Deduplicates consecutive identical slides.

### 3c. Transcription (`backend/pipeline/transcribe.py`)
- `transcribe(audio_path)` → `str`
- Primary: Gemma 3n.  Fallback: mlx-whisper (set `use_whisper_fallback=True`).

### 3d. Claims (`backend/pipeline/claims.py`)
- `extract_claims(transcript, slide_texts)` → `list[Claim]`
- Returns proper `backend.schemas.Claim` objects.
- This is where raw text turns into typed, timestamped claims.

### 3e. Orchestrator (`backend/agents/orchestrator.py`)
- `orchestrate(claims, policy_text, personas)` → `list[Finding]`
- Uses `FunctionGemmaRouter.route()` to decide which agents handle each claim.
- In mock mode, the router uses keyword heuristics (see `_mock_route`).
- When real FunctionGemma is loaded, set `settings.use_mock_pipeline = False`
  and the router will use the fine-tuned model.

### 3f. Agents (`backend/agents/{coach,compliance,persona}.py`)
- Each agent exposes `async def analyze(claim: Claim, ...) → list[Finding]`.
- Returns `[]` when `use_mock_pipeline = True` (mock data injected at main.py level).
- Do not call agents directly from `main.py` — always via the orchestrator.

### 3g. Report (`backend/reports/readiness.py`)
- `build_report(session_id, claims, findings, created_at)` → `ReadinessReport`
- Scoring is currently heuristic (point deductions per severity).
- Replace `_compute_score` with a Gemma 3 4B call for a narrative-quality score.

---

## 4. Session Store

Sessions live in `_sessions: dict[UUID, Session]` in `main.py`.  This is intentionally
simple for hackathon scope.

**To replace with persistent storage:**
1. Create a `backend/store.py` module with async `get_session`, `set_session` functions.
2. Replace all `_sessions[id]` accesses in `main.py` with `await store.get_session(id)`.
3. Back it with Redis, SQLite (via aiosqlite), or Postgres (via asyncpg).

---

## 5. Model Clients

| Module | Singleton | When to call |
|--------|-----------|--------------|
| `backend/models/gemma3n.py` | `gemma3n_client` | OCR, transcription, claim extraction |
| `backend/models/gemma3.py` | `gemma3_client` | Agent reasoning (coach, compliance, persona) |
| `backend/models/function_gemma.py` | `function_gemma_router` | Claim → agent routing only |

All three are module-level singletons.  Import the instance, not the class.

`function_gemma_router.load()` must be called once at startup (add a FastAPI
`lifespan` event to `main.py` when ready to use the real model).

---

## 6. Frontend ↔ Backend Contract

The frontend never constructs domain objects from scratch — it only reads what the API
returns.  The API always returns complete typed objects (no partial updates).

**Polling pattern:**
```typescript
// Poll every 2.5s until status === "complete"
const status = await api.getStatus(sessionId);
if (status.status === "complete") {
  const report = await api.getReport(sessionId);
}
```

**Error handling:** The API returns HTTP 202 (not an error) while processing.
The fetch client in `src/lib/api.ts` treats 202 as an ignorable exception during polling.
A real error from the pipeline returns HTTP 500 with `status === "failed"`.

---

## 7. Adding a New Agent

1. Create `backend/agents/my_agent.py` with an `async def analyze(claim, ...) → list[Finding]`.
2. Add `my_function` to `KNOWN_FUNCTIONS` in `backend/models/function_gemma.py`.
3. Update `_mock_route` in `function_gemma.py` to dispatch to your new function.
4. Add a dispatch case in `agents/orchestrator.py → _dispatch_claim`.
5. Add a new `AgentType` enum value in `backend/schemas.py` and `frontend/src/types/index.ts`.
6. Add a tab in `frontend/src/components/AgentFindings.tsx`.

---

## 8. Environment Variables

Create `.env` at the project root:

```
OLLAMA_BASE_URL=http://localhost:11434
GEMMA3N_MODEL=gemma-3n:e4b
GEMMA3_MODEL=gemma3:4b
FUNCTION_GEMMA_MODEL_ID=google/gemma-3-1b-it
FUNCTION_GEMMA_LORA_PATH=./fine_tuning/function_gemma/adapter
USE_MOCK_PIPELINE=true          # set false to use real models
```

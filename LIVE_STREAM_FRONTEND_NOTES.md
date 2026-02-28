# PitchPilot Live Stream — Frontend Integration Notes

How the frontend should connect to and consume the live WebSocket stream.

---

## 1. Session startup flow

```
POST /api/session/start-live
  Body: { mode, personas, policy_text, title }
  Response: { session_id, ws_url, mode, status }

→ Open WebSocket at ws_url  (ws://localhost:8000/api/session/live)
→ Send init message (see below)
→ Begin streaming audio + frames
→ Receive live events (see message types below)
→ Send end_session when presenter finishes
→ Receive session_complete, then poll GET /api/session/{id}/report
```

---

## 2. Init message (first message after WS connect)

```json
{
  "type": "init",
  "mode": "rehearsal | in_room | remote",
  "personas": ["Skeptical Investor", "Compliance Officer"],
  "policy_text": "...",
  "title": "Q3 Enterprise Demo"
}
```

The `mode` field drives all downstream behaviour. Missing or unknown mode defaults to `"rehearsal"`.

---

## 3. Binary streaming format

Send binary frames with a 1-byte type prefix:

| Prefix | Content | Cadence |
|--------|---------|---------|
| `0x01` | Audio chunk (WebM/Opus from MediaRecorder) | Every ~2 s |
| `0x02` | Screen/camera JPEG (canvas.toBlob()) | Every ~5 s |

```javascript
// Audio (MediaRecorder ondataavailable)
const buf = new Uint8Array(1 + chunk.size);
buf[0] = 0x01;
buf.set(new Uint8Array(await chunk.arrayBuffer()), 1);
ws.send(buf.buffer);

// Frame (canvas snapshot)
canvas.toBlob(blob => {
  blob.arrayBuffer().then(ab => {
    const buf = new Uint8Array(1 + ab.byteLength);
    buf[0] = 0x02;
    buf.set(new Uint8Array(ab), 1);
    ws.send(buf.buffer);
  });
}, 'image/jpeg', 0.85);
```

---

## 4. Inbound message types

### All modes

| Type | When | Key fields |
|------|------|------------|
| `session_created` | Immediately after init | `session_id`, `mode` |
| `transcript_update` | After each audio chunk | `segments[].text`, `segments[].start_time`, `elapsed` |
| `finding` | New agent finding | `finding.{id,agent,severity,title,detail,suggestion,cue_hint}`, `elapsed` |
| `nudge` | Coach info/warning | `agent`, `message`, `suggestion`, `severity`, `elapsed` |
| `status` | Processing milestones | `message`, `progress` |
| `finalizing` | After `end_session` | `message`, `elapsed` |
| `session_complete` | Report ready | `session_id` |
| `error` | Any error | `message` |
| `pong` | Response to ping | — |

### `in_room` mode only

```json
{
  "type": "earpiece_cue",
  "text": "slow down",
  "audio_b64": "<base64 AIFF or null>",
  "priority": "warning | critical",
  "category": "coach | compliance | persona",
  "elapsed": 22.4
}
```

**Play immediately through the earpiece output device:**

```javascript
if (msg.audio_b64) {
  const binary = atob(msg.audio_b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], { type: 'audio/aiff' });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.setSinkId(earpieceDeviceId);  // use selected earpiece output
  await audio.play();
  URL.revokeObjectURL(url);
} else {
  // Fall back to on-screen text display of msg.text
  showCueText(msg.text);
}
```

> Audio cues are rate-limited server-side to 1 per 15 s. Never play two simultaneously — queue them.

### `remote` mode only

```json
{ "type": "overlay_card", "agent": "compliance", "severity": "critical",
  "title": "...", "detail": "...", "suggestion": "...", "cue_text": "compliance risk", "elapsed": 30.1 }

{ "type": "teleprompter", "points": ["Point 1.", "Point 2.", "Point 3."],
  "slide_context": "Slide OCR text snippet...", "elapsed": 25.0 }

{ "type": "objection_prep",
  "questions": [
    { "question": "How is this different from ChatGPT?",
      "suggested_answer": "...", "persona": "Skeptical Investor", "difficulty": "hard" }
  ],
  "elapsed": 60.0 }

{ "type": "script_suggestion", "original": "fully automated", "alternative": "automated with optional review",
  "reason": "Policy §3.2 requires human oversight for high-confidence outputs.",
  "agent": "compliance", "elapsed": 35.2 }
```

---

## 5. Session termination

```json
{ "type": "end_session" }
```

Server responds with `finalizing` → (builds report) → `session_complete`. Then fetch:

```
GET /api/session/{session_id}/report
GET /api/session/{session_id}/timeline
GET /api/session/{session_id}/findings
```

These return the same JSON schema as review mode — route to `ResultsPage` directly.

---

## 6. useLiveSession hook state fields

```typescript
// Shared
transcript: TranscriptSegment[]
findings: Finding[]
status: 'idle' | 'connecting' | 'active' | 'finalizing' | 'complete' | 'error'
elapsed: number

// in_room
cues: EarpieceCue[]              // recent cues (auto-expire after 8 s)
audioQueue: AudioBuffer[]        // queued audio, play sequentially

// remote
teleprompterPoints: string[]     // current talking points
overlayCards: OverlayCard[]      // active dismissible cards
objectionCards: ObjectionCard[]  // Q&A prep drawer
scriptSuggestions: ScriptSuggestion[]  // toasts
```

---

## 7. Error handling & reconnect

- On `error` message: display to user, keep WS open if recoverable.
- On WS disconnect before `session_complete`: attempt reconnect once; if session_id is known, the in-memory session is preserved for 30 min.
- Heartbeat: send `{"type": "ping"}` every 20 s; expect `{"type": "pong"}` back.
- If `status === 'failed'` on the REST poll, show error with `error_message` field.

---

## 8. Env variable overrides (for tuning during demo)

```bash
PITCHPILOT_CUE_MIN_INTERVAL_SECONDS=10    # fire cues more frequently
PITCHPILOT_TELEPROMPTER_UPDATE_INTERVAL=15 # refresh talking points faster
PITCHPILOT_LIVE_EXTRACT_INTERVAL=3         # run claim extraction more often
PITCHPILOT_MOCK_MODE=true                  # use deterministic stub responses
```

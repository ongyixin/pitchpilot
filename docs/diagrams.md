# PitchPilot — Architecture Diagrams & Presentation Scripts

> Seven diagrams covering the full tech stack, system architecture, data pipelines, agent routing, frontend state machine, model inference, and scoring logic.

---

## 1. Tech Stack Overview

```mermaid
graph TB
    subgraph Frontend["Frontend (React 19 + Vite 6)"]
        TS[TypeScript]
        TW[Tailwind CSS 3.4]
        RH[React Hooks]
    end

    subgraph Backend["Backend (Python 3.12 + FastAPI)"]
        UV[Uvicorn ASGI]
        PY[Pydantic v2 Schemas]
        WS[WebSocket Handler]
    end

    subgraph Models["On-Device Models"]
        G3N["Gemma 3n E4B<br/>Multimodal: OCR, Audio, Claims"]
        G31B["Gemma 3 1B + LoRA<br/>Agent Router"]
        G34B["Gemma 3 4B<br/>Agent Reasoning"]
    end

    subgraph Inference["Inference Backends"]
        HF[HuggingFace Transformers<br/>Text + Image + Audio]
        OL[Ollama GGUF<br/>Text + Image]
        MLX[mlx-whisper<br/>Audio Fallback]
    end

    subgraph Processing["Media Processing"]
        CV[OpenCV<br/>Frame Extraction]
        FF[ffmpeg<br/>Audio Extraction]
        PP[pypdf<br/>Policy PDF Parsing]
    end

    subgraph FineTuning["Fine-Tuning"]
        PEFT[PEFT / LoRA]
        US[Unsloth]
        PT[PyTorch]
    end

    Frontend -->|"REST + WebSocket<br/>via Vite proxy"| Backend
    Backend --> Models
    Models --> Inference
    Backend --> Processing
    FineTuning -.->|"Adapter weights"| G31B
```

---

## 2. High-Level System Architecture

```mermaid
graph LR
    subgraph Inputs
        VID["Rehearsal Video<br/>.mp4 / .mov / .webm"]
        POL["Policy Docs<br/>.txt / .pdf"]
        MIC["Microphone<br/>(live mode)"]
        CAM["Camera<br/>(live mode)"]
    end

    subgraph Frontend
        LP[LandingPage]
        SP[SetupPage]
        AP[AnalyzingPage]
        RP[ResultsPage]
        IRM[InRoomModePage]
        RMP[RemoteModePage]
    end

    subgraph Backend
        API["FastAPI Server<br/>main.py / demo_server.py"]
        ING["IngestionPipeline<br/>ingestion.py"]
        ORCH["Orchestrator<br/>agents/orchestrator.py"]
        RPT["ReportGenerator<br/>reports/readiness.py"]
        LWS["WebSocket Handler<br/>live_ws.py"]
        LIVE["LivePipeline<br/>pipeline/live.py"]
    end

    subgraph Agents
        ROUTER["FunctionGemmaRouter<br/>Rule-based or Gemma 3 1B + LoRA"]
        COACH[CoachAgent]
        COMP[ComplianceAgent]
        PERS[PersonaAgent]
    end

    VID --> SP
    POL --> SP
    SP -->|"POST /api/session/start"| API
    API --> ING --> ORCH
    ORCH --> ROUTER --> COACH & COMP & PERS
    COACH & COMP & PERS --> RPT
    RPT -->|"GET /api/session/{id}/report"| RP

    MIC --> IRM & RMP
    CAM --> IRM & RMP
    IRM & RMP -->|"WebSocket binary<br/>audio + frames"| LWS
    LWS --> LIVE --> ROUTER
    LIVE -->|"WebSocket JSON<br/>findings, cues, overlays"| IRM & RMP
```


---

## 3. Review Mode Data Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend
    participant API as FastAPI
    participant Vid as video.py
    participant OCR as ocr.py
    participant Tx as transcribe.py
    participant Cl as claims.py
    participant Rtr as FunctionGemmaRouter
    participant Coach as CoachAgent
    participant Comp as ComplianceAgent
    participant Pers as PersonaAgent
    participant Rpt as ReportGenerator

    User->>UI: Upload video + policies
    UI->>API: POST /api/session/start
    Note over API: Creates session, saves files

    par Frame + Audio Extraction
        API->>Vid: extract_frames_and_keyframes()
        Note over Vid: OpenCV single-pass<br/>keyframe diff > 0.3
        API->>Vid: extract_audio() via ffmpeg
    end

    API->>OCR: process_frames(keyframes)
    Note over OCR: Gemma 3n + phash cache<br/>dedup Hamming ≤ 5

    API->>OCR: process_document(policy PDFs)
    API->>Tx: transcribe(audio)
    Note over Tx: Gemma 3n native → mlx-whisper fallback

    API->>Cl: extract(transcript, ocr_blocks)
    Note over Cl: Overlapping windows<br/>+ scoped OCR → claims

    API->>Rtr: route_batch(claims)
    Note over Rtr: Rule-based or Gemma 3 1B + LoRA

    par Agent Dispatch
        Rtr->>Coach: analyze_batch()
        Rtr->>Comp: analyze_batch()
        Rtr->>Pers: analyze_batch()
    end

    Coach-->>API: coaching findings
    Comp-->>API: compliance findings
    Pers-->>API: persona questions

    API->>Rpt: generate(findings, context)
    Note over Rpt: Weighted scoring<br/>0–100, grade A–F

    loop Poll every 2s
        UI->>API: GET /api/session/{id}/status
        API-->>UI: {progress, stage}
    end

    UI->>API: GET /api/session/{id}/report
    API-->>UI: ReadinessReport
    UI->>User: Render ResultsPage
```

---

## 4. Live Mode Pipeline

```mermaid
sequenceDiagram
    actor Presenter
    participant UI as InRoomMode / RemoteMode
    participant WS as WebSocket Handler<br/>(live_ws.py)
    participant LP as LivePipeline<br/>(live.py)
    participant CS as CueSynthesizer<br/>(cue_synth.py)
    participant TTS as TTS Engine<br/>(tts.py)
    participant Rpt as ReportGenerator

    Presenter->>UI: Start live session
    UI->>WS: init {mode, personas, policy_text}
    WS-->>UI: session_created {session_id}

    loop Every ~2s
        Presenter->>UI: Speak + show slides
        UI->>WS: Binary 0x01 (audio chunk)
        UI->>WS: Binary 0x02 (JPEG frame)
    end

    loop Every 5s (LIVE_EXTRACT_INTERVAL)
        WS->>LP: process_buffer()
        LP->>LP: transcribe buffered audio
        LP->>LP: OCR if slide changed<br/>(text diff > 0.25)
        LP->>LP: extract claims
        LP->>LP: route + run agents

        LP-->>WS: new findings
        WS-->>UI: finding {finding}
        WS-->>UI: transcript_update {segments}

        LP->>CS: synthesize_cue(finding)
        Note over CS: Rate limit: 15s min gap<br/>Dedup: 60s window

        alt In-Room Mode
            CS->>TTS: generate audio
            TTS-->>WS: audio bytes
            WS-->>UI: earpiece_cue {text, audio_b64}
        else Remote Mode
            CS-->>WS: overlay_card / teleprompter / objection_prep
            WS-->>UI: overlay_card / teleprompter
        end
    end

    Presenter->>UI: End Session
    UI->>WS: end_session
    WS-->>UI: finalizing
    WS->>Rpt: generate final report
    WS-->>UI: session_complete {report}
    UI->>Presenter: Render ResultsPage
```

---

## 5. Agent Router & Dispatch

```mermaid
flowchart TD
    CLAIMS["Extracted Claims<br/>(up to 50 per session)"]

    CLAIMS --> ROUTER{"FunctionGemmaRouter"}

    ROUTER -->|"ROUTER_USE_RULES=true<br/>(default)"| RULES["Rule-Based Router<br/>router_rules.yaml"]
    ROUTER -->|"ROUTER_USE_RULES=false"| MODEL["Gemma 3 1B + LoRA<br/>FunctionGemma tokens"]

    RULES --> CLASSIFY
    MODEL --> CLASSIFY

    CLASSIFY{Claim Classification}

    CLASSIFY -->|"check_compliance<br/>(claim, claim_type)"| COMP["ComplianceAgent<br/>Gemma 3 4B"]
    CLASSIFY -->|"coach_presentation<br/>(section_text, ...)"| COACH["CoachAgent<br/>Gemma 3 4B"]
    CLASSIFY -->|"simulate_persona<br/>(claim_context, ...)"| PERS["PersonaAgent<br/>Gemma 3 4B"]
    CLASSIFY -->|"tag_timestamp<br/>(timestamp, category)"| TAG["Timeline Annotation<br/>(direct, no agent)"]

    COMP --> FINDINGS["Agent Findings<br/>severity: info | warning | critical"]
    COACH --> FINDINGS
    PERS --> FINDINGS
    TAG --> TL["Timeline Markers"]

    FINDINGS --> REPORT["ReportGenerator"]
    TL --> REPORT
    REPORT --> SCORE["Readiness Score 0–100<br/>Grade A–F"]

    style ROUTER fill:#4a5568,color:#fff
    style RULES fill:#2d3748,color:#fff
    style MODEL fill:#2d3748,color:#fff
    style COMP fill:#c53030,color:#fff
    style COACH fill:#2b6cb0,color:#fff
    style PERS fill:#2f855a,color:#fff
```

---

## 6. Frontend State Machine

```mermaid
stateDiagram-v2
    [*] --> Landing

    Landing --> Setup_Review: "Launch" / "Get Started"
    Landing --> Setup_LiveInRoom: "Go Live" (in-room)
    Landing --> Setup_LiveRemote: "Go Live" (remote)
    Landing --> Analyzing: "Load Demo Session"

    state "Review Flow" as ReviewFlow {
        Setup_Review --> Analyzing: startAnalysis(video, docs)
        Setup_Review --> Analyzing: startDemo()
        Analyzing --> Results: status === complete
        Analyzing --> Setup_Review: error / reset
    }

    state "Live In-Room Flow" as LiveInRoom {
        Setup_LiveInRoom --> Connecting_IR: startSession()
        Connecting_IR --> InRoomMode: WebSocket connected
        InRoomMode --> Finalizing_IR: endSession()
        Finalizing_IR --> Results_IR: report received
    }

    state "Live Remote Flow" as LiveRemote {
        Setup_LiveRemote --> Connecting_RM: startSession()
        Connecting_RM --> RemoteMode: WebSocket connected
        RemoteMode --> Finalizing_RM: endSession()
        Finalizing_RM --> Results_RM: report received
    }

    Results --> Landing: "New Session"
    Results_IR --> Landing: "New Session"
    Results_RM --> Landing: "New Session"
```

---

## 7. Model Inference Architecture

```mermaid
flowchart TB
    subgraph Config["Configuration"]
        ENV["PITCHPILOT_GEMMA3N_BACKEND"]
    end

    ENV -->|"huggingface"| HF_PATH
    ENV -->|"ollama"| OL_PATH

    subgraph HF_PATH["HuggingFace Path"]
        HF_G3N["Gemma3nHFModel<br/>gemma3n_hf.py"]
        HF_G3N -->|"text + image + audio"| OCR_HF[OCR]
        HF_G3N -->|"native audio"| TX_HF[Transcription]
        HF_G3N -->|"text"| CL_HF[Claim Extraction]
        HF_G3N -->|"delegates agent calls"| AG_HF[Agent Reasoning]
    end

    subgraph OL_PATH["Ollama Path"]
        OL_G3N["Gemma3nOllamaModel<br/>gemma3n.py"]
        OL_G3["Gemma3OllamaModel<br/>gemma3.py"]
        OL_G3N -->|"text + image"| OCR_OL[OCR]
        OL_G3N -->|"text"| CL_OL[Claim Extraction]
        OL_G3 -->|"text"| AG_OL[Agent Reasoning]

        MLX["mlx-whisper<br/>(Apple Silicon)"]
        MLX -->|"audio fallback"| TX_OL[Transcription]
    end

    subgraph Router["Router (both paths)"]
        RULES["Rule-Based<br/>router_rules.yaml"]
        FG["Gemma 3 1B + LoRA<br/>function_gemma.py"]
    end

    subgraph Mock["Mock Mode (MOCK_MODE=true)"]
        MOCK["Deterministic stubs<br/>No model loading"]
    end

    style HF_PATH fill:#1a365d,color:#fff
    style OL_PATH fill:#22543d,color:#fff
    style Mock fill:#744210,color:#fff
```

---

## 8. Readiness Scoring Breakdown

```mermaid
flowchart LR
    subgraph Input["Agent Findings"]
        F1["CoachAgent findings"]
        F2["ComplianceAgent findings"]
        F3["PersonaAgent findings"]
    end

    subgraph Dimensions["Scoring Dimensions"]
        D1["Clarity<br/>weight: 25%"]
        D2["Compliance<br/>weight: 30%"]
        D3["Defensibility<br/>weight: 25%"]
        D4["Persuasiveness<br/>weight: 20%"]
    end

    subgraph Scoring["Per-Dimension Scoring"]
        BASE["Content floor: 50 pts"]
        BONUS["Bonus: proportional to<br/>claims analyzed (max 15)"]
        PEN["Severity penalties:<br/>info −3 | warning −8 | critical −18"]
    end

    subgraph Output["Final Output"]
        SCORE["Readiness Score<br/>0–100"]
        GRADE["Letter Grade<br/>A ≥ 90 | B ≥ 80 | C ≥ 70<br/>D ≥ 60 | F < 60"]
    end

    F1 & F2 & F3 --> D1 & D2 & D3 & D4
    D1 & D2 & D3 & D4 --> BASE --> BONUS --> PEN --> SCORE --> GRADE

    style D1 fill:#2b6cb0,color:#fff
    style D2 fill:#c53030,color:#fff
    style D3 fill:#2f855a,color:#fff
    style D4 fill:#6b46c1,color:#fff
```

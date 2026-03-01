"""
PitchPilot — FastAPI application entry point.

All routes live here for hackathon clarity.  Once agents are implemented,
each route handler should delegate to the relevant pipeline/agent/report
module rather than growing inline.

Run:
    uvicorn backend.main:app --reload --port 8000

Integration note
----------------
Set PITCHPILOT_MOCK_MODE=false (and ensure Ollama is running) to enable
real model inference.  The progress_callback wired in start_session() drives
the session status so the frontend polling always sees fresh milestones.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.api_schemas import (
    Claim,
    ClaimType,
    DimensionScore,
    Finding,
    FindingsResponse,
    LiveSessionStartRequest,
    LiveSessionStartResponse,
    PersonaQuestion,
    ReadinessReport,
    ReadinessScore,
    Session,
    SessionMode,
    SessionStartResponse,
    SessionStatus,
    SessionStatusResponse,
    Severity,
    TimelineAnnotation,
    TimelineCategory,
    TimelineResponse,
    AgentType,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PitchPilot API",
    description="On-device multi-agent copilot for demo/sales readiness",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Session store — in-memory with disk persistence across hot-reloads
# ---------------------------------------------------------------------------

_sessions: dict[str, Session] = {}

# Persisted to a stable tmp directory so uvicorn --reload doesn't lose state.
_SESSION_STORE_DIR = Path(tempfile.gettempdir()) / "pitchpilot_sessions"


def _persist_session(session: Session) -> None:
    """Write a single session to disk as JSON (best-effort, never raises)."""
    try:
        _SESSION_STORE_DIR.mkdir(parents=True, exist_ok=True)
        path = _SESSION_STORE_DIR / f"{session.id}.json"
        path.write_text(session.model_dump_json())
    except Exception:
        pass  # persistence is best-effort; don't break the pipeline


def _load_persisted_sessions() -> None:
    """
    Re-hydrate sessions from disk on startup.

    Any session that was mid-flight (PROCESSING/PENDING) when the server died
    is transitioned to FAILED so the frontend stops polling and shows an error.
    """
    if not _SESSION_STORE_DIR.exists():
        return
    for path in _SESSION_STORE_DIR.glob("*.json"):
        try:
            session = Session.model_validate_json(path.read_text())
            if session.status in (SessionStatus.PROCESSING, SessionStatus.PENDING):
                session.status = SessionStatus.FAILED
                session.error_message = "Server restarted during processing — please resubmit."
                session.progress_message = "Pipeline interrupted by server restart"
            _sessions[str(session.id)] = session
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

def _mock_claims() -> list[Claim]:
    # Matches the PitchPilot demo pitch that drives the mock findings below.
    return [
        Claim(
            text="PitchPilot is fully private and never sends data to the cloud.",
            claim_type=ClaimType.PRIVACY,
            timestamp=154.0,
            source="transcript",
            confidence=0.93,
        ),
        Claim(
            text="Our workflow is fully automated — no manual review required.",
            claim_type=ClaimType.FEATURE,
            timestamp=251.0,
            source="both",
            confidence=0.91,
        ),
        Claim(
            text="We achieved a 3x close rate improvement across all pilot customers.",
            claim_type=ClaimType.METRIC,
            timestamp=320.0,
            source="transcript",
            confidence=0.85,
        ),
    ]


def _mock_findings(claims: list[Claim]) -> list[Finding]:
    # Kept in timestamp order to match the frontend MOCK_REPORT in mock-data.ts.
    return [
        Finding(
            agent=AgentType.COACH,
            severity=Severity.INFO,
            title="Strong problem statement — preserve this opening",
            detail=(
                'Your first 45 seconds are excellent. The "pitch rehearsal is a black box" '
                "hook is memorable and clearly frames the gap."
            ),
            timestamp=12.0,
        ),
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Solution slide overloaded with technical jargon",
            detail=(
                'Slide 3 uses "multi-agent orchestration," "LoRA fine-tuning," and '
                '"tokenized function dispatch" without explanation. Non-technical audiences will disengage.'
            ),
            suggestion='Lead with the outcome ("analyzes your pitch in 90 seconds") before explaining the mechanism.',
            timestamp=118.0,
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.CRITICAL,
            title='"Fully private" conflicts with policy §4.1',
            detail=(
                'At 2:34 you stated the product is "fully private and never sends data to the cloud." '
                "Policy §4.1 requires disclosure of optional cloud fallback mode."
            ),
            suggestion=(
                'Change to: "Private by default — all processing runs on-device. '
                'An optional cloud mode is available for users who opt in."'
            ),
            timestamp=154.0,
            claim_id=claims[0].id,
            policy_reference="Enterprise Data Policy §4.1",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.INFO,
            title='Technical Reviewer: On-device inference latency?',
            detail="Technical Reviewer wants specifics on inference latency for the 90-second claim.",
            suggestion='Have concrete benchmarks ready: "On an M2 MacBook Pro: 90s for a 5-minute video, 4.2s/frame OCR, real-time audio."',
            timestamp=198.0,
            persona="Technical Reviewer",
        ),
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Abrupt demo-to-business-model transition at 3:42",
            detail=(
                "The transition from the live demo to the business model is jarring. "
                "There is no bridging sentence, causing the audience to mentally context-switch without framing."
            ),
            suggestion="Add: \"What you just saw is the core product. Here's how we monetize it.\" before advancing the slide.",
            timestamp=222.0,
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.CRITICAL,
            title='"Fully automated" conflicts with policy §3.2',
            detail=(
                'At 4:11 you claimed the workflow is "fully automated." '
                "Policy §3.2 mandates that edge cases require manual human review."
            ),
            suggestion='Replace with: "Automated for 95% of standard cases; edge cases are flagged for manual review per our policy."',
            timestamp=251.0,
            claim_id=claims[1].id,
            policy_reference="Enterprise Data Policy §3.2",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title='Skeptical Investor: "Why not just use ChatGPT?"',
            detail=(
                "This question arose from generic AI differentiation framing on the traction slide. "
                "The on-device angle has not been emphasised strongly enough."
            ),
            suggestion='Prepare: "ChatGPT requires sending your pitch to the cloud. PitchPilot runs on-device with specialized models for each evaluation task."',
            timestamp=298.0,
            persona="Skeptical Investor",
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="ROI claim lacks supporting data",
            detail='At 5:20 you claimed "3x close rate improvement" without citing a source or pilot data.',
            suggestion='Add source: cite pilot customer or qualify as "hypothesis to be validated in pilot."',
            timestamp=320.0,
            claim_id=claims[2].id,
            policy_reference="See traction slide",
        ),
    ]


def _mock_persona_questions() -> list[PersonaQuestion]:
    return [
        PersonaQuestion(
            persona="Skeptical Investor",
            question="How is this meaningfully different from asking ChatGPT to review my pitch script?",
            follow_up=(
                "Three key differences: on-device privacy (no data leaves the machine), "
                "multimodal analysis (video + slides + audio, not just text), and specialized "
                "models fine-tuned for pitch evaluation rather than general conversation."
            ),
            timestamp=298.0,
            difficulty=Severity.CRITICAL,
        ),
        PersonaQuestion(
            persona="Skeptical Investor",
            question="What is your go-to-market strategy and why will enterprise sales teams adopt this?",
            follow_up=(
                "Focus on compliance-sensitive industries (fintech, healthcare) where "
                "on-device is a requirement, not a feature."
            ),
            difficulty=Severity.WARNING,
        ),
        PersonaQuestion(
            persona="Technical Reviewer",
            question="What is the actual end-to-end latency on consumer hardware? Have you measured it?",
            follow_up="M2 MacBook Pro: 87s for a 5-min video. M1: ~2min. Windows with CUDA: ~45s.",
            timestamp=198.0,
            difficulty=Severity.WARNING,
        ),
        PersonaQuestion(
            persona="Procurement Manager",
            question="What's the all-in cost over three years, and do you have a reference customer with measurable ROI?",
            follow_up=(
                "Annual per-seat SaaS with no implementation fee. Design partners report 18% lift "
                "in first-call conversion and 40% fewer manager coaching hours. Happy to connect "
                "you with two reference customers."
            ),
            difficulty=Severity.CRITICAL,
        ),
        PersonaQuestion(
            persona="Technical Reviewer",
            question="Why FunctionGemma for routing instead of a simpler classifier?",
            follow_up=(
                "FunctionGemma was designed specifically for function dispatch with structured output. "
                "A classifier would require separate handling of argument extraction."
            ),
            difficulty=Severity.INFO,
        ),
    ]


def _mock_report(session_id: str, claims: list[Claim], findings: list[Finding]) -> ReadinessReport:
    dimensions = [
        DimensionScore(
            dimension="Clarity",
            score=78,
            rationale="Clear problem statement; solution slides are dense with jargon.",
        ),
        DimensionScore(
            dimension="Compliance",
            score=61,
            rationale='Two claims directly conflict with policy doc. "Fully automated" and "fully private" need qualification.',
        ),
        DimensionScore(
            dimension="Defensibility",
            score=74,
            rationale="Investor persona questions are answerable but require better data. Technical objections are solid.",
        ),
        DimensionScore(
            dimension="Persuasiveness",
            score=81,
            rationale="Strong open and close. Demo transition at 3:42 is rough — tighten the segue.",
        ),
    ]
    score = ReadinessScore(
        overall=72,
        dimensions=dimensions,
        priority_fixes=[
            'Qualify the "fully private" claim on slide 4: add "by default" or "when configured with on-device mode".',
            'Replace "fully automated" with "automated for standard cases, with optional manual review for edge cases" to align with policy §3.2.',
            "Add a one-sentence bridge between the live demo and the business model slide (currently jumps too abruptly at 3:42).",
            'Prepare a crisp ≤30-second answer to "How is this different from just using ChatGPT?"',
        ],
    )
    return ReadinessReport(
        session_id=UUID(session_id),
        score=score,
        findings=findings,
        persona_questions=_mock_persona_questions(),
        claims=claims,
        summary=(
            "Your pitch has strong narrative momentum and clear problem framing. "
            "The main risks are an overreaching privacy claim on slide 4 and an abrupt transition "
            "from the demo to the business model. The skeptical investor persona surfaces the "
            "sharpest questions — prepare those answers before your next rehearsal."
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _mock_timeline(findings: list[Finding]) -> list[TimelineAnnotation]:
    category_map = {
        AgentType.COACH: TimelineCategory.COACH,
        AgentType.COMPLIANCE: TimelineCategory.COMPLIANCE,
        AgentType.PERSONA: TimelineCategory.PERSONA,
    }
    annotations = [
        TimelineAnnotation(
            finding_id=f.id,
            category=category_map[f.agent],
            timestamp=f.timestamp,
            label=f.title[:60],
            severity=f.severity,
        )
        for f in findings
    ]
    annotations.sort(key=lambda a: a.timestamp)
    return annotations


# ---------------------------------------------------------------------------
# Background mock pipeline (simulates progressive processing)
# ---------------------------------------------------------------------------

async def _run_mock_pipeline(session_id: str) -> None:
    """
    Simulates pipeline stages with realistic delays.
    Replace this with real pipeline calls by importing:
        from backend.agents.orchestrator import Orchestrator
    """
    session = _sessions[session_id]
    stages = [
        (10, "Extracting video frames"),
        (25, "Running OCR on slides"),
        (40, "Transcribing audio"),
        (55, "Extracting claims"),
        (70, "Running Coach agent"),
        (82, "Running Compliance agent"),
        (92, "Running Persona agent"),
        (100, "Aggregating readiness report"),
    ]
    session.status = SessionStatus.PROCESSING
    for progress, message in stages:
        await asyncio.sleep(1.5)
        session.progress = progress
        session.progress_message = message

    claims = _mock_claims()
    findings = _mock_findings(claims)
    session.report = _mock_report(session_id, claims, findings)
    session.timeline = _mock_timeline(findings)
    session.status = SessionStatus.COMPLETE
    session.progress = 100
    session.progress_message = "Analysis complete"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post(
    "/api/session/start",
    response_model=SessionStartResponse,
    summary="Upload a rehearsal video and start analysis",
    tags=["session"],
)
async def start_session(
    video: UploadFile = File(..., description="Rehearsal video (mp4, mov, webm)"),
    policy_docs: list[UploadFile] = File(default=[], description="Optional policy PDFs"),
    presentation_materials: list[UploadFile] = File(
        default=[], description="Optional presentation materials (slides, script, speaker notes)"
    ),
    personas: str = Form(
        default="Skeptical Investor,Technical Reviewer,Procurement Manager",
        description="Comma-separated audience personas",
    ),
    enabled_agents: str = Form(
        default="coach,compliance,persona",
        description="Comma-separated agent names to run (coach, compliance, persona)",
    ),
) -> SessionStartResponse:
    """
    Create a new analysis session and kick off the pipeline.
    Poll /api/session/{id}/status for progress.
    """
    from backend.config import settings as _settings  # noqa: PLC0415

    session_id = str(uuid4())
    persona_list = [p.strip() for p in personas.split(",") if p.strip()]
    agent_list = [a.strip() for a in enabled_agents.split(",") if a.strip()]

    session = Session(
        id=UUID(session_id),
        video_filename=video.filename or "upload.mp4",
        policy_filenames=[f.filename or "" for f in policy_docs],
        presentation_filenames=[f.filename or "" for f in presentation_materials],
        personas=persona_list,
        enabled_agents=agent_list,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _sessions[session_id] = session
    _persist_session(session)

    if _settings.mock_mode:
        asyncio.create_task(_run_mock_pipeline(session_id))
    else:
        # Read uploads into memory then hand off to background task
        video_bytes = await video.read()
        doc_bytes = [(f.filename or "doc.pdf", await f.read()) for f in policy_docs]
        material_bytes = [(f.filename or "material.pdf", await f.read()) for f in presentation_materials]
        asyncio.create_task(
            _run_real_pipeline(session_id, video_bytes, video.filename or "upload.mp4", doc_bytes, material_bytes)
        )

    return SessionStartResponse(
        session_id=UUID(session_id),
        status=SessionStatus.PENDING,
        message="Session created — analysis started",
    )


@app.post(
    "/api/session/demo",
    response_model=SessionStartResponse,
    summary="Start an instant demo session (no file upload required)",
    tags=["session"],
)
async def start_demo_session(
    personas: Optional[str] = None,
) -> SessionStartResponse:
    """
    Creates a demo session immediately populated with mock results.
    Useful for demos — no video upload needed.
    """
    session_id = str(uuid4())
    persona_list = (
        [p.strip() for p in personas.split(",") if p.strip()]
        if personas
        else ["Skeptical Investor", "Technical Reviewer", "Procurement Manager"]
    )

    session = Session(
        id=UUID(session_id),
        video_filename="demo_pitch.mp4",
        policy_filenames=["enterprise_data_policy.pdf", "approved_messaging_guide.pdf"],
        personas=persona_list,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _sessions[session_id] = session
    _persist_session(session)
    asyncio.create_task(_run_mock_pipeline(session_id))

    return SessionStartResponse(
        session_id=UUID(session_id),
        status=SessionStatus.PENDING,
        message="Demo session started",
    )


async def _run_real_pipeline(
    session_id: str,
    video_bytes: bytes,
    video_filename: str,
    doc_files: list[tuple[str, bytes]],
    material_files: list[tuple[str, bytes]] | None = None,
) -> None:
    """
    Background task that runs the real ingestion + orchestrator pipeline.

    Updates session.progress and session.progress_message at each stage so
    the frontend polling sees live milestones.
    """
    import traceback  # noqa: PLC0415
    import logging  # noqa: PLC0415

    from backend.agents.orchestrator import Orchestrator  # noqa: PLC0415
    from backend.ingestion import IngestionPipeline  # noqa: PLC0415
    from backend.reports.readiness import ReadinessReportGenerator  # noqa: PLC0415
    from backend.schemas import (  # noqa: PLC0415
        Claim as SchemaClaim,
        PipelineContext,
        SlideOCR,
        TranscriptSegment as SchemaTranscriptSegment,
    )

    _log = logging.getLogger(__name__)
    session = _sessions.get(session_id)
    if session is None:
        return

    session.status = SessionStatus.PROCESSING
    _persist_session(session)

    def _update(pct: int, message: str) -> None:
        s = _sessions.get(session_id)
        if s:
            s.progress = pct
            s.progress_message = message
            _persist_session(s)

    try:
        # Save policy docs and presentation materials to temp files
        doc_paths: list[str] = []
        tmp_dir = tempfile.mkdtemp(prefix=f"pitchpilot_{session_id[:8]}_")
        for fname, fbytes in doc_files:
            p = Path(tmp_dir) / fname
            p.write_bytes(fbytes)
            doc_paths.append(str(p))
        # Presentation materials are stored alongside policy docs so the
        # ingestion pipeline can extract text from slides/scripts.
        for fname, fbytes in (material_files or []):
            p = Path(tmp_dir) / fname
            p.write_bytes(fbytes)
            doc_paths.append(str(p))

        # Stage 1-5: ingestion
        pipeline = IngestionPipeline()
        ingestion_result = await pipeline.run_from_bytes(
            video_bytes=video_bytes,
            filename=video_filename,
            policy_doc_paths=doc_paths,
            session_id=session_id,
            progress_callback=_update,
        )

        _update(88, "Running agent analysis (6/7)")

        # Stage 6: orchestrator — convert data_models types to schemas types
        # PipelineContext uses schemas dataclasses; ingestion returns data_models Pydantic models

        schema_segments = [
            SchemaTranscriptSegment(
                text=seg.text,
                start_time=seg.start_time,
                end_time=seg.end_time,
                confidence=seg.confidence,
            )
            for seg in ingestion_result.transcript_segments
        ]

        schema_slide_ocr = [
            SlideOCR(
                slide_index=i,
                timestamp=block.timestamp or 0.0,
                raw_text=block.text,
            )
            for i, block in enumerate(ingestion_result.ocr_blocks)
            if block.source_type.value == "video_frame"
        ]

        schema_claims = [
            SchemaClaim(
                id=str(c.claim_id),
                text=c.text,
                claim_type="general",
                timestamp=c.timestamp_start,
                source=c.source.value if hasattr(c.source, "value") else str(c.source),
                context_before="",
                context_after="",
            )
            for c in ingestion_result.claims
        ]

        # Policy text: OCR text from non-video (uploaded document) blocks
        policy_text = "\n".join(
            b.text for b in ingestion_result.ocr_blocks
            if b.source_type.value != "video_frame"
        )

        context = PipelineContext(
            session_id=session_id,
            claims=schema_claims,
            transcript_segments=schema_segments,
            slide_ocr=schema_slide_ocr,
            policy_text=policy_text,
            personas=session.personas,
            enabled_agents=session.enabled_agents,
        )

        orchestrator = Orchestrator()
        await orchestrator.initialize()
        orch_result = await orchestrator.run(context, progress_callback=_update)

        _update(98, "Generating readiness report (7/7)")

        # Stage 7: report — signature is generate(result, context)
        report_gen = ReadinessReportGenerator()
        report = report_gen.generate(result=orch_result, context=context)

        # Map internal report to API schema
        session.report = _map_report(session_id, report, ingestion_result)
        session.timeline = _map_timeline(orch_result.timeline)
        session.status = SessionStatus.COMPLETE
        session.progress = 100
        session.progress_message = "Analysis complete"
        _persist_session(session)

    except Exception as exc:
        tb = traceback.format_exc()
        session.status = SessionStatus.FAILED
        session.error_message = str(exc)
        session.progress_message = f"Pipeline error: {exc}"
        _persist_session(session)
        _log.error(f"Real pipeline failed for session {session_id}: {exc}\n{tb}")


@app.get(
    "/api/session/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Poll processing progress",
    tags=["session"],
)
async def get_status(session_id: str) -> SessionStatusResponse:
    """Returns current state and progress %.  Poll every 2-3 s."""
    session = _get_or_404(session_id)
    return SessionStatusResponse(
        session_id=session.id,
        status=session.status,
        progress=session.progress,
        progress_message=session.progress_message,
        error_message=session.error_message,
    )


@app.get(
    "/api/session/{session_id}/report",
    response_model=ReadinessReport,
    summary="Retrieve full readiness report",
    tags=["session"],
)
async def get_report(session_id: str) -> ReadinessReport:
    """Returns the complete report.  Returns 202 while still processing."""
    session = _get_or_404(session_id)
    _assert_complete(session)
    return session.report  # type: ignore[return-value]


@app.get(
    "/api/session/{session_id}/timeline",
    response_model=TimelineResponse,
    summary="Retrieve annotated timeline markers",
    tags=["session"],
)
async def get_timeline(session_id: str) -> TimelineResponse:
    """Returns chronologically sorted timeline annotations."""
    session = _get_or_404(session_id)
    _assert_complete(session)
    return TimelineResponse(session_id=session.id, annotations=session.timeline)


@app.get(
    "/api/session/{session_id}/findings",
    response_model=FindingsResponse,
    summary="Retrieve agent findings and persona questions",
    tags=["session"],
)
async def get_findings(session_id: str) -> FindingsResponse:
    """Returns all agent findings + persona questions.  Filter by agent client-side."""
    session = _get_or_404(session_id)
    _assert_complete(session)
    report = session.report
    return FindingsResponse(
        session_id=session.id,
        findings=report.findings,       # type: ignore[union-attr]
        persona_questions=report.persona_questions,  # type: ignore[union-attr]
    )


@app.post(
    "/api/session/start-live",
    response_model=LiveSessionStartResponse,
    summary="Pre-register a live session and get a WebSocket URL",
    tags=["session"],
)
async def start_live_session(body: LiveSessionStartRequest) -> LiveSessionStartResponse:
    """
    Register a pending live session before opening the WebSocket.

    Clients can use the returned `ws_url` to connect to the WS endpoint and
    send the `init` message.  The session is already stored in the in-memory
    store so REST polling endpoints work immediately.

    Supported modes: live_in_room, live_remote, live (legacy).
    """
    session_id = str(uuid4())

    session = Session(
        id=UUID(session_id),
        video_filename="live_session.webm",
        policy_filenames=[],
        personas=body.personas,
        enabled_agents=body.enabled_agents,
        mode=body.mode,
        status=SessionStatus.PENDING,
        progress=0,
        progress_message="Awaiting WebSocket connection",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _sessions[session_id] = session

    # Build the WS URL relative to the server.  In production this should be
    # constructed from a base URL config; for the hackathon we derive it from
    # the request origin via a hardcoded default.
    ws_url = f"ws://localhost:8000/api/session/live"

    return LiveSessionStartResponse(
        session_id=UUID(session_id),
        ws_url=ws_url,
        mode=body.mode,
        status=SessionStatus.PENDING,
        message=f"Session pre-registered for {body.mode.value} mode. Connect to ws_url.",
    )


@app.websocket("/api/session/live")
async def live_session_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for Livestream Mode (Real-Time Copilot).

    See backend/live_ws.py for the full protocol documentation.
    Supports modes: live (legacy), live_in_room, live_remote.
    """
    from backend.live_ws import live_session_ws  # noqa: PLC0415
    await live_session_ws(websocket, _sessions)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/readiness", tags=["meta"])
async def pipeline_readiness() -> dict:
    """
    Startup diagnostic: reports whether the real pipeline is reachable.

    Returns a dict with:
      - mock_mode: bool — whether PITCHPILOT_MOCK_MODE is true
      - ollama_available: bool — whether Ollama is reachable (only checked in real mode)
      - ollama_url: str
    """
    from backend.config import settings as _s  # noqa: PLC0415

    result: dict = {
        "mock_mode": _s.mock_mode,
        "ollama_url": _s.ollama_base_url,
        "ollama_available": None,
    }

    if not _s.mock_mode:
        try:
            from backend.models.gemma3 import Gemma3Adapter  # noqa: PLC0415
            adapter = Gemma3Adapter()
            result["ollama_available"] = await adapter.is_available()
        except Exception as exc:
            result["ollama_available"] = False
            result["ollama_error"] = str(exc)

    return result


@app.on_event("startup")
async def _startup() -> None:
    """Log current pipeline mode on startup and restore persisted sessions."""
    import logging  # noqa: PLC0415
    from backend.config import settings as _s  # noqa: PLC0415

    log = logging.getLogger(__name__)
    _load_persisted_sessions()
    restored = len(_sessions)
    if restored:
        log.info(f"PitchPilot: restored {restored} session(s) from disk")

    if _s.mock_mode:
        log.info("PitchPilot starting in MOCK mode — no Ollama required")
    else:
        log.info(
            f"PitchPilot starting in REAL mode — Ollama at {_s.ollama_base_url}. "
            "Ensure models are loaded: `ollama pull gemma3:4b && ollama pull gemma-3n:e4b`"
        )


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Close the shared Ollama HTTP client on server shutdown."""
    from backend.models.ollama_client import close_ollama_client  # noqa: PLC0415
    await close_ollama_client()


# ---------------------------------------------------------------------------
# Real pipeline helpers: map internal schemas -> API schemas
# ---------------------------------------------------------------------------


def _map_report(session_id: str, internal_report, ingestion_result) -> ReadinessReport:
    """
    Map an internal schemas.ReadinessReport to the API-level api_schemas.ReadinessReport.

    schemas.ReadinessReport (dataclass) has:
      overall_score, grade, dimensions (dict[str, DimensionScore]),
      findings (list[Finding]), stakeholder_questions, priority_fixes, summary

    api_schemas.ReadinessReport (Pydantic) has:
      score (ReadinessScore with .overall, .dimensions list, .priority_fixes),
      findings, persona_questions, claims, summary
    """
    from backend.api_schemas import (  # noqa: PLC0415
        Claim as ApiClaim,
        ClaimType,
        DimensionScore as ApiDimScore,
        Finding as ApiFinding,
        PersonaQuestion as ApiPQ,
        ReadinessScore,
        Severity,
        AgentType,
    )

    severity_safe = {
        "info": Severity.INFO,
        "warning": Severity.WARNING,
        "critical": Severity.CRITICAL,
    }
    agent_safe = {
        "coach": AgentType.COACH,
        "compliance": AgentType.COMPLIANCE,
        "persona": AgentType.PERSONA,
    }

    # Convert findings: schemas.Finding.description → api.Finding.detail
    api_findings: list[ApiFinding] = []
    for f in getattr(internal_report, "findings", []):
        raw_severity = getattr(f, "severity", "info")
        raw_agent = getattr(f, "agent", "coach")
        api_findings.append(
            ApiFinding(
                agent=agent_safe.get(raw_agent, AgentType.COACH),
                severity=severity_safe.get(raw_severity, Severity.INFO),
                title=getattr(f, "title", "Finding"),
                # schemas.Finding uses .description; api_schemas.Finding uses .detail
                detail=getattr(f, "description", getattr(f, "detail", "")),
                suggestion=getattr(f, "suggestion", None),
                timestamp=getattr(f, "timestamp", 0.0) or 0.0,
                claim_id=getattr(f, "claim_ref", None),
                policy_reference=getattr(f, "metadata", {}).get("policy_reference") if hasattr(f, "metadata") else None,
                persona=getattr(f, "metadata", {}).get("persona") if hasattr(f, "metadata") else None,
            )
        )

    # Convert stakeholder questions from persona agent findings
    api_pqs: list[ApiPQ] = []
    for pq in getattr(internal_report, "stakeholder_questions", []):
        raw_diff = getattr(pq, "difficulty", "medium")
        diff_map = {"easy": Severity.INFO, "medium": Severity.WARNING, "hard": Severity.CRITICAL}
        api_pqs.append(
            ApiPQ(
                persona=getattr(pq, "persona", "Unknown"),
                question=getattr(pq, "question", ""),
                difficulty=diff_map.get(raw_diff, Severity.WARNING),
                timestamp=getattr(pq, "timestamp", None),
            )
        )

    # Convert data_models.Claim list from ingestion result
    api_claims: list[ApiClaim] = []
    claim_type_map = {
        "compliance_sensitive": ClaimType.PRIVACY,
        "comparison_claim": ClaimType.COMPARISON,
        "technical_claim": ClaimType.FEATURE,
        "value_proposition": ClaimType.FEATURE,
        "automation_claim": ClaimType.FEATURE,
        "privacy_claim": ClaimType.PRIVACY,
        "accuracy_claim": ClaimType.METRIC,
        "financial_claim": ClaimType.METRIC,
    }
    for c in ingestion_result.claims[:20]:
        raw_cat = getattr(c, "category", None)
        cat_val = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat or "")
        api_claims.append(
            ApiClaim(
                text=c.text,
                claim_type=claim_type_map.get(cat_val, ClaimType.FEATURE),
                timestamp=c.timestamp_start,
                source=c.source.value if hasattr(c.source, "value") else str(c.source),
                confidence=c.confidence,
            )
        )

    # Build dimension list from schemas.ReadinessReport.dimensions dict
    raw_dims = getattr(internal_report, "dimensions", {})
    api_dimensions: list[ApiDimScore] = []
    if isinstance(raw_dims, dict):
        for name, ds in raw_dims.items():
            api_dimensions.append(
                ApiDimScore(
                    dimension=name.capitalize(),
                    score=getattr(ds, "score", 75),
                    rationale=getattr(ds, "summary", ""),
                )
            )
    elif isinstance(raw_dims, list):
        for ds in raw_dims:
            api_dimensions.append(
                ApiDimScore(
                    dimension=getattr(ds, "dimension", getattr(ds, "name", "Clarity")),
                    score=getattr(ds, "score", 75),
                    rationale=getattr(ds, "rationale", getattr(ds, "summary", "")),
                )
            )

    overall = getattr(internal_report, "overall_score", None) or 75
    priority_fixes = getattr(internal_report, "priority_fixes", [])

    return ReadinessReport(
        session_id=UUID(session_id),
        score=ReadinessScore(
            overall=overall,
            dimensions=api_dimensions,
            priority_fixes=priority_fixes,
        ),
        findings=api_findings,
        persona_questions=api_pqs,
        claims=api_claims,
        summary=getattr(internal_report, "summary", "Analysis complete."),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _map_timeline(internal_timeline) -> list[TimelineAnnotation]:
    """Map internal TimelineAnnotation objects to API TimelineAnnotation."""
    annotations: list[TimelineAnnotation] = []
    for t in internal_timeline:
        try:
            annotations.append(
                TimelineAnnotation(
                    timestamp=t.timestamp,
                    category=TimelineCategory(getattr(t, "category", "coach")),
                    label=getattr(t, "label", ""),
                    finding_id=str(getattr(t, "finding_id", "")),
                    color=getattr(t, "color", "blue"),
                )
            )
        except Exception:
            pass
    return annotations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(session_id: str) -> Session:
    s = _sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return s


def _assert_complete(session: Session) -> None:
    if session.status in (SessionStatus.PENDING, SessionStatus.PROCESSING):
        raise HTTPException(
            status_code=202,
            detail=f"Still processing ({session.progress}% — {session.progress_message})",
        )
    if session.status == SessionStatus.FAILED:
        raise HTTPException(status_code=500, detail=f"Session failed: {session.error_message}")

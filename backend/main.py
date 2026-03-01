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
    return [
        Claim(
            text="Our platform is fully automated — no manual review required.",
            claim_type=ClaimType.FEATURE,
            timestamp=34.5,
            source="transcript",
            confidence=0.93,
        ),
        Claim(
            text="We achieve 99.9% uptime across all enterprise tiers.",
            claim_type=ClaimType.METRIC,
            timestamp=72.0,
            source="slide",
            slide_number=4,
            confidence=0.88,
        ),
        Claim(
            text="All customer data is stored exclusively on-device — nothing leaves your network.",
            claim_type=ClaimType.PRIVACY,
            timestamp=112.0,
            source="both",
            slide_number=6,
            confidence=0.91,
        ),
        Claim(
            text="We outperform every competitor by 3× on inference speed.",
            claim_type=ClaimType.COMPARISON,
            timestamp=155.0,
            source="transcript",
            confidence=0.80,
        ),
    ]


def _mock_findings(claims: list[Claim]) -> list[Finding]:
    claim_automated = claims[0]
    claim_uptime = claims[1]
    claim_privacy = claims[2]
    claim_speed = claims[3]

    return [
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Abrupt transition after problem statement",
            detail=(
                "The transition from the problem slide to the demo felt rushed. "
                "There was no bridge sentence to orient the audience before the "
                "product walkthrough began."
            ),
            suggestion="Add a one-sentence recap: 'That's the problem — here's how PitchPilot solves it.'",
            timestamp=28.0,
        ),
        Finding(
            agent=AgentType.COACH,
            severity=Severity.INFO,
            title="Strong opening hook",
            detail="The opening anecdote about a failed product demo was vivid and relatable. It established stakes immediately.",
            timestamp=5.0,
        ),
        Finding(
            agent=AgentType.COACH,
            severity=Severity.CRITICAL,
            title="Speed metric lacks benchmark context",
            detail=(
                "'3× faster' is compelling but the baseline is never stated. "
                "Sophisticated audiences will dismiss unanchored comparisons."
            ),
            suggestion="Name the competitor and link to a reproducible benchmark.",
            timestamp=155.0,
            claim_id=claim_speed.id,
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.CRITICAL,
            title="'Fully automated' conflicts with policy §3.2",
            detail=(
                "Your enterprise data-handling policy (section 3.2) requires human review "
                "for model outputs above a confidence threshold of 0.95. "
                "Claiming 'fully automated — no manual review required' directly contradicts this."
            ),
            suggestion="Rephrase to: 'Automated with optional human-in-the-loop review for high-stakes decisions.'",
            timestamp=34.5,
            claim_id=claim_automated.id,
            policy_reference="Enterprise Data Policy §3.2 — Human Oversight Requirement",
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="99.9% uptime SLA not in standard contract",
            detail=(
                "The standard enterprise contract offers 99.5% SLA. "
                "Promising 99.9% creates a potential contractual liability."
            ),
            suggestion="Reference the premium-tier SLA or say 'up to 99.9%' with a footnote.",
            timestamp=72.0,
            claim_id=claim_uptime.id,
            policy_reference="SLA Addendum v2 — Enterprise Standard Tier",
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="'Nothing leaves your network' needs qualification",
            detail=(
                "Architecture slide 8 shows an optional cloud-sync feature. "
                "The blanket privacy claim may be technically false for customers who enable it."
            ),
            suggestion="Add 'by default' and mention the opt-in cloud sync explicitly.",
            timestamp=112.0,
            claim_id=claim_privacy.id,
            policy_reference="Privacy Disclosure Policy §1.1 — Accurate Representation",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Skeptical Investor: differentiation is unclear",
            detail=(
                "A skeptical investor would immediately ask how this differs from a "
                "well-prompted ChatGPT plus screen recording. The on-device angle is "
                "the key differentiator but it was mentioned only once, in passing."
            ),
            suggestion="Lead with the on-device / privacy differentiator earlier and repeat at close.",
            timestamp=90.0,
            persona="Skeptical Investor",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.INFO,
            title="Technical Reviewer: model card details appreciated",
            detail="The Technical Reviewer persona found the mention of specific model names (Gemma 3n, FunctionGemma) credible and reassuring.",
            timestamp=130.0,
            persona="Technical Reviewer",
        ),
    ]


def _mock_persona_questions() -> list[PersonaQuestion]:
    return [
        PersonaQuestion(
            persona="Skeptical Investor",
            question="How is this different from asking ChatGPT to review my slide deck?",
            follow_up="And if the answer is 'on-device', why can't a compliance-aware wrapper around GPT-4o do the same thing?",
            timestamp=90.0,
            difficulty=Severity.CRITICAL,
        ),
        PersonaQuestion(
            persona="Skeptical Investor",
            question="What does '3× faster' mean, and is there a published benchmark?",
            timestamp=155.0,
            difficulty=Severity.WARNING,
        ),
        PersonaQuestion(
            persona="Procurement Manager",
            question="What's the all-in cost over three years, including implementation and training?",
            timestamp=112.0,
            difficulty=Severity.CRITICAL,
        ),
        PersonaQuestion(
            persona="Procurement Manager",
            question="How does this integrate with our existing CRM and sales enablement stack?",
            difficulty=Severity.WARNING,
        ),
        PersonaQuestion(
            persona="Technical Reviewer",
            question="What happens when Gemma 3n hallucinates during OCR — is there a confidence threshold?",
            timestamp=50.0,
            difficulty=Severity.WARNING,
        ),
    ]


def _mock_report(session_id: str, claims: list[Claim], findings: list[Finding]) -> ReadinessReport:
    dimensions = [
        DimensionScore(dimension="Clarity", score=78, rationale="Structure and flow are solid but two transitions need bridging."),
        DimensionScore(dimension="Compliance", score=61, rationale="Two critical policy conflicts found; addressable with rewording."),
        DimensionScore(dimension="Defensibility", score=68, rationale="Speed and uptime claims need benchmark citations."),
        DimensionScore(dimension="Persuasiveness", score=82, rationale="Opening hook and model specificity are strong trust signals."),
    ]
    overall = round(sum(d.score for d in dimensions) / len(dimensions))
    score = ReadinessScore(
        overall=overall,
        dimensions=dimensions,
        priority_fixes=[
            "Fix the 'fully automated' claim — it directly contradicts Enterprise Data Policy §3.2.",
            "Anchor the '3× faster' metric to a named competitor and public benchmark.",
            "Qualify the privacy claim: add 'by default' to cover the opt-in cloud sync.",
            "Add a bridge sentence between the problem slide and the demo.",
        ],
    )
    return ReadinessReport(
        session_id=UUID(session_id),
        score=score,
        findings=findings,
        persona_questions=_mock_persona_questions(),
        claims=claims,
        summary=(
            "Overall readiness is 72/100. The pitch has a strong hook and credible technical "
            "specificity, but two compliance conflicts need resolution before presenting to "
            "an enterprise buyer. The privacy and automation claims are the highest-risk items. "
            "Prepare for the ChatGPT differentiation question — it will come from every audience."
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

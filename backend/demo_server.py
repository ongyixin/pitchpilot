"""
PitchPilot Demo Server — always-on mock backend for hackathon demos.

This server accepts the same API as the real backend but uses deterministic
mock data so you can demo the full frontend flow without Ollama or any models.

Run with:
    uvicorn backend.demo_server:app --reload --port 8000

Environment:
    PITCHPILOT_DEMO_DELAY=0   # set to 0 to skip pipeline animation
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.api_schemas import (
    AgentType,
    Claim,
    ClaimType,
    DimensionScore,
    Finding,
    FindingsResponse,
    PersonaQuestion,
    ReadinessReport,
    ReadinessScore,
    Session,
    SessionStartResponse,
    SessionStatus,
    SessionStatusResponse,
    Severity,
    TimelineAnnotation,
    TimelineCategory,
    TimelineResponse,
)

app = FastAPI(
    title="PitchPilot Demo API",
    description="Mock backend — returns realistic demo data without model inference",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_sessions: dict[UUID, Session] = {}

# Demo delay between pipeline stages (seconds); 0 = instant results
_STAGE_DELAY: float = float(os.getenv("PITCHPILOT_DEMO_DELAY", "1.5"))


# ---------------------------------------------------------------------------
# Demo fixture data
# ---------------------------------------------------------------------------


def _demo_claims() -> list[Claim]:
    return [
        Claim(
            text="Our platform is fully automated — no manual review required.",
            claim_type=ClaimType.FEATURE,
            timestamp=34.5,
            source="transcript",
            confidence=0.93,
        ),
        Claim(
            text="We achieve 99.9 % uptime across all enterprise tiers.",
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


def _demo_findings(claims: list[Claim]) -> list[Finding]:
    claim_automated = claims[0]
    claim_uptime = claims[1]
    claim_privacy = claims[2]
    claim_speed = claims[3]

    return [
        # Coach findings
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
            suggestion=None,
            timestamp=5.0,
        ),
        Finding(
            agent=AgentType.COACH,
            severity=Severity.CRITICAL,
            title="Speed metric lacks benchmark context",
            detail=(
                "'3× faster' is a compelling claim but the baseline is never stated. "
                "Sophisticated audiences will dismiss unanchored comparisons."
            ),
            suggestion="Name the competitor and link to a reproducible benchmark. E.g. 'vs. GPT-4o on the MLPerf inference suite'.",
            timestamp=155.0,
            claim_id=claim_speed.id,
        ),
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Solution slide overloaded with jargon",
            detail=(
                "Slide 3 uses 'multi-agent orchestration', 'LoRA fine-tuning', and "
                "'tokenised function dispatch' without explanation. Non-technical audiences disengage."
            ),
            suggestion="Lead with the outcome ('analyzes your pitch in 90 seconds') before explaining the mechanism.",
            timestamp=118.0,
        ),
        # Compliance findings
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
            title="99.9 % uptime SLA not reflected in current contract",
            detail=(
                "The standard enterprise contract offers 99.5 % SLA. "
                "Promising 99.9 % during a pitch creates a potential contractual liability."
            ),
            suggestion="Either reference the premium-tier SLA or say 'up to 99.9 %' with a footnote.",
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
        # Persona findings
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Skeptical Investor: differentiation is unclear",
            detail=(
                "After hearing the pitch, a skeptical investor would immediately ask "
                "how this differs from a well-prompted ChatGPT plus screen recording. "
                "The on-device angle is the key differentiator but it was mentioned only once, in passing."
            ),
            suggestion="Lead with the on-device / privacy differentiator earlier and repeat it at close.",
            timestamp=90.0,
            persona="Skeptical Investor",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.INFO,
            title="Technical Reviewer: model card details appreciated",
            detail=(
                "The Technical Reviewer persona found the mention of specific model names "
                "(Gemma 3n, FunctionGemma) credible and reassuring."
            ),
            timestamp=130.0,
            persona="Technical Reviewer",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Compliance Officer: data retention policy missing",
            detail=(
                "No mention of how long rehearsal recordings are retained locally. "
                "A Compliance Officer would flag this immediately in regulated industries."
            ),
            suggestion="Add one slide or bullet on local-only storage, auto-deletion policy, and no cloud upload.",
            timestamp=175.0,
            persona="Compliance Officer",
        ),
    ]


def _demo_persona_questions() -> list[PersonaQuestion]:
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
            persona="Compliance Officer",
            question="Your slides say 'no data leaves the device' but slide 8 shows a cloud sync icon — can you clarify?",
            timestamp=112.0,
            difficulty=Severity.CRITICAL,
        ),
        PersonaQuestion(
            persona="Compliance Officer",
            question="Has your automated decision pipeline been reviewed against GDPR Article 22?",
            difficulty=Severity.WARNING,
        ),
        PersonaQuestion(
            persona="Technical Reviewer",
            question="What happens when Gemma 3n hallucinates during OCR — is there a confidence threshold?",
            timestamp=50.0,
            difficulty=Severity.WARNING,
        ),
    ]


def _demo_report(session_id: UUID, claims: list[Claim], findings: list[Finding]) -> ReadinessReport:
    dimensions = [
        DimensionScore(
            dimension="Clarity",
            score=78,
            rationale="Structure and flow are solid but two transitions need bridging.",
        ),
        DimensionScore(
            dimension="Compliance",
            score=61,
            rationale="Two critical policy conflicts found; addressable with rewording.",
        ),
        DimensionScore(
            dimension="Defensibility",
            score=68,
            rationale="Speed and uptime claims need benchmark citations.",
        ),
        DimensionScore(
            dimension="Persuasiveness",
            score=82,
            rationale="Opening hook and model specificity are strong trust signals.",
        ),
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
        session_id=session_id,
        score=score,
        findings=findings,
        persona_questions=_demo_persona_questions(),
        claims=claims,
        summary=(
            "Overall readiness is 72/100. The pitch has a strong hook and credible technical "
            "specificity, but two compliance conflicts need resolution before presenting to "
            "an enterprise buyer. The privacy and automation claims are the highest-risk items. "
            "Prepare for the ChatGPT differentiation question — it will come from every audience."
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _demo_timeline(findings: list[Finding]) -> list[TimelineAnnotation]:
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
# Mock pipeline background task
# ---------------------------------------------------------------------------


async def _run_mock_pipeline(session_id: UUID) -> None:
    """Simulates progressive pipeline stages so the frontend can poll /status."""
    session = _sessions[session_id]
    stages = [
        (10, "Extracting video frames at 1 fps…"),
        (22, "Running OCR on slide frames…"),
        (38, "Transcribing audio via Gemma 3n…"),
        (52, "Extracting claims from transcript…"),
        (65, "FunctionGemma routing claims to agents…"),
        (75, "Presentation Coach analysing narrative flow…"),
        (84, "Compliance Reviewer cross-checking policy…"),
        (92, "Persona Simulator generating stakeholder questions…"),
        (97, "Aggregating readiness score…"),
        (100, "Analysis complete"),
    ]
    session.status = SessionStatus.PROCESSING
    for progress, message in stages:
        await asyncio.sleep(_STAGE_DELAY)
        session.progress = progress
        session.progress_message = message

    claims = _demo_claims()
    findings = _demo_findings(claims)
    session.report = _demo_report(session_id, claims, findings)
    session.timeline = _demo_timeline(findings)
    session.status = SessionStatus.COMPLETE


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
    video: UploadFile = File(..., description="Rehearsal video (mp4/mov/webm)"),
    policy_docs: list[UploadFile] = File(default=[], description="Optional compliance PDFs"),
    personas: str = Form(
        default="Skeptical Investor,Technical Reviewer,Compliance Officer",
        description="Comma-separated persona names",
    ),
) -> SessionStartResponse:
    """
    Create a new analysis session.  Accepts a video upload and kicks off the
    mock pipeline asynchronously.  Poll /status until status == 'complete'.
    """
    session_id = uuid4()
    persona_list = [p.strip() for p in personas.split(",") if p.strip()]

    session = Session(
        id=session_id,
        video_filename=video.filename or "upload.mp4",
        policy_filenames=[f.filename or "" for f in policy_docs],
        personas=persona_list,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _sessions[session_id] = session
    asyncio.create_task(_run_mock_pipeline(session_id))

    return SessionStartResponse(
        session_id=session_id,
        status=SessionStatus.PENDING,
        message="Session created — analysis started",
    )


@app.post(
    "/api/session/demo",
    response_model=SessionStartResponse,
    summary="Start an instant demo session (no file upload required)",
    tags=["demo"],
)
async def start_demo_session(
    personas: Optional[str] = None,
) -> SessionStartResponse:
    """
    Creates a demo session and immediately populates it with mock results.
    Useful for hackathon demos — no video upload needed.
    Set PITCHPILOT_DEMO_DELAY=0 to skip all stage delays.
    """
    session_id = uuid4()
    persona_list = (
        [p.strip() for p in personas.split(",") if p.strip()]
        if personas
        else ["Skeptical Investor", "Technical Reviewer", "Compliance Officer"]
    )

    session = Session(
        id=session_id,
        video_filename="demo_pitch.mp4",
        policy_filenames=["enterprise_data_policy.pdf", "approved_messaging_guide.pdf"],
        personas=persona_list,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _sessions[session_id] = session
    asyncio.create_task(_run_mock_pipeline(session_id))

    return SessionStartResponse(
        session_id=session_id,
        status=SessionStatus.PENDING,
        message="Demo session started",
    )


@app.get(
    "/api/session/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Poll processing progress",
    tags=["session"],
)
async def get_status(session_id: UUID) -> SessionStatusResponse:
    session = _get_session_or_404(session_id)
    return SessionStatusResponse(
        session_id=session_id,
        status=session.status,
        progress=session.progress,
        progress_message=session.progress_message,
        error_message=session.error_message,
    )


@app.get(
    "/api/session/{session_id}/report",
    response_model=ReadinessReport,
    summary="Full readiness report",
    tags=["session"],
)
async def get_report(session_id: UUID) -> ReadinessReport:
    session = _get_session_or_404(session_id)
    _assert_complete(session)
    return session.report  # type: ignore[return-value]


@app.get(
    "/api/session/{session_id}/timeline",
    response_model=TimelineResponse,
    summary="Annotated timeline markers",
    tags=["session"],
)
async def get_timeline(session_id: UUID) -> TimelineResponse:
    session = _get_session_or_404(session_id)
    _assert_complete(session)
    return TimelineResponse(session_id=session_id, annotations=session.timeline)


@app.get(
    "/api/session/{session_id}/findings",
    response_model=FindingsResponse,
    summary="Agent findings and persona questions",
    tags=["session"],
)
async def get_findings(session_id: UUID) -> FindingsResponse:
    session = _get_session_or_404(session_id)
    _assert_complete(session)
    report = session.report
    return FindingsResponse(
        session_id=session_id,
        findings=report.findings,  # type: ignore[union-attr]
        persona_questions=report.persona_questions,  # type: ignore[union-attr]
    )


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "mode": "demo", "sessions": len(_sessions)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_or_404(session_id: UUID) -> Session:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


def _assert_complete(session: Session) -> None:
    if session.status in (SessionStatus.PROCESSING, SessionStatus.PENDING):
        raise HTTPException(
            status_code=202,
            detail=f"Still processing ({session.progress}% — {session.progress_message})",
        )
    if session.status == SessionStatus.FAILED:
        raise HTTPException(status_code=500, detail=session.error_message)

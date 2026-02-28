"""
API-level Pydantic models for PitchPilot.

These are the request/response contracts for the FastAPI routes.  They live
separately from the pipeline data-models (data_models.py) so the API surface
stays stable while the internal pipeline evolves.

Import these in main.py:
    from backend.api_schemas import Session, ReadinessReport, ...
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AgentType(str, Enum):
    COACH = "coach"
    COMPLIANCE = "compliance"
    PERSONA = "persona"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ClaimType(str, Enum):
    FEATURE = "feature"
    METRIC = "metric"
    COMPARISON = "comparison"
    PRIVACY = "privacy"
    PRICING = "pricing"
    SECURITY = "security"
    OTHER = "other"


class SessionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class SessionMode(str, Enum):
    # Legacy values — kept for backward compatibility
    UPLOAD = "upload"
    LIVE = "live"
    # Canonical three-mode model
    REVIEW = "review"          # Post-hoc analysis of a recorded rehearsal
    LIVE_IN_ROOM = "live_in_room"  # Face-to-face; earpiece audio cues
    LIVE_REMOTE = "live_remote"    # Virtual demo; on-screen presenter overlay


class TimelineCategory(str, Enum):
    COACH = "coach"
    COMPLIANCE = "compliance"
    PERSONA = "persona"


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Claim(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    text: str
    claim_type: ClaimType
    timestamp: float
    source: str = "transcript"
    slide_number: Optional[int] = None
    confidence: float = 1.0


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    agent: AgentType
    severity: Severity
    title: str
    detail: str
    suggestion: Optional[str] = None
    timestamp: float = 0.0
    claim_id: Optional[str] = None
    policy_reference: Optional[str] = None
    persona: Optional[str] = None
    live: bool = False
    # Optional 3-6 word phrase for earpiece delivery (live modes only)
    cue_hint: Optional[str] = None


class PersonaQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    persona: str
    question: str
    follow_up: Optional[str] = None
    timestamp: Optional[float] = None
    difficulty: Severity


class TimelineAnnotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    finding_id: str
    category: TimelineCategory
    timestamp: float = 0.0
    label: str
    severity: Severity


class DimensionScore(BaseModel):
    dimension: str
    score: int  # 0–100
    rationale: str


class ReadinessScore(BaseModel):
    overall: int  # 0–100
    dimensions: List[DimensionScore]
    priority_fixes: List[str]


class ReadinessReport(BaseModel):
    session_id: UUID
    score: ReadinessScore
    findings: List[Finding]
    persona_questions: List[PersonaQuestion]
    claims: List[Claim]
    summary: str
    created_at: str
    # Live session provenance — None for review/upload mode
    session_mode: Optional[SessionMode] = None
    session_duration_seconds: Optional[float] = None
    live_cues_count: Optional[int] = None
    # Narrative post-hoc account of what happened during the live session
    live_session_summary: Optional[str] = None


# ---------------------------------------------------------------------------
# Session state (in-memory store model)
# ---------------------------------------------------------------------------


class Session(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    id: UUID
    video_filename: str
    policy_filenames: List[str] = []
    presentation_filenames: List[str] = []
    personas: List[str] = []
    mode: SessionMode = SessionMode.UPLOAD
    status: SessionStatus = SessionStatus.PENDING
    progress: int = 0
    progress_message: str = "Queued"
    error_message: Optional[str] = None
    report: Optional[ReadinessReport] = None
    timeline: List[TimelineAnnotation] = []
    live_findings: List[Finding] = []
    live_cues: List[EarpieceCue] = []
    session_duration_seconds: Optional[float] = None
    created_at: str


# ---------------------------------------------------------------------------
# API response wrappers
# ---------------------------------------------------------------------------


class SessionStartResponse(BaseModel):
    session_id: UUID
    status: SessionStatus
    message: str


class SessionStatusResponse(BaseModel):
    session_id: UUID
    status: SessionStatus
    progress: int
    progress_message: str
    error_message: Optional[str] = None


class FindingsResponse(BaseModel):
    session_id: UUID
    findings: List[Finding]
    persona_questions: List[PersonaQuestion]


class TimelineResponse(BaseModel):
    session_id: UUID
    annotations: List[TimelineAnnotation]


# ---------------------------------------------------------------------------
# Live-session startup
# ---------------------------------------------------------------------------


class LiveSessionStartRequest(BaseModel):
    """Body for POST /api/session/start-live — registers a pending live session."""
    mode: SessionMode = SessionMode.LIVE_IN_ROOM
    personas: List[str] = []
    policy_text: str = ""
    title: str = "Live Session"


class LiveSessionStartResponse(BaseModel):
    session_id: UUID
    ws_url: str   # e.g. ws://localhost:8000/api/session/live
    mode: SessionMode
    status: SessionStatus
    message: str


# ---------------------------------------------------------------------------
# Live-mode WebSocket outbound message payloads
# (mirrored in frontend/src/types/index.ts)
# ---------------------------------------------------------------------------


class EarpieceCue(BaseModel):
    """Outbound WS type: earpiece_cue  (live_in_room mode only)"""
    text: str                       # 3-6 word cue string
    audio_b64: Optional[str] = None # base64 encoded audio clip; None = play silently / TTS client-side
    priority: Severity = Severity.WARNING
    category: str = ""              # e.g. "compliance" | "pacing" | "differentiation"
    elapsed: float = 0.0


class TeleprompterUpdate(BaseModel):
    """Outbound WS type: teleprompter  (live_remote mode only)"""
    points: List[str]               # 2-3 short talking points
    slide_context: str = ""         # OCR text of current slide (for context)
    elapsed: float = 0.0


class ObjectionPrepUpdate(BaseModel):
    """Outbound WS type: objection_prep  (live_remote mode only)"""

    class ObjectionCard(BaseModel):
        question: str
        suggested_answer: str
        persona: Optional[str] = None
        difficulty: Severity = Severity.WARNING

    questions: List[ObjectionCard]
    elapsed: float = 0.0


class ScriptSuggestion(BaseModel):
    """Outbound WS type: script_suggestion  (live_remote mode only)"""
    original: str       # What the presenter said
    alternative: str    # Suggested replacement wording
    reason: str         # Why the change is recommended
    agent: AgentType = AgentType.COACH
    elapsed: float = 0.0

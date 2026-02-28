"""
Shared data contracts for PitchPilot.

All agents, the orchestrator, and the report generator communicate
through these types. Keep them stable — downstream frontend depends on them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# ---------------------------------------------------------------------------
# Severity / category type aliases (used for type hints & validation)
# ---------------------------------------------------------------------------

Severity = Literal["info", "warning", "critical"]
ClaimType = Literal["product", "compliance_sensitive", "technical", "comparison", "general"]
AgentName = Literal["coach", "compliance", "persona"]
MarkerColor = Literal["red", "yellow", "blue", "purple"]

CATEGORY_COLOR: dict[str, MarkerColor] = {
    "compliance": "red",
    "risk": "red",
    "clarity": "yellow",
    "structure": "yellow",
    "coach": "yellow",
    "persona_question": "purple",
    "persona": "purple",
    "technical": "blue",
    "general": "blue",
}


def _short_id() -> str:
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# Input types (produced by the upstream pipeline)
# ---------------------------------------------------------------------------


@dataclass
class TranscriptSegment:
    """A chunk of spoken transcript with timing."""

    text: str
    start_time: float  # seconds
    end_time: float
    speaker: str = "presenter"
    confidence: float = 1.0


@dataclass
class SlideOCR:
    """Text extracted from a single slide frame."""

    slide_index: int
    timestamp: float
    raw_text: str
    title: Optional[str] = None
    bullet_points: list[str] = field(default_factory=list)
    image_description: Optional[str] = None


@dataclass
class Claim:
    """A discrete claim extracted from the transcript or slide OCR."""

    id: str = field(default_factory=_short_id)
    text: str = ""
    claim_type: ClaimType = "general"
    timestamp: Optional[float] = None  # seconds in the recording
    source: str = "transcript"  # transcript | ocr | both
    slide_ref: Optional[str] = None  # e.g. "slide_3"
    context_before: str = ""  # surrounding text for richer agent prompts
    context_after: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "claim_type": self.claim_type,
            "timestamp": self.timestamp,
            "source": self.source,
            "slide_ref": self.slide_ref,
            "context_before": self.context_before,
            "context_after": self.context_after,
        }


@dataclass
class PipelineContext:
    """Full structured context passed from the upstream pipeline to the orchestrator."""

    session_id: str = field(default_factory=_short_id)
    transcript_segments: list[TranscriptSegment] = field(default_factory=list)
    slide_ocr: list[SlideOCR] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    policy_text: str = ""  # Loaded compliance/policy document text
    presentation_title: str = ""
    personas: list[str] = field(default_factory=list)  # persona names to simulate
    total_duration: float = 0.0  # seconds

    @property
    def full_transcript(self) -> str:
        return " ".join(seg.text for seg in self.transcript_segments)

    @property
    def full_slide_text(self) -> str:
        return "\n".join(ocr.raw_text for ocr in self.slide_ocr)


# ---------------------------------------------------------------------------
# Output types (produced by agents, consumed by orchestrator + report)
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single finding from any agent."""

    id: str = field(default_factory=_short_id)
    agent: AgentName = "coach"
    category: str = ""  # clarity | structure | compliance | risk | persona_question | technical
    severity: Severity = "info"
    timestamp: Optional[float] = None  # seconds — used for timeline annotation
    title: str = ""
    description: str = ""
    suggestion: Optional[str] = None  # actionable fix
    claim_ref: Optional[str] = None  # id of the Claim this finding relates to
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "category": self.category,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "title": self.title,
            "description": self.description,
            "suggestion": self.suggestion,
            "claim_ref": self.claim_ref,
            "metadata": self.metadata,
        }


@dataclass
class PersonaQuestion:
    """A question or objection from a simulated stakeholder persona."""

    persona: str = ""  # e.g. "Skeptical Investor"
    question: str = ""
    question_type: str = "clarification"  # objection | clarification | challenge | hostile
    difficulty: str = "medium"  # easy | medium | hard
    timestamp: Optional[float] = None
    finding_id: Optional[str] = None
    suggested_answer: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "question": self.question,
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "timestamp": self.timestamp,
            "finding_id": self.finding_id,
            "suggested_answer": self.suggested_answer,
        }


@dataclass
class TimelineAnnotation:
    """A single color-coded marker on the playback timeline."""

    timestamp: float = 0.0  # seconds
    category: str = ""  # compliance | clarity | structure | persona_question | technical
    color: MarkerColor = "blue"
    label: str = ""
    finding_id: str = ""
    agent: AgentName = "coach"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "category": self.category,
            "color": self.color,
            "label": self.label,
            "finding_id": self.finding_id,
            "agent": self.agent,
        }


@dataclass
class DimensionScore:
    """Score for one dimension of readiness (clarity, compliance, etc.)."""

    name: str = ""
    score: int = 0  # 0–100
    weight: float = 0.25  # fraction of overall score
    issues_count: int = 0
    critical_count: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "weight": self.weight,
            "issues_count": self.issues_count,
            "critical_count": self.critical_count,
            "summary": self.summary,
        }


@dataclass
class ReadinessReport:
    """Top-level output: the final readiness assessment."""

    session_id: str = field(default_factory=_short_id)
    overall_score: int = 0  # 0–100
    grade: str = ""  # A | B | C | D | F
    dimensions: dict[str, DimensionScore] = field(default_factory=dict)
    top_issues: list[Finding] = field(default_factory=list)
    priority_fixes: list[str] = field(default_factory=list)
    stakeholder_questions: list[PersonaQuestion] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    timeline: list[TimelineAnnotation] = field(default_factory=list)
    summary: str = ""
    agents_run: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "overall_score": self.overall_score,
            "grade": self.grade,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "top_issues": [f.to_dict() for f in self.top_issues],
            "priority_fixes": self.priority_fixes,
            "stakeholder_questions": [q.to_dict() for q in self.stakeholder_questions],
            "findings": [f.to_dict() for f in self.findings],
            "timeline": [a.to_dict() for a in self.timeline],
            "summary": self.summary,
            "agents_run": self.agents_run,
        }


# ---------------------------------------------------------------------------
# Router types (FunctionGemma dispatch)
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """A single dispatched tool call produced by the router."""

    function_name: str  # check_compliance | coach_presentation | simulate_persona | ...
    args: dict[str, Any] = field(default_factory=dict)
    claim_id: Optional[str] = None
    confidence: float = 1.0  # router confidence


@dataclass
class RouterOutput:
    """Output of the FunctionGemma router for a given claim."""

    claim_id: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_output: str = ""  # raw model output (for debugging)

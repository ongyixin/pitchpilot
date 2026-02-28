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
    EarpieceCue,
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
# Live-session fixture data
# ---------------------------------------------------------------------------


def _demo_live_inroom_claims() -> list[Claim]:
    """Claims extracted from a 5:22 live in-room session."""
    return [
        Claim(
            text="Our platform is fully automated — no manual review required.",
            claim_type=ClaimType.FEATURE,
            timestamp=34.0,
            source="transcript",
            confidence=0.92,
        ),
        Claim(
            text="We achieve 99.9 % uptime across all enterprise tiers.",
            claim_type=ClaimType.METRIC,
            timestamp=70.0,
            source="transcript",
            confidence=0.87,
        ),
        Claim(
            text="All customer data is stored exclusively on-device — nothing leaves your network.",
            claim_type=ClaimType.PRIVACY,
            timestamp=112.0,
            source="transcript",
            confidence=0.90,
        ),
        Claim(
            text="We outperform every competitor by 3× on inference speed.",
            claim_type=ClaimType.COMPARISON,
            timestamp=155.0,
            source="transcript",
            confidence=0.79,
        ),
    ]


def _demo_live_inroom_findings(claims: list[Claim]) -> list[Finding]:
    """
    Findings from a live in-room session. All have live=True.
    Findings with cue_hint were delivered as earpiece cues during the session.
    Info-severity findings are deferred (no earpiece cue; appear only in this report).
    """
    claim_automated = claims[0]
    claim_uptime    = claims[1]
    claim_privacy   = claims[2]
    claim_speed     = claims[3]

    return [
        # Positive — deferred (info, no earpiece cue)
        Finding(
            agent=AgentType.COACH,
            severity=Severity.INFO,
            title="Strong opening hook captured live",
            detail=(
                "The opening anecdote about a failed product demo was vivid and relatable. "
                "It established stakes immediately and held the room's attention."
            ),
            suggestion=None,
            timestamp=12.0,
            live=True,
            cue_hint=None,
        ),
        # Compliance — critical → earpiece cue delivered at 0:34
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
            timestamp=34.0,
            claim_id=claim_automated.id,
            policy_reference="Enterprise Data Policy §3.2 — Human Oversight Requirement",
            live=True,
            cue_hint="compliance risk",
        ),
        # Coach — warning → earpiece cue at 1:10
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Pacing fast through uptime metric",
            detail=(
                "The 99.9 % uptime claim was delivered quickly without a pause. "
                "Sophisticated audiences need a moment to register numeric claims."
            ),
            suggestion="Add a 1–2 second pause after stating uptime figures to let them land.",
            timestamp=70.0,
            claim_id=claim_uptime.id,
            live=True,
            cue_hint="slow down",
        ),
        # Compliance — warning → earpiece cue at 1:52
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="'Nothing leaves your network' needs qualification",
            detail=(
                "The blanket on-device privacy claim may be technically false for customers "
                "who enable the optional cloud-sync feature shown on your architecture slide."
            ),
            suggestion="Add 'by default' and mention the opt-in cloud sync explicitly.",
            timestamp=112.0,
            claim_id=claim_privacy.id,
            policy_reference="Privacy Disclosure Policy §1.1 — Accurate Representation",
            live=True,
            cue_hint="mention privacy",
        ),
        # Coach — critical → earpiece cue at 2:35
        Finding(
            agent=AgentType.COACH,
            severity=Severity.CRITICAL,
            title="Speed metric lacks benchmark context",
            detail=(
                "'3× faster' is compelling but the baseline is never stated. "
                "Sophisticated audiences dismiss unanchored comparisons immediately."
            ),
            suggestion="Name the competitor and link to a reproducible benchmark.",
            timestamp=155.0,
            claim_id=claim_speed.id,
            live=True,
            cue_hint="name the benchmark",
        ),
        # Persona — warning → earpiece cue at 3:18
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Skeptical Investor: ROI question anticipated",
            detail=(
                "Based on the claims heard so far, a skeptical investor will ask about "
                "ROI and differentiation from ChatGPT. The on-device angle has not been "
                "emphasised strongly enough yet."
            ),
            suggestion="Lead with the on-device / privacy differentiator and repeat it at close.",
            timestamp=198.0,
            persona="Skeptical Investor",
            live=True,
            cue_hint="ROI question likely",
        ),
        # Compliance — info → deferred (no earpiece cue)
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.INFO,
            title="99.9 % uptime SLA needs footnote",
            detail=(
                "The standard enterprise contract offers 99.5 % SLA. "
                "The 99.9 % claim is technically achievable under the premium tier but "
                "should be qualified to avoid contractual ambiguity."
            ),
            suggestion="Say 'up to 99.9 % on the premium tier' and add a footnote.",
            timestamp=72.0,
            claim_id=claim_uptime.id,
            policy_reference="SLA Addendum v2 — Enterprise Standard Tier",
            live=True,
            cue_hint=None,
        ),
        # Coach — warning → earpiece cue at 4:45
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Differentiation from ChatGPT still unclear at close",
            detail=(
                "Four minutes in and the on-device differentiation has still not been "
                "stated crisply. Closing without this leaves the key question unanswered."
            ),
            suggestion="Closing line: 'Unlike cloud-based AI, everything runs on your device. No data leaves the room.'",
            timestamp=285.0,
            live=True,
            cue_hint="clarify differentiation",
        ),
        # Persona — warning → deferred
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Compliance Officer: data retention policy not mentioned",
            detail=(
                "No mention of how long rehearsal recordings are retained locally. "
                "A compliance officer in the room would flag this immediately."
            ),
            suggestion="Add one sentence on local-only storage and auto-deletion policy.",
            timestamp=240.0,
            persona="Compliance Officer",
            live=True,
            cue_hint=None,
        ),
    ]


def _demo_live_remote_claims() -> list[Claim]:
    """Claims from an 8:15 live remote session with screen share."""
    return [
        Claim(
            text="Our platform is fully automated — no manual review required.",
            claim_type=ClaimType.FEATURE,
            timestamp=45.0,
            source="both",
            slide_number=2,
            confidence=0.93,
        ),
        Claim(
            text="We achieve 99.9 % uptime across all enterprise tiers.",
            claim_type=ClaimType.METRIC,
            timestamp=130.0,
            source="slide",
            slide_number=4,
            confidence=0.89,
        ),
        Claim(
            text="All customer data is stored exclusively on-device — nothing leaves your network.",
            claim_type=ClaimType.PRIVACY,
            timestamp=200.0,
            source="both",
            slide_number=4,
            confidence=0.91,
        ),
        Claim(
            text="We outperform every competitor by 3× on inference speed.",
            claim_type=ClaimType.COMPARISON,
            timestamp=255.0,
            source="transcript",
            slide_number=6,
            confidence=0.81,
        ),
        Claim(
            text="Deployment takes under one hour for any enterprise environment.",
            claim_type=ClaimType.FEATURE,
            timestamp=330.0,
            source="slide",
            slide_number=7,
            confidence=0.76,
        ),
    ]


def _demo_live_remote_findings(claims: list[Claim]) -> list[Finding]:
    """
    Findings from a live remote session (8:15 duration, 8 slides).
    All have live=True; cue_hint fields drove overlay cards during the session.
    """
    claim_automated = claims[0]
    claim_uptime    = claims[1]
    claim_privacy   = claims[2]
    claim_speed     = claims[3]
    claim_deploy    = claims[4]

    return [
        # Coach — positive, deferred
        Finding(
            agent=AgentType.COACH,
            severity=Severity.INFO,
            title="Opening hook strong — preserve for all audiences",
            detail=(
                "The opening 45 seconds established clear stakes and framed the problem "
                "memorably. Screen share was smooth from the start."
            ),
            suggestion=None,
            timestamp=15.0,
            live=True,
            cue_hint=None,
        ),
        # Compliance — critical → overlay card at 0:45
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.CRITICAL,
            title="'Fully automated' conflicts with policy §3.2",
            detail=(
                "Slide 2 and transcript both claim 'fully automated — no manual review.' "
                "Policy §3.2 mandates human review above a 0.95 confidence threshold. "
                "This will derail a compliance-focused audience."
            ),
            suggestion="Rephrase to: 'Automated with optional human-in-the-loop review for high-stakes decisions.'",
            timestamp=45.0,
            claim_id=claim_automated.id,
            policy_reference="Enterprise Data Policy §3.2 — Human Oversight Requirement",
            live=True,
            cue_hint="compliance risk",
        ),
        # Coach — warning → overlay card at 2:10
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Slide 3 overloaded with technical jargon",
            detail=(
                "Slide 3 uses 'multi-agent orchestration', 'LoRA fine-tuning', and "
                "'tokenised function dispatch' in the same bullet list. "
                "Non-technical viewers on the call will disengage here."
            ),
            suggestion="Lead with the outcome ('analyzes your pitch in 90 seconds') before explaining the mechanism.",
            timestamp=130.0,
            live=True,
            cue_hint="simplify slide",
        ),
        # Compliance — warning → overlay card at 3:20
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="'Nothing leaves your network' needs qualification",
            detail=(
                "Privacy claim on slide 4 conflicts with the optional cloud-sync icon "
                "visible on the architecture slide. Viewers who notice this will lose trust."
            ),
            suggestion="Add 'by default' and note the opt-in cloud sync.",
            timestamp=200.0,
            claim_id=claim_privacy.id,
            policy_reference="Privacy Disclosure Policy §1.1 — Accurate Representation",
            live=True,
            cue_hint="mention privacy",
        ),
        # Persona — info, deferred (positive signal)
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.INFO,
            title="Technical Reviewer: model specificity is credible",
            detail=(
                "The Technical Reviewer persona found the mention of Gemma 3n, "
                "FunctionGemma, and LoRA fine-tuning reassuring and technically credible."
            ),
            timestamp=270.0,
            persona="Technical Reviewer",
            live=True,
            cue_hint=None,
        ),
        # Coach — critical → overlay card at 4:15
        Finding(
            agent=AgentType.COACH,
            severity=Severity.CRITICAL,
            title="Speed metric lacks benchmark context",
            detail=(
                "'3× faster' is compelling but the baseline is unstated. "
                "Technical reviewers on the call will immediately ask '3× vs. what?'"
            ),
            suggestion="Name the competitor and link to a reproducible benchmark.",
            timestamp=255.0,
            claim_id=claim_speed.id,
            live=True,
            cue_hint="name benchmark",
        ),
        # Persona — warning → overlay card at 5:00
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Skeptical Investor: ChatGPT differentiation question incoming",
            detail=(
                "The presentation has not yet explained why on-device matters vs. "
                "a compliance-aware GPT-4o wrapper. Expect this question from investors."
            ),
            suggestion="Prepare: 'ChatGPT requires sending your pitch to the cloud and has no sales-specific fine-tuning.'",
            timestamp=300.0,
            persona="Skeptical Investor",
            live=True,
            cue_hint="ChatGPT pushback likely",
        ),
        # Coach — warning → overlay card at 6:10
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="Abrupt transition slide 6 → 7",
            detail=(
                "The jump from the live demo to the business model slide felt unanchored. "
                "No bridging sentence to orient the audience."
            ),
            suggestion="Add: 'What you just saw is the core product. Here's how we monetize it.'",
            timestamp=370.0,
            live=True,
            cue_hint="add bridge",
        ),
        # Compliance — warning → overlay card at 6:45
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="99.9 % uptime SLA not reflected in standard contract",
            detail=(
                "Standard tier is 99.5 %. Promising 99.9 % on-screen without qualification "
                "creates potential contractual liability."
            ),
            suggestion="Add 'premium tier only' or 'up to 99.9 %' footnote on slide 4.",
            timestamp=405.0,
            claim_id=claim_uptime.id,
            policy_reference="SLA Addendum v2 — Enterprise Standard Tier",
            live=True,
            cue_hint="add footnote",
        ),
        # Persona — warning → overlay card at 7:20
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Compliance Officer: data retention policy missing",
            detail=(
                "Eight minutes in and no mention of rehearsal recording retention. "
                "A compliance officer will note the absence and ask offline."
            ),
            suggestion="Add one sentence on local-only storage and auto-deletion policy.",
            timestamp=440.0,
            persona="Compliance Officer",
            live=True,
            cue_hint="mention retention",
        ),
        # Compliance — info, deferred
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.INFO,
            title="Deployment time claim should cite conditions",
            detail=(
                "'Under one hour' is plausible for SaaS but on-device deployment at "
                "enterprise scale typically requires IT approval cycles. Worth qualifying."
            ),
            suggestion="Add 'for standard single-user deployment' to the one-hour claim.",
            timestamp=330.0,
            claim_id=claim_deploy.id,
            live=True,
            cue_hint=None,
        ),
    ]


def _demo_live_report(
    session_id: UUID,
    claims: list[Claim],
    findings: list[Finding],
    mode: SessionMode,
    duration_seconds: float,
    cues_count: int,
) -> ReadinessReport:
    """Build a ReadinessReport for a completed live session."""
    dimensions = [
        DimensionScore(
            dimension="Clarity",
            score=76,
            rationale=(
                "Structure and flow were solid. One abrupt transition and jargon "
                "overload on the solution slide are addressable."
            ),
        ),
        DimensionScore(
            dimension="Compliance",
            score=63,
            rationale=(
                "Two critical policy conflicts detected live. The 'fully automated' "
                "and privacy claims need rewording before the next session."
            ),
        ),
        DimensionScore(
            dimension="Defensibility",
            score=69,
            rationale=(
                "Speed and uptime claims need benchmark citations. "
                "Persona simulation flagged ROI and ChatGPT differentiation gaps."
            ),
        ),
        DimensionScore(
            dimension="Persuasiveness",
            score=80,
            rationale=(
                "Opening hook and on-device framing are strong trust signals. "
                "The close needs a crisper differentiation statement."
            ),
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
            "Add a bridge sentence between the demo and the business-model slide.",
        ],
    )

    mode_label = "live in-room" if mode == SessionMode.LIVE_IN_ROOM else "live remote"
    duration_str = f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}"
    live_summary = (
        f"{duration_str} {mode_label} session. "
        f"{cues_count} real-time cues delivered during the presentation. "
        f"Two critical issues surfaced: the 'fully automated' compliance conflict "
        f"and the unanchored 3× speed claim. The on-device differentiator was "
        f"underemphasised — repeat it earlier and at close. "
        f"All findings below include both the issues that triggered live cues "
        f"and the deferred items that surface here for the first time."
    )

    return ReadinessReport(
        session_id=session_id,
        score=score,
        findings=findings,
        persona_questions=_demo_persona_questions(),
        claims=claims,
        summary=(
            f"Overall readiness is {overall}/100. "
            "The pitch has a strong hook and credible technical specificity, "
            "but two compliance conflicts need resolution before the next session. "
            "The privacy and automation claims are the highest-risk items. "
            "Prepare for the ChatGPT differentiation question — it will come from every audience."
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
        session_mode=mode,
        session_duration_seconds=duration_seconds,
        live_cues_count=cues_count,
        live_session_summary=live_summary,
    )


# ---------------------------------------------------------------------------
# Mock live-session finalization background task
# ---------------------------------------------------------------------------


async def _run_mock_live_finalization(session_id: UUID, mode: SessionMode) -> None:
    """
    Simulates a live session that has ended and is now being finalized.
    The session starts in PROCESSING and arrives at COMPLETE with a full report.
    """
    session = _sessions[session_id]
    session.status = SessionStatus.PROCESSING

    stages: list[tuple[int, str]]
    if mode == SessionMode.LIVE_IN_ROOM:
        stages = [
            (15, "Processing captured audio transcript…"),
            (35, "Running claim extraction on live transcript…"),
            (55, "FunctionGemma routing claims to agents…"),
            (70, "Presentation Coach reviewing live findings…"),
            (82, "Compliance Reviewer cross-checking policy…"),
            (91, "Persona Simulator generating stakeholder questions…"),
            (97, "Aggregating final readiness score…"),
            (100, "Live session report complete"),
        ]
        claims_fn = _demo_live_inroom_claims
        findings_fn = _demo_live_inroom_findings
        duration = 322.0   # 5:22
        cues = 6
    else:
        stages = [
            (12, "Processing captured audio + screen frames…"),
            (28, "Running OCR on captured slide frames…"),
            (44, "Extracting claims from transcript + slides…"),
            (60, "FunctionGemma routing claims to agents…"),
            (73, "Presentation Coach reviewing live findings…"),
            (84, "Compliance Reviewer cross-checking policy…"),
            (92, "Persona Simulator generating stakeholder questions…"),
            (97, "Aggregating final readiness score…"),
            (100, "Live session report complete"),
        ]
        claims_fn = _demo_live_remote_claims
        findings_fn = _demo_live_remote_findings
        duration = 495.0   # 8:15
        cues = 8

    for progress, message in stages:
        await asyncio.sleep(_STAGE_DELAY)
        session.progress = progress
        session.progress_message = message

    claims = claims_fn()
    findings = findings_fn(claims)
    session.report = _demo_live_report(session_id, claims, findings, mode, duration, cues)
    session.timeline = _demo_timeline(findings)
    session.session_duration_seconds = duration
    session.status = SessionStatus.COMPLETE


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


@app.post(
    "/api/session/start-live",
    response_model=LiveSessionStartResponse,
    summary="Register a pending live session and get the WebSocket URL",
    tags=["live"],
)
async def start_live_session(body: LiveSessionStartRequest) -> LiveSessionStartResponse:
    """
    Registers a new live session in the store and returns the WebSocket URL
    to which the client should connect for audio/frame streaming.

    In the demo server the WebSocket is not actually functional, but this
    endpoint ensures the full HTTP start-live flow can be tested end-to-end.
    """
    session_id = uuid4()
    session = Session(
        id=session_id,
        video_filename="",
        personas=body.personas,
        mode=body.mode,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _sessions[session_id] = session

    return LiveSessionStartResponse(
        session_id=session_id,
        ws_url=f"ws://localhost:8000/api/session/live",
        mode=body.mode,
        status=SessionStatus.PENDING,
        message=f"Live session registered — connect to ws_url to begin ({body.mode.value})",
    )


@app.post(
    "/api/session/demo-live",
    response_model=SessionStartResponse,
    summary="Start an instant completed-live-session demo (no WebSocket needed)",
    tags=["demo"],
)
async def start_demo_live_session(
    mode: Optional[str] = None,
    personas: Optional[str] = None,
) -> SessionStartResponse:
    """
    Creates a pre-completed live session (in-room or remote) and immediately
    begins simulating the finalization pipeline.

    Query parameters:
      - mode: "live_in_room" (default) | "live_remote"
      - personas: comma-separated persona names (optional)

    Use this endpoint to demo the full live → results flow without running
    a real WebSocket session. Results are available via the standard
    /report, /timeline, /findings endpoints once status == 'complete'.
    """
    resolved_mode = SessionMode.LIVE_IN_ROOM
    if mode == "live_remote":
        resolved_mode = SessionMode.LIVE_REMOTE

    session_id = uuid4()
    persona_list = (
        [p.strip() for p in personas.split(",") if p.strip()]
        if personas
        else ["Skeptical Investor", "Technical Reviewer", "Compliance Officer"]
    )

    session = Session(
        id=session_id,
        video_filename="",
        personas=persona_list,
        mode=resolved_mode,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _sessions[session_id] = session
    asyncio.create_task(_run_mock_live_finalization(session_id, resolved_mode))

    mode_label = "in-room" if resolved_mode == SessionMode.LIVE_IN_ROOM else "remote"
    return SessionStartResponse(
        session_id=session_id,
        status=SessionStatus.PENDING,
        message=f"Demo live {mode_label} session started — poll /status for progress",
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

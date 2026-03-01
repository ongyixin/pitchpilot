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
            text="PitchPilot analyzes your pitch in 90 seconds — fully automated, no manual review required.",
            claim_type=ClaimType.FEATURE,
            timestamp=34.5,
            source="transcript",
            confidence=0.93,
        ),
        Claim(
            text="PitchPilot runs entirely on-device — your pitch data never leaves your computer.",
            claim_type=ClaimType.PRIVACY,
            timestamp=72.0,
            source="slide",
            slide_number=4,
            confidence=0.88,
        ),
        Claim(
            text="We use Gemma 3n and FunctionGemma — state-of-the-art on-device AI models.",
            claim_type=ClaimType.FEATURE,
            timestamp=112.0,
            source="both",
            slide_number=6,
            confidence=0.91,
        ),
        Claim(
            text="PitchPilot provides real-time coaching cues during live presentations.",
            claim_type=ClaimType.FEATURE,
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
                "The transition from the problem slide to the PitchPilot demo felt rushed. "
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
            detail="The opening anecdote about a failed pitch rehearsal was vivid and relatable. It established the problem PitchPilot solves immediately.",
            suggestion=None,
            timestamp=5.0,
        ),
        Finding(
            agent=AgentType.COACH,
            severity=Severity.CRITICAL,
            title="Real-time coaching feature needs demonstration",
            detail=(
                "The claim about 'real-time coaching cues' is compelling but wasn't demonstrated. "
                "Audiences need to see how PitchPilot's coaching works in practice."
            ),
            suggestion="Add a live demo or video showing PitchPilot's earpiece cues during a presentation, or at least show a screenshot of the overlay interface.",
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
            suggestion="Lead with the outcome ('PitchPilot analyzes your pitch in 90 seconds') before explaining the mechanism.",
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
                "Claiming PitchPilot is 'fully automated — no manual review required' directly contradicts this."
            ),
            suggestion="Rephrase to: 'PitchPilot is automated with optional human-in-the-loop review for high-stakes decisions.'",
            timestamp=34.5,
            claim_id=claim_automated.id,
            policy_reference="Enterprise Data Policy §3.2 — Human Oversight Requirement",
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="'Never leaves your computer' claim needs technical clarification",
            detail=(
                "The claim that 'pitch data never leaves your computer' is strong but needs clarification "
                "about how PitchPilot processes data locally. Does this include model inference, or just storage?"
            ),
            suggestion="Clarify: 'All pitch analysis runs locally on your device. No video or transcript data is sent to external servers.'",
            timestamp=72.0,
            claim_id=claim_uptime.id,
            policy_reference="Privacy Disclosure Policy §1.1 — Accurate Representation",
        ),
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="Model names need context for non-technical audiences",
            detail=(
                "Mentioning 'Gemma 3n and FunctionGemma' is technically credible but may confuse non-technical investors. "
                "The value proposition should come first."
            ),
            suggestion="Lead with: 'PitchPilot uses state-of-the-art on-device AI' before naming specific models.",
            timestamp=112.0,
            claim_id=claim_privacy.id,
            policy_reference="Approved Messaging Guide — Technical Terminology",
        ),
        # Persona findings
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Skeptical Investor: differentiation is unclear",
            detail=(
                "After hearing the PitchPilot pitch, a skeptical investor would immediately ask "
                "how this differs from a well-prompted ChatGPT plus screen recording. "
                "The on-device angle is the key differentiator but it was mentioned only once, in passing."
            ),
            suggestion="Lead with the on-device / privacy differentiator earlier and repeat it at close. Emphasize that PitchPilot runs entirely locally, unlike ChatGPT which requires cloud access.",
            timestamp=90.0,
            persona="Skeptical Investor",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.INFO,
            title="Technical Reviewer: model card details appreciated",
            detail=(
                "The Technical Reviewer persona found the mention of specific model names "
                "(Gemma 3n, FunctionGemma) in the PitchPilot pitch credible and reassuring. "
                "This demonstrates technical depth."
            ),
            timestamp=130.0,
            persona="Technical Reviewer",
        ),
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Procurement Manager: TCO and integration path not addressed",
            detail=(
                "No mention of three-year total cost of ownership or CRM integrations. "
                "A Procurement Manager will block sign-off without this information."
            ),
            suggestion="Add a slide covering per-seat pricing, implementation timeline, and current Salesforce/Gong integrations.",
            timestamp=175.0,
            persona="Procurement Manager",
        ),
    ]


def _demo_persona_questions() -> list[PersonaQuestion]:
    return [
        PersonaQuestion(
            persona="ops_manager",
            question="That's a bold claim – can you specifically detail the data mapping and transformation processes required to ensure accurate, real-time synchronization between this system and *both* SAP and Oracle, and what's the estimated timeline and cost for that integration?",
            timestamp=85.0,
            difficulty=Severity.CRITICAL,
        ),
        PersonaQuestion(
            persona="investor",
            question="Guaranteeing ROI is a bold claim – can you quantify what 'ROI' actually means for a typical InstaLILY customer and demonstrate how you've achieved this consistently across at least three separate case studies?",
            timestamp=108.0,
            difficulty=Severity.CRITICAL,
        ),
        PersonaQuestion(
            persona="cto",
            question="That's a bold claim. Can you detail the specific on-device machine learning model architecture you're utilizing, and how you've addressed potential privacy concerns related to continuous sales data collection?",
            timestamp=155.0,
            difficulty=Severity.CRITICAL,
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
            "Fix the 'fully automated' claim about PitchPilot — it directly contradicts Enterprise Data Policy §3.2.",
            "Demonstrate the real-time coaching feature with a live demo or video.",
            "Clarify the on-device privacy claim: specify that all analysis runs locally, not just storage.",
            "Add a bridge sentence between the problem slide and the PitchPilot demo.",
        ],
    )
    return ReadinessReport(
        session_id=session_id,
        score=score,
        findings=findings,
        persona_questions=_demo_persona_questions(),
        claims=claims,
        summary=(
            "Overall readiness is 72/100. The PitchPilot pitch has a strong hook and credible technical "
            "specificity, but two compliance conflicts need resolution before presenting to investors. "
            "The privacy and automation claims are the highest-risk items. "
            "Prepare for the ChatGPT differentiation question — it will come from every audience. "
            "Consider adding a live demo of the real-time coaching feature to make it more tangible."
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
            text="PitchPilot runs locally on your laptop because your sales playbook and pricing strategy cannot leave the device.",
            claim_type=ClaimType.PRIVACY,
            timestamp=25.0,
            source="transcript",
            confidence=0.95,
        ),
        Claim(
            text="Our system integrates seamlessly with your existing CRM and ERP workflows including SAP and Oracle.",
            claim_type=ClaimType.FEATURE,
            timestamp=48.0,
            source="transcript",
            confidence=0.88,
        ),
        Claim(
            text="We guarantee ROI within 90 days for every InstaLILY customer.",
            claim_type=ClaimType.METRIC,
            timestamp=72.0,
            source="transcript",
            confidence=0.85,
        ),
        Claim(
            text="Our on-device model processes sales conversations in real time with no latency.",
            claim_type=ClaimType.FEATURE,
            timestamp=95.0,
            source="transcript",
            confidence=0.90,
        ),
        Claim(
            text="We are the only company building domain-trained on-device sales coaching for distribution verticals.",
            claim_type=ClaimType.COMPARISON,
            timestamp=118.0,
            source="transcript",
            confidence=0.82,
        ),
        Claim(
            text="Our finetuned FunctionGemma model outperforms base Gemma on enterprise sales objection detection.",
            claim_type=ClaimType.FEATURE,
            timestamp=142.0,
            source="transcript",
            confidence=0.91,
        ),
        Claim(
            text="InstaLILY sales reps using PitchPilot will close 40% more enterprise deals.",
            claim_type=ClaimType.METRIC,
            timestamp=165.0,
            source="transcript",
            confidence=0.87,
        ),
    ]


def _demo_live_inroom_findings(claims: list[Claim]) -> list[Finding]:
    """
    Findings from a live in-room session. All have live=True.
    Findings with cue_hint were delivered as earpiece cues during the session.
    Info-severity findings are deferred (no earpiece cue; appear only in this report).
    """
    claim_privacy = claims[0]
    claim_integration = claims[1]
    claim_roi = claims[2]
    claim_realtime = claims[3]
    claim_differentiation = claims[4]
    claim_model = claims[5]
    claim_deals = claims[6]

    return [
        # Coach — info → deferred (positive signal)
        Finding(
            agent=AgentType.COACH,
            severity=Severity.INFO,
            title="Clear value proposition established",
            detail=(
                "The opening statement clearly establishes PitchPilot as an on-device AI sales coach "
                "for InstaLILY sales reps. The privacy angle is immediately clear."
            ),
            suggestion=None,
            timestamp=15.0,
            live=True,
            cue_hint=None,
        ),
        # Compliance — warning → earpiece cue at 0:48
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="Integration claim lacks technical detail",
            detail=(
                "The claim about 'seamless integration' with SAP and Oracle is vague. "
                "Ops managers will immediately ask for specifics about data mapping, transformation, "
                "timeline, and cost."
            ),
            suggestion="Prepare detailed answers about ETL processes, data mapping, and integration timelines before making this claim.",
            timestamp=48.0,
            claim_id=claim_integration.id,
            live=True,
            cue_hint="integration detail needed",
        ),
        # Persona — critical → earpiece cue at 1:12
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.CRITICAL,
            title="Ops Manager: integration question incoming",
            detail=(
                "An ops manager will challenge the SAP/Oracle integration claim. "
                "They need specifics on data mapping, transformation processes, timeline, and cost."
            ),
            suggestion="Be ready with: phased integration strategy, ETL tool details, 6-8 week pilot timeline, $15K-$30K cost estimate.",
            timestamp=72.0,
            persona="ops_manager",
            live=True,
            cue_hint="integration question likely",
        ),
        # Persona — critical → earpiece cue at 1:35
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.CRITICAL,
            title="Investor: ROI guarantee needs quantification",
            detail=(
                "An investor will challenge the ROI guarantee. They need to know what 'ROI' means "
                "quantitatively and see case studies demonstrating consistent achievement."
            ),
            suggestion="Prepare: define ROI as 15-20% increase in close rates, reference beta testing data, offer to share case studies post-demo.",
            timestamp=95.0,
            persona="investor",
            live=True,
            cue_hint="ROI question incoming",
        ),
        # Coach — info → deferred
        Finding(
            agent=AgentType.COACH,
            severity=Severity.INFO,
            title="Real-time processing claim is strong",
            detail=(
                "The claim about 'no latency' real-time processing is compelling and differentiates "
                "PitchPilot from batch-processing alternatives."
            ),
            suggestion=None,
            timestamp=98.0,
            claim_id=claim_realtime.id,
            live=True,
            cue_hint=None,
        ),
        # Compliance — warning → earpiece cue at 2:22
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="CTO: technical architecture question anticipated",
            detail=(
                "A CTO will ask about the specific on-device ML model architecture and how privacy "
                "concerns around continuous sales data collection are addressed."
            ),
            suggestion="Prepare: FunctionGemma architecture details, federated learning approach, encryption (in transit and at rest), data anonymization policy, opt-out controls.",
            timestamp=142.0,
            persona="cto",
            live=True,
            cue_hint="technical deep dive likely",
        ),
        # Coach — warning → deferred
        Finding(
            agent=AgentType.COACH,
            severity=Severity.WARNING,
            title="40% deal closure claim needs context",
            detail=(
                "The '40% more enterprise deals' claim is bold but lacks context about baseline metrics, "
                "deal size, sales cycle duration, and customer acquisition costs."
            ),
            suggestion="Add context: 'Based on simulations and beta testing with InstaLILY's typical sales cycle and deal size.'",
            timestamp=168.0,
            claim_id=claim_deals.id,
            live=True,
            cue_hint=None,
        ),
    ]


def _demo_live_remote_claims() -> list[Claim]:
    """Claims from an 8:15 live remote session with screen share."""
    return [
        Claim(
            text="PitchPilot analyzes your pitch in 90 seconds — fully automated, no manual review required.",
            claim_type=ClaimType.FEATURE,
            timestamp=45.0,
            source="both",
            slide_number=2,
            confidence=0.93,
        ),
        Claim(
            text="PitchPilot runs entirely on-device — your pitch data never leaves your computer.",
            claim_type=ClaimType.PRIVACY,
            timestamp=130.0,
            source="slide",
            slide_number=4,
            confidence=0.89,
        ),
        Claim(
            text="We use Gemma 3n and FunctionGemma — state-of-the-art on-device AI models.",
            claim_type=ClaimType.FEATURE,
            timestamp=200.0,
            source="both",
            slide_number=4,
            confidence=0.91,
        ),
        Claim(
            text="PitchPilot provides real-time coaching cues during live presentations.",
            claim_type=ClaimType.FEATURE,
            timestamp=255.0,
            source="transcript",
            slide_number=6,
            confidence=0.81,
        ),
        Claim(
            text="PitchPilot setup takes under one hour for any user.",
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
    claim_privacy   = claims[1]
    claim_models    = claims[2]
    claim_coaching  = claims[3]
    claim_setup     = claims[4]

    return [
        # Coach — positive, deferred
        Finding(
            agent=AgentType.COACH,
            severity=Severity.INFO,
            title="Opening hook strong — preserve for all audiences",
            detail=(
                "The opening 45 seconds established clear stakes and framed the problem PitchPilot solves "
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
                "Slide 2 and transcript both claim PitchPilot is 'fully automated — no manual review.' "
                "Policy §3.2 mandates human review above a 0.95 confidence threshold. "
                "This will derail a compliance-focused audience."
            ),
            suggestion="Rephrase to: 'PitchPilot is automated with optional human-in-the-loop review for high-stakes decisions.'",
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
            suggestion="Lead with the outcome ('PitchPilot analyzes your pitch in 90 seconds') before explaining the mechanism.",
            timestamp=130.0,
            live=True,
            cue_hint="simplify slide",
        ),
        # Compliance — warning → overlay card at 3:20
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="On-device privacy claim needs technical clarification",
            detail=(
                "The claim that 'pitch data never leaves your computer' is strong but needs clarification "
                "about how PitchPilot processes data locally. Does this include model inference, or just storage?"
            ),
            suggestion="Clarify: 'All pitch analysis runs locally on your device. No video or transcript data is sent to external servers.'",
            timestamp=200.0,
            claim_id=claim_privacy.id,
            policy_reference="Privacy Disclosure Policy §1.1 — Accurate Representation",
            live=True,
            cue_hint="clarify privacy",
        ),
        # Persona — info, deferred (positive signal)
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.INFO,
            title="Technical Reviewer: model specificity is credible",
            detail=(
                "The Technical Reviewer persona found the mention of Gemma 3n, "
                "FunctionGemma, and LoRA fine-tuning in the PitchPilot pitch reassuring and technically credible."
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
            title="Real-time coaching feature needs demonstration",
            detail=(
                "The claim about 'real-time coaching cues' is compelling but wasn't demonstrated. "
                "Technical reviewers on the call will immediately ask how PitchPilot's coaching works."
            ),
            suggestion="Add a live demo or video showing PitchPilot's earpiece cues during a presentation.",
            timestamp=255.0,
            claim_id=claim_coaching.id,
            live=True,
            cue_hint="demonstrate coaching",
        ),
        # Persona — warning → overlay card at 5:00
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Skeptical Investor: ChatGPT differentiation question incoming",
            detail=(
                "The PitchPilot presentation has not yet explained why on-device matters vs. "
                "a compliance-aware GPT-4o wrapper. Expect this question from investors."
            ),
            suggestion="Prepare: 'ChatGPT requires sending your pitch to the cloud and has no sales-specific fine-tuning. PitchPilot runs entirely locally.'",
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
                "The jump from the PitchPilot live demo to the business model slide felt unanchored. "
                "No bridging sentence to orient the audience."
            ),
            suggestion="Add: 'What you just saw is PitchPilot's core product. Here's how we monetize it.'",
            timestamp=370.0,
            live=True,
            cue_hint="add bridge",
        ),
        # Compliance — warning → overlay card at 6:45
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="Model names need context for non-technical audiences",
            detail=(
                "Mentioning 'Gemma 3n and FunctionGemma' is technically credible but may confuse non-technical investors. "
                "The value proposition should come first."
            ),
            suggestion="Lead with: 'PitchPilot uses state-of-the-art on-device AI' before naming specific models.",
            timestamp=405.0,
            claim_id=claim_models.id,
            policy_reference="Approved Messaging Guide — Technical Terminology",
            live=True,
            cue_hint="simplify model names",
        ),
        # Persona — warning → overlay card at 7:20
        Finding(
            agent=AgentType.PERSONA,
            severity=Severity.WARNING,
            title="Procurement Manager: TCO and integration path not addressed",
            detail=(
                "Eight minutes in and no mention of three-year cost or CRM integrations. "
                "A Procurement Manager will block sign-off without this — address it before close."
            ),
            suggestion="Add a slide covering per-seat pricing, implementation timeline, and Salesforce/Gong integrations.",
            timestamp=440.0,
            persona="Procurement Manager",
            live=True,
            cue_hint="address TCO",
        ),
        # Compliance — info, deferred
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.INFO,
            title="Setup time claim should cite conditions",
            detail=(
                "'Under one hour' for PitchPilot setup is plausible for standard users but "
                "enterprise deployments typically require IT approval cycles. Worth qualifying."
            ),
            suggestion="Add 'for standard single-user deployment' to the one-hour claim.",
            timestamp=330.0,
            claim_id=claim_setup.id,
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
            score=75,
            rationale="Structure and flow are solid but integration and ROI claims need more detail.",
        ),
        DimensionScore(
            dimension="Compliance",
            score=70,
            rationale="Privacy and on-device claims are strong but need technical clarification for CTO-level audiences.",
        ),
        DimensionScore(
            dimension="Defensibility",
            score=65,
            rationale="ROI guarantee and 40% deal closure claims need quantified context and case study support.",
        ),
        DimensionScore(
            dimension="Persuasiveness",
            score=78,
            rationale="Clear value proposition and unique differentiation are strong, but integration vagueness weakens credibility.",
        ),
    ]
    overall = round(sum(d.score for d in dimensions) / len(dimensions))
    score = ReadinessScore(
        overall=overall,
        dimensions=dimensions,
        priority_fixes=[
            "Develop a Detailed Integration Case Study: Create a concise, one-page document outlining the proposed SAP/Oracle integration process, including data mapping, transformation steps, and timeline.",
            "Quantify InstaLILY's ROI: Replace the blanket \"40%\" claim with a more targeted ROI projection based on typical InstaLILY sales metrics. Provide a range and clearly define the assumptions.",
            "Prepare a Privacy FAQ: Draft a short FAQ addressing potential privacy concerns regarding data collection and model usage, demonstrating transparency and proactive measures.",
        ],
    )

    mode_label = "live in-room" if mode == SessionMode.LIVE_IN_ROOM else "live remote"
    duration_str = f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}"
    live_summary = (
        f"{duration_str} {mode_label} session. "
        f"{cues_count} real-time cues delivered during the PitchPilot presentation. "
        f"Three critical interruptions occurred from ops_manager, investor, and cto personas, "
        f"highlighting the need for more detailed integration specifications, quantified ROI metrics, "
        f"and technical architecture documentation. The readiness report identifies key areas for improvement "
        f"including integration case studies, ROI quantification, and privacy FAQ preparation."
    )

    return ReadinessReport(
        session_id=session_id,
        score=score,
        findings=findings,
        persona_questions=_demo_persona_questions(),
        claims=claims,
        summary=(
            "## Readiness Score: 6/10\n\n"
            "## ✅ What's Working\n"
            "*   **Clear Value Proposition:** The core benefit – increased deal closure rates – \"InstaLILY sales reps will close 40% more enterprise deals\" – is immediately understandable and impactful.\n"
            "*   **Unique Differentiation:** The emphasis on \"on-device AI sales coaching\" and \"domain-trained\" sets PitchPilot apart from generic AI solutions and highlights a key technical advantage.\n"
            "*   **Specific ROI Claim:** Guaranteeing ROI within 90 days, paired with a concrete percentage, provides a tangible target for the customer.\n\n\n"
            "## ⚠️ Weak Points\n"
            "*   **Data Integration Vagueness:** The pitch glosses over the complexities of SAP and Oracle integration, which is a significant hurdle for large enterprises. \"Seamless integration\" lacks detail and appears to overpromise.\n"
            "*   **Quantified ROI Ambiguity:** \"Guaranteeing ROI\" and the 40% deal closure rate feels speculative without deeper context around InstaLILY's typical sales cycle, average deal size, and customer acquisition costs.\n"
            "*   **Technical Detail Shortfall:** The mention of FunctionGemma and its performance improvement is impressive but requires further explanation to establish credibility, especially regarding the privacy concerns.\n\n\n"
            "## ❓ Objections You Must Prepare For\n"
            "*   **[OPS_MANAGER]: \"That's a bold claim – can you specifically detail the data mapping and transformation processes required to ensure accurate, real-time synchronization between this system and *both* SAP and Oracle, and what's the estimated timeline and cost for that integration?\"**\n"
            "    *   **Suggested Answer:** \"Absolutely. We recognize that data integration is critical. Our team is already developing a phased integration strategy, starting with prioritized data fields – specifically order history, customer contacts, and pricing. We use a robust ETL process utilizing [Name a specific ETL tool, e.g., Fivetran] to map and transform data.  We estimate a 6-8 week initial integration for a pilot group, with a cost of [State a realistic estimated cost range, e.g., $15,000 - $30,000] for development and configuration.  We can provide a detailed technical specification document post-demo if that's helpful.\"\n\n"
            "*   **[INVESTOR]: \"Guaranteeing ROI is a bold claim – can you quantify what 'ROI' actually means for a typical InstaLILY customer and demonstrate how you've achieved this consistently across at least three separate case studies?\"**\n"
            "    *   **Suggested Answer:** \"You're right to challenge that. For a typical InstaLILY customer, ROI translates to an average of a 15-20% increase in close rates, based on our simulations and early beta testing. We're currently compiling three detailed case studies with pilot customers that demonstrate this – we'll share the full documentation after the demo, including projected revenue increases and cost savings. We can also discuss a tailored ROI projection based on your specific sales data.\"\n\n"
            "*   **[CTO]: That's a bold claim. Can you detail the specific on-device machine learning model architecture you're utilizing, and how you've addressed potential privacy concerns related to continuous sales data collection?**\n"
            "    *   **Suggested Answer:** \"Our model is based on a FunctionGemma architecture, but it's been significantly finetuned for enterprise sales objection detection. We employ a federated learning approach where the model updates are generated locally on each rep's laptop, minimizing data transfer. All data is encrypted both in transit and at rest, and we operate under a strict data anonymization policy. Reps retain full control over their data and can opt-out at any time. We can provide a more technical deep dive during a follow-up session.\"\n\n\n\n"
            "## 🎯 Top 3 Things To Fix Before The Real Demo\n"
            "1.  **Develop a Detailed Integration Case Study:** Create a concise, one-page document outlining the proposed SAP/Oracle integration process, including data mapping, transformation steps, and timeline.\n"
            "2.  **Quantify InstaLILY's ROI:**  Replace the blanket \"40%\" claim with a more targeted ROI projection based on typical InstaLILY sales metrics. Provide a range and clearly define the assumptions.\n"
            "3.  **Prepare a Privacy FAQ:** Draft a short FAQ addressing potential privacy concerns regarding data collection and model usage, demonstrating transparency and proactive measures."
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
        cues = 3
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
        default="Skeptical Investor,Technical Reviewer,Procurement Manager",
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
        else ["Skeptical Investor", "Technical Reviewer", "Procurement Manager"]
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
        else ["Skeptical Investor", "Technical Reviewer", "Procurement Manager"]
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

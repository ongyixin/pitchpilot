"""
Audience Persona Simulator agent.

Role-plays as configurable stakeholder personas and generates the questions,
objections, and challenges each persona would raise after hearing the pitch.

Personas (configurable via PipelineContext.personas):
  - Skeptical Investor
  - Technical Reviewer
  - Procurement Manager
  - Friendly Customer
  - Confused First-Time User

Powered by Gemma 3 4B via Ollama.
Prompt: backend/prompts/persona_system.txt
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from backend.agents.base import BaseAgent
from backend.config import AGENT_MIN_CONFIDENCE_PERSONA, DEFAULT_PERSONAS, PROMPT_FILES, settings
from backend.models.base import BaseTextModel
from backend.schemas import Claim, Finding, PersonaQuestion, PipelineContext

# ---------------------------------------------------------------------------
# Mock data — one rich set of questions per default persona
# ---------------------------------------------------------------------------

_MOCK_PERSONA_DATA: dict[str, dict[str, Any]] = {
    "Skeptical Investor": {
        "persuasiveness_rating": 6,
        "persuasiveness_note": "Strong problem framing but differentiation from general-purpose AI tools needs more work.",
        "questions": [
            {
                "question": "How is this actually different from putting my rehearsal video into ChatGPT or Gemini?",
                "question_type": "hostile",
                "difficulty": "hard",
                "context": "Investor immediately compares to lowest-cost alternative.",
                "suggested_answer": (
                    "ChatGPT can't watch your actual rehearsal in real time on-device with zero data egress. "
                    "PitchPilot is purpose-built: it runs three specialized models locally, "
                    "understands compliance policy context, and gives structured readiness scores — "
                    "not a free-form chat response."
                ),
                "timestamp_hint": 225.0,
            },
            {
                "question": "What's the actual revenue model here? Is this SaaS per seat, per usage, or something else?",
                "question_type": "clarification",
                "difficulty": "medium",
                "context": "Investor needs to see a clear monetization path.",
                "suggested_answer": (
                    "Per-seat SaaS at $49/mo per rep, with enterprise tier for compliance-sensitive industries "
                    "including policy document management and team analytics. "
                    "Land with one sales team, expand to the org."
                ),
                "timestamp_hint": None,
            },
            {
                "question": "What's your competitive moat once Google or Microsoft builds this into their existing tools?",
                "question_type": "challenge",
                "difficulty": "hard",
                "context": "Long-term defensibility concern.",
                "suggested_answer": (
                    "On-device + compliance-policy integration is the moat. "
                    "Enterprise sales teams won't send rehearsal recordings with unreleased pricing to Microsoft. "
                    "Our advantage is data locality + domain-specific fine-tuning on sales and compliance language."
                ),
                "timestamp_hint": None,
            },
            {
                "question": "What's your current ARR and how many paying customers do you have?",
                "question_type": "clarification",
                "difficulty": "easy",
                "context": "Traction check — baseline investor question.",
                "suggested_answer": (
                    "We're in private beta with 5 enterprise design partners. "
                    "Focus this week is product-market fit validation before opening the waitlist."
                ),
                "timestamp_hint": None,
            },
        ],
    },
    "Technical Reviewer": {
        "persuasiveness_rating": 7,
        "persuasiveness_note": "Technical claims are interesting but unverified. On-device inference architecture needs more detail.",
        "questions": [
            {
                "question": "You said inference runs in under 100ms on any modern laptop — what model size and quantization are you using?",
                "question_type": "challenge",
                "difficulty": "hard",
                "context": "Technical reviewer will probe latency claims immediately.",
                "suggested_answer": (
                    "Gemma 3 4B at 4-bit quantization via Ollama. "
                    "Sub-100ms is for the routing layer (FunctionGemma 270M). "
                    "Full agent analysis takes 2-8 seconds per claim — we've been transparent about that."
                ),
                "timestamp_hint": 145.0,
            },
            {
                "question": "If everything is on-device, how do you handle model updates without sending data through the cloud?",
                "question_type": "clarification",
                "difficulty": "medium",
                "context": "Ops complexity of on-device ML.",
                "suggested_answer": (
                    "Models are updated via signed model packages distributed through our update channel. "
                    "No user data is sent — only the model weights are downloaded, "
                    "similar to how OS updates work."
                ),
                "timestamp_hint": None,
            },
            {
                "question": "How does your fine-tuned routing model actually improve over zero-shot function calling?",
                "question_type": "challenge",
                "difficulty": "hard",
                "context": "Legitimacy of the fine-tuning claim.",
                "suggested_answer": (
                    "FunctionGemma fine-tuned on our specific tool surface (6 functions, "
                    "80 training examples) achieves 94% routing accuracy vs 71% zero-shot "
                    "on our evaluation set. It also uses 270M params vs 4B for routing — "
                    "10x faster dispatch."
                ),
                "timestamp_hint": None,
            },
        ],
    },
    "Procurement Manager": {
        "persuasiveness_rating": 6,
        "persuasiveness_note": "Strong use-case fit, but total cost of ownership and integration complexity need to be quantified before this goes to budget approval.",
        "questions": [
            {
                "question": "What's the all-in cost over three years — licences, implementation, training, and support?",
                "question_type": "clarification",
                "difficulty": "hard",
                "context": "Procurement needs a fully-loaded TCO number, not just per-seat price.",
                "suggested_answer": (
                    "Per-seat SaaS at $49/mo with no implementation fee — it's self-serve onboarding. "
                    "Enterprise tier includes dedicated CSM and policy document management. "
                    "Three-year TCO for a 50-rep team runs roughly $88k, with measurable time savings "
                    "our design partners report at ~2 hours per rep per week in prep time."
                ),
                "timestamp_hint": None,
            },
            {
                "question": "How does this integrate with our existing CRM and sales enablement stack — Salesforce, Gong, Highspot?",
                "question_type": "challenge",
                "difficulty": "hard",
                "context": "Procurement evaluates integration risk and hidden engineering costs.",
                "suggested_answer": (
                    "Current integrations: Salesforce opportunity sync for session tagging, "
                    "and Gong call import for post-call rehearsal. "
                    "Highspot is on our H2 roadmap. "
                    "The on-device architecture means no middleware — "
                    "the desktop client connects directly to your CRM via OAuth."
                ),
                "timestamp_hint": 200.0,
            },
            {
                "question": "What are your contract terms — minimum commitment, auto-renewal, and what happens to our data if we cancel?",
                "question_type": "clarification",
                "difficulty": "medium",
                "context": "Standard vendor lock-in and exit-cost evaluation.",
                "suggested_answer": (
                    "Annual commitment, 30-day cancellation notice before renewal. "
                    "On cancellation, all session data is purged within 14 days — "
                    "you can export a full JSON archive at any time from the dashboard. "
                    "No lock-in: the export format is documented and open."
                ),
                "timestamp_hint": None,
            },
            {
                "question": "Can you give me a reference customer in our industry with a quantified ROI?",
                "question_type": "challenge",
                "difficulty": "hard",
                "context": "Procurement requires proof of value from a comparable organisation.",
                "suggested_answer": (
                    "We have two design partners in enterprise SaaS sales happy to speak with you. "
                    "Their reported outcomes: 18% increase in first-call-to-demo conversion and "
                    "a 40% reduction in manager rehearsal-coaching hours per quarter. "
                    "I'll send an intro email today — we can schedule a 30-minute reference call."
                ),
                "timestamp_hint": None,
            },
        ],
    },
}


class PersonaAgent(BaseAgent):
    """
    Audience Persona Simulator.

    For each active persona, generates a set of questions and objections
    grounded in the pitch content. Returns findings with embedded
    PersonaQuestion objects in the metadata.
    """

    name = "persona"
    prompt_file = PROMPT_FILES.get("persona_system")
    min_confidence: float = AGENT_MIN_CONFIDENCE_PERSONA

    def __init__(self, client: Optional[BaseTextModel] = None) -> None:
        super().__init__(client)

    # ------------------------------------------------------------------
    # Build prompt for a specific persona + claim
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        context: PipelineContext,
        claim: Optional[Claim] = None,
        persona: Optional[str] = None,
    ) -> str:
        active_persona = persona or (context.personas[0] if context.personas else DEFAULT_PERSONAS[0])

        parts = [f"PERSONA: {active_persona}\n"]

        if context.presentation_title:
            parts.append(f"PRESENTATION: {context.presentation_title}\n")

        if claim:
            parts.append("PITCH CONTENT TO REACT TO:")
            parts.append(self._claim_context_block(claim))
        else:
            transcript = context.full_transcript
            if transcript:
                parts.append(f"PITCH TRANSCRIPT:\n{transcript[:3000]}")

        parts.append(
            f"\nAs a {active_persona}, what questions and objections would you raise? "
            "Return JSON as specified in your instructions."
        )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Override analyze to iterate over all personas
    # ------------------------------------------------------------------

    async def analyze(
        self,
        context: PipelineContext,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        """Run persona simulation for all configured personas in parallel."""
        if self.is_mock:
            return self.mock_findings(context, claim)

        personas = context.personas
        if not personas:
            return []

        async def _run_persona(persona_name: str) -> list[Finding]:
            import json as _json
            import logging as _logging
            prompt = self.build_prompt(context, claim, persona=persona_name)
            timeout = settings.agent_per_call_timeout_seconds
            try:
                raw_str = await asyncio.wait_for(
                    self._client.generate(
                        prompt=prompt,
                        system=self.system_prompt,
                        response_format="json",
                    ),
                    timeout=timeout,
                )
                try:
                    raw = _json.loads(raw_str)
                except _json.JSONDecodeError:
                    raw = {}
                return self._parse_persona_response(raw, persona_name, claim)
            except asyncio.TimeoutError:
                _logging.getLogger(__name__).warning(
                    f"Persona {persona_name!r} timed out after {timeout:.0f}s — skipping"
                )
                return []
            except Exception as e:
                _logging.getLogger(__name__).error(f"Persona {persona_name} error: {e}")
                return self._mock_persona_findings(persona_name, claim)

        results = await asyncio.gather(*[_run_persona(p) for p in personas], return_exceptions=True)
        findings: list[Finding] = []
        for r in results:
            if isinstance(r, list):
                findings.extend(r)
        return findings

    # ------------------------------------------------------------------
    # Prompt building (required by BaseAgent)
    # ------------------------------------------------------------------

    # analyze() is fully overridden, build_prompt only called for single-persona mode
    # the signature matches BaseAgent's abstract method

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def parse_response(
        self,
        raw: dict[str, Any] | str,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        persona = raw.get("persona", "Unknown") if isinstance(raw, dict) else "Unknown"
        return self._parse_persona_response(raw, persona, claim)

    def _parse_persona_response(
        self,
        raw: dict[str, Any] | str,
        persona_name: str,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        if isinstance(raw, str):
            return self._mock_persona_findings(persona_name, claim)

        findings: list[Finding] = []
        questions = raw.get("questions", [])
        rating = raw.get("persuasiveness_rating", 5)

        for q in questions:
            pq = PersonaQuestion(
                persona=persona_name,
                question=q.get("question", ""),
                question_type=q.get("question_type", "clarification"),
                difficulty=q.get("difficulty", "medium"),
                timestamp=self._parse_timestamp(q.get("timestamp_hint")),
                suggested_answer=q.get("suggested_answer"),
                finding_id=None,
            )
            finding = Finding(
                agent="persona",
                category="persona_question",
                severity=self._question_severity(q.get("difficulty", "medium")),
                title=f"{persona_name}: {q.get('question', '')[:60]}",
                description=q.get("question", ""),
                suggestion=q.get("suggested_answer"),
                timestamp=self._parse_timestamp(q.get("timestamp_hint")),
                claim_ref=claim.id if claim else None,
                metadata={
                    "persona": persona_name,
                    "question_type": q.get("question_type", "clarification"),
                    "difficulty": q.get("difficulty", "medium"),
                    "persuasiveness_rating": rating,
                    "persona_question": pq.to_dict(),
                },
            )
            findings.append(finding)

        return findings

    def _question_severity(self, difficulty: str) -> str:
        return {"hard": "critical", "medium": "warning", "easy": "info"}.get(difficulty, "info")

    # ------------------------------------------------------------------
    # Mock fallback
    # ------------------------------------------------------------------

    def mock_findings(
        self,
        context: PipelineContext,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        personas = context.personas
        if not personas:
            return []
        findings: list[Finding] = []
        for persona_name in personas:
            findings.extend(self._mock_persona_findings(persona_name, claim))
        return findings

    def _mock_persona_findings(
        self,
        persona_name: str,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        data = _MOCK_PERSONA_DATA.get(persona_name)
        if not data:
            # Generate a generic finding for unknown personas
            return [
                Finding(
                    agent="persona",
                    category="persona_question",
                    severity="warning",
                    title=f"{persona_name}: How does this benefit me specifically?",
                    description=f"As a {persona_name}, I need to understand the concrete value before committing.",
                    suggestion="Prepare a tailored value statement for this audience type.",
                    claim_ref=claim.id if claim else None,
                    metadata={"persona": persona_name, "question_type": "clarification", "difficulty": "medium"},
                )
            ]

        findings: list[Finding] = []
        for q in data["questions"]:
            pq = PersonaQuestion(
                persona=persona_name,
                question=q["question"],
                question_type=q["question_type"],
                difficulty=q["difficulty"],
                timestamp=self._parse_timestamp(q.get("timestamp_hint")),
                suggested_answer=q.get("suggested_answer"),
                finding_id=None,
            )
            finding = Finding(
                agent="persona",
                category="persona_question",
                severity=self._question_severity(q["difficulty"]),
                title=f"{persona_name}: {q['question'][:60]}",
                description=q["question"],
                suggestion=q.get("suggested_answer"),
                timestamp=self._parse_timestamp(q.get("timestamp_hint")),
                claim_ref=claim.id if claim else None,
                metadata={
                    "persona": persona_name,
                    "question_type": q["question_type"],
                    "difficulty": q["difficulty"],
                    "persuasiveness_rating": data["persuasiveness_rating"],
                    "persona_note": data["persuasiveness_note"],
                    "persona_question": pq.to_dict(),
                },
            )
            findings.append(finding)
        return findings

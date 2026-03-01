"""
Presentation Coach agent.

Evaluates clarity, structure, narrative flow, pacing, and specificity
of a pitch section. Powered by Gemma 3 4B via Ollama.

Prompt: backend/prompts/coach_system.txt (edit to tune behavior)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from backend.agents.base import BaseAgent
from backend.config import PROMPT_FILES
from backend.models.base import BaseTextModel
from backend.schemas import Claim, Finding, PipelineContext

# ---------------------------------------------------------------------------
# Mock findings — realistic examples for development / no-GPU demos
# ---------------------------------------------------------------------------

_MOCK_FINDINGS: list[dict[str, Any]] = [
    {
        "category": "structure",
        "severity": "warning",
        "title": "Problem statement introduced too late",
        "description": (
            "The presenter jumped to the solution demo before clearly stating the problem. "
            "The audience needs to feel the pain before they can appreciate the cure."
        ),
        "suggestion": (
            "Open with a concrete 30-second problem narrative (a specific customer story works well) "
            "before showing the product."
        ),
        "timestamp_hint": 12.0,
    },
    {
        "category": "clarity",
        "severity": "warning",
        "title": "Value proposition is vague",
        "description": (
            "The claim 'saves your team hours every week' lacks specificity. "
            "Without a number or example, it sounds like marketing copy."
        ),
        "suggestion": (
            "Replace with a quantified claim: 'In our pilot, teams cut prep time by 3 hours per pitch.' "
            "If you don't have data yet, say 'our beta users report saving 2–4 hours'."
        ),
        "timestamp_hint": 45.0,
    },
    {
        "category": "narrative_flow",
        "severity": "warning",
        "title": "Abrupt transition into the demo",
        "description": (
            "The transition from the privacy slide to the live demo was sudden — "
            "'And now let me show you...' without framing what the audience will see."
        ),
        "suggestion": (
            "Add a one-sentence setup before the demo: "
            "'To make this concrete, I'll walk through exactly what happens when you upload a rehearsal.'"
        ),
        "timestamp_hint": 155.0,
    },
    {
        "category": "clarity",
        "severity": "info",
        "title": "Strong problem framing in opening",
        "description": (
            "The 67% stat on the problem slide is compelling and grounded. "
            "The opening resonates — the audience immediately understands the gap."
        ),
        "suggestion": None,
        "timestamp_hint": 30.0,
    },
    {
        "category": "specificity",
        "severity": "critical",
        "title": "Differentiation not clearly stated",
        "description": (
            "The presenter mentioned being 'unlike ChatGPT or Copilot' but never explained "
            "what specifically makes PitchPilot different. Savvy audiences will push on this."
        ),
        "suggestion": (
            "Prepare a crisp one-liner: 'Unlike general-purpose AI, PitchPilot is purpose-built for "
            "pre-meeting stress testing and runs 100% locally — no data leaves your device.'"
        ),
        "timestamp_hint": 225.0,
    },
]


class CoachAgent(BaseAgent):
    """
    Presentation Coach agent.

    Evaluates a pitch section or claim for:
    - Clarity and specificity
    - Narrative structure and flow
    - Transition quality
    - Jargon / accessibility
    - Pacing signals
    """

    name = "coach"
    prompt_file = PROMPT_FILES.get("coach_system")

    def __init__(self, client: Optional[BaseTextModel] = None) -> None:
        super().__init__(client)

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def build_prompt(self, context: PipelineContext, claim: Optional[Claim] = None) -> str:
        parts: list[str] = []

        if context.presentation_title:
            parts.append(f"PRESENTATION: {context.presentation_title}\n")

        if claim:
            parts.append("SECTION TO EVALUATE:")
            parts.append(self._claim_context_block(claim))
        else:
            # Full-transcript mode (called without a specific claim)
            transcript = context.full_transcript
            if transcript:
                parts.append(f"FULL TRANSCRIPT:\n{transcript[:3000]}")
            slide_text = context.full_slide_text
            if slide_text:
                parts.append(f"\nSLIDE CONTENT:\n{slide_text[:2000]}")

        parts.append(
            "\nAnalyze the above content for presentation quality. "
            "Return JSON findings as specified in your instructions."
        )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def parse_response(
        self,
        raw: dict[str, Any] | str,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        if isinstance(raw, str):
            return self.mock_findings(PipelineContext(), claim)

        findings: list[Finding] = []
        for item in raw.get("findings", []):
            findings.append(
                Finding(
                    agent="coach",
                    category=item.get("category", "clarity"),
                    severity=self._severity_from_str(item.get("severity", "info")),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion"),
                    timestamp=self._parse_timestamp(item.get("timestamp_hint")),
                    claim_ref=claim.id if claim else None,
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Mock fallback
    # ------------------------------------------------------------------

    def mock_findings(
        self,
        context: PipelineContext,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        for item in _MOCK_FINDINGS:
            f = Finding(
                agent="coach",
                category=item["category"],
                severity=item["severity"],
                title=item["title"],
                description=item["description"],
                suggestion=item.get("suggestion"),
                timestamp=item.get("timestamp_hint"),
                claim_ref=claim.id if claim else None,
            )
            findings.append(f)

        # If a specific claim was provided, return only the most relevant findings
        if claim:
            # Pick findings most relevant to the claim type
            relevant_categories = {
                "product": ["clarity", "specificity"],
                "technical": ["specificity", "clarity"],
                "comparison": ["specificity", "narrative_flow"],
                "compliance_sensitive": ["clarity"],
                "general": ["structure", "narrative_flow"],
            }
            preferred = relevant_categories.get(claim.claim_type, ["clarity"])
            scored = sorted(findings, key=lambda f: (0 if f.category in preferred else 1, f.severity == "info"))
            return scored[:3]

        return findings

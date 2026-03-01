"""
Compliance Reviewer agent.

Cross-checks claims against loaded policy documents and flags:
- Policy conflicts
- Overstatements (guaranteed, always, 100%, never)
- Missing disclaimers
- Unsubstantiated performance claims
- Privacy/security assertions

Powered by Gemma 3 4B via Ollama.
Prompt: backend/prompts/compliance_system.txt
"""

from __future__ import annotations

from typing import Any, Optional

from backend.agents.base import BaseAgent
from backend.config import PROMPT_FILES
from backend.models.base import BaseTextModel
from backend.schemas import Claim, Finding, PipelineContext

# ---------------------------------------------------------------------------
# Mock findings
# ---------------------------------------------------------------------------

_MOCK_FINDINGS: list[dict[str, Any]] = [
    {
        "category": "policy_conflict",
        "severity": "critical",
        "title": "Automation claim conflicts with manual review policy",
        "description": (
            "Presenter stated: 'Our platform is fully automated — no manual steps required.' "
            "Policy document states: 'Edge cases and high-value transactions require manual review "
            "by a qualified team member before processing.'"
        ),
        "policy_ref": "Section 3.2: Manual Review Requirements — High-value and edge-case transactions must undergo human review.",
        "suggestion": (
            "Reword to: 'Our platform automates the standard workflow — edge cases are flagged "
            "automatically for your team to review, reducing manual effort by 90%.'"
        ),
        "timestamp_hint": 45.0,
    },
    {
        "category": "overstatement",
        "severity": "critical",
        "title": "Absolute privacy claim is not fully accurate",
        "description": (
            "Presenter claimed: 'Nothing ever leaves the user's machine.' "
            "However, the architecture slide mentions 'optional cloud fallback for large models' — "
            "this directly contradicts the on-device only claim."
        ),
        "policy_ref": "Architecture slide text: 'Optional cloud fallback for model inference on low-end hardware.'",
        "suggestion": (
            "Change to: 'By default, all processing runs on-device. Cloud fallback is opt-in "
            "and disabled by default — your data stays local unless you choose otherwise.'"
        ),
        "timestamp_hint": 78.0,
    },
    {
        "category": "unsubstantiated",
        "severity": "warning",
        "title": "10x performance claim needs a source",
        "description": (
            "Claim: 'We achieve 10x faster processing than traditional rule-based systems.' "
            "No benchmark, methodology, or sample size is cited. In investor or enterprise contexts, "
            "this will be challenged."
        ),
        "policy_ref": None,
        "suggestion": (
            "Add context: '10x faster in our internal benchmark on a 30-slide deck — details in the appendix.' "
            "Alternatively, say 'significantly faster' and be ready to show the data."
        ),
        "timestamp_hint": 112.0,
    },
    {
        "category": "missing_disclaimer",
        "severity": "warning",
        "title": "GDPR compliance claim needs qualification",
        "description": (
            "Slide states: 'GDPR-Compliant out of the box.' GDPR compliance depends on "
            "deployment configuration, data residency, and customer's own DPA obligations — "
            "a blanket claim is misleading."
        ),
        "policy_ref": None,
        "suggestion": (
            "Change to: 'Designed for GDPR-compatible deployments. Contact us for a data processing "
            "addendum and compliance documentation.'"
        ),
        "timestamp_hint": 160.0,
    },
    {
        "category": "overstatement",
        "severity": "warning",
        "title": "99% accuracy claim is too broad",
        "description": (
            "'Our accuracy rate is 99% across all supported languages.' "
            "This is an extraordinary claim that requires specificity about task, dataset, "
            "and measurement methodology. 'All supported languages' is vague."
        ),
        "policy_ref": None,
        "suggestion": (
            "Specify: '99% claim extraction accuracy on English-language sales pitches in our evaluation set. "
            "Accuracy varies by language and domain — see our evaluation report.'"
        ),
        "timestamp_hint": 190.0,
    },
]


class ComplianceAgent(BaseAgent):
    """
    Compliance Reviewer agent.

    Evaluates claims against:
    - Loaded policy documents
    - Overstatement patterns (absolute language)
    - Missing disclaimer requirements
    - Unsubstantiated performance assertions
    """

    name = "compliance"
    prompt_file = PROMPT_FILES.get("compliance_system")

    # Patterns that always trigger compliance review regardless of claim type
    HIGH_RISK_PATTERNS = [
        "fully automated", "no manual", "always", "never", "guaranteed",
        "100%", "zero risk", "instant approval", "no data leaves", "nothing ever",
        "GDPR", "compliant", "certified", "SOC 2", "99%", "10x", "fully private",
    ]

    def __init__(self, client: Optional[BaseTextModel] = None) -> None:
        super().__init__(client)

    # ------------------------------------------------------------------
    # Gate: only run on compliance-sensitive or high-risk claims
    # ------------------------------------------------------------------

    def should_run(self, context: PipelineContext, claim: Optional[Claim] = None) -> bool:
        if claim is None:
            return True  # full-context review
        if claim.claim_type in ("compliance_sensitive", "comparison", "product"):
            return True
        # Check for high-risk language patterns
        text_lower = claim.text.lower()
        return any(p.lower() in text_lower for p in self.HIGH_RISK_PATTERNS)

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def build_prompt(self, context: PipelineContext, claim: Optional[Claim] = None) -> str:
        parts: list[str] = []

        if context.policy_text:
            policy_excerpt = context.policy_text[:4000]
            parts.append(f"POLICY DOCUMENT:\n{policy_excerpt}\n")
        else:
            parts.append(
                "POLICY DOCUMENT: [Not provided — flag any claims that typically require policy backing]\n"
            )

        if claim:
            parts.append("CLAIM TO REVIEW:")
            parts.append(self._claim_context_block(claim))
            parts.append(f"\nClaim type: {claim.claim_type}")
        else:
            transcript = context.full_transcript
            if transcript:
                parts.append(f"FULL TRANSCRIPT TO REVIEW:\n{transcript[:3000]}")
            slide_text = context.full_slide_text
            if slide_text:
                parts.append(f"\nSLIDE TEXT:\n{slide_text[:2000]}")

        parts.append(
            "\nReview the above for compliance, policy conflicts, and risky claims. "
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
            metadata: dict = {}
            if item.get("policy_ref"):
                metadata["policy_ref"] = item["policy_ref"]
            overall_risk = raw.get("overall_risk_level", "medium")
            metadata["overall_risk_level"] = overall_risk

            findings.append(
                Finding(
                    agent="compliance",
                    category=item.get("category", "compliance"),
                    severity=self._severity_from_str(item.get("severity", "warning")),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion"),
                    timestamp=self._parse_timestamp(item.get("timestamp_hint")),
                    claim_ref=claim.id if claim else None,
                    metadata=metadata,
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
            metadata: dict = {}
            if item.get("policy_ref"):
                metadata["policy_ref"] = item["policy_ref"]

            f = Finding(
                agent="compliance",
                category=item["category"],
                severity=item["severity"],
                title=item["title"],
                description=item["description"],
                suggestion=item.get("suggestion"),
                timestamp=self._parse_timestamp(item.get("timestamp_hint")),
                claim_ref=claim.id if claim else None,
                metadata=metadata,
            )
            findings.append(f)

        # If a specific claim was provided, return the most relevant finding
        if claim:
            # Filter to findings most relevant to this claim's text
            text_lower = claim.text.lower()
            matched = [
                f for f in findings
                if any(kw in text_lower for kw in ["automat", "privacy", "gdpr", "compli", "10x", "99"])
            ]
            return matched[:2] if matched else findings[:2]

        return findings

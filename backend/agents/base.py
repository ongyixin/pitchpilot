"""
BaseAgent — the common interface all PitchPilot agents extend.

Design principles:
- Each agent owns its system prompt (loaded from prompts/)
- Each agent owns its mock data (fallback when model is unavailable)
- All agents return list[Finding] — the orchestrator doesn't care which agent ran
- analyze() is the single public interface; build_prompt() is the customization point
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from backend.config import settings
from backend.metrics import ConcurrencyLimiter
from backend.models.base import BaseTextModel
from backend.models.gemma3 import get_gemma3_adapter
from backend.schemas import Claim, Finding, PipelineContext

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base for all PitchPilot reasoning agents.

    Subclasses must implement:
      - build_prompt(context, claim)  → str  (user-facing prompt for the model)
      - parse_response(raw)           → list[Finding]
      - mock_findings(context, claim) → list[Finding]  (fallback data)

    Optional overrides:
      - system_prompt: str property (reads from prompts/ by default)
      - should_run(context, claim) → bool (gate logic for this agent)
    """

    name: str = "base"
    prompt_file: Optional[Path] = None  # set in subclass to auto-load system prompt

    def __init__(self, client: Optional[BaseTextModel] = None) -> None:
        self._client = client if client is not None else get_gemma3_adapter()
        self._system_prompt: Optional[str] = None
        self._limiter = ConcurrencyLimiter(settings.agent_concurrency)

    @property
    def is_mock(self) -> bool:
        return settings.mock_mode

    # ------------------------------------------------------------------
    # System prompt (loaded lazily from file)
    # ------------------------------------------------------------------

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            if self.prompt_file and self.prompt_file.exists():
                self._system_prompt = self.prompt_file.read_text()
            else:
                self._system_prompt = self._default_system_prompt()
        return self._system_prompt

    def _default_system_prompt(self) -> str:
        """Minimal fallback if no prompt file is found."""
        return (
            f"You are the {self.name} agent for PitchPilot. "
            "Analyze the provided pitch content and return structured JSON findings."
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def build_prompt(self, context: PipelineContext, claim: Optional[Claim] = None) -> str:
        """Build the user-facing prompt sent to Gemma 3."""
        ...

    @abstractmethod
    def parse_response(self, raw: dict[str, Any] | str, claim: Optional[Claim] = None) -> list[Finding]:
        """Parse the model response dict into Finding objects."""
        ...

    @abstractmethod
    def mock_findings(self, context: PipelineContext, claim: Optional[Claim] = None) -> list[Finding]:
        """Return realistic mock findings when the model is not available."""
        ...

    def should_run(self, context: PipelineContext, claim: Optional[Claim] = None) -> bool:
        """Optional gate: return False to skip this agent for a given claim."""
        return True

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def analyze(
        self,
        context: PipelineContext,
        claim: Optional[Claim] = None,
    ) -> list[Finding]:
        """
        Run the agent on the given context (and optional specific claim).

        Returns a list of Finding objects. On model failure, falls back to
        mock_findings() so the system keeps running.
        """
        if not self.should_run(context, claim):
            return []

        if self.is_mock:
            return self.mock_findings(context, claim)

        prompt = self.build_prompt(context, claim)

        try:
            import json as _json
            timeout = settings.agent_per_call_timeout_seconds
            try:
                raw_str = await asyncio.wait_for(
                    self._client.generate(
                        prompt=prompt,
                        system=self.system_prompt,
                        response_format="json",
                        max_tokens=640,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"{self.name} LLM call timed out after {timeout:.0f}s "
                    f"(claim={claim.id if claim else 'full'}) — using mock findings"
                )
                return self.mock_findings(context, claim)

            try:
                raw = _json.loads(raw_str)
            except _json.JSONDecodeError:
                import re
                match = re.search(r"\{.*\}", raw_str, re.DOTALL)
                raw = _json.loads(match.group()) if match else {}

            findings = self.parse_response(raw, claim)
            # Stamp the agent name and claim ref onto every finding
            for f in findings:
                f.agent = self.name  # type: ignore[assignment]
                if claim and not f.claim_ref:
                    f.claim_ref = claim.id
                if claim and f.timestamp is None:
                    f.timestamp = claim.timestamp
            return findings

        except Exception as e:
            logger.error(f"{self.name} agent error: {e} — using mock findings")
            return self.mock_findings(context, claim)

    async def analyze_batch(
        self,
        context: PipelineContext,
        claims: list[Claim],
    ) -> list[Finding]:
        """
        Run the agent on multiple claims with bounded concurrency.

        Uses ConcurrencyLimiter (settings.agent_concurrency) to avoid
        piling up unbounded Ollama requests.
        """
        coros = [self.analyze(context, claim) for claim in claims]
        results = await self._limiter.run_many(coros)
        findings: list[Finding] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"{self.name} batch error: {result}")
            elif isinstance(result, list):
                findings.extend(result)
        return findings

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _claim_context_block(claim: Claim) -> str:
        """Format a claim and its context into a readable prompt block."""
        parts = []
        if claim.context_before:
            parts.append(f"[Before]: {claim.context_before}")
        parts.append(f"[Claim]: {claim.text}")
        if claim.context_after:
            parts.append(f"[After]: {claim.context_after}")
        if claim.timestamp is not None:
            parts.append(f"[Timestamp]: {claim.timestamp:.1f}s")
        if claim.source != "transcript":
            parts.append(f"[Source]: {claim.source}")
        return "\n".join(parts)

    @staticmethod
    def _severity_from_str(s: str) -> str:
        s = s.lower().strip()
        if s in ("critical", "error", "high"):
            return "critical"
        if s in ("warning", "warn", "medium"):
            return "warning"
        return "info"

    @staticmethod
    def _parse_timestamp(v: object) -> Optional[float]:
        """Coerce a model-returned timestamp to float, tolerating an 's' suffix."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(str(v).rstrip("s"))
        except (ValueError, TypeError):
            return None

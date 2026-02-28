"""
PitchPilot Orchestrator.

Takes a PipelineContext (claims + transcript + OCR + policy text), routes each
claim through FunctionGemma, dispatches to the appropriate agents, collects
all findings, and generates timeline annotations.

Design:
  1. FunctionGemmaRouter decides which tools run per claim
  2. Agents run in parallel across all claims using asyncio.gather
  3. All findings are collected and deduplicated
  4. Timeline annotations are generated from findings that have timestamps
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from backend.agents.coach import CoachAgent
from backend.agents.compliance import ComplianceAgent
from backend.agents.persona import PersonaAgent
from backend.config import MAX_CLAIMS_PER_SESSION, settings
from backend.metrics import SessionMetrics, StageTimer
from backend.models.base import BaseTextModel
from backend.models.function_gemma import FunctionGemmaRouter
from backend.models.gemma3 import get_gemma3_adapter
from backend.schemas import (
    CATEGORY_COLOR,
    Claim,
    Finding,
    PipelineContext,
    RouterOutput,
    TimelineAnnotation,
    ToolCall,
)

ProgressCallback = Callable[[int, str], None]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Orchestrator result
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorResult:
    """Everything the orchestrator produces in a single pass."""

    session_id: str = ""
    findings: list[Finding] = field(default_factory=list)
    timeline: list[TimelineAnnotation] = field(default_factory=list)
    router_outputs: list[RouterOutput] = field(default_factory=list)
    agents_run: list[str] = field(default_factory=list)
    claims_processed: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """
    Central coordinator for the PitchPilot multi-agent pipeline.

    Usage:
        orchestrator = Orchestrator()
        await orchestrator.initialize()
        result = await orchestrator.run(context)
    """

    def __init__(
        self,
        gemma3_client: Optional[BaseTextModel] = None,
        router: Optional[FunctionGemmaRouter] = None,
    ) -> None:
        self._client = gemma3_client if gemma3_client is not None else get_gemma3_adapter()
        self._router = router or FunctionGemmaRouter()

        # Agents share the same Gemma3 client (they don't run simultaneously
        # on the same claim, but do run in parallel across different claims)
        self._coach = CoachAgent(client=self._client)
        self._compliance = ComplianceAgent(client=self._client)
        self._persona = PersonaAgent(client=self._client)

        self._initialized = False

    async def initialize(self) -> None:
        """Probe Ollama and load the router. Call once at startup."""
        if self._initialized:
            return

        from backend.config import settings
        # Probe availability if not already in mock mode
        if not settings.mock_mode and hasattr(self._client, "is_available"):
            available = await self._client.is_available()
            if not available:
                logger.warning("Orchestrator: Ollama unavailable — mock mode active")
        self._router.initialize()
        self._initialized = True

        from backend.config import settings as _s
        mode = "MOCK" if _s.mock_mode else "LIVE (Ollama)"
        router_mode = "rule-based" if self._router._use_rules else "FunctionGemma model"
        logger.info(f"Orchestrator initialized | model={mode} | router={router_mode}")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        context: PipelineContext,
        metrics: Optional[SessionMetrics] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> OrchestratorResult:
        """
        Full orchestration pass over a PipelineContext.

        Steps:
          1. Cap claims to MAX_CLAIMS_PER_SESSION
          2. Route each claim through FunctionGemma
          3. Group claims by agent
          4. Dispatch agents in parallel (Coach, Compliance, Persona skip in fast_mode)
          5. Deduplicate findings
          6. Generate timeline annotations

        Args:
            context: Full pipeline context (claims, transcript, OCR, policy).
            metrics: Optional SessionMetrics to record per-agent timing.
            progress_callback: Optional (pct, message) callback for frontend.
        """
        if not self._initialized:
            await self.initialize()

        result = OrchestratorResult(session_id=context.session_id)

        claims = context.claims[:MAX_CLAIMS_PER_SESSION]
        result.claims_processed = len(claims)

        # ------------------------------------------------------------------
        # Step 1: Route all claims
        # ------------------------------------------------------------------
        async with StageTimer("routing", metrics) as t:
            router_outputs = self._router.route_batch(claims)
            t.item_count = len(router_outputs)
        result.router_outputs = router_outputs

        routing_map: dict[str, RouterOutput] = {ro.claim_id: ro for ro in router_outputs}

        # ------------------------------------------------------------------
        # Step 2: Group claims by which agents should handle them
        # ------------------------------------------------------------------
        coach_claims: list[Claim] = []
        compliance_claims: list[Claim] = []
        persona_claims: list[Claim] = []

        for claim in claims:
            ro = routing_map.get(claim.id)
            if not ro:
                continue
            fn_names = {tc.function_name for tc in ro.tool_calls}
            if "coach_presentation" in fn_names:
                coach_claims.append(claim)
            if "check_compliance" in fn_names:
                compliance_claims.append(claim)
            if "simulate_persona" in fn_names:
                persona_claims.append(claim)

        # ------------------------------------------------------------------
        # Step 3: Dispatch agents in parallel with metrics
        # ------------------------------------------------------------------
        agents_run: set[str] = set()

        async def run_coach() -> list[Finding]:
            if not coach_claims and not context.full_transcript:
                return []
            agents_run.add("coach")
            if progress_callback:
                await _async_progress(progress_callback, 92, "Coach agent (5/7)")
            async with StageTimer("agent_coach", metrics) as t:
                if coach_claims:
                    result_list = await self._coach.analyze_batch(context, coach_claims)
                else:
                    result_list = await self._coach.analyze(context)
                t.item_count = len(result_list)
            return result_list

        async def run_compliance() -> list[Finding]:
            if not compliance_claims and not context.policy_text:
                return []
            agents_run.add("compliance")
            if progress_callback:
                await _async_progress(progress_callback, 94, "Compliance agent (6/7)")
            async with StageTimer("agent_compliance", metrics) as t:
                if compliance_claims:
                    result_list = await self._compliance.analyze_batch(context, compliance_claims)
                else:
                    result_list = await self._compliance.analyze(context)
                t.item_count = len(result_list)
            return result_list

        async def run_persona() -> list[Finding]:
            # Skip persona in fast mode
            if settings.fast_mode:
                return []
            if not persona_claims:
                if not context.full_transcript:
                    return []
            agents_run.add("persona")
            if progress_callback:
                await _async_progress(progress_callback, 96, "Persona agent (7/7)")
            async with StageTimer("agent_persona", metrics) as t:
                if persona_claims:
                    result_list = await self._persona.analyze_batch(context, persona_claims[:5])
                else:
                    result_list = await self._persona.analyze(context)
                t.item_count = len(result_list)
            return result_list

        coach_findings, compliance_findings, persona_findings = await asyncio.gather(
            run_coach(),
            run_compliance(),
            run_persona(),
            return_exceptions=True,
        )

        all_findings: list[Finding] = []
        for batch, label in [
            (coach_findings, "coach"),
            (compliance_findings, "compliance"),
            (persona_findings, "persona"),
        ]:
            if isinstance(batch, Exception):
                msg = f"{label} agent failed: {batch}"
                logger.error(msg)
                result.errors.append(msg)
            elif isinstance(batch, list):
                all_findings.extend(batch)

        # ------------------------------------------------------------------
        # Step 4: Deduplicate findings (by title + agent)
        # ------------------------------------------------------------------
        async with StageTimer("dedup_findings", metrics) as t:
            result.findings = _deduplicate_findings(all_findings)
            t.item_count = len(result.findings)
        result.agents_run = sorted(agents_run)

        # ------------------------------------------------------------------
        # Step 5: Generate timeline annotations
        # ------------------------------------------------------------------
        async with StageTimer("build_timeline", metrics) as t:
            result.timeline = _build_timeline(result.findings)
            t.item_count = len(result.timeline)

        logger.info(
            f"Orchestrator complete | claims={result.claims_processed} "
            f"findings={len(result.findings)} annotations={len(result.timeline)}"
        )
        return result

    # ------------------------------------------------------------------
    # Convenience: run a single claim through all relevant agents
    # ------------------------------------------------------------------

    async def run_claim(self, context: PipelineContext, claim: Claim) -> list[Finding]:
        """
        Process a single claim. Useful for streaming/live mode where claims
        arrive one at a time.
        """
        if not self._initialized:
            await self.initialize()

        ro = self._router.route(claim)
        fn_names = {tc.function_name for tc in ro.tool_calls}

        tasks: list[asyncio.Task] = []

        async def _safe(coro):
            try:
                return await coro
            except Exception as e:
                logger.error(f"Claim dispatch error: {e}")
                return []

        if "coach_presentation" in fn_names:
            tasks.append(asyncio.create_task(_safe(self._coach.analyze(context, claim))))
        if "check_compliance" in fn_names:
            tasks.append(asyncio.create_task(_safe(self._compliance.analyze(context, claim))))
        if "simulate_persona" in fn_names:
            tasks.append(asyncio.create_task(_safe(self._persona.analyze(context, claim))))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks)
        findings: list[Finding] = []
        for r in results:
            if isinstance(r, list):
                findings.extend(r)
        return findings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async_progress(callback: Optional[ProgressCallback], pct: int, message: str) -> None:
    """Invoke progress callback, supporting both sync and async callables."""
    if callback is None:
        return
    result = callback(pct, message)
    if result is not None and hasattr(result, "__await__"):
        await result


def _deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Remove duplicate findings based on (agent, title) key."""
    seen: set[tuple[str, str]] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.agent, f.title.strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def _build_timeline(findings: list[Finding]) -> list[TimelineAnnotation]:
    """Convert findings with timestamps into sorted timeline annotations."""
    annotations: list[TimelineAnnotation] = []
    for f in findings:
        if f.timestamp is None:
            continue
        color = CATEGORY_COLOR.get(f.category, CATEGORY_COLOR.get(f.agent, "blue"))
        annotations.append(
            TimelineAnnotation(
                timestamp=f.timestamp,
                category=f.category,
                color=color,
                label=f.title[:50],
                finding_id=f.id,
                agent=f.agent,  # type: ignore[arg-type]
            )
        )
    # Sort by timestamp
    annotations.sort(key=lambda a: a.timestamp)
    return annotations

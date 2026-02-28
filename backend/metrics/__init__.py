"""
PitchPilot metrics package.

Provides lightweight per-stage timing, session-level metric aggregation,
and a bounded concurrency utility for Ollama/LLM calls.

Quick start::

    from backend.metrics import SessionMetrics, StageTimer, ConcurrencyLimiter

    metrics = SessionMetrics(session_id=session_id)

    async with StageTimer("my_stage", metrics) as t:
        result = await do_work()
        t.item_count = len(result)

    metrics.print_report()
"""

from backend.metrics.session_metrics import SessionMetrics
from backend.metrics.timer import ConcurrencyLimiter, StageRecord, StageTimer

__all__ = [
    "SessionMetrics",
    "StageTimer",
    "StageRecord",
    "ConcurrencyLimiter",
]

"""
Lightweight timing and concurrency utilities for PitchPilot pipeline instrumentation.

Usage::

    from backend.metrics.timer import StageTimer, ConcurrencyLimiter

    # Time a pipeline stage
    async with StageTimer("ocr", metrics) as t:
        results = await process_frames(...)
        t.item_count = len(results)

    # Rate-limit concurrent coroutines
    limiter = ConcurrencyLimiter(max_concurrent=2)
    results = await limiter.run_many([process(f) for f in frames])
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Optional, TypeVar

if TYPE_CHECKING:
    from backend.metrics.session_metrics import SessionMetrics

T = TypeVar("T")


@dataclass
class StageRecord:
    """Immutable timing record for a single pipeline stage."""

    stage: str
    start: float
    end: float
    duration: float
    item_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        items = f" ({self.item_count} items)" if self.item_count else ""
        return f"{self.stage:<30} {self.duration:>7.2f}s{items}"


class StageTimer:
    """
    Async context manager that records wall-clock duration of a pipeline stage.

    Optionally appends the resulting StageRecord to a SessionMetrics object.

    Example::

        async with StageTimer("frame_extraction", metrics) as t:
            frames = await extract_frames(...)
            t.item_count = len(frames)
    """

    def __init__(
        self,
        stage: str,
        metrics: Optional["SessionMetrics"] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.stage = stage
        self._metrics = metrics
        self._metadata = metadata or {}
        self._start: float = 0.0
        self.item_count: int = 0

    async def __aenter__(self) -> "StageTimer":
        self._start = time.perf_counter()
        return self

    async def __aexit__(self, *_: Any) -> None:
        end = time.perf_counter()
        record = StageRecord(
            stage=self.stage,
            start=self._start,
            end=end,
            duration=round(end - self._start, 3),
            item_count=self.item_count,
            metadata=self._metadata,
        )
        if self._metrics is not None:
            self._metrics.add(record)


class ConcurrencyLimiter:
    """
    Wraps an asyncio.Semaphore to bound parallelism over a list of coroutines.

    This prevents unbounded concurrency (e.g., firing 30 Ollama calls at once
    when Ollama can only process them serially).

    Example::

        limiter = ConcurrencyLimiter(max_concurrent=2)
        results = await limiter.run_many([ocr_frame(f) for f in keyframes])
    """

    def __init__(self, max_concurrent: int) -> None:
        self._sem = asyncio.Semaphore(max_concurrent)

    async def run_many(
        self,
        coros: list[Awaitable[T]],
        return_exceptions: bool = True,
    ) -> list[T | BaseException]:
        """
        Run all coroutines with bounded concurrency.

        Args:
            coros: List of awaitables to execute.
            return_exceptions: If True, exceptions are returned as values
                instead of propagating (mirrors asyncio.gather behavior).

        Returns:
            List of results in the same order as input coroutines.
        """
        async def _limited(coro: Awaitable[T]) -> T:
            async with self._sem:
                return await coro  # type: ignore[return-value]

        return await asyncio.gather(
            *(_limited(c) for c in coros),
            return_exceptions=return_exceptions,
        )

"""
SessionMetrics — collects per-stage timing records for a single pipeline run.

Usage::

    from backend.metrics.session_metrics import SessionMetrics

    metrics = SessionMetrics(session_id="abc-123")

    # Stages append records via StageTimer
    async with StageTimer("frame_extraction", metrics) as t:
        frames = await extract_frames(...)
        t.item_count = len(frames)

    # Print summary to console
    metrics.print_report()

    # Serialize for storage
    data = metrics.to_dict()
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.metrics.timer import StageRecord


@dataclass
class SessionMetrics:
    """Accumulates StageRecords for one pipeline session."""

    session_id: str
    started_at: float = field(default_factory=time.perf_counter)
    records: list[StageRecord] = field(default_factory=list)

    def add(self, record: StageRecord) -> None:
        """Append a completed StageRecord."""
        self.records.append(record)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def total_duration(self) -> float:
        """Wall-clock time from first record start to last record end."""
        if not self.records:
            return 0.0
        return round(max(r.end for r in self.records) - min(r.start for r in self.records), 3)

    @property
    def llm_call_count(self) -> int:
        """Count records whose metadata marks them as LLM calls."""
        return sum(1 for r in self.records if r.metadata.get("llm_call"))

    def stage_duration(self, stage: str) -> Optional[float]:
        """Return duration for a named stage, or None if not recorded."""
        for r in self.records:
            if r.stage == stage:
                return r.duration
        return None

    def top_stages(self, n: int = 5) -> list[StageRecord]:
        """Return the n slowest stages."""
        return sorted(self.records, key=lambda r: r.duration, reverse=True)[:n]

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return a flat dict suitable for JSON serialization."""
        return {
            "session_id": self.session_id,
            "total_duration_s": self.total_duration,
            "llm_call_count": self.llm_call_count,
            "stage_count": len(self.records),
            "stages": [
                {
                    "stage": r.stage,
                    "duration_s": r.duration,
                    "items": r.item_count,
                    **r.metadata,
                }
                for r in self.records
            ],
        }

    def print_report(self) -> None:
        """Print a formatted timing table to stdout."""
        sep = "─" * 55
        print(f"\n{sep}")
        print(f"  PitchPilot Session Metrics  [{self.session_id[:8]}...]")
        print(sep)
        for r in self.records:
            print(f"  {r}")
        print(sep)
        print(f"  {'TOTAL':<30} {self.total_duration:>7.2f}s")
        print(f"  LLM calls: {self.llm_call_count}")
        print(f"{sep}\n")

    def to_dict(self) -> dict:
        return self.summary()

    def save(self, directory: Path) -> Path:
        """Write metrics JSON to directory/session_metrics.json."""
        out = directory / "session_metrics.json"
        out.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return out

"""
CueSynthesizer — transforms Finding objects into mode-specific output cues.

For live_in_room:
  - Compresses findings to 3-6 word earpiece strings
  - Rate-limits delivery to 1 cue per CUE_MIN_INTERVAL seconds
  - Deduplicates by category within a sliding window

For live_remote:
  - Formats findings as overlay cards (title + detail + suggestion)
  - Generates script_suggestion payloads when a compliance or clarity issue
    has a direct rewording available

For review (upload) mode:
  - Pass-through; no synthesis needed — findings are returned as-is
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

from loguru import logger

from backend.api_schemas import (
    EarpieceCue,
    Finding,
    ScriptSuggestion,
    SessionMode,
    Severity,
)
from backend.config import (
    CUE_DEDUP_WINDOW,
    CUE_MIN_INTERVAL,
    CUE_URGENCY,
)


# ---------------------------------------------------------------------------
# Urgency helpers
# ---------------------------------------------------------------------------

def _urgency(severity: str) -> str:
    """Map a severity string to an urgency bucket: immediate | soon | deferred."""
    for bucket, severities in CUE_URGENCY.items():
        if severity in severities:
            return bucket
    return "deferred"


def _is_live_mode(mode: SessionMode) -> bool:
    return mode in (
        SessionMode.LIVE,
        SessionMode.LIVE_IN_ROOM,
        SessionMode.LIVE_REMOTE,
    )


# ---------------------------------------------------------------------------
# Default cue compression table
# Populated at startup; novel cues fall through to the model or a heuristic.
# ---------------------------------------------------------------------------

_CUE_BANK: dict[str, str] = {
    # Compliance
    "fully automated":          "compliance risk",
    "no manual review":         "compliance risk",
    "privacy":                  "mention privacy",
    "privacy disclaimer":       "mention privacy",
    "disclaimer":               "add disclaimer",
    "gdpr":                     "mention GDPR",
    "fully automated":          "compliance risk",
    # Coach — pacing / clarity
    "pacing":                   "slow down",
    "fast":                     "slow down",
    "abrupt transition":        "smoother transition",
    "differentiation":          "clarify differentiation",
    "problem statement":        "define problem first",
    "benchmark":                "name the benchmark",
    # Persona
    "roi":                      "ROI question likely",
    "how is this different":    "clarify differentiation",
    "skeptical investor":       "expect ROI pushback",
}


def _compress_to_cue(finding: Finding) -> str:
    """
    Return a 3-6 word earpiece cue for a finding.

    Strategy:
      1. Use finding.cue_hint if the agent provided one.
      2. Look for keyword matches in the title/detail against _CUE_BANK.
      3. Fall back to a truncated title slug.
    """
    if finding.cue_hint:
        return finding.cue_hint.strip()

    lowered = (finding.title + " " + finding.detail).lower()
    for keyword, cue in _CUE_BANK.items():
        if keyword in lowered:
            return cue

    # Heuristic fallback: first 4 words of the title
    words = finding.title.split()
    return " ".join(words[:4]).lower().rstrip(".,;:")


# ---------------------------------------------------------------------------
# CueSynthesizer
# ---------------------------------------------------------------------------


class CueSynthesizer:
    """
    Transforms a stream of Finding objects into mode-appropriate output.

    Usage (live_ws.py):
        synth = CueSynthesizer(mode=SessionMode.LIVE_IN_ROOM)
        earpiece_cues = synth.process(findings, elapsed=elapsed)
        # Returns list[EarpieceCue] (in_room) or list[ScriptSuggestion] (remote)
    """

    def __init__(self, mode: SessionMode) -> None:
        self.mode = mode
        self._last_cue_at: float = 0.0          # wall-clock time of last emitted cue
        self._recent_categories: deque[tuple[float, str]] = deque()  # (wall_time, category)
        logger.debug(f"[cue_synth] Initialized | mode={mode}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_for_in_room(
        self, findings: list[Finding], elapsed: float
    ) -> list[EarpieceCue]:
        """
        Filter and compress findings into earpiece cues for live_in_room mode.

        Only critical/warning findings produce cues; info findings are deferred
        to the post-session report.  Rate-limited to 1 cue per CUE_MIN_INTERVAL.
        """
        if not findings:
            return []

        now = time.monotonic()
        self._evict_old_categories(now)

        cues: list[EarpieceCue] = []
        for finding in sorted(findings, key=lambda f: self._priority_rank(f)):
            urgency = _urgency(finding.severity)
            if urgency == "deferred":
                continue  # info-level: skip for live cue, include in report

            category = finding.agent + ":" + (finding.cue_hint or finding.title[:20])
            if self._is_category_recent(category, now):
                logger.debug(f"[cue_synth] Dedup suppressed | category={category}")
                continue

            if now - self._last_cue_at < CUE_MIN_INTERVAL and cues:
                logger.debug("[cue_synth] Rate-limited — queued for later")
                break  # Only one cue per interval

            text = _compress_to_cue(finding)
            cue = EarpieceCue(
                text=text,
                audio_b64=None,   # TTSService fills this in
                priority=finding.severity,  # type: ignore[arg-type]
                category=finding.agent,
                elapsed=elapsed,
            )
            cues.append(cue)
            self._last_cue_at = now
            self._recent_categories.append((now, category))

            if len(cues) >= 1:
                break  # Deliver at most one cue per batch

        return cues

    def process_for_remote(
        self, findings: list[Finding], elapsed: float
    ) -> list[ScriptSuggestion]:
        """
        Convert findings into ScriptSuggestion overlays for live_remote mode.

        Returns a suggestion only when a finding has both a title (the 'original'
        phrasing) and a suggestion (the 'alternative').
        """
        suggestions: list[ScriptSuggestion] = []
        for finding in findings:
            if finding.suggestion and finding.severity in (
                Severity.WARNING, Severity.CRITICAL
            ):
                suggestions.append(
                    ScriptSuggestion(
                        original=finding.title,
                        alternative=finding.suggestion,
                        reason=finding.detail[:120],
                        agent=finding.agent,  # type: ignore[arg-type]
                        elapsed=elapsed,
                    )
                )
        return suggestions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _priority_rank(finding: Finding) -> int:
        """Lower = higher priority."""
        return {"critical": 0, "warning": 1, "info": 2}.get(finding.severity, 99)

    def _evict_old_categories(self, now: float) -> None:
        cutoff = now - CUE_DEDUP_WINDOW
        while self._recent_categories and self._recent_categories[0][0] < cutoff:
            self._recent_categories.popleft()

    def _is_category_recent(self, category: str, now: float) -> bool:
        self._evict_old_categories(now)
        return any(cat == category for _, cat in self._recent_categories)

    def _compress_cue_for_remote(self, finding: Finding) -> str:
        """Return a compact cue label for remote overlay cards."""
        return _compress_to_cue(finding)

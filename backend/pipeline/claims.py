"""
Claim extraction pipeline for the PitchPilot ingestion pipeline.

Responsibilities
----------------
* Combine TranscriptSegments and OCRBlocks into a unified text context.
* Send context windows to the model and parse structured Claim objects.
* Assign ClaimCategory, ClaimSource, timestamp range, and evidence items.
* Deduplicate highly similar claims (cosine-like string overlap).

Performance improvements
------------------------
* Scoped OCR text: each transcript window now only includes OCR blocks that
  are temporally nearby (±5s margin), rather than ALL OCR blocks from the
  session.  This reduces prompt size significantly for long videos.

* Bounded concurrency: window tasks use ConcurrencyLimiter instead of
  unbounded asyncio.gather.  The OCR concurrency setting is reused here
  since both compete for the same Ollama instance.

Claim output contract
----------------------
Each Claim has:
    text            – normalised claim statement
    category        – ClaimCategory enum
    source          – ClaimSource (TRANSCRIPT / OCR / BOTH)
    timestamp_start – earliest timestamp where this claim appears (seconds)
    timestamp_end   – latest timestamp where this claim appears (seconds)
    evidence        – list of EvidenceItem (verbatim source snippets)
    confidence      – float [0,1]
    model_used      – name of the model used

The extractor processes transcript in overlapping windows to preserve context.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.config import CLAIM_CONCURRENCY, CLAIM_WINDOW_OVERLAP, settings
from backend.data_models import (
    Claim,
    ClaimCategory,
    ClaimSource,
    EvidenceItem,
    OCRBlock,
    TranscriptSegment,
)
from backend.metrics import ConcurrencyLimiter
from backend.models.base import BaseMultimodalModel
from backend.models.gemma3n import get_gemma3n_adapter
from backend.pipeline.ocr import build_scoped_ocr_text

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_CLAIM_SYSTEM = """You are a claim extraction specialist for pitch presentation analysis.

Extract ALL factual, comparative, or compliance-sensitive claims from the provided text.
Return a JSON object with a 'claims' list. Each claim must have:
  - "text": the claim statement (concise, normalised)
  - "category": one of: product_claim, value_proposition, technical_claim,
                compliance_sensitive, comparison_claim, automation_claim,
                privacy_claim, accuracy_claim, financial_claim, unclassified
  - "confidence": float 0-1
  - "evidence": verbatim quote from the source text that supports the claim
  - "timestamp_start": start time in seconds where this claim occurs, taken from the
                       [Xs-Ys] markers in the transcript (use the segment start time)

Only extract claims that can be factually evaluated or challenged.
Do not extract opinions, greetings, or transition phrases.
Return only the JSON object, no explanation."""

_CLAIM_PROMPT_TEMPLATE = """Extract claims from the following presentation text.
Each transcript segment is prefixed with its time range, e.g. [3.2s-7.8s].
Use those time markers to populate "timestamp_start" for each claim.

TRANSCRIPT SEGMENTS:
{transcript_text}

SLIDE / DOCUMENT TEXT (OCR):
{ocr_text}

Return JSON: {{"claims": [{{"text": "...", "category": "...", "confidence": 0.9, "evidence": "...", "timestamp_start": 0.0}}]}}"""


class ClaimExtractor:
    """
    Extracts structured claims from combined transcript and OCR text.

    Usage::

        extractor = ClaimExtractor()
        claims = await extractor.extract(
            transcript_segments=segments,
            ocr_blocks=ocr_blocks,
        )
    """

    def __init__(
        self,
        model: Optional[BaseMultimodalModel] = None,
        claim_concurrency: Optional[int] = None,
    ):
        self._model = model or get_gemma3n_adapter()
        self._limiter = ConcurrencyLimiter(
            claim_concurrency if claim_concurrency is not None else CLAIM_CONCURRENCY
        )
        logger.info(f"[claims] Initialised with model: {self._model.model_name}")

    async def extract(
        self,
        transcript_segments: list[TranscriptSegment],
        ocr_blocks: list[OCRBlock],
        max_claims: Optional[int] = None,
    ) -> list[Claim]:
        """
        Extract candidate claims from transcript + OCR text.

        The extractor uses a sliding window over the transcript to maintain
        temporal locality, enriched with temporally-scoped OCR text.

        Args:
            transcript_segments: Ordered transcript segments from the audio.
            ocr_blocks: OCR blocks from frames and documents.
            max_claims: Hard cap on output size.  Defaults to
                settings.max_claims_per_session.

        Returns:
            List of Claim objects sorted by timestamp_start.
        """
        cap = max_claims if max_claims is not None else settings.max_claims_per_session
        if settings.fast_mode:
            cap = min(cap, 15)

        window_secs = settings.claim_context_window_seconds

        if not transcript_segments and not ocr_blocks:
            logger.warning("[claims] No input text; returning empty claims list")
            return []

        # Partition transcript into overlapping time windows
        windows = _build_transcript_windows(transcript_segments, window_secs)

        logger.info(
            f"[claims] Processing {len(windows)} transcript windows + "
            f"{len(ocr_blocks)} OCR blocks (scoped per window)"
        )

        coros = [
            self._extract_window(window_segs, ocr_blocks)
            for window_segs in windows
        ]
        window_results = await self._limiter.run_many(coros)

        all_claims: list[Claim] = []
        for result in window_results:
            if isinstance(result, Exception):
                logger.error(f"[claims] Window extraction error: {result}")
            elif isinstance(result, list):
                all_claims.extend(result)

        # Deduplicate and sort
        unique_claims = _deduplicate_claims(all_claims)
        unique_claims.sort(key=lambda c: c.timestamp_start)

        if len(unique_claims) > cap:
            logger.info(f"[claims] Capping from {len(unique_claims)} -> {cap}")
            unique_claims = unique_claims[:cap]

        logger.info(f"[claims] Extracted {len(unique_claims)} unique claims")
        return unique_claims

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _extract_window(
        self,
        segments: list[TranscriptSegment],
        ocr_blocks: list[OCRBlock],
    ) -> list[Claim]:
        """Run extraction on a single context window with scoped OCR text."""
        if not segments:
            return []

        window_start = segments[0].start_time
        window_end = segments[-1].end_time

        transcript_text = "\n".join(
            f"[{s.start_time:.1f}s-{s.end_time:.1f}s] {s.text}"
            for s in segments
        )
        # Use only OCR blocks near this time window
        ocr_text = build_scoped_ocr_text(ocr_blocks, window_start, window_end)

        prompt = _CLAIM_PROMPT_TEMPLATE.format(
            transcript_text=transcript_text,
            ocr_text=ocr_text,
        )

        try:
            raw = await self._model.generate_text(
                prompt=prompt,
                system=_CLAIM_SYSTEM,
                temperature=0.1,
            )
        except Exception as exc:
            logger.exception(
                f"[claims] Model call failed for window "
                f"[{window_start:.1f}-{window_end:.1f}s]: {exc}"
            )
            return []

        raw_claims = _parse_claims_json(raw)
        claims: list[Claim] = []

        for item in raw_claims:
            claim_text = (item.get("text") or "").strip()
            if not claim_text:
                continue

            category = _parse_category(item.get("category", "unclassified"))
            evidence_text = (item.get("evidence") or claim_text).strip()

            matching_segs: list[TranscriptSegment] = []

            # 1. Use model-returned timestamp if present and valid
            model_ts = item.get("timestamp_start")
            if isinstance(model_ts, (int, float)) and window_start <= model_ts <= window_end:
                ts_start = float(model_ts)
                ts_end = ts_start + 2.0
                source = ClaimSource.TRANSCRIPT
            else:
                # 2. Try to match evidence back to transcript segments via word overlap
                matching_segs = _match_segments_by_overlap(evidence_text, segments)

                if matching_segs:
                    ts_start = matching_segs[0].start_time
                    ts_end = matching_segs[-1].end_time
                    source = ClaimSource.TRANSCRIPT
                else:
                    # 3. Estimate position proportionally from where evidence appears
                    #    in the combined transcript text
                    ts_start, ts_end = _estimate_timestamp(
                        evidence_text, segments, window_start, window_end
                    )
                    source = ClaimSource.TRANSCRIPT

            evidence = [
                EvidenceItem(
                    source_type=source,
                    text=evidence_text,
                    timestamp=ts_start,
                    segment_id=matching_segs[0].segment_id if matching_segs else None,
                )
            ]

            claims.append(
                Claim(
                    text=claim_text,
                    category=category,
                    source=source,
                    timestamp_start=ts_start,
                    timestamp_end=ts_end,
                    evidence=evidence,
                    confidence=float(item.get("confidence", 1.0)),
                    model_used=self._model.model_name,
                    raw_response=raw,
                )
            )

        return claims

    def combine_text(
        self,
        transcript_segments: list[TranscriptSegment],
        ocr_blocks: list[OCRBlock],
    ) -> str:
        """
        Return a flat combined text representation suitable for debugging.
        """
        lines = ["=== TRANSCRIPT ==="]
        for seg in transcript_segments:
            lines.append(f"[{seg.start_time:.1f}s] {seg.text}")
        lines.append("\n=== SLIDE / DOCUMENT TEXT ===")
        for block in ocr_blocks:
            ts = f"[{block.timestamp:.1f}s]" if block.timestamp is not None else f"[p.{block.page_number}]"
            lines.append(f"{ts} {block.text}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text window helpers
# ---------------------------------------------------------------------------


def _build_transcript_windows(
    segments: list[TranscriptSegment],
    window_secs: float,
) -> list[list[TranscriptSegment]]:
    """
    Partition transcript segments into overlapping time windows.

    For short transcripts (< 2 * window_secs), returns a single window
    containing all segments.
    """
    if not segments:
        return []

    total_duration = segments[-1].end_time - segments[0].start_time
    if total_duration <= window_secs * 1.5:
        return [segments]

    windows: list[list[TranscriptSegment]] = []
    # Overlap fraction comes from config (PITCHPILOT_CLAIM_WINDOW_OVERLAP).
    # Lower overlap = fewer LLM extraction calls; Jaccard dedup absorbs boundary duplicates.
    step = window_secs * (1.0 - CLAIM_WINDOW_OVERLAP)
    current_start = segments[0].start_time

    while current_start < segments[-1].end_time:
        window_end = current_start + window_secs
        window_segs = [
            s for s in segments
            if s.start_time < window_end and s.end_time > current_start
        ]
        if window_segs:
            windows.append(window_segs)
        current_start += step

    return windows if windows else [segments]


def _match_segments_by_overlap(evidence: str, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """
    Find segments whose text meaningfully overlaps with the evidence string.

    Uses word-level Jaccard overlap rather than a rigid prefix check so that
    paraphrased or partially-quoted evidence still gets matched.
    """
    def words(text: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9 ]", "", text.lower()).split())

    ev_words = words(evidence)
    if not ev_words:
        return []

    scored: list[tuple[float, TranscriptSegment]] = []
    for seg in segments:
        seg_words = words(seg.text)
        if not seg_words:
            continue
        overlap = len(ev_words & seg_words) / len(ev_words | seg_words)
        if overlap >= 0.25:  # at least 25% word overlap
            scored.append((overlap, seg))

    if not scored:
        return []

    scored.sort(key=lambda x: -x[0])
    best_score = scored[0][0]
    # Return all segments within 20% of the best score, preserving time order
    good = [seg for score, seg in scored if score >= best_score * 0.8]
    good.sort(key=lambda s: s.start_time)
    return good


def _estimate_timestamp(
    evidence: str,
    segments: list[TranscriptSegment],
    window_start: float,
    window_end: float,
) -> tuple[float, float]:
    """
    Estimate where in the window the evidence occurs by finding its approximate
    character position within the combined transcript text.

    Falls back to the midpoint of the window if no estimate is possible.
    """
    if not segments:
        mid = (window_start + window_end) / 2
        return mid, mid + 2.0

    combined = " ".join(s.text for s in segments).lower()
    needle = evidence.lower()[:60]

    # Try to find position of evidence in the combined text
    pos = combined.find(needle[:20]) if len(needle) >= 20 else -1
    if pos < 0:
        # Use midpoint as fallback
        mid = (window_start + window_end) / 2
        return mid, mid + 2.0

    # Map character position to time
    fraction = pos / max(len(combined), 1)
    duration = window_end - window_start
    ts_start = window_start + fraction * duration
    return ts_start, ts_start + 2.0


def _build_ocr_text(ocr_blocks: list[OCRBlock]) -> str:
    """Produce a compact text summary of all OCR blocks (for debugging)."""
    if not ocr_blocks:
        return ""
    lines = []
    for block in ocr_blocks:
        if block.timestamp is not None:
            lines.append(f"[{block.timestamp:.1f}s] {block.text}")
        elif block.page_number is not None:
            lines.append(f"[page {block.page_number}] {block.text}")
        else:
            lines.append(block.text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------


def _parse_claims_json(raw: str) -> list[dict]:
    """Extract the 'claims' list from a model response string."""
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        data = json.loads(raw)
        return data.get("claims", [])
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return data.get("claims", [])
            except json.JSONDecodeError:
                pass
        logger.warning(f"[claims] Failed to parse claims JSON: {raw[:200]!r}")
        return []


_CATEGORY_MAP = {
    "product_claim": ClaimCategory.PRODUCT_CLAIM,
    "value_proposition": ClaimCategory.VALUE_PROPOSITION,
    "technical_claim": ClaimCategory.TECHNICAL_CLAIM,
    "compliance_sensitive": ClaimCategory.COMPLIANCE_SENSITIVE,
    "comparison_claim": ClaimCategory.COMPARISON_CLAIM,
    "automation_claim": ClaimCategory.AUTOMATION_CLAIM,
    "privacy_claim": ClaimCategory.PRIVACY_CLAIM,
    "accuracy_claim": ClaimCategory.ACCURACY_CLAIM,
    "financial_claim": ClaimCategory.FINANCIAL_CLAIM,
}


def _parse_category(raw: str) -> ClaimCategory:
    return _CATEGORY_MAP.get(raw.strip().lower(), ClaimCategory.UNCLASSIFIED)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _deduplicate_claims(claims: list[Claim], similarity_threshold: float = 0.7) -> list[Claim]:
    """
    Remove claims that are near-duplicates based on token overlap (Jaccard).

    Keeps the higher-confidence copy when duplicates are found.
    """
    if not claims:
        return claims

    def tokenize(text: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9 ]", "", text.lower()).split())

    unique: list[Claim] = []
    for candidate in sorted(claims, key=lambda c: -c.confidence):
        is_dup = False
        cand_tokens = tokenize(candidate.text)
        for existing in unique:
            existing_tokens = tokenize(existing.text)
            union = cand_tokens | existing_tokens
            if not union:
                continue
            jaccard = len(cand_tokens & existing_tokens) / len(union)
            if jaccard >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(candidate)

    return unique

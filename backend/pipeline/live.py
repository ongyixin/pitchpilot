"""
Live (real-time) processing pipeline for PitchPilot.

Manages the streaming state for a single live rehearsal session.
Audio chunks and frame snapshots arrive incrementally from the browser via
WebSocket, are processed in small batches, and yield agent findings in
near-real-time.

Flow per cycle:
  1. ingest_audio_chunk()  → incremental transcription → appended to buffer
  2. ingest_frame()        → single-frame OCR → appended to buffer
  3. extract_and_route()   → sliding-window claim extraction → Orchestrator.run_claim()
                           → new findings returned to caller

After the presenter ends the session:
  4. finalize()            → full Orchestrator.run() pass on accumulated context
                           → ReadinessReport generated (same schema as upload mode)
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.agents.orchestrator import Orchestrator, OrchestratorResult
from backend.config import SESSIONS_DIR, settings
from backend.data_models import (
    AudioTrack,
    OCRBlock,
    OCRSourceType,
    TranscriptSegment,
)
from backend.pipeline.claims import ClaimExtractor
from backend.pipeline.ocr import OCRPipeline
from backend.pipeline.transcribe import TranscriptionPipeline
from backend.reports.readiness import ReadinessReportGenerator
from backend.schemas import (
    Claim,
    Finding,
    PipelineContext,
    TranscriptSegment as SchemaTranscriptSegment,
    SlideOCR,
)


# ---------------------------------------------------------------------------
# Mock helpers (used when settings.mock_mode = True)
# ---------------------------------------------------------------------------

_MOCK_TRANSCRIPT_CHUNKS = [
    "We've built a fully automated compliance layer that requires no manual review.",
    "Our platform achieves 99.9 percent uptime across all enterprise tiers.",
    "All customer data is stored exclusively on-device — nothing leaves your network.",
    "We outperform every competitor by three times on inference speed.",
    "The integration is seamless and can be deployed in under an hour.",
]

_MOCK_FINDINGS_POOL = [
    {
        "agent": "compliance",
        "severity": "critical",
        "title": "'Fully automated' conflicts with policy §3.2",
        "detail": "Your enterprise data-handling policy requires human review for model outputs above a confidence threshold.",
        "suggestion": "Rephrase to: 'Automated with optional human-in-the-loop review.'",
        "timestamp": 8.0,
    },
    {
        "agent": "coach",
        "severity": "warning",
        "title": "Pacing is fast — slow down for key metrics",
        "detail": "The 99.9% uptime claim was delivered quickly. Pause briefly after key numbers to let them land.",
        "suggestion": "Add a 1-second pause after stating uptime figures.",
        "timestamp": 22.0,
    },
    {
        "agent": "compliance",
        "severity": "warning",
        "title": "'Nothing leaves your network' needs qualification",
        "detail": "The blanket privacy claim may be false for customers who enable optional cloud sync.",
        "suggestion": "Add 'by default' and mention the opt-in cloud sync explicitly.",
        "timestamp": 35.0,
    },
    {
        "agent": "coach",
        "severity": "critical",
        "title": "Speed metric lacks benchmark context",
        "detail": "'3× faster' is compelling but the baseline is never stated.",
        "suggestion": "Name the competitor and link to a reproducible benchmark.",
        "timestamp": 48.0,
    },
    {
        "agent": "persona",
        "severity": "warning",
        "title": "Skeptical Investor: differentiation is unclear",
        "detail": "A skeptical investor would immediately ask how this differs from a well-prompted ChatGPT.",
        "suggestion": "Lead with the on-device / privacy differentiator earlier.",
        "timestamp": 60.0,
    },
]


# ---------------------------------------------------------------------------
# LivePipeline
# ---------------------------------------------------------------------------


class LivePipeline:
    """
    Manages streaming transcription, OCR, claim extraction, and agent
    dispatch for a single live rehearsal session.

    Usage::

        pipeline = LivePipeline(session_id="abc", orchestrator=orch, personas=["Skeptical Investor"])
        await pipeline.initialize()

        # Per audio chunk (every ~2 s):
        segments = await pipeline.ingest_audio_chunk(raw_bytes, offset_seconds=12.0)
        findings = await pipeline.extract_and_route()

        # Per frame (every ~5 s):
        await pipeline.ingest_frame(jpeg_bytes, timestamp=15.0)

        # End of session:
        result = await pipeline.finalize()
    """

    def __init__(
        self,
        session_id: str,
        orchestrator: Optional[Orchestrator] = None,
        personas: Optional[list[str]] = None,
        policy_text: str = "",
        presentation_title: str = "",
    ) -> None:
        self.session_id = session_id
        self._orchestrator = orchestrator or Orchestrator()
        self.personas: list[str] = personas or []
        self.policy_text = policy_text
        self.presentation_title = presentation_title

        # Accumulated buffers
        self._transcript_segments: list[TranscriptSegment] = []
        self._ocr_blocks: list[OCRBlock] = []
        self._all_claims: list[Claim] = []
        self._all_findings: list[Finding] = []

        # Track which claims have already been routed so we never double-process
        self._processed_claim_ids: set[str] = set()

        # Session timing
        self._session_start: float = time.monotonic()
        self._mock_chunk_index: int = 0
        self._mock_finding_index: int = 0

        # Sub-pipelines (initialised lazily)
        self._transcriber: Optional[TranscriptionPipeline] = None
        self._ocr: Optional[OCRPipeline] = None
        self._claim_extractor: Optional[ClaimExtractor] = None
        self._report_gen: Optional[ReadinessReportGenerator] = None

        # Session directory for temp audio chunks
        self._session_dir = SESSIONS_DIR / session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = False

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Set up sub-pipelines and orchestrator. Call once before any ingestion."""
        if self._initialized:
            return
        await self._orchestrator.initialize()
        if not settings.mock_mode:
            self._transcriber = TranscriptionPipeline()
            self._ocr = OCRPipeline()
            self._claim_extractor = ClaimExtractor()
        self._report_gen = ReadinessReportGenerator()
        self._initialized = True
        logger.info(f"[live] Pipeline initialized | session={self.session_id} | mock={settings.mock_mode}")

    # ------------------------------------------------------------------
    # Per-chunk ingestion
    # ------------------------------------------------------------------

    async def ingest_audio_chunk(
        self,
        audio_bytes: bytes,
        offset_seconds: float = 0.0,
    ) -> list[TranscriptSegment]:
        """
        Transcribe a raw audio chunk and append segments to the buffer.

        Args:
            audio_bytes: Raw audio bytes (WebM/Opus or PCM WAV from browser).
            offset_seconds: Wall-clock offset of this chunk from session start.

        Returns:
            Newly transcribed segments (may be empty in mock mode).
        """
        if not self._initialized:
            await self.initialize()

        if settings.mock_mode:
            return self._mock_ingest_audio_chunk(offset_seconds)

        if not audio_bytes:
            return []

        # Write chunk to a temp WAV file so TranscriptionPipeline can read it
        chunk_path = self._session_dir / f"chunk_{int(offset_seconds * 1000):08d}.webm"
        chunk_path.write_bytes(audio_bytes)

        try:
            audio_track = AudioTrack(
                file_path=str(chunk_path),
                duration_seconds=2.0,  # approximate; transcription will adjust
                sample_rate=settings.audio_sample_rate,
                channels=1,
                source_video_path="",
            )
            segments = await self._transcriber.transcribe(audio_track)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning(f"[live] Audio chunk transcription failed: {exc}")
            return []

        # Adjust timestamps by offset so the session-level timeline is correct
        adjusted: list[TranscriptSegment] = []
        for seg in segments:
            adjusted_seg = TranscriptSegment(
                text=seg.text,
                start_time=seg.start_time + offset_seconds,
                end_time=seg.end_time + offset_seconds,
                confidence=seg.confidence,
                language=getattr(seg, "language", "en"),
                model_used=getattr(seg, "model_used", "live"),
            )
            adjusted.append(adjusted_seg)

        self._transcript_segments.extend(adjusted)
        logger.debug(f"[live] Ingested {len(adjusted)} transcript segments at offset {offset_seconds:.1f}s")
        return adjusted

    async def ingest_frame(
        self,
        frame_bytes: bytes,
        timestamp: float = 0.0,
        frame_index: int = 0,
    ) -> list[OCRBlock]:
        """
        Run OCR on a single JPEG frame and append results to the buffer.

        Args:
            frame_bytes: Raw JPEG bytes from the browser canvas.
            timestamp: Seconds from session start when this frame was captured.
            frame_index: Sequential frame number.

        Returns:
            OCR blocks extracted from the frame.
        """
        if not self._initialized:
            await self.initialize()

        if settings.mock_mode:
            return []  # frames are optional in mock mode

        if not frame_bytes:
            return []

        frame_path = self._session_dir / f"frame_{frame_index:04d}.jpg"
        frame_path.write_bytes(frame_bytes)

        try:
            from backend.data_models import ExtractedFrame  # noqa: PLC0415
            frame = ExtractedFrame(
                file_path=str(frame_path),
                frame_index=frame_index,
                timestamp=timestamp,
                is_keyframe=True,
            )
            blocks = await self._ocr.process_frames([frame], keyframes_only=False)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning(f"[live] Frame OCR failed at {timestamp:.1f}s: {exc}")
            return []

        self._ocr_blocks.extend(blocks)
        logger.debug(f"[live] OCR'd frame at {timestamp:.1f}s: {len(blocks)} blocks")
        return blocks

    # ------------------------------------------------------------------
    # Claim extraction + agent routing
    # ------------------------------------------------------------------

    async def extract_and_route(self) -> list[Finding]:
        """
        Run claim extraction over the tail of the transcript buffer and
        route any new claims through the orchestrator.

        Only claims not previously processed are dispatched to agents.

        Returns:
            New findings produced in this cycle (may be empty).
        """
        if not self._initialized:
            await self.initialize()

        if settings.mock_mode:
            return self._mock_extract_and_route()

        if not self._transcript_segments:
            return []

        try:
            if self._claim_extractor is None:
                self._claim_extractor = ClaimExtractor()

            # Extract claims from the current buffer
            from backend.data_models import TranscriptSegment as DataTranscriptSegment  # noqa: PLC0415
            new_claims = await self._claim_extractor.extract(
                transcript_segments=self._transcript_segments,
                ocr_blocks=self._ocr_blocks,
            )
        except Exception as exc:
            logger.error(f"[live] Claim extraction failed: {exc}")
            return []

        # Filter to only claims not already processed
        unprocessed = [c for c in new_claims if c.id not in self._processed_claim_ids]
        if not unprocessed:
            return []

        logger.info(f"[live] Routing {len(unprocessed)} new claims to agents")

        context = self._build_pipeline_context()
        new_findings: list[Finding] = []

        for claim in unprocessed:
            try:
                schema_claim = _data_claim_to_schema(claim)
                findings = await self._orchestrator.run_claim(context, schema_claim)
                # Tag findings as live
                for f in findings:
                    f.timestamp = claim.timestamp_start
                new_findings.extend(findings)
                self._processed_claim_ids.add(claim.id)
                self._all_claims.append(claim)
            except Exception as exc:
                logger.error(f"[live] Claim routing failed for '{claim.text[:40]}': {exc}")

        self._all_findings.extend(new_findings)
        logger.info(f"[live] Cycle complete | new_findings={len(new_findings)}")
        return new_findings

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------

    async def finalize(self) -> OrchestratorResult:
        """
        End the session: run a comprehensive agent pass on all accumulated
        context and generate the final readiness report.

        This mirrors the upload-mode pipeline and produces a compatible
        ReadinessReport that the existing ResultsPage can render.

        Returns:
            OrchestratorResult containing merged findings + timeline.
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"[live] Finalizing session={self.session_id} | "
                    f"segments={len(self._transcript_segments)} | "
                    f"ocr_blocks={len(self._ocr_blocks)} | "
                    f"live_findings={len(self._all_findings)}")

        if settings.mock_mode:
            return self._mock_finalize()

        context = self._build_pipeline_context()
        try:
            result = await self._orchestrator.run(context)
        except Exception as exc:
            logger.error(f"[live] Final orchestration failed: {exc}")
            # Return whatever we have from incremental processing
            from backend.agents.orchestrator import OrchestratorResult  # noqa: PLC0415
            from backend.agents.orchestrator import _build_timeline  # noqa: PLC0415
            result = OrchestratorResult(
                session_id=self.session_id,
                findings=self._all_findings,
                timeline=_build_timeline(self._all_findings),
            )

        # Merge incremental live findings (dedup by title+agent)
        result.findings = _merge_findings(self._all_findings, result.findings)
        result.timeline = _rebuild_timeline(result.findings)

        return result

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _build_pipeline_context(self) -> PipelineContext:
        """Construct a PipelineContext from accumulated buffers."""
        schema_segments = [
            SchemaTranscriptSegment(
                text=seg.text,
                start_time=seg.start_time,
                end_time=seg.end_time,
                confidence=seg.confidence,
            )
            for seg in self._transcript_segments
        ]

        slide_ocr = [
            SlideOCR(
                slide_index=i,
                timestamp=block.timestamp or 0.0,
                raw_text=block.text,
            )
            for i, block in enumerate(self._ocr_blocks)
        ]

        elapsed = time.monotonic() - self._session_start

        return PipelineContext(
            session_id=self.session_id,
            transcript_segments=schema_segments,
            slide_ocr=slide_ocr,
            claims=[_data_claim_to_schema(c) for c in self._all_claims],
            policy_text=self.policy_text,
            presentation_title=self.presentation_title,
            personas=self.personas,
            total_duration=elapsed,
        )

    # ------------------------------------------------------------------
    # Mock helpers
    # ------------------------------------------------------------------

    def _mock_ingest_audio_chunk(self, offset_seconds: float) -> list[TranscriptSegment]:
        """Return a fake transcript segment for mock mode."""
        idx = self._mock_chunk_index % len(_MOCK_TRANSCRIPT_CHUNKS)
        text = _MOCK_TRANSCRIPT_CHUNKS[idx]
        self._mock_chunk_index += 1

        seg = TranscriptSegment(
            text=text,
            start_time=offset_seconds,
            end_time=offset_seconds + 2.0,
            confidence=0.95,
            model_used="mock",
        )
        self._transcript_segments.append(seg)
        return [seg]

    def _mock_extract_and_route(self) -> list[Finding]:
        """Return one fake finding per call (cycling through the pool)."""
        if self._mock_finding_index >= len(_MOCK_FINDINGS_POOL):
            return []

        raw = _MOCK_FINDINGS_POOL[self._mock_finding_index]
        self._mock_finding_index += 1

        elapsed = time.monotonic() - self._session_start
        finding = Finding(
            agent=raw["agent"],  # type: ignore[arg-type]
            category=raw["agent"],
            severity=raw["severity"],  # type: ignore[arg-type]
            title=raw["title"],
            description=raw["detail"],
            suggestion=raw.get("suggestion"),
            timestamp=elapsed,
        )
        self._all_findings.append(finding)
        return [finding]

    def _mock_finalize(self) -> OrchestratorResult:
        """Build a mock OrchestratorResult from accumulated mock findings."""
        from backend.agents.orchestrator import OrchestratorResult, _build_timeline  # noqa: PLC0415

        # Emit any remaining mock findings
        while self._mock_finding_index < len(_MOCK_FINDINGS_POOL):
            self._mock_extract_and_route()

        return OrchestratorResult(
            session_id=self.session_id,
            findings=self._all_findings,
            timeline=_build_timeline(self._all_findings),
            claims_processed=len(self._all_claims),
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._session_start

    @property
    def findings(self) -> list[Finding]:
        return list(self._all_findings)

    @property
    def transcript_segments(self) -> list[TranscriptSegment]:
        return list(self._transcript_segments)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _data_claim_to_schema(claim) -> "Claim":
    """Convert a data_models.Claim to a schemas.Claim."""
    from backend.schemas import Claim as SchemaClaim  # noqa: PLC0415

    return SchemaClaim(
        id=str(claim.id) if hasattr(claim, "id") else str(uuid.uuid4())[:8],
        text=claim.text,
        claim_type="general",
        timestamp=getattr(claim, "timestamp_start", None),
        source=getattr(claim, "source", "transcript").lower()
        if hasattr(getattr(claim, "source", None), "lower")
        else str(getattr(claim, "source", "transcript")),
        context_before="",
        context_after="",
    )


def _merge_findings(live: list[Finding], final: list[Finding]) -> list[Finding]:
    """
    Merge incremental live findings with the final batch findings.
    Deduplicates by (agent, title) key; live findings take precedence.
    """
    seen: set[tuple[str, str]] = set()
    merged: list[Finding] = []

    for f in live:
        key = (f.agent, f.title.strip().lower())
        if key not in seen:
            seen.add(key)
            merged.append(f)

    for f in final:
        key = (f.agent, f.title.strip().lower())
        if key not in seen:
            seen.add(key)
            merged.append(f)

    merged.sort(key=lambda x: x.timestamp or 0.0)
    return merged


def _rebuild_timeline(findings: list[Finding]):
    """Re-generate timeline annotations from findings."""
    from backend.agents.orchestrator import _build_timeline  # noqa: PLC0415
    return _build_timeline(findings)

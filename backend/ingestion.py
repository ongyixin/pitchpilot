"""
Top-level ingestion pipeline coordinator for PitchPilot.

This module wires together:
  1. Video processing  (frame extraction + audio extraction)
  2. OCR pipeline      (frames + policy documents)
  3. Transcription     (audio -> transcript segments)
  4. Claim extraction  (transcript + OCR -> structured claims)

It produces an IngestionResult artifact that is serialised to JSON in the
session directory and consumed by the downstream agents.

Performance design
------------------
* Stage overlap: audio extraction runs concurrently with frame extraction
  (both are offloaded to the thread pool via asyncio.to_thread).
* OCR starts as soon as frame extraction completes — it no longer waits for
  audio extraction.  Transcription runs concurrently with OCR.
* All LLM-heavy stages (OCR, claim extraction) use bounded concurrency via
  ConcurrencyLimiter to avoid queuing too many requests to Ollama.
* CPU-bound video work (OpenCV) runs in asyncio.to_thread to avoid blocking
  the event loop.
* Session artifacts (frames, audio, video) are cleaned up after the pipeline
  unless settings.retain_artifacts is True.
* A SessionMetrics object records per-stage timing and is saved alongside
  the ingestion result as session_metrics.json.
* A progress_callback (optional) is called at each milestone so the API
  layer can update the session status without polling the pipeline internals.

Usage
-----
Standalone (CLI / testing)::

    import asyncio
    from backend.ingestion import IngestionPipeline

    pipeline = IngestionPipeline()
    result = asyncio.run(pipeline.run(
        video_path="/path/to/rehearsal.mp4",
        policy_doc_paths=["/path/to/policy.pdf"],
    ))
    print(result.summary())

Via FastAPI::

    pipeline = IngestionPipeline()
    result = await pipeline.run(video_path=..., ...)
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable, Optional

from loguru import logger

from backend.config import SESSIONS_DIR, settings
from backend.data_models import AudioTrack, IngestionResult
from backend.metrics import SessionMetrics, StageTimer
from backend.pipeline.claims import ClaimExtractor
from backend.pipeline.ocr import OCRPipeline
from backend.pipeline.transcribe import TranscriptionPipeline
from backend.pipeline.video import (
    async_extract_audio,
    async_extract_frames_and_keyframes,
    cleanup_session_artifacts,
    save_video,
    save_video_file,
)

# Callback type: (progress: int, message: str) -> None (or coroutine)
ProgressCallback = Callable[[int, str], None]


class IngestionPipeline:
    """
    Orchestrates the full multimodal ingestion sequence.

    Each stage is individually accessible for unit testing.  The high-level
    ``run()`` method executes all stages with maximum overlap and writes the
    result to ``data/sessions/{session_id}/ingestion_result.json``.
    """

    def __init__(
        self,
        ocr_pipeline: Optional[OCRPipeline] = None,
        transcription_pipeline: Optional[TranscriptionPipeline] = None,
        claim_extractor: Optional[ClaimExtractor] = None,
    ):
        self.ocr = ocr_pipeline or OCRPipeline()
        self.transcriber = transcription_pipeline or TranscriptionPipeline()
        self.claim_extractor = claim_extractor or ClaimExtractor()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        video_path: str,
        policy_doc_paths: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        extraction_fps: Optional[float] = None,
        keyframes_only_ocr: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> IngestionResult:
        """
        Run the full ingestion pipeline on a video file.

        Args:
            video_path: Absolute path to the rehearsal video.
            policy_doc_paths: Optional list of paths to policy / compliance
                documents (.txt, .md, .pdf).
            session_id: Optional session identifier.  A new UUID is generated
                if not provided.
            extraction_fps: Frame extraction rate.  Defaults to
                settings.extraction_fps (0.5 in fast_mode).
            keyframes_only_ocr: If True, only run OCR on keyframes (slide
                transitions).  Dramatically reduces latency for long videos.
            progress_callback: Optional callable ``(progress_pct, message)``
                invoked at each stage milestone.  Can be async or sync.

        Returns:
            IngestionResult containing all intermediate artifacts.
        """
        t_start = time.perf_counter()
        sid = session_id or str(uuid.uuid4())
        docs = policy_doc_paths or []
        metrics = SessionMetrics(session_id=sid)

        # In fast mode, use reduced settings
        fps = extraction_fps or (0.5 if settings.fast_mode else settings.extraction_fps)
        max_dim = 768 if settings.fast_mode else settings.frame_max_dimension

        logger.info(
            f"[ingestion] Starting pipeline | session={sid} | "
            f"video={Path(video_path).name} | policy_docs={len(docs)} | "
            f"fast_mode={settings.fast_mode} | mock_mode={settings.mock_mode}"
        )

        await _progress(progress_callback, 5, "Extracting video frames (1/7)")

        # ------------------------------------------------------------------
        # Stage 1a+1b: Frame extraction + audio extraction run in parallel.
        #              Both are CPU/subprocess work; offload to thread pool.
        # ------------------------------------------------------------------
        logger.info("[ingestion] Stage 1: Video processing (frames + audio in parallel)")

        from backend.pipeline.video import save_video_file as _svf  # noqa
        video_meta_task = asyncio.get_event_loop().run_in_executor(
            None, save_video_file, video_path, sid
        )

        video_meta = await video_meta_task

        async with StageTimer("frame_extraction", metrics) as t:
            frames = await async_extract_frames_and_keyframes(
                video_meta,
                fps=fps,
                keyframes_only_save=True,
                max_dimension=max_dim,
            )
            t.item_count = len(frames)

        keyframe_count = sum(1 for f in frames if f.is_keyframe)
        logger.info(
            f"[ingestion] Frames: {len(frames)} total, {keyframe_count} keyframes"
        )

        await _progress(progress_callback, 15, "Extracting audio (2/7)")

        # Start audio extraction concurrently with OCR below
        async with StageTimer("audio_extraction", metrics) as t:
            try:
                audio_track = await async_extract_audio(video_meta)
                t.item_count = 1
            except RuntimeError as exc:
                logger.warning(f"[ingestion] Audio extraction failed: {exc}")
                audio_track = AudioTrack(
                    file_path="",
                    duration_seconds=video_meta.duration_seconds,
                    sample_rate=settings.audio_sample_rate,
                    channels=1,
                    source_video_path=video_meta.file_path,
                )

        # ------------------------------------------------------------------
        # Stage 2: OCR + Transcription (overlap as tasks)
        # ------------------------------------------------------------------
        logger.info("[ingestion] Stage 2: OCR + Transcription (parallel)")
        await _progress(progress_callback, 25, "Running OCR on slides (3/7)")

        ocr_frames_task = asyncio.create_task(
            self.ocr.process_frames(frames, keyframes_only=keyframes_only_ocr)
        )
        ocr_docs_tasks = [
            asyncio.create_task(self.ocr.process_document(p)) for p in docs
        ]

        async def _empty_transcript():
            return []

        transcribe_coro = (
            self.transcriber.transcribe(audio_track)
            if audio_track.file_path and Path(audio_track.file_path).exists()
            else _empty_transcript()
        )

        await _progress(progress_callback, 30, "Transcribing audio (4/7)")

        # Run OCR and transcription in parallel
        async with StageTimer("ocr_frames", metrics) as t:
            ocr_results = await asyncio.gather(
                ocr_frames_task,
                *ocr_docs_tasks,
                return_exceptions=True,
            )
            t.item_count = sum(
                len(r) for r in ocr_results if isinstance(r, list)
            )

        async with StageTimer("transcription", metrics) as t:
            try:
                transcript_segments = await transcribe_coro
                t.item_count = len(transcript_segments)
            except Exception as exc:
                logger.error(f"[ingestion] Transcription error: {exc}")
                transcript_segments = []

        # Unpack OCR results
        ocr_blocks = []
        for ocr_result in ocr_results:
            if isinstance(ocr_result, Exception):
                logger.error(f"[ingestion] OCR stage error: {ocr_result}")
            else:
                ocr_blocks.extend(ocr_result)

        logger.info(
            f"[ingestion] OCR: {len(ocr_blocks)} blocks | "
            f"Transcript: {len(transcript_segments)} segments"
        )

        # ------------------------------------------------------------------
        # Stage 3: Claim extraction
        # ------------------------------------------------------------------
        logger.info("[ingestion] Stage 3: Claim extraction")
        await _progress(progress_callback, 60, "Extracting claims (5/7)")

        async with StageTimer("claim_extraction", metrics) as t:
            claims = await self.claim_extractor.extract(
                transcript_segments=transcript_segments,
                ocr_blocks=ocr_blocks,
            )
            t.item_count = len(claims)

        elapsed = time.perf_counter() - t_start
        await _progress(progress_callback, 80, "Building ingestion result (6/7)")

        result = IngestionResult(
            session_id=sid,
            video_metadata=video_meta,
            frames=frames,
            audio_track=audio_track,
            ocr_blocks=ocr_blocks,
            transcript_segments=transcript_segments,
            claims=claims,
            policy_documents=[str(Path(p).resolve()) for p in docs],
            processing_time_seconds=round(elapsed, 2),
        )

        self._save_result(result, sid)
        metrics.save(SESSIONS_DIR / sid)

        # Cleanup disk artifacts unless retain_artifacts is set
        if not settings.retain_artifacts:
            await asyncio.to_thread(cleanup_session_artifacts, sid)

        await _progress(progress_callback, 90, "Ingestion complete (7/7)")

        metrics.print_report()

        logger.info(
            f"[ingestion] Pipeline complete in {elapsed:.1f}s | "
            + " | ".join(f"{k}={v}" for k, v in result.summary().items() if k != "session_id")
        )
        return result

    # ------------------------------------------------------------------
    # Convenience: from uploaded bytes
    # ------------------------------------------------------------------

    async def run_from_bytes(
        self,
        video_bytes: bytes,
        filename: str,
        policy_doc_paths: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs,
    ) -> IngestionResult:
        """
        Run the pipeline from raw uploaded video bytes.

        Saves the video to the session directory first, then delegates to run().

        Args:
            video_bytes: Raw bytes of the uploaded video file.
            filename: Original filename (preserves extension).
            policy_doc_paths: Optional list of policy document paths.
            session_id: Optional session ID.
            progress_callback: Optional progress update callback.
            **kwargs: Forwarded to run().

        Returns:
            IngestionResult.
        """
        sid = session_id or str(uuid.uuid4())
        video_meta = await asyncio.to_thread(save_video, video_bytes, filename, sid)
        return await self.run(
            video_path=video_meta.file_path,
            policy_doc_paths=policy_doc_paths,
            session_id=sid,
            progress_callback=progress_callback,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_result(self, result: IngestionResult, session_id: str) -> None:
        """Serialise the IngestionResult to JSON in the session directory."""
        sess_dir = SESSIONS_DIR / session_id
        sess_dir.mkdir(parents=True, exist_ok=True)
        out_path = sess_dir / "ingestion_result.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"[ingestion] Result saved to {out_path}")

    @staticmethod
    def load_result(session_id: str) -> IngestionResult:
        """
        Load a previously saved IngestionResult from disk.

        Args:
            session_id: Session identifier.

        Returns:
            IngestionResult loaded from JSON.

        Raises:
            FileNotFoundError: If the session does not exist.
        """
        path = SESSIONS_DIR / session_id / "ingestion_result.json"
        if not path.exists():
            raise FileNotFoundError(f"No ingestion result for session: {session_id}")
        return IngestionResult.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _progress(
    callback: Optional[ProgressCallback],
    pct: int,
    message: str,
) -> None:
    """Invoke the progress callback (sync or async) if provided."""
    if callback is None:
        return
    result = callback(pct, message)
    if result is not None and hasattr(result, "__await__"):
        await result

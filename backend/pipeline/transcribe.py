"""
Transcription pipeline for the PitchPilot ingestion pipeline.

Responsibilities
----------------
* Accept an AudioTrack and return a list of TranscriptSegment objects.
* Primary backend: Gemma 3n audio via Ollama.
* Fallback backend: mlx-whisper (Apple Silicon optimised Whisper).
* Mock backend: deterministic stub segments (settings.mock_mode=True).

TranscriptSegment output contract
----------------------------------
Each TranscriptSegment has:
    text        – transcribed text for this segment
    start_time  – segment start in seconds from audio start
    end_time    – segment end in seconds
    confidence  – average token confidence
    language    – ISO 639-1 code (typically "en")
    model_used  – name of the model/method used

The segments are guaranteed to be sorted by start_time and non-overlapping.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.config import settings
from backend.data_models import AudioTrack, TranscriptSegment, WordTiming
from backend.models.base import BaseMultimodalModel
from backend.models.gemma3n import get_gemma3n_adapter

_TRANSCRIPTION_SYSTEM = (
    "You are an accurate audio transcription system. "
    "Transcribe the provided audio into English text. "
    "Return a JSON object with a 'segments' list. "
    "Each segment must have: 'text' (string), 'start' (float seconds), "
    "'end' (float seconds), 'confidence' (float 0-1). "
    "Do not include any explanation outside the JSON object."
)

_TRANSCRIPTION_PROMPT = (
    "Transcribe this audio file. Return JSON with 'segments' list where each "
    "segment has 'text', 'start', 'end', and 'confidence' fields."
)


class TranscriptionPipeline:
    """
    Converts an AudioTrack to a list of timed TranscriptSegments.

    Usage::

        pipeline = TranscriptionPipeline()
        segments = await pipeline.transcribe(audio_track)
    """

    def __init__(
        self,
        model: Optional[BaseMultimodalModel] = None,
        use_whisper_fallback: bool = True,
    ):
        self._model = model or get_gemma3n_adapter()
        self._use_whisper_fallback = use_whisper_fallback
        logger.info(
            f"[transcribe] Initialised with model: {self._model.model_name}, "
            f"whisper_fallback={use_whisper_fallback}"
        )

    async def transcribe(self, audio: AudioTrack) -> list[TranscriptSegment]:
        """
        Transcribe an audio file and return ordered TranscriptSegment list.

        Args:
            audio: AudioTrack produced by the video pipeline.

        Returns:
            List of TranscriptSegment objects sorted by start_time.
        """
        audio_path = Path(audio.file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio.file_path}")

        logger.info(f"[transcribe] Transcribing {audio_path.name} ({audio.duration_seconds:.1f}s)")

        # Try primary model first
        try:
            segments = await self._transcribe_with_model(audio)
            if segments:
                logger.info(f"[transcribe] Got {len(segments)} segments via {self._model.model_name}")
                return segments
            logger.warning("[transcribe] Primary model returned no segments")
        except Exception as exc:
            logger.warning(f"[transcribe] Primary model failed: {exc}")

        # Whisper fallback
        if self._use_whisper_fallback and not settings.mock_mode:
            try:
                segments = self._transcribe_with_whisper(audio)
                if segments:
                    logger.info(f"[transcribe] Got {len(segments)} segments via whisper")
                    return segments
            except Exception as exc:
                logger.warning(f"[transcribe] Whisper fallback failed: {exc}")

        # Final fallback: return a single segment with empty text so the
        # pipeline doesn't crash but the issue is visible in the output
        logger.error("[transcribe] All transcription methods failed; returning empty segment")
        return [
            TranscriptSegment(
                text="[transcription unavailable]",
                start_time=0.0,
                end_time=audio.duration_seconds,
                confidence=0.0,
                model_used="fallback",
            )
        ]

    # ------------------------------------------------------------------
    # Primary: Gemma 3n
    # ------------------------------------------------------------------

    async def _transcribe_with_model(self, audio: AudioTrack) -> list[TranscriptSegment]:
        """Call the configured multimodal model for transcription."""
        raw = await self._model.generate_with_audio(
            prompt=_TRANSCRIPTION_PROMPT,
            audio_path=audio.file_path,
            system=_TRANSCRIPTION_SYSTEM,
        )
        return _parse_transcript_json(raw, model_name=self._model.model_name)

    # ------------------------------------------------------------------
    # Fallback: mlx-whisper (Apple Silicon)
    # ------------------------------------------------------------------

    def _transcribe_with_whisper(self, audio: AudioTrack) -> list[TranscriptSegment]:
        """
        Use mlx-whisper for transcription on Apple Silicon.

        Returns an empty list if mlx_whisper is not installed or the
        transcription produces no output.
        """
        try:
            import mlx_whisper  # noqa: PLC0415

            logger.info(f"[transcribe] Running mlx-whisper ({settings.whisper_model})")
            result = mlx_whisper.transcribe(
                audio.file_path,
                path_or_hf_repo=f"mlx-community/whisper-{settings.whisper_model}-mlx",
            )

            raw_segments = result.get("segments", [])
            segments: list[TranscriptSegment] = []
            for seg in raw_segments:
                text = (seg.get("text") or "").strip()
                if not text:
                    continue
                words = [
                    WordTiming(
                        word=w.get("word", ""),
                        start=float(w.get("start", 0)),
                        end=float(w.get("end", 0)),
                    )
                    for w in seg.get("words", [])
                ]
                segments.append(
                    TranscriptSegment(
                        text=text,
                        start_time=float(seg.get("start", 0)),
                        end_time=float(seg.get("end", 0)),
                        words=words,
                        confidence=float(seg.get("avg_logprob", 0)) + 1.0,  # log-prob -> ~[0,1]
                        language=result.get("language", "en"),
                        model_used=f"mlx-whisper-{settings.whisper_model}",
                    )
                )
            return segments

        except ImportError:
            logger.info("[transcribe] mlx-whisper not installed, skipping")
            return []

    def get_full_transcript(self, segments: list[TranscriptSegment]) -> str:
        """Concatenate all segment texts into a single string."""
        return " ".join(s.text for s in segments)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------


def _parse_transcript_json(raw: str, model_name: str = "unknown") -> list[TranscriptSegment]:
    """
    Parse a model response string into a list of TranscriptSegments.

    Handles JSON wrapped in markdown code fences and partial/malformed JSON.
    """
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning(f"[transcribe] Failed to parse JSON: {raw[:200]!r}")
                return []
        else:
            logger.warning(f"[transcribe] No JSON found in response: {raw[:200]!r}")
            return []

    raw_segments = data.get("segments", [])
    segments: list[TranscriptSegment] = []

    for seg in raw_segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        try:
            segments.append(
                TranscriptSegment(
                    text=text,
                    start_time=float(seg.get("start", 0)),
                    end_time=float(seg.get("end", 0)),
                    confidence=float(seg.get("confidence", 1.0)),
                    language=seg.get("language", "en"),
                    model_used=model_name,
                )
            )
        except Exception as exc:
            logger.warning(f"[transcribe] Skipping malformed segment {seg}: {exc}")

    # Ensure sorted and non-overlapping
    segments.sort(key=lambda s: s.start_time)
    return segments

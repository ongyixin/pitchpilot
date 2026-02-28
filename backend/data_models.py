"""
Intermediate data models for the PitchPilot ingestion pipeline.

All timestamps are in seconds (float) relative to the start of the video.
All models are Pydantic v2 and JSON-serializable so they can be written to
disk between pipeline stages and consumed by downstream agents.
"""

from __future__ import annotations

import uuid
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ClaimCategory(str, Enum):
    """Taxonomy of claim types that the ingestion pipeline can surface."""

    PRODUCT_CLAIM = "product_claim"
    VALUE_PROPOSITION = "value_proposition"
    TECHNICAL_CLAIM = "technical_claim"
    COMPLIANCE_SENSITIVE = "compliance_sensitive"
    COMPARISON_CLAIM = "comparison_claim"
    AUTOMATION_CLAIM = "automation_claim"
    PRIVACY_CLAIM = "privacy_claim"
    ACCURACY_CLAIM = "accuracy_claim"
    FINANCIAL_CLAIM = "financial_claim"
    UNCLASSIFIED = "unclassified"


class ClaimSource(str, Enum):
    """Which raw signal the claim was derived from."""

    TRANSCRIPT = "transcript"
    OCR = "ocr"
    BOTH = "both"


class OCRSourceType(str, Enum):
    """Where the OCR input came from."""

    VIDEO_FRAME = "video_frame"
    POLICY_DOCUMENT = "policy_document"
    UPLOADED_DOCUMENT = "uploaded_document"


# ---------------------------------------------------------------------------
# Video metadata
# ---------------------------------------------------------------------------


class VideoMetadata(BaseModel):
    """Describes a video file that has been accepted by the pipeline."""

    session_id: str = Field(description="Unique session identifier")
    file_path: str = Field(description="Absolute path to the video file on disk")
    filename: str = Field(description="Original filename")
    duration_seconds: float = Field(description="Total video duration in seconds")
    fps: float = Field(description="Native frame rate of the video")
    width: int = Field(description="Frame width in pixels")
    height: int = Field(description="Frame height in pixels")
    total_frames: int = Field(description="Total number of frames in the video")
    file_size_bytes: int = Field(description="File size in bytes")

    @field_validator("duration_seconds", "fps")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Must be positive")
        return v


# ---------------------------------------------------------------------------
# Extracted frames
# ---------------------------------------------------------------------------


class ExtractedFrame(BaseModel):
    """A single frame extracted from the video at a specific timestamp."""

    frame_index: int = Field(
        description="Sequential index among extracted frames (0-based)"
    )
    original_frame_number: int = Field(
        description="Frame number in the original video stream"
    )
    timestamp: float = Field(
        description="Timestamp in seconds from the start of the video"
    )
    file_path: str = Field(description="Absolute path to the saved frame image (JPEG)")
    width: int = Field(description="Frame width in pixels")
    height: int = Field(description="Frame height in pixels")
    is_keyframe: bool = Field(
        default=False,
        description="True if this frame was detected as a scene-change keyframe",
    )
    scene_change_score: Optional[float] = Field(
        default=None,
        description="Normalised [0,1] frame-difference score used for keyframe detection",
    )
    phash: str = Field(
        default="",
        description=(
            "Perceptual average-hash (aHash) hex string for OCR deduplication. "
            "Two frames with Hamming distance <= 5 are considered near-identical."
        ),
    )


# ---------------------------------------------------------------------------
# Audio track
# ---------------------------------------------------------------------------


class AudioTrack(BaseModel):
    """Extracted audio file produced from the video."""

    file_path: str = Field(description="Absolute path to the WAV file")
    duration_seconds: float = Field(description="Duration of the audio track in seconds")
    sample_rate: int = Field(description="Sample rate in Hz (typically 16000 for ASR)")
    channels: int = Field(default=1, description="Number of audio channels")
    source_video_path: str = Field(description="Path to the video this was extracted from")


# ---------------------------------------------------------------------------
# OCR blocks
# ---------------------------------------------------------------------------


class BoundingBox(BaseModel):
    """Pixel-space bounding box for an OCR text region."""

    x: int = Field(description="Left edge in pixels")
    y: int = Field(description="Top edge in pixels")
    width: int = Field(description="Box width in pixels")
    height: int = Field(description="Box height in pixels")


class OCRBlock(BaseModel):
    """A single contiguous text block recovered by OCR from a frame or document page."""

    block_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique block identifier",
    )
    text: str = Field(description="Extracted text content")
    source_type: OCRSourceType = Field(
        description="Whether this came from a video frame or an uploaded document"
    )
    # Frame-specific fields (populated when source_type == VIDEO_FRAME)
    frame_index: Optional[int] = Field(
        default=None, description="Index of the frame this block was extracted from"
    )
    timestamp: Optional[float] = Field(
        default=None,
        description="Video timestamp (seconds) for the frame this block came from",
    )
    # Document-specific fields (populated when source_type == *_DOCUMENT)
    page_number: Optional[int] = Field(
        default=None,
        description="Page number (1-based) within the source document",
    )
    document_path: Optional[str] = Field(
        default=None, description="Path to the source document"
    )
    bounding_box: Optional[BoundingBox] = Field(
        default=None, description="Pixel-space location within the source image"
    )
    confidence: float = Field(
        default=1.0,
        description="Model confidence score [0, 1]; 1.0 for mock/exact extractions",
    )
    model_used: str = Field(
        default="mock",
        description="Name of the model or method used for this extraction",
    )


# ---------------------------------------------------------------------------
# Transcript segments
# ---------------------------------------------------------------------------


class WordTiming(BaseModel):
    """Word-level timing from an ASR model (optional; only when the model supports it)."""

    word: str
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    confidence: float = Field(default=1.0)


class TranscriptSegment(BaseModel):
    """A continuous speech segment from the audio transcription."""

    segment_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique segment identifier",
    )
    text: str = Field(description="Transcribed text for this segment")
    start_time: float = Field(description="Segment start time in seconds")
    end_time: float = Field(description="Segment end time in seconds")
    speaker: Optional[str] = Field(
        default=None,
        description="Speaker label (populated when diarisation is enabled)",
    )
    words: list[WordTiming] = Field(
        default_factory=list,
        description="Word-level timings (empty list if model does not support)",
    )
    confidence: float = Field(
        default=1.0,
        description="Average ASR confidence for this segment",
    )
    language: str = Field(default="en", description="ISO 639-1 language code")
    model_used: str = Field(
        default="mock",
        description="Name of the transcription model/method used",
    )

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


# ---------------------------------------------------------------------------
# Candidate claims
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """A single piece of evidence that supports (or contextualises) a claim."""

    source_type: ClaimSource
    text: str = Field(description="Verbatim text snippet from which the claim was inferred")
    timestamp: Optional[float] = Field(
        default=None,
        description="Timestamp (seconds) of the evidence; None for document evidence",
    )
    frame_index: Optional[int] = Field(default=None)
    segment_id: Optional[str] = Field(default=None, description="TranscriptSegment ID")
    ocr_block_id: Optional[str] = Field(default=None, description="OCRBlock ID")


class Claim(BaseModel):
    """A candidate claim extracted from the presentation, ready for agent analysis."""

    claim_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique claim identifier",
    )
    text: str = Field(
        description="Normalised claim statement as extracted from the presentation"
    )
    category: ClaimCategory = Field(
        description="Claim type classification"
    )
    source: ClaimSource = Field(
        description="Which raw signal(s) contributed to this claim"
    )
    timestamp_start: float = Field(
        description="Earliest timestamp (seconds) at which this claim appears"
    )
    timestamp_end: float = Field(
        description="Latest timestamp (seconds) at which this claim appears"
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Supporting evidence items (transcript snippets, OCR blocks)",
    )
    confidence: float = Field(
        default=1.0,
        description="Extraction confidence [0, 1]",
    )
    model_used: str = Field(
        default="mock",
        description="Name of the model used to extract this claim",
    )
    raw_response: Optional[str] = Field(
        default=None,
        description="Raw model output used for this extraction (for debugging)",
    )


# ---------------------------------------------------------------------------
# Top-level ingestion result
# ---------------------------------------------------------------------------


class IngestionResult(BaseModel):
    """
    Complete output of the multimodal ingestion pipeline for one session.

    This artifact is written to disk as JSON after the pipeline completes
    and consumed by the orchestrator / downstream agents.
    """

    session_id: str = Field(description="Unique session identifier")
    video_metadata: VideoMetadata
    frames: list[ExtractedFrame] = Field(
        description="All extracted frames, ordered by timestamp"
    )
    audio_track: AudioTrack
    ocr_blocks: list[OCRBlock] = Field(
        description="All OCR blocks from frames AND uploaded documents, ordered by timestamp/page"
    )
    transcript_segments: list[TranscriptSegment] = Field(
        description="All transcript segments, ordered by start_time"
    )
    claims: list[Claim] = Field(
        description="Candidate claims ordered by timestamp_start"
    )
    policy_documents: list[str] = Field(
        default_factory=list,
        description="Paths to policy/compliance documents that were ingested",
    )
    pipeline_version: str = Field(
        default="0.1.0",
        description="Version string for the ingestion pipeline",
    )
    processing_time_seconds: Optional[float] = Field(
        default=None,
        description="Wall-clock time to run the full pipeline",
    )

    def summary(self) -> dict:
        """Return a brief human-readable summary of the ingestion result."""
        return {
            "session_id": self.session_id,
            "video_duration_s": self.video_metadata.duration_seconds,
            "frames_extracted": len(self.frames),
            "keyframes": sum(1 for f in self.frames if f.is_keyframe),
            "ocr_blocks": len(self.ocr_blocks),
            "transcript_segments": len(self.transcript_segments),
            "claims": len(self.claims),
            "claim_categories": {
                cat.value: sum(1 for c in self.claims if c.category == cat)
                for cat in ClaimCategory
                if any(c.category == cat for c in self.claims)
            },
            "policy_documents": len(self.policy_documents),
        }

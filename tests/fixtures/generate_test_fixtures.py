"""
Test fixture generator for the PitchPilot ingestion pipeline.

Generates:
  * A synthetic 10-second MP4 video with coloured slides and text overlays.
  * A corresponding silent WAV audio file (so ffmpeg extraction can succeed).
  * A sample policy document (.txt).

Run directly::

    python tests/fixtures/generate_test_fixtures.py

Output files will be written to data/test_outputs/.
"""

from __future__ import annotations

import struct
import subprocess
import wave
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent
PROJECT_ROOT = FIXTURES_DIR.parent.parent
TEST_OUTPUTS = PROJECT_ROOT / "data" / "test_outputs"
SAMPLE_POLICIES = PROJECT_ROOT / "data" / "sample_policies"

TEST_VIDEO_PATH = TEST_OUTPUTS / "sample_rehearsal.mp4"
TEST_AUDIO_PATH = TEST_OUTPUTS / "sample_audio.wav"
SAMPLE_POLICY_PATH = SAMPLE_POLICIES / "sample_policy.txt"


# ---------------------------------------------------------------------------
# Slide content for the synthetic video
# ---------------------------------------------------------------------------

SLIDES = [
    {
        "title": "PitchPilot",
        "subtitle": "The AI-powered demo rehearsal copilot",
        "bg_color": (30, 30, 80),   # dark blue
        "duration_s": 2,
    },
    {
        "title": "The Problem",
        "subtitle": "Teams rehearse but cannot objectively assess readiness",
        "bg_color": (80, 30, 30),   # dark red
        "duration_s": 2,
    },
    {
        "title": "Our Solution",
        "subtitle": "Fully automated compliance checking. 100% on-device.",
        "bg_color": (30, 80, 30),   # dark green
        "duration_s": 2,
    },
    {
        "title": "Key Claims",
        "subtitle": "Instant approval. Zero manual steps. 99.9% accuracy.",
        "bg_color": (60, 30, 80),   # dark purple
        "duration_s": 2,
    },
    {
        "title": "Privacy Guarantee",
        "subtitle": "Your data never leaves the device. Private by design.",
        "bg_color": (30, 60, 80),   # dark teal
        "duration_s": 2,
    },
]

FPS = 30
FRAME_WIDTH = 640
FRAME_HEIGHT = 360


def _render_slide(slide: dict) -> np.ndarray:
    """Render a single slide as a numpy array (BGR)."""
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    frame[:] = slide["bg_color"]

    # Title
    cv2.putText(
        frame,
        slide["title"],
        (40, FRAME_HEIGHT // 3),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    # Subtitle – word-wrap at ~50 chars
    subtitle = slide["subtitle"]
    words = subtitle.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > 50:
            lines.append(current.strip())
            current = word
        else:
            current += " " + word
    if current.strip():
        lines.append(current.strip())

    y_start = FRAME_HEIGHT // 2
    for i, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (40, y_start + i * 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

    # Frame counter watermark (bottom right)
    return frame


def generate_test_video(output_path: Path = TEST_VIDEO_PATH) -> Path:
    """
    Generate a synthetic 10-second MP4 with slide-like frames.

    Returns:
        Path to the generated video file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, FPS, (FRAME_WIDTH, FRAME_HEIGHT))

    total_frames_written = 0
    for slide in SLIDES:
        n_frames = int(slide["duration_s"] * FPS)
        base_frame = _render_slide(slide)
        for i in range(n_frames):
            # Slight flicker to make frames non-identical (helps keyframe detection)
            noise = (np.random.rand(FRAME_HEIGHT, FRAME_WIDTH, 3) * 3).astype(np.uint8)
            frame = np.clip(base_frame.astype(int) + noise, 0, 255).astype(np.uint8)
            # Timestamp overlay
            cv2.putText(
                frame,
                f"{total_frames_written / FPS:.1f}s",
                (FRAME_WIDTH - 90, FRAME_HEIGHT - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (150, 150, 150),
                1,
            )
            writer.write(frame)
            total_frames_written += 1

    writer.release()
    print(f"[fixture] Video generated: {output_path} ({total_frames_written} frames @ {FPS} fps)")
    return output_path


def generate_silent_wav(
    output_path: Path = TEST_AUDIO_PATH,
    duration_s: float = 10.0,
    sample_rate: int = 16000,
) -> Path:
    """
    Generate a silent WAV file for testing transcription without ffmpeg.

    Returns:
        Path to the generated WAV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(duration_s * sample_rate)
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))
    print(f"[fixture] Silent WAV generated: {output_path} ({duration_s}s @ {sample_rate} Hz)")
    return output_path


def generate_sample_policy(output_path: Path = SAMPLE_POLICY_PATH) -> Path:
    """
    Write a realistic-looking sample compliance policy document.

    Returns:
        Path to the written file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = """\
ACME CORP — PRODUCT CLAIMS AND COMPLIANCE POLICY
Version 2.4 | Effective Date: January 1, 2026

1. AUTOMATION CLAIMS

1.1 Products or features described as "automated" must include a disclosure
    when manual review or human oversight is required in any operational path.

1.2 The phrase "fully automated" is prohibited unless the product processes
    100% of cases without human intervention, as verified by QA sign-off.

1.3 Acceptable alternative: "automated for standard cases; edge cases are
    reviewed by our compliance team within 24 hours."

2. APPROVAL AND PROCESSING TIME

2.1 Claims of "instant approval" must be qualified with the expected time
    range (e.g., "typically within seconds for standard submissions").

2.2 "Zero manual steps" claims are only permissible for products that have
    achieved Tier-1 automation certification from the Product Operations team.

2.3 For uncertified products, use: "minimal manual intervention required."

3. ACCURACY AND PERFORMANCE METRICS

3.1 All accuracy figures used in sales or marketing materials must be
    sourced from a published internal benchmark report, referenced by ID.

3.2 Claims of "99%" or higher accuracy require executive sign-off and must
    include the test dataset description and date.

3.3 Contextualise accuracy: state the task, dataset size, and timeframe.

4. PRIVACY AND DATA HANDLING

4.1 "On-device" or "private by design" claims are valid only if the product
    processes all data locally without transmitting customer data externally.

4.2 If any optional cloud functionality exists (even as a fallback), the
    privacy claim must be qualified: "on-device by default; cloud features
    are opt-in and clearly disclosed."

4.3 "Data never leaves the device" is a strong claim requiring legal review
    before use in customer-facing materials.

5. COMPARISON CLAIMS

5.1 Comparative claims (e.g., "faster than X", "more accurate than Y") must
    reference a specific, dated benchmark and be approved by Product Marketing.

5.2 Unnamed competitor comparisons ("unlike other solutions") are permitted
    only if the comparison is verifiable by an independent third party.

6. FINANCIAL PROJECTIONS

6.1 ROI claims must cite the assumption set and methodology.

6.2 "Guaranteed ROI" language is prohibited without legal review.

7. COMPLIANCE REVIEW PROCESS

7.1 All new claims must be submitted to compliance@acmecorp.example.com
    at least 5 business days before use in customer-facing contexts.

7.2 Urgent reviews (< 24h) require VP-level sponsorship.
"""
    output_path.write_text(content, encoding="utf-8")
    print(f"[fixture] Sample policy written: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Pre-built mock output fixtures (for testing without model calls)
# ---------------------------------------------------------------------------

MOCK_OCR_BLOCKS_JSON = """[
  {
    "block_id": "ocr-001",
    "text": "PitchPilot — The AI-powered demo rehearsal copilot",
    "source_type": "video_frame",
    "frame_index": 0,
    "timestamp": 0.0,
    "confidence": 0.97,
    "model_used": "mock-multimodal-v0"
  },
  {
    "block_id": "ocr-002",
    "text": "Our solution is fully automated and compliant.",
    "source_type": "video_frame",
    "frame_index": 2,
    "timestamp": 4.0,
    "confidence": 0.91,
    "model_used": "mock-multimodal-v0"
  },
  {
    "block_id": "ocr-003",
    "text": "Instant approval. Zero manual steps. 99.9% accuracy.",
    "source_type": "video_frame",
    "frame_index": 3,
    "timestamp": 6.0,
    "confidence": 0.88,
    "model_used": "mock-multimodal-v0"
  },
  {
    "block_id": "ocr-004",
    "text": "Your data never leaves the device. Private by design.",
    "source_type": "video_frame",
    "frame_index": 4,
    "timestamp": 8.0,
    "confidence": 0.93,
    "model_used": "mock-multimodal-v0"
  }
]"""

MOCK_TRANSCRIPT_JSON = """[
  {
    "segment_id": "seg-001",
    "text": "Welcome everyone, today I'm going to walk you through our pitch.",
    "start_time": 0.0,
    "end_time": 4.2,
    "confidence": 0.96,
    "language": "en",
    "model_used": "mock-multimodal-v0"
  },
  {
    "segment_id": "seg-002",
    "text": "Our platform provides fully automated compliance checking.",
    "start_time": 4.3,
    "end_time": 8.7,
    "confidence": 0.94,
    "language": "en",
    "model_used": "mock-multimodal-v0"
  },
  {
    "segment_id": "seg-003",
    "text": "We guarantee instant approval with zero manual review steps.",
    "start_time": 8.8,
    "end_time": 13.1,
    "confidence": 0.93,
    "language": "en",
    "model_used": "mock-multimodal-v0"
  },
  {
    "segment_id": "seg-004",
    "text": "Everything runs on-device. Your data never leaves the building.",
    "start_time": 13.2,
    "end_time": 17.5,
    "confidence": 0.97,
    "language": "en",
    "model_used": "mock-multimodal-v0"
  },
  {
    "segment_id": "seg-005",
    "text": "Our accuracy rate is 99.9 percent across all test datasets.",
    "start_time": 17.6,
    "end_time": 22.0,
    "confidence": 0.91,
    "language": "en",
    "model_used": "mock-multimodal-v0"
  }
]"""

MOCK_CLAIMS_JSON = """[
  {
    "claim_id": "claim-001",
    "text": "The platform provides fully automated compliance checking",
    "category": "automation_claim",
    "source": "transcript",
    "timestamp_start": 4.3,
    "timestamp_end": 8.7,
    "confidence": 0.94,
    "model_used": "mock-multimodal-v0",
    "evidence": [
      {
        "source_type": "transcript",
        "text": "Our platform provides fully automated compliance checking.",
        "timestamp": 4.3,
        "segment_id": "seg-002"
      }
    ]
  },
  {
    "claim_id": "claim-002",
    "text": "Instant approval with zero manual review steps is guaranteed",
    "category": "compliance_sensitive",
    "source": "both",
    "timestamp_start": 8.8,
    "timestamp_end": 13.1,
    "confidence": 0.93,
    "model_used": "mock-multimodal-v0",
    "evidence": [
      {
        "source_type": "transcript",
        "text": "We guarantee instant approval with zero manual review steps.",
        "timestamp": 8.8,
        "segment_id": "seg-003"
      },
      {
        "source_type": "ocr",
        "text": "Instant approval. Zero manual steps. 99.9% accuracy.",
        "timestamp": 6.0,
        "ocr_block_id": "ocr-003"
      }
    ]
  },
  {
    "claim_id": "claim-003",
    "text": "All data processing is on-device and data never leaves the building",
    "category": "privacy_claim",
    "source": "both",
    "timestamp_start": 13.2,
    "timestamp_end": 17.5,
    "confidence": 0.97,
    "model_used": "mock-multimodal-v0",
    "evidence": [
      {
        "source_type": "transcript",
        "text": "Everything runs on-device. Your data never leaves the building.",
        "timestamp": 13.2,
        "segment_id": "seg-004"
      },
      {
        "source_type": "ocr",
        "text": "Your data never leaves the device. Private by design.",
        "timestamp": 8.0,
        "ocr_block_id": "ocr-004"
      }
    ]
  },
  {
    "claim_id": "claim-004",
    "text": "Accuracy rate is 99.9% across all test datasets",
    "category": "accuracy_claim",
    "source": "transcript",
    "timestamp_start": 17.6,
    "timestamp_end": 22.0,
    "confidence": 0.91,
    "model_used": "mock-multimodal-v0",
    "evidence": [
      {
        "source_type": "transcript",
        "text": "Our accuracy rate is 99.9 percent across all test datasets.",
        "timestamp": 17.6,
        "segment_id": "seg-005"
      }
    ]
  }
]"""


if __name__ == "__main__":
    print("Generating PitchPilot test fixtures...")
    generate_test_video()
    generate_silent_wav()
    generate_sample_policy()
    print("\nAll fixtures generated successfully.")
    print(f"  Video : {TEST_VIDEO_PATH}")
    print(f"  Audio : {TEST_AUDIO_PATH}")
    print(f"  Policy: {SAMPLE_POLICY_PATH}")

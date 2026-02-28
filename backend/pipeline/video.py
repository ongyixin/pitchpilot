"""
Video processing utilities for the PitchPilot ingestion pipeline.

Responsibilities
----------------
* Save an uploaded video file to a session directory.
* Extract frames at a configurable FPS using OpenCV (single pass).
* Detect scene-change keyframes inline during extraction (no second disk read).
* Optionally save only keyframes to disk to minimize I/O (see keyframes_only_save).
* Downscale frames before JPEG encoding when max_dimension is set.
* Compute a lightweight perceptual hash per frame for OCR deduplication.
* Extract the audio track to a 16 kHz mono WAV file using ffmpeg.

Performance design
------------------
* All public sync functions are CPU-bound (OpenCV/ffmpeg).  Call them via
  ``asyncio.to_thread()`` from async code to avoid blocking the event loop.
* ``extract_frames_and_keyframes()`` replaces the two-pass approach (old
  ``extract_frames`` + ``detect_keyframes``) with a single OpenCV pass that
  computes pixel diff while reading frames.  This halves disk I/O and removes
  the second ``cv2.imread`` loop.
* ``async_extract_frames_and_keyframes()`` is the async entry point used by
  the ingestion pipeline.

Expected input/output
---------------------
    save_video(data, session_id, filename) -> VideoMetadata
    extract_frames_and_keyframes(meta, fps, ...) -> list[ExtractedFrame]
    async_extract_frames_and_keyframes(meta, fps, ...) -> list[ExtractedFrame]
    extract_audio(meta, output_dir) -> AudioTrack
    frame_phash(file_path) -> str
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from backend.config import SESSIONS_DIR, settings
from backend.data_models import AudioTrack, ExtractedFrame, VideoMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_dir(session_id: str) -> Path:
    """Return (and create) the base directory for a session's artifacts."""
    d = SESSIONS_DIR / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _frames_dir(session_id: str) -> Path:
    d = _session_dir(session_id) / "frames"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _audio_dir(session_id: str) -> Path:
    d = _session_dir(session_id) / "audio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _downscale_frame(frame: np.ndarray, max_dimension: int) -> np.ndarray:
    """
    Resize a frame so max(width, height) <= max_dimension, preserving aspect ratio.

    Returns the original array unchanged if already within bounds.
    """
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= max_dimension:
        return frame
    scale = max_dimension / longest
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def frame_phash(file_path: str, hash_size: int = 8) -> str:
    """
    Compute a simple average-hash (aHash) for a saved frame image.

    Returns a hex string of ``hash_size*hash_size`` bits.  Two frames are
    considered near-identical when their Hamming distance is <= 5.

    Args:
        file_path: Path to the JPEG frame.
        hash_size: Grid dimension for the hash (8 → 64-bit hash).

    Returns:
        Hex string representing the perceptual hash, or "" on failure.
    """
    img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return ""
    small = cv2.resize(img, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    mean_val = small.mean()
    bits = (small > mean_val).flatten()
    # Pack bits into an integer, convert to hex
    value = int("".join("1" if b else "0" for b in bits), 2)
    return f"{value:0{hash_size * hash_size // 4}x}"


def _phash_distance(a: str, b: str) -> int:
    """Hamming distance between two phash hex strings. Returns 999 on mismatch."""
    if not a or not b or len(a) != len(b):
        return 999
    a_int = int(a, 16)
    b_int = int(b, 16)
    return bin(a_int ^ b_int).count("1")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_video(
    data: bytes,
    filename: str,
    session_id: Optional[str] = None,
) -> VideoMetadata:
    """
    Persist raw video bytes to disk and return metadata.

    Args:
        data: Raw bytes of the uploaded video file.
        filename: Original filename (used for extension preservation).
        session_id: Optional existing session ID.  A new UUID is generated if
            not provided.

    Returns:
        VideoMetadata populated from the saved file.
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    sess_dir = _session_dir(session_id)
    ext = Path(filename).suffix or ".mp4"
    video_path = sess_dir / f"video{ext}"

    video_path.write_bytes(data)
    logger.info(f"[video] Saved {len(data):,} bytes -> {video_path}")

    return _probe_video(str(video_path), session_id, filename)


def save_video_file(
    src_path: str,
    session_id: Optional[str] = None,
) -> VideoMetadata:
    """
    Copy an existing video file into a session directory and return metadata.

    Args:
        src_path: Absolute path to an existing video file.
        session_id: Optional existing session ID.

    Returns:
        VideoMetadata populated from the copied file.
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    src = Path(src_path)
    sess_dir = _session_dir(session_id)
    dest = sess_dir / f"video{src.suffix}"

    shutil.copy2(src, dest)
    logger.info(f"[video] Copied {src} -> {dest}")

    return _probe_video(str(dest), session_id, src.name)


def _probe_video(video_path: str, session_id: str, original_filename: str) -> VideoMetadata:
    """Use OpenCV to read basic video metadata without decoding every frame."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    duration = total_frames / fps if fps > 0 else 0.0
    file_size = os.path.getsize(video_path)

    meta = VideoMetadata(
        session_id=session_id,
        file_path=str(Path(video_path).resolve()),
        filename=original_filename,
        duration_seconds=max(duration, 0.001),
        fps=fps,
        width=width,
        height=height,
        total_frames=total_frames,
        file_size_bytes=file_size,
    )
    logger.info(
        f"[video] Probed: {width}x{height} @ {fps:.1f} fps, "
        f"{duration:.1f}s, {total_frames} frames"
    )
    return meta


def extract_frames_and_keyframes(
    meta: VideoMetadata,
    fps: Optional[float] = None,
    output_dir: Optional[str] = None,
    quality: int = 90,
    keyframe_threshold: Optional[float] = None,
    keyframes_only_save: bool = True,
    max_dimension: Optional[int] = None,
    phash_similarity_threshold: int = 5,
) -> list[ExtractedFrame]:
    """
    Single-pass frame extraction with inline keyframe detection.

    Replaces the old two-pass (extract_frames + detect_keyframes) approach.
    In one OpenCV pass:
      1. Decode every Nth native frame (based on target FPS).
      2. Compute grayscale pixel diff vs. previous extracted frame.
      3. Mark as keyframe if diff > threshold.
      4. Optionally downscale before JPEG encoding.
      5. Skip saving to disk if keyframes_only_save=True and not a keyframe.
      6. Compute perceptual hash (aHash) for OCR dedup.

    Args:
        meta: VideoMetadata for the source video.
        fps: Target extraction rate. Defaults to settings.extraction_fps.
        output_dir: Directory to write JPEG images.
        quality: JPEG quality 1-100.
        keyframe_threshold: Pixel-diff threshold [0,1]. Defaults to
            settings.keyframe_diff_threshold.
        keyframes_only_save: If True, only write keyframe JPEGs to disk.
            Non-keyframes still appear in the returned list (with
            file_path="") so timing data is preserved.
        max_dimension: Downscale frames before encoding if set. Defaults to
            settings.frame_max_dimension (0 = no downscaling).
        phash_similarity_threshold: Maximum Hamming distance between two
            frame hashes to consider them near-identical (skip OCR).

    Returns:
        List of ExtractedFrame ordered by timestamp.
    """
    target_fps = fps if fps is not None else settings.extraction_fps
    cutoff = keyframe_threshold if keyframe_threshold is not None else settings.keyframe_diff_threshold
    max_dim = max_dimension if max_dimension is not None else settings.frame_max_dimension
    out_dir = Path(output_dir) if output_dir else _frames_dir(meta.session_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(meta.file_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {meta.file_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_step = max(1, round(native_fps / target_fps))
    logger.info(
        f"[video] Single-pass extraction: target={target_fps:.1f} fps, "
        f"native={native_fps:.1f} fps, step={frame_step}, "
        f"keyframes_only_save={keyframes_only_save}, max_dim={max_dim}"
    )

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    frames: list[ExtractedFrame] = []
    prev_gray: Optional[np.ndarray] = None
    native_frame_num = 0
    extracted_index = 0
    keyframe_count = 0

    while True:
        ret, frame_bgr = cap.read()
        if not ret:
            break

        if native_frame_num % frame_step == 0:
            timestamp = native_frame_num / native_fps

            # Compute scene-change score
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            if prev_gray is None:
                is_keyframe = True
                scene_score = 1.0
            else:
                diff = np.mean(np.abs(gray.astype(np.float32) - prev_gray.astype(np.float32))) / 255.0
                scene_score = round(float(diff), 4)
                is_keyframe = bool(diff > cutoff)

            prev_gray = gray

            # Downscale for encoding if needed
            save_frame = _downscale_frame(frame_bgr, max_dim) if max_dim > 0 else frame_bgr
            h, w = save_frame.shape[:2]

            # Decide whether to write to disk
            if is_keyframe or not keyframes_only_save:
                frame_filename = f"frame_{extracted_index:05d}.jpg"
                frame_path = out_dir / frame_filename
                cv2.imwrite(str(frame_path), save_frame, encode_params)
                file_path_str = str(frame_path.resolve())
                # Compute perceptual hash for OCR dedup
                phash = frame_phash(file_path_str)
                if is_keyframe:
                    keyframe_count += 1
            else:
                file_path_str = ""
                phash = ""

            frames.append(
                ExtractedFrame(
                    frame_index=extracted_index,
                    original_frame_number=native_frame_num,
                    timestamp=round(timestamp, 3),
                    file_path=file_path_str,
                    width=w,
                    height=h,
                    is_keyframe=is_keyframe,
                    scene_change_score=scene_score,
                    phash=phash,
                )
            )
            extracted_index += 1

        native_frame_num += 1

    cap.release()
    logger.info(
        f"[video] Extracted {len(frames)} frames, "
        f"{keyframe_count} keyframes written to {out_dir}"
    )
    return frames


async def async_extract_frames_and_keyframes(
    meta: VideoMetadata,
    **kwargs,
) -> list[ExtractedFrame]:
    """
    Async wrapper: runs extract_frames_and_keyframes in a thread pool.

    Use this from async ingestion code to avoid blocking the event loop.
    All kwargs are forwarded to extract_frames_and_keyframes().
    """
    return await asyncio.to_thread(extract_frames_and_keyframes, meta, **kwargs)


def extract_audio(
    meta: VideoMetadata,
    output_dir: Optional[str] = None,
    sample_rate: Optional[int] = None,
) -> AudioTrack:
    """
    Extract the audio track from a video file as a 16 kHz mono WAV.

    Requires ffmpeg to be installed and available on PATH.

    Args:
        meta: VideoMetadata for the source video.
        output_dir: Directory to write the WAV file.
        sample_rate: Sample rate in Hz. Defaults to settings.audio_sample_rate.

    Returns:
        AudioTrack pointing to the extracted WAV file.

    Raises:
        RuntimeError: If ffmpeg is not installed or the extraction fails.
    """
    sr = sample_rate if sample_rate is not None else settings.audio_sample_rate
    out_dir = Path(output_dir) if output_dir else _audio_dir(meta.session_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    wav_path = out_dir / "audio.wav"

    _check_ffmpeg()

    cmd = [
        "ffmpeg",
        "-y",
        "-i", meta.file_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sr),
        "-ac", "1",
        str(wav_path),
    ]

    logger.info(f"[video] Extracting audio: {meta.file_path} -> {wav_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        stderr_tail = result.stderr[-500:]
        if "does not contain any stream" in result.stderr or "no streams" in result.stderr.lower():
            logger.warning("[video] Video has no audio stream; skipping audio extraction")
            raise RuntimeError("Video has no audio stream")
        logger.error(f"[video] ffmpeg stderr: {stderr_tail}")
        raise RuntimeError(
            f"ffmpeg audio extraction failed (exit {result.returncode}). "
            "Ensure ffmpeg is installed: brew install ffmpeg"
        )

    audio_track = AudioTrack(
        file_path=str(wav_path.resolve()),
        duration_seconds=meta.duration_seconds,
        sample_rate=sr,
        channels=1,
        source_video_path=meta.file_path,
    )
    logger.info(f"[video] Audio extracted: {wav_path} ({sr} Hz mono)")
    return audio_track


async def async_extract_audio(meta: VideoMetadata, **kwargs) -> AudioTrack:
    """Async wrapper: runs extract_audio in a thread pool."""
    return await asyncio.to_thread(extract_audio, meta, **kwargs)


def cleanup_session_artifacts(session_id: str) -> None:
    """
    Delete extracted frames and audio for a session to free disk space.

    Called after report generation when settings.retain_artifacts is False.
    The session directory itself (with ingestion_result.json) is preserved.

    Args:
        session_id: The session whose artifacts should be removed.
    """
    sess_dir = SESSIONS_DIR / session_id
    for subdir in ("frames", "audio"):
        target = sess_dir / subdir
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            logger.info(f"[video] Cleaned up {target}")

    # Also remove the raw video file to free space
    for video_file in sess_dir.glob("video.*"):
        video_file.unlink(missing_ok=True)
        logger.info(f"[video] Removed video file {video_file}")


def _check_ffmpeg() -> None:
    """Raise RuntimeError with a helpful message if ffmpeg is not on PATH."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it with:\n"
            "  macOS:  brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg"
        )


def get_timestamp_for_frame(frame_number: int, fps: float) -> float:
    """Convert a native frame number to a wall-clock timestamp in seconds."""
    return frame_number / fps if fps > 0 else 0.0


# ---------------------------------------------------------------------------
# Legacy compatibility shims
# ---------------------------------------------------------------------------
# The old two-function API is kept so existing tests and imports don't break.
# Both delegates to the new single-pass function.


def extract_frames(
    meta: VideoMetadata,
    fps: Optional[float] = None,
    output_dir: Optional[str] = None,
    quality: int = 90,
) -> list[ExtractedFrame]:
    """Compat shim: runs single-pass extraction, saves all frames."""
    return extract_frames_and_keyframes(
        meta,
        fps=fps,
        output_dir=output_dir,
        quality=quality,
        keyframes_only_save=False,
    )


def detect_keyframes(
    frames: list[ExtractedFrame],
    threshold: Optional[float] = None,
) -> list[ExtractedFrame]:
    """
    Compat shim: keyframe scores are already populated by extract_frames_and_keyframes.

    If called after the new single-pass function, this is a no-op.
    If called after the legacy extract_frames shim (which saves all frames),
    it re-reads from disk and computes diffs as before.
    """
    cutoff = threshold if threshold is not None else settings.keyframe_diff_threshold

    if not frames:
        return frames

    # Check if keyframe detection was already done in-pass
    if any(f.scene_change_score is not None and f.scene_change_score > 0 for f in frames[1:]):
        logger.debug("[video] detect_keyframes: scores already populated, skipping re-computation")
        return frames

    # Fallback: re-read from disk (legacy path)
    prev_gray: Optional[np.ndarray] = None
    for frame in frames:
        if not frame.file_path or not Path(frame.file_path).exists():
            continue
        img = cv2.imread(frame.file_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        if prev_gray is None:
            frame.is_keyframe = True
            frame.scene_change_score = 1.0
        else:
            diff = np.mean(np.abs(img.astype(float) - prev_gray.astype(float))) / 255.0
            frame.scene_change_score = round(float(diff), 4)
            frame.is_keyframe = bool(diff > cutoff)
        prev_gray = img

    keyframe_count = sum(1 for f in frames if f.is_keyframe)
    logger.info(
        f"[video] Keyframe detection (legacy): {keyframe_count}/{len(frames)} frames "
        f"marked (threshold={cutoff})"
    )
    return frames

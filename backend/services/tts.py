"""
TTSService — on-device text-to-speech for earpiece cues.

Strategy (tiered for low latency):
  1. Pre-rendered clip bank (~30 common cues, sub-10ms playback start)
     Clips live in data/cue_bank/<cue_slug>.wav
  2. macOS system TTS via `say -r 200` (~50-100ms, Apple Silicon)
  3. Piper ONNX TTS (~50ms on Apple Silicon, cross-platform)

The service returns base64-encoded WAV audio that the frontend decodes and
plays through the earpiece output device.  If no audio can be produced in time
(circuit-breaker), audio_b64=None is returned and the frontend falls back to
on-screen text display.
"""

from __future__ import annotations

import asyncio
import base64
import re
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.config import TTS_CUE_BANK_PATH, TTS_ENGINE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    """Convert a cue string to a filesystem-safe slug for pre-rendered lookup."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower().strip()).strip("_")


def _load_clip(slug: str) -> Optional[bytes]:
    """Try to load a pre-rendered audio clip from the cue bank."""
    for ext in (".wav", ".mp3"):
        path = Path(TTS_CUE_BANK_PATH) / f"{slug}{ext}"
        if path.exists():
            return path.read_bytes()
    return None


async def _synthesize_system_tts(text: str) -> Optional[bytes]:
    """
    Synthesise short audio on macOS using the `say` command.
    Outputs AIFF then converts to WAV via afconvert for cross-browser support.
    Falls back gracefully on non-macOS or if `say` is not available.
    """
    aiff_path = ""
    wav_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            aiff_path = tmp.name
        wav_path = aiff_path.replace(".aiff", ".wav")

        proc = await asyncio.create_subprocess_exec(
            "say", "-r", "200", "-o", aiff_path, text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=3.0)

        # Convert AIFF → WAV (linear PCM) for universal browser decodeAudioData support
        conv = await asyncio.create_subprocess_exec(
            "afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, wav_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(conv.wait(), timeout=2.0)

        data = Path(wav_path).read_bytes()
        return data
    except (FileNotFoundError, asyncio.TimeoutError, OSError) as exc:
        # If afconvert fails, try returning the raw AIFF (Safari handles it)
        if aiff_path and Path(aiff_path).exists():
            try:
                return Path(aiff_path).read_bytes()
            except OSError:
                pass
        logger.debug(f"[tts] system TTS failed: {exc}")
        return None
    finally:
        for p in (aiff_path, wav_path):
            if p:
                Path(p).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# TTSService
# ---------------------------------------------------------------------------


class TTSService:
    """
    Provides on-device TTS audio for earpiece cues.

    Example usage in CueSynthesizer / live_ws.py:
        tts = TTSService()
        audio_b64 = await tts.synthesize("compliance risk")
        # audio_b64 is a base64 str or None (fall through to text-only cue)
    """

    def __init__(self) -> None:
        self._engine = TTS_ENGINE
        logger.info(f"[tts] TTSService initialised | engine={self._engine}")

    async def synthesize(self, text: str) -> Optional[str]:
        """
        Attempt to produce base64-encoded audio for the given cue text.

        Returns None if audio cannot be produced in time so that the caller
        can degrade gracefully to a text-only cue.
        """
        # 1. Pre-rendered clip bank (fastest path)
        clip = _load_clip(_slug(text))
        if clip:
            logger.debug(f"[tts] pre-rendered hit | text='{text}'")
            return base64.b64encode(clip).decode()

        if self._engine == "prerendered":
            logger.debug(f"[tts] prerendered-only mode — no clip for '{text}'")
            return None

        # 2. System TTS (macOS say)
        if self._engine in ("system", "auto"):
            audio = await _synthesize_system_tts(text)
            if audio:
                logger.debug(f"[tts] system TTS ok | text='{text}' | bytes={len(audio)}")
                return base64.b64encode(audio).decode()

        # 3. Piper ONNX — placeholder; wire up when piper binary is present
        if self._engine == "piper":
            logger.warning("[tts] piper engine not yet wired — returning None")
            return None

        logger.debug(f"[tts] all engines failed for '{text}'")
        return None

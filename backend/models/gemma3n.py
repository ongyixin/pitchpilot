"""
Gemma 3n adapter — multimodal OCR, transcription, and claim extraction.

Backend selection (controlled by settings / env vars):

  ``PITCHPILOT_GEMMA3N_BACKEND=huggingface``  (default)
      Uses Gemma3nHFAdapter — full multimodal weights from HuggingFace,
      including the vision and audio encoders.  Requires a HuggingFace
      account with the Gemma licence accepted and ``huggingface-cli login``.

  ``PITCHPILOT_GEMMA3N_BACKEND=ollama``
      Uses Gemma3nAdapter (Ollama GGUF) — text + image only; audio calls
      return empty string and fall through to the mlx-whisper fallback.

When ``settings.mock_mode`` is True, MockMultimodalAdapter is always used
regardless of backend setting.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.config import settings
from backend.models.base import BaseMultimodalModel
from backend.models.ollama_client import ollama_post

# Keep-alive duration sent with every request so Ollama does not unload the
# model between back-to-back pipeline calls.
_KEEP_ALIVE = "10m"


class Gemma3nAdapter(BaseMultimodalModel):
    """Wraps the Ollama REST API to call Gemma 3n E4B."""

    def __init__(self, model: Optional[str] = None):
        self._model = model or settings.gemma3n_model

    @property
    def model_name(self) -> str:
        return self._model

    async def _generate(self, payload: dict) -> str:
        """POST to /api/generate using the shared retrying client."""
        payload.setdefault("keep_alive", _KEEP_ALIVE)
        data = await ollama_post("/api/generate", payload)
        return data.get("response", "")

    async def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        return await self._generate(payload)

    async def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        return await self._generate(payload)

    async def generate_with_audio(
        self,
        prompt: str,
        audio_path: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        # The GGUF version of gemma3n served by Ollama is text-only; the audio
        # encoder is not included in the quantised weights. This call will always
        # return an empty/useless response. TranscriptionPipeline falls back to
        # mlx-whisper automatically when this returns no segments.
        logger.warning(
            "[gemma3n] generate_with_audio called but gemma3n:e4b (Ollama GGUF) "
            "does not include an audio encoder. Returning empty string so the "
            "caller can fall back to mlx-whisper."
        )
        return ""

    async def is_available(self) -> bool:
        from backend.models.ollama_client import get_ollama_client
        try:
            r = await get_ollama_client().get("/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    async def aclose(self) -> None:
        pass  # shared client — closed by close_ollama_client() at shutdown


class MockMultimodalAdapter(BaseMultimodalModel):
    """
    Deterministic stub that mimics Gemma 3n responses without any model.

    Used when settings.mock_mode is True or when Ollama is not running.
    Returns structurally-valid JSON that downstream pipeline stages can parse.
    """

    @property
    def model_name(self) -> str:
        return "mock-multimodal-v0"

    async def generate_text(self, prompt: str, system: Optional[str] = None,
                            temperature: float = 0.2, max_tokens: int = 2048) -> str:
        logger.debug("[MOCK] generate_text called")
        return (
            '{"claims": ['
            '  {"text": "The platform provides fully automated compliance checking",'
            '   "category": "automation_claim", "confidence": 0.94,'
            '   "evidence": "Our platform provides fully automated compliance checking."},'
            '  {"text": "Instant approval with zero manual review steps is guaranteed",'
            '   "category": "compliance_sensitive", "confidence": 0.93,'
            '   "evidence": "We guarantee instant approval with zero manual review steps."},'
            '  {"text": "All data processing is on-device and never leaves the building",'
            '   "category": "privacy_claim", "confidence": 0.97,'
            '   "evidence": "Everything runs on-device. Your data never leaves the building."},'
            '  {"text": "Accuracy rate is 99.9% across all test datasets",'
            '   "category": "accuracy_claim", "confidence": 0.91,'
            '   "evidence": "Our accuracy rate is 99.9 percent across all test datasets."}'
            "]}"
        )

    async def generate_with_image(self, prompt: str, image_path: str,
                                  system: Optional[str] = None,
                                  temperature: float = 0.2, max_tokens: int = 2048) -> str:
        logger.debug(f"[MOCK] generate_with_image called for {image_path}")
        stem = Path(image_path).stem
        return (
            '{"blocks": ['
            '  {"text": "PitchPilot Demo — Slide Overview", "confidence": 0.97},'
            f' {{"text": "Frame: {stem}", "confidence": 0.95}},'
            '  {"text": "Our solution is fully automated and compliant.", "confidence": 0.91},'
            '  {"text": "Instant approval, zero manual steps.", "confidence": 0.88},'
            '  {"text": "100% on-device, private by design.", "confidence": 0.93}'
            "]}"
        )

    async def generate_with_audio(self, prompt: str, audio_path: str,
                                  system: Optional[str] = None,
                                  temperature: float = 0.1, max_tokens: int = 4096) -> str:
        logger.debug(f"[MOCK] generate_with_audio called for {audio_path}")
        return (
            '{"segments": ['
            '  {"text": "Welcome everyone, today I\'m going to walk you through our pitch.",'
            '   "start": 0.0, "end": 4.2, "confidence": 0.96},'
            '  {"text": "Our platform provides fully automated compliance checking.",'
            '   "start": 4.3, "end": 8.7, "confidence": 0.94},'
            '  {"text": "We guarantee instant approval with zero manual review steps.",'
            '   "start": 8.8, "end": 13.1, "confidence": 0.93},'
            '  {"text": "Everything runs on-device. Your data never leaves the building.",'
            '   "start": 13.2, "end": 17.5, "confidence": 0.97},'
            '  {"text": "Our accuracy rate is 99.9 percent across all test datasets.",'
            '   "start": 17.6, "end": 22.0, "confidence": 0.91}'
            "]}"
        )


def get_gemma3n_adapter() -> BaseMultimodalModel:
    """
    Return the appropriate Gemma 3n adapter based on settings.

    Selection priority:
      1. mock_mode=True          → MockMultimodalAdapter (no model needed)
      2. gemma3n_backend=huggingface → Gemma3nHFAdapter (full multimodal)
      3. gemma3n_backend=ollama  → Gemma3nAdapter (text+image only via Ollama)
    """
    if settings.mock_mode:
        logger.info("[gemma3n] Mock mode — using MockMultimodalAdapter")
        return MockMultimodalAdapter()

    backend = getattr(settings, "gemma3n_backend", "huggingface").lower()

    if backend == "huggingface":
        from backend.models.gemma3n_hf import Gemma3nHFAdapter  # noqa: PLC0415
        model_id = getattr(settings, "gemma3n_hf_model_id", "google/gemma-3n-e4b-it")
        logger.info(f"[gemma3n] Using Gemma3nHFAdapter — model={model_id!r}")
        return Gemma3nHFAdapter(model_id)

    logger.info(f"[gemma3n] Using Gemma3nAdapter (Ollama) at {settings.ollama_base_url}")
    return Gemma3nAdapter()

"""
Gemma 3n HuggingFace adapter — full multimodal (text + image + audio).

Uses ``transformers.Gemma3nForConditionalGeneration`` with the full model
weights from HuggingFace (``google/gemma-3n-e4b-it`` by default), which
includes the MobileNet v5 vision encoder and the USM-based audio encoder
that the Ollama GGUF version strips out.

Requirements
------------
* ``pip install transformers accelerate``
* A HuggingFace account with the Gemma licence accepted at
  https://huggingface.co/google/gemma-3n-e4b-it
* ``huggingface-cli login`` (or ``HUGGINGFACE_TOKEN`` env var) so the
  model can be downloaded on first use.

Audio spec (Gemma 3n)
---------------------
* Sample rate : 16 kHz mono
* Max duration: ~30 s per call (6.25 tokens / second of audio)
* Formats     : WAV or MP3 (WAV preferred; the pipeline already writes .webm
  chunks — ``soundfile`` or ``librosa`` can resample if needed, but
  ``torchaudio`` is used here for zero extra deps).

The adapter is loaded lazily on first use and kept in memory for the
lifetime of the process (model weights are expensive to load).
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from backend.config import settings
from backend.models.base import BaseMultimodalModel

# PyTorch MPS (Apple Silicon GPU) is not thread-safe for concurrent inference.
# Multiple asyncio.to_thread calls hitting model.generate() simultaneously will
# deadlock on the Metal command queue. This semaphore serializes all HF inference
# calls at the coroutine level so only one thread ever runs _run_inference at a time.
# Crucially it's acquired *before* dispatching to the thread pool, so waiting
# coroutines never consume a thread pool slot while blocked.
_inference_sem: Optional[asyncio.Semaphore] = None
_inference_sem_lock = threading.Lock()


def _get_inference_sem() -> asyncio.Semaphore:
    """Return the process-wide inference semaphore, creating it lazily."""
    global _inference_sem
    if _inference_sem is None:
        with _inference_sem_lock:
            if _inference_sem is None:
                _inference_sem = asyncio.Semaphore(1)
    return _inference_sem

# HuggingFace model ID — override with PITCHPILOT_GEMMA3N_HF_MODEL_ID
_DEFAULT_HF_MODEL = "google/gemma-3n-e4b-it"


# ---------------------------------------------------------------------------
# Lazy model loader — singleton, loaded once per process
# ---------------------------------------------------------------------------

# Lock prevents concurrent from_pretrained calls when multiple agents trigger
# the first load simultaneously (lru_cache alone does not serialize threads).
_load_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load_model_and_processor(model_id: str):
    """
    Download (on first call) and load Gemma 3n weights into memory.

    Returns (model, processor). Cached so subsequent calls are free.
    Uses bfloat16 + MPS on Apple Silicon, CUDA if available, else CPU.
    """
    import torch
    from transformers import AutoProcessor, Gemma3nForConditionalGeneration

    logger.info(f"[gemma3n_hf] Loading model {model_id!r} — this may take a minute on first run")

    if torch.backends.mps.is_available():
        device = "mps"
        dtype = torch.bfloat16
    elif torch.cuda.is_available():
        device = "cuda"
        dtype = torch.bfloat16
    else:
        device = "cpu"
        dtype = torch.float32

    logger.info(f"[gemma3n_hf] Using device={device} dtype={dtype}")

    model = Gemma3nForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=dtype,
        device_map=device,
    )
    model.eval()

    processor = AutoProcessor.from_pretrained(model_id, padding_side="left")

    logger.info(f"[gemma3n_hf] Model ready on {device}")
    return model, processor


def _load_model_and_processor_safe(model_id: str):
    """Thread-safe wrapper: serialises concurrent first-load attempts."""
    # Fast path — already cached, no lock needed.
    if _load_model_and_processor.cache_info().currsize > 0:
        return _load_model_and_processor(model_id)
    with _load_lock:
        return _load_model_and_processor(model_id)


# ---------------------------------------------------------------------------
# Audio loading helper
# ---------------------------------------------------------------------------

def _load_audio_16k_mono(audio_path: str) -> np.ndarray:
    """
    Load an audio file and return a 1-D float32 numpy array at 16 kHz.

    Supports WAV, WebM/Opus, MP3 via torchaudio (which uses ffmpeg as
    backend on macOS).  Raises RuntimeError if torchaudio is unavailable.
    """
    try:
        import torchaudio  # noqa: PLC0415
        import torchaudio.functional as F  # noqa: PLC0415

        waveform, sr = torchaudio.load(audio_path)
        if sr != 16000:
            waveform = F.resample(waveform, sr, 16000)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        return waveform.squeeze(0).numpy().astype(np.float32)

    except ImportError:
        raise RuntimeError(
            "torchaudio is required for Gemma 3n audio input. "
            "Install it with: pip install torchaudio"
        )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class Gemma3nHFAdapter(BaseMultimodalModel):
    """
    HuggingFace Transformers adapter for the full Gemma 3n E4B model.

    Unlike the Ollama GGUF variant, this loads the complete model weights
    including the vision and audio encoders, enabling all three modalities.
    """

    def __init__(self, model_id: Optional[str] = None):
        self._model_id = model_id or getattr(settings, "gemma3n_hf_model_id", _DEFAULT_HF_MODEL)

    @property
    def model_name(self) -> str:
        return self._model_id

    def _get_model_and_processor(self):
        return _load_model_and_processor_safe(self._model_id)

    def _run_inference(self, messages: list[dict], max_new_tokens: int) -> str:
        """
        Synchronous inference call — run via asyncio.to_thread in async callers.

        Returns the assistant's raw text response.
        """
        import torch  # noqa: PLC0415

        model, processor = self._get_model_and_processor()

        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
        )
        inputs = {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}

        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )

        # Decode only the newly generated tokens (skip the input prompt)
        input_len = inputs["input_ids"].shape[-1]
        generated = output_ids[0][input_len:]
        return processor.decode(generated, skip_special_tokens=True).strip()

    # ------------------------------------------------------------------
    # BaseMultimodalModel interface
    # ------------------------------------------------------------------

    async def _run_inference_with_timeout(self, messages: list[dict], max_new_tokens: int) -> str:
        """Acquire the semaphore then run inference with a hard timeout."""
        timeout = settings.hf_inference_timeout_seconds
        async with _get_inference_sem():
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._run_inference, messages, max_new_tokens),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"[gemma3n_hf] Inference timed out after {timeout:.0f}s — returning empty string"
                )
                return ""

    async def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": [{"type": "text", "text": system}]})
        messages.append({"role": "user", "content": [{"type": "text", "text": prompt}]})
        return await self._run_inference_with_timeout(messages, max_tokens)

    async def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": [{"type": "text", "text": system}]})
        messages.append({"role": "user", "content": [
            {"type": "image", "url": str(Path(image_path).resolve())},
            {"type": "text",  "text": prompt},
        ]})
        return await self._run_inference_with_timeout(messages, max_tokens)

    async def generate_with_audio(
        self,
        prompt: str,
        audio_path: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        waveform = await asyncio.to_thread(_load_audio_16k_mono, audio_path)

        messages = []
        if system:
            messages.append({"role": "system", "content": [{"type": "text", "text": system}]})
        messages.append({"role": "user", "content": [
            {"type": "audio", "audio": waveform},
            {"type": "text",  "text": prompt},
        ]})
        return await self._run_inference_with_timeout(messages, max_tokens)

    async def is_available(self) -> bool:
        try:
            from transformers import Gemma3nForConditionalGeneration  # noqa: F401
            return True
        except ImportError:
            return False

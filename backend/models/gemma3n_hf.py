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
* Formats     : any format supported by ffmpeg (WAV, WebM/Opus, MP3, AAC …).
  Audio loading uses ffmpeg + stdlib wave — no torchaudio.load() because
  torchaudio ≥ 2.6 requires the optional torchcodec package for all decoding.

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


def _verify_gemma3n_audio_patch() -> None:
    """
    Guard against the transformers 5.2.0 bug where audio_mel_mask is accessed
    on pooler_output (a plain Tensor) after the AudioEncoderModelOutput has
    already been overwritten.

    Reads the installed modeling_gemma3n.py and checks that the mask is
    extracted BEFORE pooler_output assignment.  If not (i.e. the library was
    reinstalled without the patch), re-applies the one-line fix automatically.

    IMPORTANT: must be called BEFORE `from transformers import
    Gemma3nForConditionalGeneration` so that the patched file is read when
    Python first compiles the module.  If the module is somehow already in
    sys.modules, it is reloaded so the fix takes effect in the running process.

    Uses ``transformers.__file__`` to locate the modeling file without
    triggering the submodule import (unlike find_spec on the full dotted path).
    """
    import importlib  # noqa: PLC0415
    import sys  # noqa: PLC0415

    try:
        import transformers as _tf  # noqa: PLC0415
        model_file = Path(_tf.__file__).parent / "models" / "gemma3n" / "modeling_gemma3n.py"
    except ImportError:
        return

    if not model_file.exists():
        return

    src = model_file.read_text(encoding="utf-8")
    buggy = "audio_features = audio_features.pooler_output\n            audio_mask = audio_features.audio_mel_mask"
    fixed = "audio_mask = audio_features.audio_mel_mask  # save before overwriting (transformers 5.2.0 bug fix)\n            audio_features = audio_features.pooler_output"

    if buggy in src:
        logger.warning(
            "[gemma3n_hf] Detected transformers 5.2.0 audio_mel_mask bug — patching in place"
        )
        model_file.write_text(src.replace(buggy, fixed), encoding="utf-8")
        logger.info("[gemma3n_hf] Patch applied to modeling_gemma3n.py")

        # If the module snuck into sys.modules before we could patch the file
        # (e.g. another import path triggered it), reload it so the fix is live
        # without requiring a full server restart.
        module_key = "transformers.models.gemma3n.modeling_gemma3n"
        if module_key in sys.modules:
            logger.info("[gemma3n_hf] Reloading modeling_gemma3n to pick up patch")
            importlib.reload(sys.modules[module_key])
    elif fixed not in src:
        logger.info("[gemma3n_hf] modeling_gemma3n.py audio fix already applied or not needed")


@lru_cache(maxsize=1)
def _load_model_and_processor(model_id: str):
    """
    Download (on first call) and load Gemma 3n weights into memory.

    Returns (model, processor). Cached so subsequent calls are free.
    Uses bfloat16 + MPS on Apple Silicon, CUDA if available, else CPU.
    """
    # Must run BEFORE the transformers import below so that the patched file
    # is what Python compiles when it first loads modeling_gemma3n.
    _verify_gemma3n_audio_patch()

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

    Uses ffmpeg to decode any container (WAV, WebM/Opus, MP3, AAC, …) to a
    raw 16-kHz mono PCM stream, then reads it with numpy.  This avoids a
    dependency on torchaudio.load() which requires the optional torchcodec
    package in torchaudio ≥ 2.6.

    Raises RuntimeError if ffmpeg is not on PATH or conversion fails.
    """
    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    import wave as _wave  # noqa: PLC0415

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", audio_path,
                "-ar", "16000", "-ac", "1",
                "-sample_fmt", "s16",
                "-f", "wav", tmp_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg conversion failed: {result.stderr.decode()[:300]}"
            )

        with _wave.open(tmp_path, "rb") as wf:
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        samples /= 32768.0  # normalise to [-1, 1]
        return samples
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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
        model_dtype = next(model.parameters()).dtype
        inputs = {
            k: (
                v.to(device=model.device, dtype=model_dtype)
                if hasattr(v, "is_floating_point") and v.is_floating_point()
                else v.to(model.device)
                if hasattr(v, "to")
                else v
            )
            for k, v in inputs.items()
        }

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

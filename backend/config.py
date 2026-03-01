"""
Central configuration for the PitchPilot backend.

All tuneable knobs live here.  Values can be overridden with environment
variables (e.g. PITCHPILOT_MOCK_MODE=true) or a .env file in the project root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
SAMPLE_POLICIES_DIR = DATA_DIR / "sample_policies"
TEST_OUTPUTS_DIR = DATA_DIR / "test_outputs"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="PITCHPILOT_",
        # Read .env.local first, then .env as fallback (later files take lower priority)
        env_file=(
            str(PROJECT_ROOT / ".env.local"),
            str(PROJECT_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Mock / development mode
    # ------------------------------------------------------------------
    mock_mode: bool = Field(
        default=True,
        description=(
            "When True, all model calls are replaced with deterministic stubs. "
            "Set PITCHPILOT_MOCK_MODE=false (in .env.local) to enable real model inference. "
            "Note: the env var is PITCHPILOT_MOCK_MODE, not USE_MOCK_PIPELINE."
        ),
    )

    # ------------------------------------------------------------------
    # Video processing
    # ------------------------------------------------------------------
    extraction_fps: float = Field(
        default=1.0,
        description="Frames-per-second rate for uniform frame extraction",
    )
    keyframe_diff_threshold: float = Field(
        default=0.3,
        description=(
            "Normalised mean-pixel-difference threshold [0,1] above which a "
            "frame is classified as a scene-change keyframe"
        ),
    )
    frame_image_quality: int = Field(
        default=90,
        description="JPEG quality (1-100) for saved frame images",
    )
    audio_sample_rate: int = Field(
        default=16000,
        description="Audio sample rate in Hz; Whisper expects 16 kHz",
    )

    # ------------------------------------------------------------------
    # Gemma 3n backend selection
    # ------------------------------------------------------------------
    gemma3n_backend: str = Field(
        default="huggingface",
        description=(
            "Which backend to use for multimodal (OCR + audio) inference. "
            "'huggingface' — full model via HuggingFace Transformers (text + image + audio). "
            "'ollama' — GGUF via local Ollama (text + image only; audio falls back to mlx-whisper)."
        ),
    )
    gemma3n_hf_model_id: str = Field(
        default="google/gemma-3n-e4b-it",
        description=(
            "HuggingFace model ID for Gemma 3n when gemma3n_backend=huggingface. "
            "Requires HuggingFace login and Gemma licence acceptance."
        ),
    )

    # ------------------------------------------------------------------
    # Ollama / Gemma 3n  (multimodal processing)
    # ------------------------------------------------------------------
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama REST API",
    )
    gemma3n_model: str = Field(
        default="gemma3n:e4b",
        description="Ollama model tag for Gemma 3n (used when gemma3n_backend=ollama)",
    )
    gemma3_model: str = Field(
        default="gemma3:4b",
        description="Ollama model tag for Gemma 3 (agent reasoning)",
    )
    ollama_timeout_seconds: float = Field(
        default=120.0,
        description="HTTP timeout for Ollama requests",
    )

    # ------------------------------------------------------------------
    # FunctionGemma (fine-tuned router)
    # ------------------------------------------------------------------
    function_gemma_model_id: str = Field(
        default="google/gemma-3-1b-it",
        description="HuggingFace model ID for FunctionGemma base",
    )
    function_gemma_lora_path: Optional[str] = Field(
        default=None,
        description="Path to fine-tuned LoRA adapter directory; None = base model only",
    )

    # ------------------------------------------------------------------
    # Transcription fallback (mlx-whisper on Apple Silicon)
    # ------------------------------------------------------------------
    whisper_model: str = Field(
        default="base",
        description="Whisper model size: tiny / base / small / medium / large",
    )

    # ------------------------------------------------------------------
    # Claim extraction
    # ------------------------------------------------------------------
    max_claims_per_session: int = Field(
        default=50,
        description="Hard cap on the number of claims extracted per session",
    )
    claim_context_window_seconds: float = Field(
        default=30.0,
        description=(
            "How many seconds of transcript to include as context when "
            "extracting claims from a segment"
        ),
    )

    # ------------------------------------------------------------------
    # Performance / concurrency
    # ------------------------------------------------------------------
    fast_mode: bool = Field(
        default=False,
        description=(
            "When True, trade accuracy for speed: lower extraction FPS, "
            "smaller frames, fewer claims, persona agent skipped."
        ),
    )
    frame_max_dimension: int = Field(
        default=1920,
        description=(
            "Downscale frames so that max(width, height) <= this value before "
            "saving to disk and OCR. Use 768-1024 for fast mode."
        ),
    )
    ocr_concurrency: int = Field(
        default=2,
        description=(
            "Maximum number of concurrent OCR Ollama requests. "
            "Ollama is serial on GPU; keeping this at 1-2 avoids queue pile-up."
        ),
    )
    agent_concurrency: int = Field(
        default=3,
        description="Maximum number of concurrent agent LLM calls per batch.",
    )
    agent_per_call_timeout_seconds: float = Field(
        default=30.0,
        description=(
            "Maximum seconds to wait for a single agent LLM reasoning call "
            "(coach, compliance, persona). When exceeded, the call falls back to "
            "mock findings for that claim so the pipeline can proceed. "
            "Separate from hf_inference_timeout_seconds, which gates raw model.generate()."
        ),
    )
    hf_inference_timeout_seconds: float = Field(
        default=120.0,
        description=(
            "Maximum seconds to wait for a single HuggingFace model.generate() call "
            "before cancelling and falling back to mock findings. "
            "Prevents the pipeline from hanging indefinitely on slow CPU inference."
        ),
    )
    retain_artifacts: bool = Field(
        default=False,
        description=(
            "When False (default), extracted frames and audio are deleted after "
            "the session report is generated to save disk space. "
            "Set True (or pass --retain-artifacts) to keep them for debugging."
        ),
    )

    # ------------------------------------------------------------------
    # Live In-Room Mode — earpiece cue delivery
    # ------------------------------------------------------------------
    cue_min_interval_seconds: float = Field(
        default=15.0,
        description=(
            "Minimum gap (seconds) between successive earpiece cues. "
            "Prevents cue flooding during fast-paced sections."
        ),
    )
    cue_dedup_window_seconds: float = Field(
        default=60.0,
        description=(
            "Sliding window (seconds) within which duplicate cue categories "
            "are suppressed."
        ),
    )
    tts_engine: str = Field(
        default="system",
        description=(
            "TTS backend for earpiece cues. "
            "Options: 'system' (macOS say), 'piper' (cross-platform ONNX), "
            "'prerendered' (clip bank only)."
        ),
    )
    tts_cue_bank_path: str = Field(
        default="data/cue_bank/",
        description="Directory containing pre-rendered earpiece audio clips (.wav/.mp3).",
    )

    # ------------------------------------------------------------------
    # Live Remote Mode — presenter overlay
    # ------------------------------------------------------------------
    teleprompter_update_interval: float = Field(
        default=20.0,
        description=(
            "How often (seconds) to regenerate teleprompter talking points "
            "if no slide-change is detected."
        ),
    )
    objection_prep_update_interval: float = Field(
        default=30.0,
        description="How often (seconds) to refresh the objection prep sidebar.",
    )
    slide_change_ocr_diff_threshold: float = Field(
        default=0.25,
        description=(
            "Fraction of OCR text that must differ between frames before a "
            "slide change is declared (triggers teleprompter refresh)."
        ),
    )

    # ------------------------------------------------------------------
    # Live pipeline extract interval (applies to both live modes)
    # ------------------------------------------------------------------
    live_extract_interval_seconds: float = Field(
        default=5.0,
        description=(
            "How often (seconds) to run claim extraction + agent routing "
            "during a live session. Reduced from 10s vs. review mode."
        ),
    )


# Module-level singleton — import this everywhere
settings = Settings()

# ---------------------------------------------------------------------------
# Module-level convenience constants expected by agent/model modules
# ---------------------------------------------------------------------------

import os as _os

BACKEND_DIR = Path(__file__).parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
SAMPLE_OUTPUTS_DIR = PROJECT_ROOT / "sample_outputs"

API_HOST: str = "0.0.0.0"
API_PORT: int = 8000
API_RELOAD: bool = True

MAX_CLAIMS_PER_SESSION: int = settings.max_claims_per_session

DEFAULT_PERSONAS: list[str] = [
    "Skeptical Investor",
    "Technical Reviewer",
    "Procurement Manager",
]

# Ollama / model settings (flat constants for easy import)
OLLAMA_BASE_URL: str = settings.ollama_base_url
OLLAMA_TIMEOUT: float = settings.ollama_timeout_seconds
GEMMA3N_MODEL: str = settings.gemma3n_model
GEMMA3_MODEL: str = settings.gemma3_model

# FunctionGemma router
FUNCTION_GEMMA_BASE_MODEL: str = settings.function_gemma_model_id
FUNCTION_GEMMA_ADAPTER_PATH: str = settings.function_gemma_lora_path or ""
ROUTER_USE_RULES: bool = _os.getenv("ROUTER_USE_RULES", "true").lower() == "true"

# Mock / fallback flags
USE_MOCK: bool = settings.mock_mode
AUTO_FALLBACK_TO_MOCK: bool = _os.getenv("AUTO_FALLBACK_TO_MOCK", "true").lower() == "true"

# Prompt file paths (edit the .txt files to tune agent behaviour)
PROMPT_FILES: dict[str, Path] = {
    "coach_system": PROMPTS_DIR / "coach_system.txt",
    "compliance_system": PROMPTS_DIR / "compliance_system.txt",
    "persona_system": PROMPTS_DIR / "persona_system.txt",
    "claim_extraction": PROMPTS_DIR / "claim_extraction.txt",
}

# Readiness scoring
READINESS_DIMENSIONS: dict[str, float] = {
    "clarity": 0.25,
    "compliance": 0.30,
    "defensibility": 0.25,
    "persuasiveness": 0.20,
}

SEVERITY_PENALTY: dict[str, int] = {
    "info": 3,
    "warning": 8,
    "critical": 18,
}

GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (0, "F"),
]

# Content-richness scoring (positive marking component)
#
# Each dimension starts at CONTENT_SCORE_FLOOR and earns bonus points
# proportional to how many claims the AI was able to analyse.
# Penalty deductions then apply from that earned ceiling.
#
#   content_base = CONTENT_SCORE_FLOOR
#                  + CONTENT_SCORE_BONUS * min(claims, CONTENT_SATURATION_CLAIMS)
#                                        / CONTENT_SATURATION_CLAIMS
#
# Examples (before any deductions):
#   0 claims  →  50   (barely enough to assess)
#   8 claims  →  74
#  15+ claims →  95   (full bonus — substantive content analysed)
CONTENT_SCORE_FLOOR: int = 50        # baseline score with zero claims detected
CONTENT_SCORE_BONUS: int = 45        # max additional points from content richness
CONTENT_SATURATION_CLAIMS: int = 15  # claims needed to earn the full bonus

# ---------------------------------------------------------------------------
# Live-mode constants (imported by cue_synth.py, tts.py, live_ws.py)
# ---------------------------------------------------------------------------
CUE_MIN_INTERVAL: float = settings.cue_min_interval_seconds
CUE_DEDUP_WINDOW: float = settings.cue_dedup_window_seconds
TTS_ENGINE: str = settings.tts_engine
TTS_CUE_BANK_PATH: str = settings.tts_cue_bank_path or str(DATA_DIR / "cue_bank")
TELEPROMPTER_UPDATE_INTERVAL: float = settings.teleprompter_update_interval
OBJECTION_PREP_UPDATE_INTERVAL: float = settings.objection_prep_update_interval
LIVE_EXTRACT_INTERVAL: float = settings.live_extract_interval_seconds
SLIDE_CHANGE_OCR_DIFF_THRESHOLD: float = settings.slide_change_ocr_diff_threshold

# Cue priority urgency model thresholds
CUE_URGENCY: dict[str, list[str]] = {
    "immediate": ["critical"],           # deliver within 2s
    "soon":      ["warning"],            # deliver within 10s
    "deferred":  ["info"],               # post-session only
}

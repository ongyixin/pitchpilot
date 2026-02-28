"""
Gemma 3 4B adapter — text-only reasoning for agent analysis.

In production this talks to a locally running Ollama instance via the shared
httpx.AsyncClient (backend.models.ollama_client).  When settings.mock_mode is
True it returns deterministic stub responses.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from backend.config import settings
from backend.models.base import BaseTextModel
from backend.models.ollama_client import ollama_post

_KEEP_ALIVE = "10m"


class Gemma3Adapter(BaseTextModel):
    """Wraps the Ollama /api/chat endpoint for Gemma 3 4B."""

    def __init__(self, model: Optional[str] = None):
        self._model = model or settings.gemma3_model

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[str] = None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "keep_alive": _KEEP_ALIVE,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if response_format == "json":
            payload["format"] = "json"

        data = await ollama_post("/api/chat", payload)
        return data["message"]["content"]

    async def is_available(self) -> bool:
        from backend.models.ollama_client import get_ollama_client
        try:
            r = await get_ollama_client().get("/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    async def aclose(self) -> None:
        pass  # shared client — closed by close_ollama_client() at shutdown


class MockTextAdapter(BaseTextModel):
    """Deterministic stub that returns plausible JSON responses without a model."""

    @property
    def model_name(self) -> str:
        return "mock-text-v0"

    async def generate(self, prompt: str, system: Optional[str] = None,
                       temperature: float = 0.3, max_tokens: int = 2048,
                       response_format: Optional[str] = None) -> str:
        logger.debug("[MOCK] Gemma3 generate called")
        return """{
  "findings": [
    {
      "severity": "warning",
      "category": "compliance",
      "text": "The claim 'fully automated' may conflict with policy requiring manual review.",
      "suggestion": "Add qualifier: 'automated for standard cases; edge cases undergo manual review'.",
      "timestamp": 8.8
    },
    {
      "severity": "info",
      "category": "clarity",
      "text": "The problem statement is clear but the solution section moves quickly.",
      "suggestion": "Add a brief pause and summary slide after the solution overview.",
      "timestamp": 0.0
    }
  ]
}"""


def get_gemma3_adapter() -> BaseTextModel:
    """Return the appropriate Gemma 3 adapter based on settings."""
    if settings.mock_mode:
        logger.info("Mock mode enabled — using MockTextAdapter for Gemma 3")
        return MockTextAdapter()
    logger.info(f"Using Gemma3Adapter via Ollama at {settings.ollama_base_url}")
    return Gemma3Adapter()

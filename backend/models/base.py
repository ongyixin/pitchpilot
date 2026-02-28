"""
Abstract base classes for all model adapters.

Every adapter (real or mock) must implement these interfaces so that the
pipeline modules can swap implementations without code changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseMultimodalModel(ABC):
    """
    Adapter contract for a model capable of text, vision, and/or audio input.

    Implementors: Gemma3nAdapter (Ollama), MockMultimodalAdapter.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable name / version tag for this model."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate a text completion.

        Args:
            prompt: User-facing instruction or question.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            Raw text response from the model.
        """

    @abstractmethod
    async def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate a text completion given a text prompt and an image.

        Args:
            prompt: Instruction for what to do with the image.
            image_path: Absolute path to a JPEG or PNG image.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            Raw text response from the model.
        """

    @abstractmethod
    async def generate_with_audio(
        self,
        prompt: str,
        audio_path: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate a text completion given a text prompt and an audio file.

        Args:
            prompt: Instruction for what to do with the audio (e.g. "Transcribe").
            audio_path: Absolute path to a WAV file.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            Raw text response (e.g. transcript JSON).
        """

    async def is_available(self) -> bool:
        """
        Probe whether the model backend is reachable.

        Default implementation returns True; override for real adapters.
        """
        return True


class BaseTextModel(ABC):
    """
    Adapter contract for a text-only reasoning model.

    Implementors: Gemma3Adapter (Ollama), MockTextAdapter.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable name / version tag."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[str] = None,
    ) -> str:
        """
        Generate a text completion.

        Args:
            prompt: User-facing prompt.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            response_format: Optional hint, e.g. "json".

        Returns:
            Raw model response as a string.
        """

    async def is_available(self) -> bool:
        return True

"""
Shared Ollama HTTP client module.

Provides a single, connection-pooled ``httpx.AsyncClient`` instance that is
reused by all model adapters (Gemma3nAdapter, Gemma3Adapter).  This avoids
the overhead of creating/destroying connections per-request and per-adapter.

Usage::

    from backend.models.ollama_client import get_ollama_client, close_ollama_client

    # In a FastAPI lifespan / startup event:
    @app.on_event("startup")
    async def startup():
        pass  # client is created lazily on first call

    @app.on_event("shutdown")
    async def shutdown():
        await close_ollama_client()

    # In adapter code:
    client = get_ollama_client()
    response = await client.post("/api/generate", json=payload)

Retry behaviour
---------------
``ollama_post()`` wraps a POST with configurable retries and exponential
backoff.  Transient Ollama errors (503, timeout, connection reset) are
retried up to ``max_attempts`` times.  The final exception is re-raised so
callers can handle it.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx
from loguru import logger

from backend.config import settings

# ---------------------------------------------------------------------------
# Shared client singleton
# ---------------------------------------------------------------------------

_client: Optional[httpx.AsyncClient] = None


def get_ollama_client() -> httpx.AsyncClient:
    """
    Return (or lazily create) the shared Ollama httpx.AsyncClient.

    Connection limits are sized conservatively for a single-GPU local setup:
    - max_connections=8: allows parallelism without overwhelming the GPU queue
    - max_keepalive_connections=4: reuses TCP connections across sequential calls
    """
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(
                connect=10.0,
                read=settings.ollama_timeout_seconds,
                write=30.0,
                pool=10.0,
            ),
            limits=httpx.Limits(
                max_connections=8,
                max_keepalive_connections=4,
                keepalive_expiry=60.0,
            ),
        )
        logger.info(
            f"[ollama_client] Created shared httpx.AsyncClient -> {settings.ollama_base_url}"
        )
    return _client


async def close_ollama_client() -> None:
    """Close the shared client. Call on application shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("[ollama_client] Shared client closed")
    _client = None


# ---------------------------------------------------------------------------
# Retry-aware POST helper
# ---------------------------------------------------------------------------

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
)


async def ollama_post(
    path: str,
    payload: dict[str, Any],
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> dict[str, Any]:
    """
    POST to an Ollama endpoint with automatic retry on transient errors.

    Args:
        path: URL path relative to the Ollama base URL (e.g. "/api/generate").
        payload: JSON body dict.
        max_attempts: Total attempt count (including the first).
        base_delay: Initial backoff delay in seconds (doubles each retry).

    Returns:
        Parsed JSON response dict.

    Raises:
        httpx.HTTPStatusError: On non-retryable HTTP errors.
        httpx.HTTPError: After all retries are exhausted.
    """
    client = get_ollama_client()
    last_exc: Optional[Exception] = None
    delay = base_delay

    for attempt in range(1, max_attempts + 1):
        try:
            t0 = time.perf_counter()
            response = await client.post(path, json=payload)

            if response.status_code in _RETRYABLE_STATUS:
                raise httpx.HTTPStatusError(
                    f"Retryable HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )

            response.raise_for_status()
            elapsed = time.perf_counter() - t0
            logger.debug(f"[ollama_client] POST {path} -> {response.status_code} in {elapsed:.2f}s")
            return response.json()

        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            logger.warning(
                f"[ollama_client] Attempt {attempt}/{max_attempts} failed "
                f"({type(exc).__name__}): {exc}"
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _RETRYABLE_STATUS:
                last_exc = exc
                logger.warning(
                    f"[ollama_client] Attempt {attempt}/{max_attempts} -> "
                    f"HTTP {exc.response.status_code}; will retry"
                )
            else:
                raise

        if attempt < max_attempts:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)

    raise last_exc or RuntimeError(f"ollama_post: all {max_attempts} attempts failed")

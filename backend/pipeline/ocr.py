"""
OCR pipeline for the PitchPilot ingestion pipeline.

Responsibilities
----------------
* Process extracted video frames -> OCRBlock list with frame timestamps.
* Process uploaded policy/compliance documents (PDF or plain text) ->
  OCRBlock list with page numbers.
* Return all blocks in a consistent schema regardless of source type.

Performance improvements
------------------------
* Bounded concurrency: frames are OCR'd with a configurable semaphore
  (settings.ocr_concurrency, default 2) instead of unbounded asyncio.gather.
  Ollama is serial on GPU; unbounded concurrency just piles up a queue and
  wastes RAM on in-flight base64 blobs.

* Hash-based frame cache: before calling the model, the frame's perceptual
  hash (stored on ExtractedFrame.phash) is looked up in a per-pipeline-run
  dict.  Near-identical frames (Hamming distance <= threshold) reuse the
  previous OCR result with adjusted timestamps.  This avoids redundant calls
  for static slides that didn't change between keyframes.

* format=json enforced: Gemma3nAdapter already injects "format": "json" in
  every payload, eliminating the markdown-fence stripping fallback path.

Model integration points
------------------------
* In mock mode (settings.mock_mode=True): returns deterministic stub blocks.
* Real mode – Gemma3nAdapter.generate_with_image() for frames.
* Swap path for PaliGemma: replace the _ocr_frame_with_model() body.

OCRBlock output contract
------------------------
Each OCRBlock has:
    text            – extracted text (non-empty)
    source_type     – OCRSourceType enum (VIDEO_FRAME or *_DOCUMENT)
    timestamp       – seconds from video start  (frame blocks only)
    frame_index     – sequential frame index     (frame blocks only)
    page_number     – 1-based page number        (document blocks only)
    document_path   – source document path       (document blocks only)
    confidence      – float [0,1]
    model_used      – adapter name
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.config import settings
from backend.data_models import BoundingBox, ExtractedFrame, OCRBlock, OCRSourceType
from backend.metrics import ConcurrencyLimiter
from backend.models.base import BaseMultimodalModel
from backend.models.gemma3n import get_gemma3n_adapter
from backend.pipeline.video import _phash_distance

# System prompt shared across all OCR calls
_OCR_SYSTEM = (
    "You are an OCR engine. Extract all text visible in the image. "
    "Return a JSON object with a 'blocks' list. Each block must have a "
    "'text' field (string) and a 'confidence' field (float 0-1). "
    "Do not include any explanation, only the JSON object."
)

_FRAME_PROMPT = (
    "Extract all visible text from this presentation slide or screen capture. "
    "Return JSON: {\"blocks\": [{\"text\": \"...\", \"confidence\": 0.95}, ...]}"
)

_DOC_PROMPT = (
    "Extract all text from this document page. "
    "Return JSON: {\"blocks\": [{\"text\": \"...\", \"confidence\": 0.95}, ...]}"
)

# Maximum Hamming distance for two phashes to be considered identical
_PHASH_CACHE_THRESHOLD = 5


class OCRPipeline:
    """
    Orchestrates OCR across video frames and uploaded documents.

    Usage::

        pipeline = OCRPipeline()
        # Process frames from a video
        blocks = await pipeline.process_frames(frames)
        # Process a policy PDF or text file
        doc_blocks = await pipeline.process_document("/path/to/policy.pdf")
    """

    def __init__(
        self,
        model: Optional[BaseMultimodalModel] = None,
        ocr_concurrency: Optional[int] = None,
    ):
        self._model = model or get_gemma3n_adapter()
        self._limiter = ConcurrencyLimiter(
            ocr_concurrency if ocr_concurrency is not None else settings.ocr_concurrency
        )
        # Per-session phash -> list[OCRBlock] cache
        self._phash_cache: dict[str, list[OCRBlock]] = {}
        logger.info(
            f"[ocr] Initialised with model={self._model.model_name}, "
            f"concurrency={ocr_concurrency or settings.ocr_concurrency}"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def process_frames(
        self,
        frames: list[ExtractedFrame],
        keyframes_only: bool = False,
    ) -> list[OCRBlock]:
        """
        Run OCR on a list of video frames with bounded concurrency.

        Args:
            frames: Extracted frames from the video pipeline.
            keyframes_only: If True, only run OCR on frames where
                is_keyframe=True (slide transitions).

        Returns:
            List of OCRBlock objects ordered by timestamp.
        """
        targets = [f for f in frames if f.is_keyframe] if keyframes_only else frames
        # Drop frames with no file path (non-keyframes skipped during extraction)
        targets = [f for f in targets if f.file_path]
        logger.info(
            f"[ocr] Processing {len(targets)}/{len(frames)} frames "
            f"(keyframes_only={keyframes_only})"
        )

        coros = [self._process_frame(frame) for frame in targets]
        results: list[list[OCRBlock] | BaseException] = await self._limiter.run_many(coros)

        all_blocks: list[OCRBlock] = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"[ocr] Frame OCR error: {r}")
            elif isinstance(r, list):
                all_blocks.extend(r)

        all_blocks.sort(key=lambda b: (b.timestamp or 0.0))
        logger.info(f"[ocr] Extracted {len(all_blocks)} blocks from frames")
        return all_blocks

    async def process_document(
        self,
        document_path: str,
    ) -> list[OCRBlock]:
        """
        Extract text blocks from a policy/compliance document.

        Supports:
          * .txt / .md  – read directly, return one block per paragraph
          * .pdf        – extract text per page using pypdf

        Args:
            document_path: Absolute path to the document file.

        Returns:
            List of OCRBlock objects ordered by page number.
        """
        path = Path(document_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {document_path}")

        suffix = path.suffix.lower()
        logger.info(f"[ocr] Processing document: {path.name} ({suffix})")

        if suffix in {".txt", ".md"}:
            return self._process_text_file(document_path)
        elif suffix == ".pdf":
            return await self._process_pdf(document_path)
        else:
            logger.warning(f"[ocr] Unsupported extension '{suffix}', treating as text")
            return self._process_text_file(document_path)

    def clear_cache(self) -> None:
        """Clear the per-session phash cache (call between sessions)."""
        self._phash_cache.clear()

    # ------------------------------------------------------------------
    # Private helpers — frames
    # ------------------------------------------------------------------

    async def _process_frame(self, frame: ExtractedFrame) -> list[OCRBlock]:
        """Run OCR on a single frame, with hash-based cache lookup."""
        if not Path(frame.file_path).exists():
            logger.warning(f"[ocr] Frame file missing: {frame.file_path}")
            return []

        # Check phash cache: if a near-identical frame was already OCR'd,
        # reuse those blocks with adjusted timestamp/frame_index.
        if frame.phash:
            cached = self._lookup_cache(frame.phash)
            if cached is not None:
                logger.debug(
                    f"[ocr] Cache hit for frame {frame.frame_index} "
                    f"(phash={frame.phash[:8]}...)"
                )
                return [
                    b.model_copy(update={
                        "frame_index": frame.frame_index,
                        "timestamp": frame.timestamp,
                    })
                    for b in cached
                ]

        try:
            raw = await self._model.generate_with_image(
                prompt=_FRAME_PROMPT,
                image_path=frame.file_path,
                system=_OCR_SYSTEM,
            )
            parsed = _parse_ocr_json(raw)
        except Exception as exc:
            logger.exception(f"[ocr] Frame OCR failed for frame {frame.frame_index}: {exc}")
            return []

        blocks = []
        for item in parsed:
            text = item.get("text", "").strip()
            if not text:
                continue
            blocks.append(
                OCRBlock(
                    text=text,
                    source_type=OCRSourceType.VIDEO_FRAME,
                    frame_index=frame.frame_index,
                    timestamp=frame.timestamp,
                    confidence=float(item.get("confidence", 1.0)),
                    model_used=self._model.model_name,
                    bounding_box=_parse_bbox(item),
                )
            )

        # Store in cache
        if frame.phash and blocks:
            self._phash_cache[frame.phash] = blocks

        return blocks

    def _lookup_cache(self, phash: str) -> Optional[list[OCRBlock]]:
        """
        Look up cached OCR blocks for a near-identical frame.

        Returns cached blocks if a stored hash is within _PHASH_CACHE_THRESHOLD
        Hamming distance, otherwise None.
        """
        for cached_hash, blocks in self._phash_cache.items():
            if _phash_distance(phash, cached_hash) <= _PHASH_CACHE_THRESHOLD:
                return blocks
        return None

    # ------------------------------------------------------------------
    # Private helpers — documents
    # ------------------------------------------------------------------

    def _process_text_file(self, document_path: str) -> list[OCRBlock]:
        """Split a plain-text document into paragraph-level OCRBlocks."""
        text = Path(document_path).read_text(encoding="utf-8", errors="replace")
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

        blocks = []
        for i, para in enumerate(paragraphs, start=1):
            blocks.append(
                OCRBlock(
                    text=para,
                    source_type=OCRSourceType.POLICY_DOCUMENT,
                    page_number=i,
                    document_path=str(Path(document_path).resolve()),
                    confidence=1.0,
                    model_used="text-parser",
                )
            )
        logger.info(f"[ocr] Text file: {len(blocks)} paragraph blocks")
        return blocks

    async def _process_pdf(self, document_path: str) -> list[OCRBlock]:
        """Extract text from a PDF using pypdf's text layer."""
        try:
            import pypdf  # noqa: PLC0415

            blocks: list[OCRBlock] = []
            reader = pypdf.PdfReader(document_path)
            for page_num, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    paragraphs = [p.strip() for p in re.split(r"\n{2,}", page_text) if p.strip()]
                    for para in paragraphs:
                        blocks.append(
                            OCRBlock(
                                text=para,
                                source_type=OCRSourceType.POLICY_DOCUMENT,
                                page_number=page_num,
                                document_path=str(Path(document_path).resolve()),
                                confidence=1.0,
                                model_used="pypdf",
                            )
                        )
                else:
                    logger.debug(f"[ocr] PDF page {page_num} has no text layer; skipping")

            if not blocks:
                logger.warning(f"[ocr] No text extracted from PDF: {document_path}")
            else:
                logger.info(f"[ocr] PDF: extracted {len(blocks)} blocks from {len(reader.pages)} pages")
            return blocks

        except ImportError:
            logger.warning("[ocr] pypdf not installed; treating PDF as binary, skipping")
            return []
        except Exception as exc:
            logger.error(f"[ocr] PDF extraction failed: {exc}")
            return []


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------


def _parse_ocr_json(raw: str) -> list[dict]:
    """
    Extract the 'blocks' list from a model response.

    Handles:
      * Pure JSON  {"blocks": [...]}
      * JSON wrapped in markdown code fences (defensive fallback)
      * Partial / malformed JSON (returns empty list and logs warning)
    """
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        data = json.loads(raw)
        return data.get("blocks", [])
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return data.get("blocks", [])
            except json.JSONDecodeError:
                pass
        logger.warning(f"[ocr] Failed to parse OCR JSON response: {raw[:200]!r}")
        return []


def _parse_bbox(item: dict) -> Optional[BoundingBox]:
    """Parse an optional bounding_box from an OCR item dict."""
    bb = item.get("bounding_box") or item.get("bbox")
    if not bb:
        return None
    try:
        return BoundingBox(
            x=int(bb.get("x", 0)),
            y=int(bb.get("y", 0)),
            width=int(bb.get("width", bb.get("w", 0))),
            height=int(bb.get("height", bb.get("h", 0))),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Convenience helper: temporally-scoped OCR text for claim windows
# ---------------------------------------------------------------------------


def build_scoped_ocr_text(
    ocr_blocks: list[OCRBlock],
    window_start: float,
    window_end: float,
    margin_secs: float = 5.0,
) -> str:
    """
    Return OCR text scoped to a transcript time window.

    Includes blocks whose timestamp falls within
    [window_start - margin_secs, window_end + margin_secs], plus all
    document blocks (page-numbered, no timestamp).

    Args:
        ocr_blocks: All OCR blocks for the session.
        window_start: Start of transcript window in seconds.
        window_end: End of transcript window in seconds.
        margin_secs: Extra seconds of OCR context to include on each side.

    Returns:
        Formatted text string suitable for inclusion in a claim extraction prompt.
    """
    lo = window_start - margin_secs
    hi = window_end + margin_secs
    lines = []
    for block in ocr_blocks:
        if block.timestamp is not None:
            if lo <= block.timestamp <= hi:
                lines.append(f"[{block.timestamp:.1f}s] {block.text}")
        else:
            # Document block — always include
            tag = f"[page {block.page_number}]" if block.page_number else "[doc]"
            lines.append(f"{tag} {block.text}")
    return "\n".join(lines) if lines else "(none)"

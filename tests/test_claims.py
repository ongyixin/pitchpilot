"""
Tests for backend/pipeline/claims.py

Uses mock mode (no model required).
"""

from __future__ import annotations

import pytest

from backend.data_models import ClaimCategory, ClaimSource


@pytest.fixture
def mock_extractor():
    """ClaimExtractor using MockMultimodalAdapter."""
    from backend.models.gemma3n import MockMultimodalAdapter
    from backend.pipeline.claims import ClaimExtractor

    return ClaimExtractor(model=MockMultimodalAdapter())


@pytest.fixture
def sample_transcript_segments():
    from backend.data_models import TranscriptSegment

    return [
        TranscriptSegment(
            text="Welcome everyone, today I'm going to walk you through our pitch.",
            start_time=0.0, end_time=4.2, confidence=0.96, language="en",
            model_used="mock",
        ),
        TranscriptSegment(
            text="Our platform provides fully automated compliance checking.",
            start_time=4.3, end_time=8.7, confidence=0.94, language="en",
            model_used="mock",
        ),
        TranscriptSegment(
            text="We guarantee instant approval with zero manual review steps.",
            start_time=8.8, end_time=13.1, confidence=0.93, language="en",
            model_used="mock",
        ),
        TranscriptSegment(
            text="Everything runs on-device. Your data never leaves the building.",
            start_time=13.2, end_time=17.5, confidence=0.97, language="en",
            model_used="mock",
        ),
        TranscriptSegment(
            text="Our accuracy rate is 99.9 percent across all test datasets.",
            start_time=17.6, end_time=22.0, confidence=0.91, language="en",
            model_used="mock",
        ),
    ]


@pytest.fixture
def sample_ocr_blocks():
    from backend.data_models import OCRBlock, OCRSourceType

    return [
        OCRBlock(
            text="PitchPilot — The AI-powered demo rehearsal copilot",
            source_type=OCRSourceType.VIDEO_FRAME,
            frame_index=0, timestamp=0.0, confidence=0.97, model_used="mock",
        ),
        OCRBlock(
            text="Instant approval. Zero manual steps. 99.9% accuracy.",
            source_type=OCRSourceType.VIDEO_FRAME,
            frame_index=3, timestamp=6.0, confidence=0.88, model_used="mock",
        ),
        OCRBlock(
            text="Your data never leaves the device. Private by design.",
            source_type=OCRSourceType.VIDEO_FRAME,
            frame_index=4, timestamp=8.0, confidence=0.93, model_used="mock",
        ),
    ]


class TestClaimExtractor:
    @pytest.mark.asyncio
    async def test_returns_claims(self, mock_extractor, sample_transcript_segments, sample_ocr_blocks):
        claims = await mock_extractor.extract(sample_transcript_segments, sample_ocr_blocks)
        assert isinstance(claims, list)
        assert len(claims) > 0

    @pytest.mark.asyncio
    async def test_claims_have_required_fields(
        self, mock_extractor, sample_transcript_segments, sample_ocr_blocks
    ):
        claims = await mock_extractor.extract(sample_transcript_segments, sample_ocr_blocks)
        for claim in claims:
            assert claim.text, f"Claim has empty text: {claim}"
            assert claim.category in ClaimCategory
            assert claim.source in ClaimSource
            assert claim.timestamp_start >= 0.0
            assert claim.timestamp_end >= claim.timestamp_start
            assert 0.0 <= claim.confidence <= 1.0
            assert claim.model_used

    @pytest.mark.asyncio
    async def test_claims_sorted_by_timestamp(
        self, mock_extractor, sample_transcript_segments, sample_ocr_blocks
    ):
        claims = await mock_extractor.extract(sample_transcript_segments, sample_ocr_blocks)
        starts = [c.timestamp_start for c in claims]
        assert starts == sorted(starts)

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, mock_extractor):
        claims = await mock_extractor.extract([], [])
        assert claims == []

    @pytest.mark.asyncio
    async def test_max_claims_cap(self, mock_extractor, sample_transcript_segments, sample_ocr_blocks):
        claims = await mock_extractor.extract(
            sample_transcript_segments, sample_ocr_blocks, max_claims=2
        )
        assert len(claims) <= 2

    @pytest.mark.asyncio
    async def test_transcript_only_input(self, mock_extractor, sample_transcript_segments):
        claims = await mock_extractor.extract(sample_transcript_segments, [])
        assert len(claims) >= 0  # Mock may still return claims from transcript

    @pytest.mark.asyncio
    async def test_evidence_attached(self, mock_extractor, sample_transcript_segments, sample_ocr_blocks):
        claims = await mock_extractor.extract(sample_transcript_segments, sample_ocr_blocks)
        # Each claim should have at least one evidence item
        for claim in claims:
            assert len(claim.evidence) >= 1


class TestCombineText:
    def test_combine_returns_string(self, mock_extractor, sample_transcript_segments, sample_ocr_blocks):
        text = mock_extractor.combine_text(sample_transcript_segments, sample_ocr_blocks)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_combine_contains_transcript(
        self, mock_extractor, sample_transcript_segments, sample_ocr_blocks
    ):
        text = mock_extractor.combine_text(sample_transcript_segments, sample_ocr_blocks)
        assert "automated" in text.lower()

    def test_combine_contains_ocr(
        self, mock_extractor, sample_transcript_segments, sample_ocr_blocks
    ):
        text = mock_extractor.combine_text(sample_transcript_segments, sample_ocr_blocks)
        assert "instant approval" in text.lower()


class TestBuildTranscriptWindows:
    def test_short_transcript_single_window(self):
        from backend.data_models import TranscriptSegment
        from backend.pipeline.claims import _build_transcript_windows

        segs = [
            TranscriptSegment(text="A", start_time=0.0, end_time=5.0, model_used="mock"),
            TranscriptSegment(text="B", start_time=5.1, end_time=10.0, model_used="mock"),
        ]
        windows = _build_transcript_windows(segs, window_secs=30.0)
        assert len(windows) == 1

    def test_empty_returns_empty(self):
        from backend.pipeline.claims import _build_transcript_windows

        assert _build_transcript_windows([], window_secs=30.0) == []

    def test_long_transcript_multiple_windows(self):
        from backend.data_models import TranscriptSegment
        from backend.pipeline.claims import _build_transcript_windows

        segs = [
            TranscriptSegment(
                text=f"Segment {i}", start_time=float(i * 10), end_time=float(i * 10 + 9),
                model_used="mock",
            )
            for i in range(10)  # 0-90 seconds
        ]
        windows = _build_transcript_windows(segs, window_secs=20.0)
        assert len(windows) > 1


class TestDeduplicateClaims:
    def test_identical_claims_deduplicated(self):
        from backend.data_models import Claim, ClaimCategory, ClaimSource
        from backend.pipeline.claims import _deduplicate_claims

        claim = Claim(
            text="The platform is fully automated",
            category=ClaimCategory.AUTOMATION_CLAIM,
            source=ClaimSource.TRANSCRIPT,
            timestamp_start=0.0,
            timestamp_end=5.0,
            confidence=0.9,
        )
        # Two identical claims
        result = _deduplicate_claims([claim, claim])
        assert len(result) == 1

    def test_different_claims_kept(self):
        from backend.data_models import Claim, ClaimCategory, ClaimSource
        from backend.pipeline.claims import _deduplicate_claims

        c1 = Claim(
            text="We provide automated compliance checking",
            category=ClaimCategory.AUTOMATION_CLAIM,
            source=ClaimSource.TRANSCRIPT,
            timestamp_start=0.0,
            timestamp_end=5.0,
        )
        c2 = Claim(
            text="Our accuracy rate is 99.9 percent",
            category=ClaimCategory.ACCURACY_CLAIM,
            source=ClaimSource.TRANSCRIPT,
            timestamp_start=10.0,
            timestamp_end=15.0,
        )
        result = _deduplicate_claims([c1, c2])
        assert len(result) == 2

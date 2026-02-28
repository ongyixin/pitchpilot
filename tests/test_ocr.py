"""
Tests for backend/pipeline/ocr.py

Uses mock mode (no model required).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures.generate_test_fixtures import (
    SAMPLE_POLICY_PATH,
    TEST_VIDEO_PATH,
    generate_sample_policy,
    generate_test_video,
)


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    if not TEST_VIDEO_PATH.exists():
        generate_test_video()
    if not SAMPLE_POLICY_PATH.exists():
        generate_sample_policy()
    yield


@pytest.fixture
def mock_ocr():
    """OCRPipeline using MockMultimodalAdapter."""
    from backend.models.gemma3n import MockMultimodalAdapter
    from backend.pipeline.ocr import OCRPipeline

    return OCRPipeline(model=MockMultimodalAdapter())


@pytest.fixture
def sample_frames(tmp_path, monkeypatch):
    """Return a list of ExtractedFrame from the test video."""
    import backend.pipeline.video as video_module
    from backend.pipeline.video import detect_keyframes, extract_frames, save_video_file

    monkeypatch.setattr(video_module, "SESSIONS_DIR", tmp_path)
    meta = save_video_file(str(TEST_VIDEO_PATH), session_id="ocr-frames-fixture")
    frames = extract_frames(meta, fps=1.0, output_dir=str(tmp_path / "frames"))
    return detect_keyframes(frames)


class TestProcessFrames:
    @pytest.mark.asyncio
    async def test_returns_ocr_blocks(self, mock_ocr, sample_frames):
        blocks = await mock_ocr.process_frames(sample_frames)
        assert isinstance(blocks, list)
        assert len(blocks) > 0

    @pytest.mark.asyncio
    async def test_blocks_have_required_fields(self, mock_ocr, sample_frames):
        blocks = await mock_ocr.process_frames(sample_frames)
        for block in blocks:
            assert block.text, f"Block has empty text: {block}"
            assert block.timestamp is not None
            assert block.frame_index is not None
            assert 0.0 <= block.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_blocks_sorted_by_timestamp(self, mock_ocr, sample_frames):
        blocks = await mock_ocr.process_frames(sample_frames)
        timestamps = [b.timestamp for b in blocks]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_keyframes_only_reduces_count(self, mock_ocr, sample_frames):
        all_blocks = await mock_ocr.process_frames(sample_frames, keyframes_only=False)
        kf_blocks = await mock_ocr.process_frames(sample_frames, keyframes_only=True)

        kf_count = sum(1 for f in sample_frames if f.is_keyframe)
        non_kf_count = len(sample_frames) - kf_count

        if non_kf_count > 0:
            # Keyframes-only should process fewer frames
            assert len(kf_blocks) <= len(all_blocks)


class TestProcessDocument:
    @pytest.mark.asyncio
    async def test_text_file_returns_blocks(self, mock_ocr):
        blocks = await mock_ocr.process_document(str(SAMPLE_POLICY_PATH))
        assert len(blocks) > 0

    @pytest.mark.asyncio
    async def test_text_blocks_have_page_numbers(self, mock_ocr):
        blocks = await mock_ocr.process_document(str(SAMPLE_POLICY_PATH))
        for block in blocks:
            assert block.page_number is not None and block.page_number >= 1

    @pytest.mark.asyncio
    async def test_text_blocks_have_document_path(self, mock_ocr):
        blocks = await mock_ocr.process_document(str(SAMPLE_POLICY_PATH))
        for block in blocks:
            assert block.document_path is not None

    @pytest.mark.asyncio
    async def test_missing_file_raises(self, mock_ocr):
        with pytest.raises(FileNotFoundError):
            await mock_ocr.process_document("/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_text_content_preserved(self, mock_ocr):
        blocks = await mock_ocr.process_document(str(SAMPLE_POLICY_PATH))
        full_text = " ".join(b.text for b in blocks).lower()
        assert "automated" in full_text
        assert "compliance" in full_text


class TestParseOCRJson:
    def test_valid_json(self):
        from backend.pipeline.ocr import _parse_ocr_json

        raw = '{"blocks": [{"text": "Hello", "confidence": 0.9}]}'
        result = _parse_ocr_json(raw)
        assert result == [{"text": "Hello", "confidence": 0.9}]

    def test_markdown_wrapped_json(self):
        from backend.pipeline.ocr import _parse_ocr_json

        raw = '```json\n{"blocks": [{"text": "Slide title", "confidence": 0.95}]}\n```'
        result = _parse_ocr_json(raw)
        assert len(result) == 1
        assert result[0]["text"] == "Slide title"

    def test_malformed_json_returns_empty(self):
        from backend.pipeline.ocr import _parse_ocr_json

        result = _parse_ocr_json("this is not json at all")
        assert result == []

    def test_empty_blocks_list(self):
        from backend.pipeline.ocr import _parse_ocr_json

        raw = '{"blocks": []}'
        result = _parse_ocr_json(raw)
        assert result == []

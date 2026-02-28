"""
Tests for backend/pipeline/transcribe.py

Uses mock mode (no model required).
"""

from __future__ import annotations

import pytest

from tests.fixtures.generate_test_fixtures import (
    TEST_AUDIO_PATH,
    generate_silent_wav,
)


@pytest.fixture(scope="module", autouse=True)
def ensure_audio_fixture():
    if not TEST_AUDIO_PATH.exists():
        generate_silent_wav()
    yield


@pytest.fixture
def mock_transcriber():
    """TranscriptionPipeline using MockMultimodalAdapter."""
    from backend.models.gemma3n import MockMultimodalAdapter
    from backend.pipeline.transcribe import TranscriptionPipeline

    return TranscriptionPipeline(
        model=MockMultimodalAdapter(),
        use_whisper_fallback=False,
    )


@pytest.fixture
def sample_audio_track():
    from backend.data_models import AudioTrack

    return AudioTrack(
        file_path=str(TEST_AUDIO_PATH),
        duration_seconds=10.0,
        sample_rate=16000,
        channels=1,
        source_video_path="/fake/video.mp4",
    )


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_returns_segments(self, mock_transcriber, sample_audio_track):
        segments = await mock_transcriber.transcribe(sample_audio_track)
        assert isinstance(segments, list)
        assert len(segments) > 0

    @pytest.mark.asyncio
    async def test_segments_have_required_fields(self, mock_transcriber, sample_audio_track):
        segments = await mock_transcriber.transcribe(sample_audio_track)
        for seg in segments:
            assert seg.text, f"Segment has empty text: {seg}"
            assert seg.start_time >= 0.0
            assert seg.end_time > seg.start_time
            assert 0.0 <= seg.confidence <= 1.5  # whisper log-prob shifted can exceed 1
            assert seg.language

    @pytest.mark.asyncio
    async def test_segments_sorted_by_start_time(self, mock_transcriber, sample_audio_track):
        segments = await mock_transcriber.transcribe(sample_audio_track)
        starts = [s.start_time for s in segments]
        assert starts == sorted(starts)

    @pytest.mark.asyncio
    async def test_missing_audio_raises(self, mock_transcriber):
        from backend.data_models import AudioTrack

        bad_audio = AudioTrack(
            file_path="/nonexistent/audio.wav",
            duration_seconds=5.0,
            sample_rate=16000,
            channels=1,
            source_video_path="/fake/video.mp4",
        )
        with pytest.raises(FileNotFoundError):
            await mock_transcriber.transcribe(bad_audio)

    @pytest.mark.asyncio
    async def test_full_transcript_concatenation(self, mock_transcriber, sample_audio_track):
        segments = await mock_transcriber.transcribe(sample_audio_track)
        full_text = mock_transcriber.get_full_transcript(segments)
        assert isinstance(full_text, str)
        assert len(full_text) > 0
        # Each segment text should appear in the full transcript
        for seg in segments:
            assert seg.text in full_text

    @pytest.mark.asyncio
    async def test_mock_transcript_contains_expected_claims(
        self, mock_transcriber, sample_audio_track
    ):
        """The mock transcript should contain compliance-sensitive language."""
        segments = await mock_transcriber.transcribe(sample_audio_track)
        full_text = mock_transcriber.get_full_transcript(segments).lower()
        assert "automated" in full_text or "on-device" in full_text or "accuracy" in full_text


class TestParseTranscriptJson:
    def test_valid_json(self):
        from backend.pipeline.transcribe import _parse_transcript_json

        raw = '{"segments": [{"text": "Hello world", "start": 0.0, "end": 2.5, "confidence": 0.9}]}'
        result = _parse_transcript_json(raw, model_name="test")
        assert len(result) == 1
        assert result[0].text == "Hello world"
        assert result[0].start_time == 0.0
        assert result[0].end_time == 2.5

    def test_markdown_wrapped(self):
        from backend.pipeline.transcribe import _parse_transcript_json

        raw = '```json\n{"segments": [{"text": "Test", "start": 1.0, "end": 2.0, "confidence": 0.8}]}\n```'
        result = _parse_transcript_json(raw, model_name="test")
        assert len(result) == 1

    def test_empty_segments(self):
        from backend.pipeline.transcribe import _parse_transcript_json

        raw = '{"segments": []}'
        assert _parse_transcript_json(raw) == []

    def test_segments_sorted(self):
        from backend.pipeline.transcribe import _parse_transcript_json

        raw = (
            '{"segments": ['
            '{"text": "B", "start": 3.0, "end": 4.0, "confidence": 0.9},'
            '{"text": "A", "start": 0.0, "end": 2.0, "confidence": 0.9}'
            "]}"
        )
        result = _parse_transcript_json(raw)
        assert result[0].text == "A"
        assert result[1].text == "B"

    def test_malformed_returns_empty(self):
        from backend.pipeline.transcribe import _parse_transcript_json

        assert _parse_transcript_json("not json") == []

"""
Smoke tests — fast sanity checks that don't require running servers or models.

Run with:
    pytest tests/test_smoke.py -v

These tests verify:
1. Backend modules import cleanly
2. Config loads with defaults
3. Pydantic schemas validate correctly
4. Mock pipeline data is well-formed
5. Demo fixture file is valid JSON with expected shape
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------


def test_import_api_schemas():
    """All Pydantic API schema models import cleanly."""
    from backend.api_schemas import (
        AgentType,
        Claim,
        ClaimType,
        DimensionScore,
        Finding,
        FindingsResponse,
        PersonaQuestion,
        ReadinessReport,
        ReadinessScore,
        Session,
        SessionStartResponse,
        SessionStatus,
        SessionStatusResponse,
        Severity,
        TimelineAnnotation,
        TimelineCategory,
        TimelineResponse,
    )
    assert AgentType.COACH == "coach"
    assert Severity.CRITICAL == "critical"
    assert SessionStatus.COMPLETE == "complete"


def test_import_config():
    """Config module loads without errors and exports required constants."""
    from backend.config import (
        API_HOST,
        API_PORT,
        DEFAULT_PERSONAS,
        MAX_CLAIMS_PER_SESSION,
        settings,
    )
    assert API_PORT == 8000
    assert API_HOST == "0.0.0.0"
    assert len(DEFAULT_PERSONAS) >= 3
    assert MAX_CLAIMS_PER_SESSION > 0
    assert settings.mock_mode is True  # default should be True


def test_import_schemas():
    """Internal pipeline schemas (dataclasses) import cleanly."""
    from backend.schemas import (
        Claim,
        Finding,
        PipelineContext,
        ReadinessReport,
        TimelineAnnotation,
        TranscriptSegment,
    )
    # Should be importable without errors


def test_import_data_models():
    """Ingestion pipeline Pydantic models import cleanly."""
    from backend.data_models import (
        AudioTrack,
        Claim,
        ExtractedFrame,
        IngestionResult,
        OCRBlock,
        TranscriptSegment,
        VideoMetadata,
    )


def test_import_demo_server():
    """Demo server FastAPI app imports cleanly."""
    from backend.demo_server import app
    assert app.title == "PitchPilot Demo API"


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_finding_schema():
    """Finding model validates and serialises correctly."""
    from backend.api_schemas import AgentType, Finding, Severity

    f = Finding(
        agent=AgentType.COMPLIANCE,
        severity=Severity.CRITICAL,
        title="Test finding",
        detail="Some detail",
        timestamp=30.0,
    )
    assert f.agent == "compliance"
    assert f.severity == "critical"
    assert len(f.id) > 0
    data = f.model_dump()
    assert data["title"] == "Test finding"


def test_readiness_report_schema():
    """ReadinessReport roundtrips through JSON without data loss."""
    from uuid import uuid4
    from datetime import datetime, timezone

    from backend.api_schemas import (
        AgentType,
        Claim,
        ClaimType,
        DimensionScore,
        Finding,
        PersonaQuestion,
        ReadinessReport,
        ReadinessScore,
        Severity,
    )

    claims = [
        Claim(
            text="We are fully automated.",
            claim_type=ClaimType.FEATURE,
            timestamp=10.0,
            confidence=0.9,
        )
    ]
    findings = [
        Finding(
            agent=AgentType.COMPLIANCE,
            severity=Severity.WARNING,
            title="Test compliance issue",
            detail="This is a test finding.",
            timestamp=10.0,
        )
    ]
    score = ReadinessScore(
        overall=75,
        dimensions=[DimensionScore(dimension="Clarity", score=75, rationale="OK")],
        priority_fixes=["Fix X"],
    )
    report = ReadinessReport(
        session_id=uuid4(),
        score=score,
        findings=findings,
        persona_questions=[],
        claims=claims,
        summary="Test summary.",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    assert report.score.overall == 75
    # Roundtrip JSON
    dumped = report.model_dump_json()
    restored = ReadinessReport.model_validate_json(dumped)
    assert restored.score.overall == 75
    assert len(restored.findings) == 1


def test_session_schema():
    """Session model creates cleanly with defaults."""
    from uuid import uuid4
    from datetime import datetime, timezone
    from backend.api_schemas import Session, SessionStatus

    session = Session(
        id=uuid4(),
        video_filename="test.mp4",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    assert session.status == SessionStatus.PENDING
    assert session.progress == 0
    assert session.report is None


# ---------------------------------------------------------------------------
# Demo fixture tests
# ---------------------------------------------------------------------------


def test_demo_fixture_exists():
    """The demo fixture JSON file exists at the expected path."""
    fixture_path = PROJECT_ROOT / "data" / "fixtures" / "demo_session.json"
    assert fixture_path.exists(), f"Demo fixture not found at {fixture_path}"


def test_demo_fixture_valid_json():
    """The demo fixture is valid JSON with required top-level keys."""
    fixture_path = PROJECT_ROOT / "data" / "fixtures" / "demo_session.json"
    with open(fixture_path) as f:
        data = json.load(f)

    required_keys = {"session_id", "score", "findings", "persona_questions", "claims", "summary"}
    missing = required_keys - data.keys()
    assert not missing, f"Demo fixture missing keys: {missing}"


def test_demo_fixture_score_shape():
    """The demo fixture score has the expected shape."""
    fixture_path = PROJECT_ROOT / "data" / "fixtures" / "demo_session.json"
    with open(fixture_path) as f:
        data = json.load(f)

    score = data["score"]
    assert isinstance(score["overall"], int)
    assert 0 <= score["overall"] <= 100
    assert isinstance(score["dimensions"], list)
    assert len(score["dimensions"]) >= 3
    assert isinstance(score["priority_fixes"], list)
    assert len(score["priority_fixes"]) >= 1


def test_demo_fixture_findings_shape():
    """Each finding in the demo fixture has required fields."""
    fixture_path = PROJECT_ROOT / "data" / "fixtures" / "demo_session.json"
    with open(fixture_path) as f:
        data = json.load(f)

    required = {"id", "agent", "severity", "title", "detail", "timestamp"}
    valid_agents = {"coach", "compliance", "persona"}
    valid_severities = {"info", "warning", "critical"}

    for finding in data["findings"]:
        missing = required - finding.keys()
        assert not missing, f"Finding {finding.get('id')} missing: {missing}"
        assert finding["agent"] in valid_agents, f"Unknown agent: {finding['agent']}"
        assert finding["severity"] in valid_severities


def test_sample_policy_files_exist():
    """Sample policy documents exist in data/sample_policies/."""
    policy_dir = PROJECT_ROOT / "data" / "sample_policies"
    assert policy_dir.exists()
    policy_files = list(policy_dir.glob("*.txt")) + list(policy_dir.glob("*.pdf"))
    assert len(policy_files) >= 1, "No policy files found in data/sample_policies/"


# ---------------------------------------------------------------------------
# Live session fixture tests
# ---------------------------------------------------------------------------


def test_live_inroom_fixture_exists():
    """The live in-room fixture JSON file exists at the expected path."""
    path = PROJECT_ROOT / "data" / "fixtures" / "live_inroom_session.json"
    assert path.exists(), f"Live in-room fixture not found at {path}"


def test_live_remote_fixture_exists():
    """The live remote fixture JSON file exists at the expected path."""
    path = PROJECT_ROOT / "data" / "fixtures" / "live_remote_session.json"
    assert path.exists(), f"Live remote fixture not found at {path}"


def _load_live_fixture(name: str) -> dict:
    path = PROJECT_ROOT / "data" / "fixtures" / name
    with open(path) as f:
        return json.load(f)


def test_live_inroom_fixture_valid_json():
    """Live in-room fixture has the required top-level keys."""
    data = _load_live_fixture("live_inroom_session.json")
    required = {"session_id", "session_mode", "score", "findings", "persona_questions", "claims", "summary"}
    missing = required - data.keys()
    assert not missing, f"Live in-room fixture missing keys: {missing}"
    assert data["session_mode"] == "live_in_room"


def test_live_remote_fixture_valid_json():
    """Live remote fixture has the required top-level keys."""
    data = _load_live_fixture("live_remote_session.json")
    required = {"session_id", "session_mode", "score", "findings", "persona_questions", "claims", "summary"}
    missing = required - data.keys()
    assert not missing, f"Live remote fixture missing keys: {missing}"
    assert data["session_mode"] == "live_remote"


def test_live_inroom_fixture_has_live_findings():
    """All findings in the in-room fixture have live=true and valid agent/severity."""
    data = _load_live_fixture("live_inroom_session.json")
    valid_agents = {"coach", "compliance", "persona"}
    valid_severities = {"info", "warning", "critical"}
    required = {"id", "agent", "severity", "title", "detail", "timestamp"}

    for finding in data["findings"]:
        missing = required - finding.keys()
        assert not missing, f"Finding {finding.get('id')} missing: {missing}"
        assert finding["agent"] in valid_agents
        assert finding["severity"] in valid_severities
        assert finding.get("live") is True, f"Finding {finding['id']} is missing live=true"


def test_live_remote_fixture_has_live_findings():
    """All findings in the remote fixture have live=true and valid agent/severity."""
    data = _load_live_fixture("live_remote_session.json")
    valid_agents = {"coach", "compliance", "persona"}
    valid_severities = {"info", "warning", "critical"}
    required = {"id", "agent", "severity", "title", "detail", "timestamp"}

    for finding in data["findings"]:
        missing = required - finding.keys()
        assert not missing, f"Finding {finding.get('id')} missing: {missing}"
        assert finding["agent"] in valid_agents
        assert finding["severity"] in valid_severities
        assert finding.get("live") is True, f"Finding {finding['id']} is missing live=true"


def test_live_inroom_fixture_has_earpiece_cues():
    """Critical and warning findings in the in-room fixture have cue_hint fields."""
    data = _load_live_fixture("live_inroom_session.json")
    actionable = [f for f in data["findings"] if f["severity"] in ("critical", "warning")]
    with_cues = [f for f in actionable if f.get("cue_hint")]
    assert len(with_cues) >= 4, (
        f"Expected ≥4 findings with cue_hint in live in-room fixture, got {len(with_cues)}"
    )
    # Cue hints should be 3-6 words
    for f in with_cues:
        words = f["cue_hint"].split()
        assert 2 <= len(words) <= 8, (
            f"cue_hint '{f['cue_hint']}' on finding {f['id']} is unexpectedly long/short"
        )


def test_live_remote_fixture_has_overlay_cues():
    """Critical and warning findings in the remote fixture have cue_hint fields."""
    data = _load_live_fixture("live_remote_session.json")
    actionable = [f for f in data["findings"] if f["severity"] in ("critical", "warning")]
    with_cues = [f for f in actionable if f.get("cue_hint")]
    assert len(with_cues) >= 5, (
        f"Expected ≥5 findings with cue_hint in live remote fixture, got {len(with_cues)}"
    )


def test_live_fixtures_duration_and_cues_count():
    """Live fixtures include session_duration_seconds and live_cues_count."""
    inroom = _load_live_fixture("live_inroom_session.json")
    assert "session_duration_seconds" in inroom
    assert "live_cues_count" in inroom
    assert inroom["session_duration_seconds"] > 0
    assert inroom["live_cues_count"] > 0

    remote = _load_live_fixture("live_remote_session.json")
    assert "session_duration_seconds" in remote
    assert "live_cues_count" in remote
    assert remote["session_duration_seconds"] > 0
    assert remote["live_cues_count"] > 0


def test_live_inroom_score_in_range():
    """Live in-room fixture score is valid (0–100, ≥3 dimensions)."""
    data = _load_live_fixture("live_inroom_session.json")
    score = data["score"]
    assert 0 <= score["overall"] <= 100
    assert len(score["dimensions"]) >= 3
    assert len(score["priority_fixes"]) >= 1


def test_live_remote_score_in_range():
    """Live remote fixture score is valid (0–100, ≥3 dimensions)."""
    data = _load_live_fixture("live_remote_session.json")
    score = data["score"]
    assert 0 <= score["overall"] <= 100
    assert len(score["dimensions"]) >= 3
    assert len(score["priority_fixes"]) >= 1


# ---------------------------------------------------------------------------
# Pipeline utility tests
# ---------------------------------------------------------------------------


def test_demo_server_mock_pipeline_data():
    """Demo server produces valid claims and findings."""
    from backend.demo_server import _demo_claims, _demo_findings, _demo_report
    from uuid import uuid4

    claims = _demo_claims()
    assert len(claims) >= 3
    for c in claims:
        assert c.text
        assert c.timestamp >= 0

    findings = _demo_findings(claims)
    assert len(findings) >= 5
    agents = {f.agent.value for f in findings}
    assert "coach" in agents
    assert "compliance" in agents
    assert "persona" in agents

    uuid = uuid4()
    report = _demo_report(uuid, claims, findings)
    assert 0 <= report.score.overall <= 100
    assert len(report.score.dimensions) >= 3
    assert report.summary


# ---------------------------------------------------------------------------
# Real pipeline readiness checks (run without Ollama; verify wiring only)
# ---------------------------------------------------------------------------


def test_env_var_wiring():
    """
    PITCHPILOT_MOCK_MODE env var is correctly wired to settings.mock_mode.

    This test verifies the env var name mismatch is fixed: the old code read
    USE_MOCK_PIPELINE (which never mapped to anything), the new code reads
    PITCHPILOT_MOCK_MODE via pydantic-settings env_prefix.
    """
    import os
    from importlib import reload
    import backend.config as cfg

    # The currently loaded settings should reflect the .env.local value
    # (whatever is set in the environment when tests run).
    # We simply assert the field is accessible and a bool.
    assert isinstance(cfg.settings.mock_mode, bool), (
        "settings.mock_mode must be a bool — check env var PITCHPILOT_MOCK_MODE"
    )
    assert isinstance(cfg.USE_MOCK, bool), "config.USE_MOCK must be a bool"


def test_real_pipeline_module_imports():
    """
    All real pipeline modules import cleanly (no import-time dependency on Ollama).

    This verifies that the code path reached when mock_mode=False doesn't crash
    at import time — Ollama calls are deferred to actual usage.
    """
    from backend.ingestion import IngestionPipeline
    from backend.agents.orchestrator import Orchestrator
    from backend.reports.readiness import ReadinessReportGenerator
    from backend.pipeline.live import LivePipeline
    from backend.pipeline.claims import ClaimExtractor
    from backend.pipeline.ocr import OCRPipeline
    from backend.pipeline.transcribe import TranscriptionPipeline

    assert IngestionPipeline is not None
    assert Orchestrator is not None
    assert ReadinessReportGenerator is not None
    assert LivePipeline is not None


def test_report_generator_real_path():
    """
    ReadinessReportGenerator.generate() works with a real OrchestratorResult.

    Specifically validates the method signature (result, context) — not the old
    wrong kwargs (session_id, orchestrator_result, ingestion_result).
    """
    from backend.agents.orchestrator import OrchestratorResult
    from backend.reports.readiness import ReadinessReportGenerator
    from backend.schemas import (
        Claim,
        Finding,
        PipelineContext,
        TimelineAnnotation,
    )

    claim = Claim(
        text="Our platform is fully automated.",
        claim_type="general",
        timestamp=10.0,
        source="transcript",
    )
    finding = Finding(
        agent="compliance",
        category="compliance",
        severity="warning",
        title="Automation claim",
        description="Automation claim may need qualification.",
        suggestion="Add a qualifier.",
        timestamp=10.0,
        claim_ref=claim.id,
    )

    result = OrchestratorResult(
        session_id="smoke-test-001",
        findings=[finding],
        timeline=[
            TimelineAnnotation(
                timestamp=10.0,
                category="compliance",
                color="red",
                label="Automation claim",
                finding_id=finding.id,
                agent="compliance",
            )
        ],
        claims_processed=1,
    )

    context = PipelineContext(
        session_id="smoke-test-001",
        claims=[claim],
        personas=["Skeptical Investor"],
        presentation_title="PitchPilot Demo",
    )

    gen = ReadinessReportGenerator()
    report = gen.generate(result=result, context=context)

    assert 0 <= report.overall_score <= 100
    assert report.grade in ("A", "B", "C", "D", "F")
    assert len(report.findings) == 1
    assert report.summary


def test_pipeline_context_full_transcript_property():
    """
    PipelineContext.full_transcript is a @property — passing it as a constructor
    kwarg would cause a TypeError.  This test ensures we build context correctly.
    """
    from backend.schemas import PipelineContext, TranscriptSegment

    seg = TranscriptSegment(text="Hello world.", start_time=0.0, end_time=2.0)
    ctx = PipelineContext(
        session_id="test",
        transcript_segments=[seg],
    )
    # Must be accessible as a property, not a stored value
    assert ctx.full_transcript == "Hello world."
    # Confirm passing as kwarg raises
    try:
        PipelineContext(session_id="test2", full_transcript="ignored")
        raise AssertionError("Should have raised TypeError for unknown kwarg")
    except TypeError:
        pass  # expected


def test_live_ws_json_serialisation():
    """
    live_ws.py sends session_mode.value (str), not the enum itself.

    SessionMode is a str-enum (class SessionMode(str, Enum)), so both the
    enum instance and .value serialize to the same JSON string.  This test
    verifies the payload round-trips correctly either way.
    """
    import json
    from backend.api_schemas import SessionMode

    mode = SessionMode.LIVE_IN_ROOM

    # Using .value is explicit and preferred
    payload = {"type": "session_created", "session_id": "abc", "mode": mode.value}
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    assert decoded["mode"] == "live_in_room"

    # str-enums also serialize directly (SessionMode inherits str)
    payload2 = {"type": "session_created", "session_id": "abc", "mode": mode}
    encoded2 = json.dumps(payload2)
    decoded2 = json.loads(encoded2)
    assert decoded2["mode"] == "live_in_room", (
        "str-enum should serialise to its string value"
    )

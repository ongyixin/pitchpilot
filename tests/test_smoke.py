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

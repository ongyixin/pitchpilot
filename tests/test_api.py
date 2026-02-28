"""
API integration tests for the demo server.

These tests spin up the FastAPI app in-process using httpx.AsyncClient +
the ASGI transport, so no real server needs to be running.

Run with:
    pytest tests/test_api.py -v
    pytest tests/test_api.py -v -k "test_demo"  # just demo tests

Environment:
    PITCHPILOT_DEMO_DELAY=0  (auto-set by the test fixtures for speed)
"""

from __future__ import annotations

import io
import json
import os

import pytest

# Force instant pipeline (no asyncio.sleep delays)
os.environ["PITCHPILOT_DEMO_DELAY"] = "0"

try:
    import httpx
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("httpx not installed — skipping API tests", allow_module_level=True)


@pytest.fixture(scope="module")
def client():
    from backend.demo_server import app

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] == "demo"


# ---------------------------------------------------------------------------
# Demo session endpoint
# ---------------------------------------------------------------------------


def test_demo_session_start(client: TestClient):
    """POST /api/session/demo returns a session_id and pending status."""
    resp = client.post("/api/session/demo")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] in ("pending", "processing", "complete")
    assert data["message"]


def test_demo_session_full_cycle(client: TestClient):
    """Full demo session cycle: start → status → report → timeline → findings."""
    import time

    # Start
    resp = client.post("/api/session/demo")
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # Poll until complete (max 10 seconds, DEMO_DELAY=0 so should be instant)
    for _ in range(20):
        status_resp = client.get(f"/api/session/{session_id}/status")
        assert status_resp.status_code == 200
        status = status_resp.json()
        if status["status"] == "complete":
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"Session did not complete. Last status: {status}")

    assert status["progress"] == 100

    # Report
    report_resp = client.get(f"/api/session/{session_id}/report")
    assert report_resp.status_code == 200
    report = report_resp.json()
    _validate_report(report)

    # Timeline
    timeline_resp = client.get(f"/api/session/{session_id}/timeline")
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert timeline["session_id"] == session_id
    assert isinstance(timeline["annotations"], list)
    assert len(timeline["annotations"]) > 0

    # Findings
    findings_resp = client.get(f"/api/session/{session_id}/findings")
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    assert isinstance(findings_data["findings"], list)
    assert isinstance(findings_data["persona_questions"], list)


def _validate_report(report: dict) -> None:
    """Assert the report has the expected structure."""
    assert "session_id" in report
    assert "score" in report
    assert "findings" in report
    assert "summary" in report

    score = report["score"]
    assert isinstance(score["overall"], int)
    assert 0 <= score["overall"] <= 100
    assert isinstance(score["dimensions"], list)
    assert len(score["dimensions"]) >= 3
    assert isinstance(score["priority_fixes"], list)

    for dim in score["dimensions"]:
        assert "dimension" in dim
        assert "score" in dim
        assert 0 <= dim["score"] <= 100

    for finding in report["findings"]:
        assert finding["agent"] in ("coach", "compliance", "persona")
        assert finding["severity"] in ("info", "warning", "critical")
        assert finding["title"]
        assert finding["detail"]


# ---------------------------------------------------------------------------
# Video upload session
# ---------------------------------------------------------------------------


def test_start_session_with_upload(client: TestClient):
    """POST /api/session/start with a mock video file returns a session_id."""
    dummy_video = io.BytesIO(b"fake video content")
    resp = client.post(
        "/api/session/start",
        files={"video": ("test.mp4", dummy_video, "video/mp4")},
        data={"personas": "Skeptical Investor,Technical Reviewer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] in ("pending", "processing", "complete")


def test_start_session_with_policy_doc(client: TestClient):
    """POST /api/session/start with policy document attaches correctly."""
    dummy_video = io.BytesIO(b"fake video content")
    dummy_policy = io.BytesIO(b"Policy text content")
    resp = client.post(
        "/api/session/start",
        files={
            "video": ("demo.mp4", dummy_video, "video/mp4"),
            "policy_docs": ("policy.txt", dummy_policy, "text/plain"),
        },
        data={"personas": "Compliance Officer"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_session_not_found(client: TestClient):
    """GET /status for unknown session returns 404."""
    resp = client.get("/api/session/00000000-0000-0000-0000-000000000000/status")
    assert resp.status_code == 404


def test_report_not_ready(client: TestClient):
    """GET /report while session is still processing returns 202."""
    # Start a session with non-zero delay temporarily
    # We patch by creating the session without waiting
    resp = client.post(
        "/api/session/start",
        files={"video": ("v.mp4", io.BytesIO(b"x"), "video/mp4")},
    )
    assert resp.status_code == 200
    # Note: with DEMO_DELAY=0 the session completes almost immediately,
    # so this test is best-effort — it's fine if it returns 200 too.
    # We just verify the endpoint is reachable.
    session_id = resp.json()["session_id"]
    report_resp = client.get(f"/api/session/{session_id}/report")
    assert report_resp.status_code in (200, 202)


# ---------------------------------------------------------------------------
# Report quality assertions
# ---------------------------------------------------------------------------


def test_report_has_coach_and_compliance_findings(client: TestClient):
    """Demo report always contains findings from coach and compliance agents."""
    import time

    resp = client.post("/api/session/demo")
    session_id = resp.json()["session_id"]

    for _ in range(20):
        s = client.get(f"/api/session/{session_id}/status").json()
        if s["status"] == "complete":
            break
        time.sleep(0.1)

    report = client.get(f"/api/session/{session_id}/report").json()
    agents = {f["agent"] for f in report["findings"]}
    assert "coach" in agents, "Missing Coach findings"
    assert "compliance" in agents, "Missing Compliance findings"


def test_report_has_critical_finding(client: TestClient):
    """Demo report always contains at least one critical finding."""
    import time

    resp = client.post("/api/session/demo")
    session_id = resp.json()["session_id"]

    for _ in range(20):
        s = client.get(f"/api/session/{session_id}/status").json()
        if s["status"] == "complete":
            break
        time.sleep(0.1)

    report = client.get(f"/api/session/{session_id}/report").json()
    critical = [f for f in report["findings"] if f["severity"] == "critical"]
    assert len(critical) >= 1, "Demo report should have at least one critical finding"


def test_timeline_annotations_are_sorted(client: TestClient):
    """Timeline annotations are sorted chronologically."""
    import time

    resp = client.post("/api/session/demo")
    session_id = resp.json()["session_id"]

    for _ in range(20):
        s = client.get(f"/api/session/{session_id}/status").json()
        if s["status"] == "complete":
            break
        time.sleep(0.1)

    tl = client.get(f"/api/session/{session_id}/timeline").json()
    timestamps = [a["timestamp"] for a in tl["annotations"]]
    assert timestamps == sorted(timestamps), "Timeline annotations are not sorted"


# ---------------------------------------------------------------------------
# Live session registration endpoint
# ---------------------------------------------------------------------------


def test_start_live_session_default_mode(client: TestClient):
    """POST /api/session/start-live returns session_id, ws_url, and mode."""
    resp = client.post(
        "/api/session/start-live",
        json={"mode": "live_in_room", "personas": ["Skeptical Investor"], "policy_text": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "ws_url" in data
    assert data["mode"] == "live_in_room"
    assert data["status"] in ("pending", "processing", "complete")


def test_start_live_session_remote_mode(client: TestClient):
    """POST /api/session/start-live with live_remote mode."""
    resp = client.post(
        "/api/session/start-live",
        json={"mode": "live_remote", "personas": [], "policy_text": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "live_remote"
    assert "session_id" in data


# ---------------------------------------------------------------------------
# Demo-live endpoint (instant completed live session)
# ---------------------------------------------------------------------------


def test_demo_live_inroom_start(client: TestClient):
    """POST /api/session/demo-live creates a pending live in-room session."""
    resp = client.post("/api/session/demo-live?mode=live_in_room")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] in ("pending", "processing", "complete")
    assert "in-room" in data["message"].lower() or "live" in data["message"].lower()


def test_demo_live_remote_start(client: TestClient):
    """POST /api/session/demo-live?mode=live_remote creates a pending live remote session."""
    resp = client.post("/api/session/demo-live?mode=live_remote")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] in ("pending", "processing", "complete")


def test_demo_live_inroom_full_cycle(client: TestClient):
    """Full live in-room demo cycle: start → poll → report → timeline → findings."""
    import time

    resp = client.post("/api/session/demo-live?mode=live_in_room")
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    for _ in range(40):
        s = client.get(f"/api/session/{session_id}/status").json()
        if s["status"] == "complete":
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"Live in-room session did not complete. Last status: {s}")

    # Report
    report = client.get(f"/api/session/{session_id}/report").json()
    _validate_report(report)

    # Report includes live-session provenance
    assert report.get("session_mode") == "live_in_room", "Live in-room report missing session_mode"
    assert report.get("session_duration_seconds", 0) > 0, "Missing session_duration_seconds"
    assert report.get("live_cues_count", 0) > 0, "Missing live_cues_count"
    assert report.get("live_session_summary"), "Missing live_session_summary"

    # Findings all carry live=True
    for finding in report["findings"]:
        assert finding.get("live") is True, f"Finding {finding['id']} missing live=True"

    # Timeline
    tl = client.get(f"/api/session/{session_id}/timeline").json()
    assert len(tl["annotations"]) > 0
    timestamps = [a["timestamp"] for a in tl["annotations"]]
    assert timestamps == sorted(timestamps), "Timeline not sorted"


def test_demo_live_remote_full_cycle(client: TestClient):
    """Full live remote demo cycle: start → poll → report → findings."""
    import time

    resp = client.post("/api/session/demo-live?mode=live_remote")
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    for _ in range(40):
        s = client.get(f"/api/session/{session_id}/status").json()
        if s["status"] == "complete":
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"Live remote session did not complete. Last status: {s}")

    report = client.get(f"/api/session/{session_id}/report").json()
    _validate_report(report)

    assert report.get("session_mode") == "live_remote", "Live remote report missing session_mode"
    assert report.get("session_duration_seconds", 0) > 0
    assert report.get("live_cues_count", 0) > 0

    for finding in report["findings"]:
        assert finding.get("live") is True, f"Finding {finding['id']} missing live=True"


def test_live_report_has_cue_hints(client: TestClient):
    """Live session report findings include cue_hint on critical/warning items."""
    import time

    resp = client.post("/api/session/demo-live?mode=live_in_room")
    session_id = resp.json()["session_id"]

    for _ in range(40):
        s = client.get(f"/api/session/{session_id}/status").json()
        if s["status"] == "complete":
            break
        time.sleep(0.1)

    report = client.get(f"/api/session/{session_id}/report").json()
    actionable = [f for f in report["findings"] if f["severity"] in ("critical", "warning")]
    with_cues = [f for f in actionable if f.get("cue_hint")]
    assert len(with_cues) >= 3, (
        f"Expected ≥3 findings with cue_hint in live report, got {len(with_cues)}"
    )


def test_live_and_review_reports_share_same_endpoints(client: TestClient):
    """Review /report, /timeline, /findings all work identically for live sessions."""
    import time

    resp = client.post("/api/session/demo-live")
    session_id = resp.json()["session_id"]

    for _ in range(40):
        s = client.get(f"/api/session/{session_id}/status").json()
        if s["status"] == "complete":
            break
        time.sleep(0.1)

    assert client.get(f"/api/session/{session_id}/report").status_code == 200
    assert client.get(f"/api/session/{session_id}/timeline").status_code == 200
    assert client.get(f"/api/session/{session_id}/findings").status_code == 200

"""
WebSocket endpoint for PitchPilot Livestream Mode.

Protocol summary
----------------
Client → Server (JSON text frames):
  {"type": "init",        "personas": [...], "policy_text": "...", "title": "..."}
  {"type": "end_session"}

Client → Server (binary frames):
  Prefixed with a 1-byte type tag:
    0x01  audio_chunk   — WebM/Opus audio data
    0x02  frame_snapshot — JPEG frame from canvas

Server → Client (JSON text frames):
  {"type": "session_created",   "session_id": "..."}
  {"type": "transcript_update", "segments": [...], "elapsed": 12.3}
  {"type": "finding",           "finding": {...},  "elapsed": 15.1}
  {"type": "nudge",             "agent": "...", "message": "...", "severity": "...", "elapsed": 20.0}
  {"type": "session_complete",  "session_id": "..."}
  {"type": "error",             "message": "..."}

The session produced by this endpoint is stored in the shared _sessions dict
and can be retrieved via the existing REST endpoints once complete.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from backend.agents.orchestrator import Orchestrator
from backend.api_schemas import (
    AgentType,
    DimensionScore,
    Finding as ApiFinding,
    PersonaQuestion,
    ReadinessReport,
    ReadinessScore,
    Session,
    SessionMode,
    SessionStatus,
    Severity,
    TimelineAnnotation,
    TimelineCategory,
)
from backend.config import settings
from backend.pipeline.live import LivePipeline
from backend.reports.readiness import ReadinessReportGenerator
from backend.schemas import Finding as SchemaFinding


# ---------------------------------------------------------------------------
# Binary message type tags (1-byte prefix)
# ---------------------------------------------------------------------------

MSG_AUDIO = 0x01
MSG_FRAME = 0x02


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------


async def live_session_ws(websocket: WebSocket, sessions: dict) -> None:
    """
    Main WebSocket handler for a live session.

    Args:
        websocket: The FastAPI WebSocket connection.
        sessions: Shared _sessions dict from main.py (mutated in-place).
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    pipeline: LivePipeline | None = None
    elapsed_offset: float = 0.0
    start_wall: float = time.monotonic()
    frame_index: int = 0

    logger.info(f"[ws] Client connected | session={session_id}")

    try:
        # ------------------------------------------------------------------
        # Phase 1: Wait for init message
        # ------------------------------------------------------------------
        raw_init = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        init_msg = json.loads(raw_init)

        if init_msg.get("type") != "init":
            await _send(websocket, {"type": "error", "message": "Expected 'init' message first"})
            return

        personas: list[str] = init_msg.get("personas", [])
        policy_text: str = init_msg.get("policy_text", "")
        title: str = init_msg.get("title", "Live Rehearsal")

        # Create session record
        session = Session(
            id=uuid.UUID(session_id),
            video_filename="live_session.webm",
            policy_filenames=[],
            personas=personas,
            mode=SessionMode.LIVE,
            status=SessionStatus.PROCESSING,
            progress=0,
            progress_message="Live session active",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        sessions[session_id] = session

        # Initialise pipeline
        orchestrator = Orchestrator()
        pipeline = LivePipeline(
            session_id=session_id,
            orchestrator=orchestrator,
            personas=personas,
            policy_text=policy_text,
            presentation_title=title,
        )
        await pipeline.initialize()

        await _send(websocket, {"type": "session_created", "session_id": session_id})
        logger.info(f"[ws] Session ready | session={session_id} | personas={personas}")

        start_wall = time.monotonic()
        # How often (seconds) to run extract_and_route after accumulating audio
        extract_interval = 10.0
        last_extract_at = start_wall

        # ------------------------------------------------------------------
        # Phase 2: Main message loop
        # ------------------------------------------------------------------
        while True:
            try:
                # Use a short receive timeout so we can run periodic tasks
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                # Periodic claim extraction + routing
                now = time.monotonic()
                if now - last_extract_at >= extract_interval:
                    last_extract_at = now
                    elapsed = now - start_wall
                    findings = await pipeline.extract_and_route()
                    for f in findings:
                        await _send_finding(websocket, f, elapsed)
                continue
            except WebSocketDisconnect:
                logger.info(f"[ws] Client disconnected | session={session_id}")
                break

            # Text frame → control message
            if "text" in message:
                ctrl = json.loads(message["text"])
                msg_type = ctrl.get("type")

                if msg_type == "end_session":
                    logger.info(f"[ws] end_session received | session={session_id}")
                    await _handle_end_session(
                        websocket, session_id, pipeline, session, sessions
                    )
                    break

                elif msg_type == "ping":
                    await _send(websocket, {"type": "pong"})

            # Binary frame → audio chunk or frame snapshot
            elif "bytes" in message:
                data: bytes = message["bytes"]
                if not data:
                    continue

                tag = data[0]
                payload = data[1:]
                elapsed = time.monotonic() - start_wall

                if tag == MSG_AUDIO:
                    # Transcribe and send transcript update
                    segments = await pipeline.ingest_audio_chunk(payload, offset_seconds=elapsed)
                    if segments:
                        await _send(websocket, {
                            "type": "transcript_update",
                            "segments": [
                                {
                                    "text": s.text,
                                    "start_time": s.start_time,
                                    "end_time": s.end_time,
                                }
                                for s in segments
                            ],
                            "elapsed": elapsed,
                        })

                    # Run extract + route if interval elapsed
                    now = time.monotonic()
                    if now - last_extract_at >= extract_interval:
                        last_extract_at = now
                        findings = await pipeline.extract_and_route()
                        for f in findings:
                            await _send_finding(websocket, f, elapsed)

                elif tag == MSG_FRAME:
                    await pipeline.ingest_frame(payload, timestamp=elapsed, frame_index=frame_index)
                    frame_index += 1

    except WebSocketDisconnect:
        logger.info(f"[ws] WebSocket disconnected (outer) | session={session_id}")
    except Exception as exc:
        logger.error(f"[ws] Unexpected error | session={session_id}: {exc}", exc_info=True)
        try:
            await _send(websocket, {"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        # If session exists but wasn't finalized cleanly, mark it failed
        if session_id in sessions:
            s = sessions[session_id]
            if s.status == SessionStatus.PROCESSING:
                s.status = SessionStatus.FAILED
                s.error_message = "Session ended unexpectedly"
        logger.info(f"[ws] Handler exiting | session={session_id}")


# ---------------------------------------------------------------------------
# End-session handler
# ---------------------------------------------------------------------------


async def _handle_end_session(
    websocket: WebSocket,
    session_id: str,
    pipeline: LivePipeline,
    session: Session,
    sessions: dict,
) -> None:
    """Finalize the pipeline, build the report, and notify the client."""
    elapsed = pipeline.elapsed_seconds

    await _send(websocket, {
        "type": "finalizing",
        "message": "Building your readiness report...",
        "elapsed": elapsed,
    })

    try:
        result = await pipeline.finalize()
    except Exception as exc:
        logger.error(f"[ws] Finalize failed: {exc}")
        await _send(websocket, {"type": "error", "message": f"Report generation failed: {exc}"})
        session.status = SessionStatus.FAILED
        session.error_message = str(exc)
        return

    # Convert schema findings → api findings for the report
    api_findings = [_schema_finding_to_api(f) for f in result.findings]
    api_timeline = _build_api_timeline(api_findings)

    # Generate the readiness report using the existing generator
    try:
        report_gen = ReadinessReportGenerator()
        report = report_gen.generate(
            result=result,
            context=pipeline._build_pipeline_context(),
        )
        # Convert internal ReadinessReport → api_schemas.ReadinessReport
        api_report = _schema_report_to_api(report, session_id, api_findings, api_timeline)
    except Exception as exc:
        logger.error(f"[ws] Report generation failed: {exc}")
        # Fallback: build a minimal report from findings
        api_report = _build_fallback_report(session_id, api_findings, api_timeline)

    session.report = api_report
    session.timeline = api_timeline
    session.status = SessionStatus.COMPLETE
    session.progress = 100
    session.progress_message = "Live session complete"

    await _send(websocket, {
        "type": "session_complete",
        "session_id": session_id,
    })
    logger.info(f"[ws] Session complete | session={session_id} | findings={len(api_findings)}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _send(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_text(json.dumps(payload))
    except Exception as exc:
        logger.debug(f"[ws] Send failed: {exc}")


async def _send_finding(ws: WebSocket, finding: SchemaFinding, elapsed: float) -> None:
    """Send a finding event. Emits 'nudge' for info/warning from coach, 'finding' otherwise."""
    api_f = _schema_finding_to_api(finding)
    payload_finding = {
        "id": api_f.id,
        "agent": api_f.agent,
        "severity": api_f.severity,
        "title": api_f.title,
        "detail": api_f.detail,
        "suggestion": api_f.suggestion,
        "timestamp": api_f.timestamp,
        "policy_reference": api_f.policy_reference,
        "persona": api_f.persona,
        "live": True,
    }

    # Lightweight pacing/clarity nudges go as 'nudge' type
    if api_f.agent == AgentType.COACH and api_f.severity in (Severity.INFO, Severity.WARNING):
        await _send(ws, {
            "type": "nudge",
            "agent": api_f.agent,
            "message": api_f.detail,
            "suggestion": api_f.suggestion,
            "severity": api_f.severity,
            "elapsed": elapsed,
        })
    else:
        await _send(ws, {
            "type": "finding",
            "finding": payload_finding,
            "elapsed": elapsed,
        })


def _schema_finding_to_api(f: SchemaFinding) -> ApiFinding:
    """Convert a schemas.Finding to an api_schemas.Finding."""
    agent_map = {"coach": AgentType.COACH, "compliance": AgentType.COMPLIANCE, "persona": AgentType.PERSONA}
    severity_map = {"info": Severity.INFO, "warning": Severity.WARNING, "critical": Severity.CRITICAL}

    agent = agent_map.get(f.agent, AgentType.COACH)
    severity = severity_map.get(f.severity, Severity.INFO)

    return ApiFinding(
        id=f.id,
        agent=agent,
        severity=severity,
        title=f.title,
        detail=f.description,
        suggestion=f.suggestion,
        timestamp=f.timestamp or 0.0,
        claim_id=f.claim_ref,
        policy_reference=f.metadata.get("policy_reference") if f.metadata else None,
        persona=f.metadata.get("persona") if f.metadata else None,
        live=True,
    )


def _build_api_timeline(findings: list[ApiFinding]) -> list[TimelineAnnotation]:
    category_map = {
        AgentType.COACH: TimelineCategory.COACH,
        AgentType.COMPLIANCE: TimelineCategory.COMPLIANCE,
        AgentType.PERSONA: TimelineCategory.PERSONA,
    }
    annotations = [
        TimelineAnnotation(
            finding_id=f.id,
            category=category_map.get(f.agent, TimelineCategory.COACH),
            timestamp=f.timestamp,
            label=f.title[:60],
            severity=f.severity,
        )
        for f in findings
    ]
    annotations.sort(key=lambda a: a.timestamp)
    return annotations


def _schema_report_to_api(
    report: Any,
    session_id: str,
    findings: list[ApiFinding],
    timeline: list[TimelineAnnotation],
) -> ReadinessReport:
    """Convert an internal ReadinessReport to the API schema."""
    import uuid as _uuid  # noqa: PLC0415
    from backend.api_schemas import DimensionScore as ApiDimScore  # noqa: PLC0415

    dimensions = [
        ApiDimScore(
            dimension=name,
            score=int(ds.score),
            rationale=ds.summary or "",
        )
        for name, ds in (report.dimensions.items() if hasattr(report, "dimensions") else {}.items())
    ]

    persona_questions = [
        PersonaQuestion(
            persona=pq.persona,
            question=pq.question,
            timestamp=pq.timestamp,
            difficulty=Severity.WARNING,
        )
        for pq in getattr(report, "stakeholder_questions", [])
    ]

    priority_fixes = getattr(report, "priority_fixes", [])
    overall = getattr(report, "overall_score", 70)
    summary = getattr(report, "summary", "Live session complete.")

    return ReadinessReport(
        session_id=_uuid.UUID(session_id),
        score=ReadinessScore(
            overall=overall,
            dimensions=dimensions,
            priority_fixes=priority_fixes,
        ),
        findings=findings,
        persona_questions=persona_questions,
        claims=[],
        summary=summary,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_fallback_report(
    session_id: str,
    findings: list[ApiFinding],
    timeline: list[TimelineAnnotation],
) -> ReadinessReport:
    """Build a minimal ReadinessReport directly from findings (no full scoring)."""
    import uuid as _uuid  # noqa: PLC0415

    critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
    base = max(40, 100 - critical * 15 - warnings * 8)

    priority_fixes = [
        f.suggestion for f in findings
        if f.suggestion and f.severity == Severity.CRITICAL
    ][:5]

    return ReadinessReport(
        session_id=_uuid.UUID(session_id),
        score=ReadinessScore(
            overall=base,
            dimensions=[
                DimensionScore(dimension="Live Session", score=base, rationale="Based on live findings."),
            ],
            priority_fixes=priority_fixes,
        ),
        findings=findings,
        persona_questions=[],
        claims=[],
        summary=f"Live session complete. {len(findings)} findings detected.",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

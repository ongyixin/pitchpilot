"""
WebSocket endpoint for PitchPilot Live Modes.

Protocol summary
----------------
Client → Server (JSON text frames):
  {"type": "init",        "mode": "rehearsal|in_room|remote", "personas": [...], "policy_text": "...", "title": "..."}
  {"type": "end_session"}
  {"type": "ping"}

Client → Server (binary frames):
  Prefixed with a 1-byte type tag:
    0x01  audio_chunk     — WebM/Opus audio data (sent every ~2 s)
    0x02  frame_snapshot  — JPEG frame from canvas (sent every ~5 s)

Server → Client (JSON text frames):
  {"type": "session_created",    "session_id": "...", "mode": "..."}
  {"type": "transcript_update",  "segments": [...], "elapsed": 12.3}
  {"type": "finding",            "finding": {...}, "elapsed": 15.1}
  {"type": "nudge",              "agent": "...", "message": "...", "severity": "...", "elapsed": 20.0}
  {"type": "earpiece_cue",       "text": "slow down", "audio_b64": "...", "priority": "warning",
                                  "category": "coach", "elapsed": 22.0}       [in_room only]
  {"type": "overlay_card",       "agent": "...", "severity": "...", "title": "...", "detail": "...",
                                  "suggestion": "...", "cue_text": "...", "elapsed": 22.0}  [remote only]
  {"type": "teleprompter",       "points": ["...", "..."], "slide_context": "...", "elapsed": 25.0}  [remote only]
  {"type": "objection_prep",     "questions": [{"question": "...", "suggested_answer": "...",
                                  "persona": "...", "difficulty": "..."}], "elapsed": 40.0}  [remote only]
  {"type": "script_suggestion",  "original": "...", "alternative": "...", "reason": "...",
                                  "agent": "...", "elapsed": 30.0}             [remote only]
  {"type": "status",             "message": "...", "progress": 42}
  {"type": "finalizing",         "message": "...", "elapsed": 180.0}
  {"type": "session_complete",   "session_id": "..."}
  {"type": "error",              "message": "..."}

The session produced by this endpoint is stored in the shared _sessions dict
and can be retrieved via the existing REST endpoints once complete.

Mode-specific behaviour
-----------------------
rehearsal  — legacy / default.  Findings sent as "nudge" and "finding" messages.
             No cue synthesis, no teleprompter, no objection prep.

in_room    — After each extract_and_route() cycle findings are passed through
             CueSynthesizer.process_for_in_room().  Qualifying cues are
             synthesised to audio via TTSService and sent as "earpiece_cue".
             Rate-limited to 1 cue per CUE_MIN_INTERVAL seconds.

remote     — Findings sent as "overlay_card" messages (richer than nudge).
             CueSynthesizer.process_for_remote() produces "script_suggestion"
             messages for compliance/coach findings with rewording.
             Teleprompter points regenerated every TELEPROMPTER_UPDATE_INTERVAL
             seconds or on slide change.
             Objection prep regenerated on a slower cadence (~60 s).
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
    EarpieceCue,
    Finding as ApiFinding,
    PersonaQuestion,
    ReadinessReport,
    ReadinessScore,
    ScriptSuggestion,
    Session,
    SessionMode,
    SessionStatus,
    Severity,
    TimelineAnnotation,
    TimelineCategory,
)
from backend.config import (
    CUE_MIN_INTERVAL,
    LIVE_EXTRACT_INTERVAL,
    TELEPROMPTER_UPDATE_INTERVAL,
    settings,
)
from backend.pipeline.cue_synth import CueSynthesizer
from backend.pipeline.live import LivePipeline
from backend.reports.readiness import ReadinessReportGenerator
from backend.schemas import Finding as SchemaFinding
from backend.services.tts import TTSService


# ---------------------------------------------------------------------------
# Binary message type tags (1-byte prefix)
# ---------------------------------------------------------------------------

MSG_AUDIO = 0x01
MSG_FRAME = 0x02

# How often (seconds) to send objection prep updates in remote mode
_OBJECTION_PREP_INTERVAL = 60.0


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
        title: str = init_msg.get("title", "Live Session")
        raw_mode: str = init_msg.get("mode", "rehearsal")

        # Normalise mode string → SessionMode enum
        mode_map = {
            "in_room":    SessionMode.LIVE_IN_ROOM,
            "live_in_room": SessionMode.LIVE_IN_ROOM,
            "remote":     SessionMode.LIVE_REMOTE,
            "live_remote": SessionMode.LIVE_REMOTE,
            "rehearsal":  SessionMode.LIVE,
            "live":       SessionMode.LIVE,
        }
        session_mode: SessionMode = mode_map.get(raw_mode, SessionMode.LIVE)
        pipeline_mode = raw_mode if raw_mode in ("in_room", "remote") else "rehearsal"

        # Create session record
        session = Session(
            id=uuid.UUID(session_id),
            video_filename="live_session.webm",
            policy_filenames=[],
            personas=personas,
            mode=session_mode,
            status=SessionStatus.PROCESSING,
            progress=0,
            progress_message="Live session active",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        sessions[session_id] = session

        # Initialise live pipeline with mode
        orchestrator = Orchestrator()
        pipeline = LivePipeline(
            session_id=session_id,
            orchestrator=orchestrator,
            personas=personas,
            policy_text=policy_text,
            presentation_title=title,
            mode=pipeline_mode,
        )
        await pipeline.initialize()

        # Cue synthesis + TTS (shared across all live modes)
        synth = CueSynthesizer(mode=session_mode)
        tts = TTSService()

        await _send(websocket, {
            "type": "session_created",
            "session_id": session_id,
            "mode": session_mode.value,
        })
        logger.info(
            f"[ws] Session ready | session={session_id} | mode={session_mode} | personas={personas}"
        )

        start_wall = time.monotonic()

        # Live modes use a shorter extract interval (5 s vs 10 s)
        extract_interval = (
            LIVE_EXTRACT_INTERVAL
            if session_mode in (SessionMode.LIVE_IN_ROOM, SessionMode.LIVE_REMOTE)
            else 10.0
        )
        last_extract_at = start_wall
        last_teleprompter_at = start_wall
        last_objection_prep_at = start_wall

        # ------------------------------------------------------------------
        # Phase 2: Main message loop
        # ------------------------------------------------------------------
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                now = time.monotonic()
                elapsed = now - start_wall

                # Periodic claim extraction + routing
                if now - last_extract_at >= extract_interval:
                    last_extract_at = now
                    findings = await pipeline.extract_and_route()
                    for f in findings:
                        await _dispatch_finding(
                            websocket, f, elapsed, synth, tts, pipeline, session_mode
                        )

                # Remote-mode: periodic teleprompter updates
                if session_mode == SessionMode.LIVE_REMOTE:
                    slide_changed = pipeline.consume_slide_changed()
                    if (
                        slide_changed
                        or now - last_teleprompter_at >= TELEPROMPTER_UPDATE_INTERVAL
                    ):
                        last_teleprompter_at = now
                        await _send_teleprompter(websocket, pipeline, elapsed)

                    if now - last_objection_prep_at >= _OBJECTION_PREP_INTERVAL:
                        last_objection_prep_at = now
                        await _send_objection_prep(websocket, pipeline, elapsed)

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
                            await _dispatch_finding(
                                websocket, f, elapsed, synth, tts, pipeline, session_mode
                            )

                elif tag == MSG_FRAME:
                    await pipeline.ingest_frame(payload, timestamp=elapsed, frame_index=frame_index)
                    frame_index += 1

                    # Trigger teleprompter immediately on slide change (remote mode)
                    if session_mode == SessionMode.LIVE_REMOTE and pipeline.consume_slide_changed():
                        last_teleprompter_at = time.monotonic()
                        await _send_teleprompter(websocket, pipeline, elapsed)

    except WebSocketDisconnect:
        logger.info(f"[ws] WebSocket disconnected (outer) | session={session_id}")
    except Exception as exc:
        logger.error(f"[ws] Unexpected error | session={session_id}: {exc}", exc_info=True)
        try:
            await _send(websocket, {"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        if session_id in sessions:
            s = sessions[session_id]
            if s.status == SessionStatus.PROCESSING:
                s.status = SessionStatus.FAILED
                s.error_message = "Session ended unexpectedly"
        logger.info(f"[ws] Handler exiting | session={session_id}")


# ---------------------------------------------------------------------------
# Mode-aware finding dispatch
# ---------------------------------------------------------------------------


async def _dispatch_finding(
    websocket: WebSocket,
    finding: SchemaFinding,
    elapsed: float,
    synth: CueSynthesizer,
    tts: TTSService,
    pipeline: LivePipeline,
    mode: SessionMode,
) -> None:
    """
    Route a finding to the appropriate WS message type based on session mode.

    rehearsal  → nudge / finding (existing behaviour)
    in_room    → earpiece_cue  (rate-limited, TTS audio)
                 + finding (always — kept for post-session report)
    remote     → overlay_card + script_suggestion (if available)
                 + finding (always — kept for post-session report)
    """
    api_f = _schema_finding_to_api(finding)

    # Always persist the raw finding for post-session report
    await _send_finding_raw(websocket, api_f, elapsed)

    if mode == SessionMode.LIVE_IN_ROOM:
        cues = synth.process_for_in_room([api_f], elapsed)
        for cue in cues:
            audio_b64 = await tts.synthesize(cue.text)
            await _send(websocket, {
                "type": "earpiece_cue",
                "text": cue.text,
                "audio_b64": audio_b64,
                "priority": cue.priority,
                "category": cue.category,
                "elapsed": elapsed,
            })
            logger.info(f"[ws] earpiece_cue emitted | text='{cue.text}' | session={pipeline.session_id}")

    elif mode == SessionMode.LIVE_REMOTE:
        # Overlay card (richer than nudge — always shown in presenter panel)
        if api_f.severity in (Severity.WARNING, Severity.CRITICAL):
            cue_text = synth._compress_cue_for_remote(api_f)
            await _send(websocket, {
                "type": "overlay_card",
                "agent": api_f.agent,
                "severity": api_f.severity,
                "title": api_f.title,
                "detail": api_f.detail,
                "suggestion": api_f.suggestion,
                "cue_text": cue_text,
                "category": api_f.agent,
                "elapsed": elapsed,
            })

        # Script suggestion for compliance or clarity findings with rewording
        suggestions = synth.process_for_remote([api_f], elapsed)
        for s in suggestions:
            await _send(websocket, {
                "type": "script_suggestion",
                "original": s.original,
                "alternative": s.alternative,
                "reason": s.reason,
                "agent": s.agent,
                "elapsed": elapsed,
            })


# ---------------------------------------------------------------------------
# Teleprompter + objection prep dispatch (remote mode)
# ---------------------------------------------------------------------------


async def _send_teleprompter(
    websocket: WebSocket,
    pipeline: LivePipeline,
    elapsed: float,
) -> None:
    """Generate and send a teleprompter update for remote mode."""
    try:
        points = await pipeline.generate_teleprompter_points()
        if points:
            await _send(websocket, {
                "type": "teleprompter",
                "points": points,
                "slide_context": pipeline.current_slide_text()[:300],
                "elapsed": elapsed,
            })
            logger.debug(f"[ws] teleprompter sent | points={len(points)}")
    except Exception as exc:
        logger.warning(f"[ws] teleprompter dispatch failed: {exc}")


async def _send_objection_prep(
    websocket: WebSocket,
    pipeline: LivePipeline,
    elapsed: float,
) -> None:
    """Generate and send objection prep questions for remote mode."""
    try:
        questions = await pipeline.generate_objection_prep()
        if questions:
            await _send(websocket, {
                "type": "objection_prep",
                "questions": questions,
                "elapsed": elapsed,
            })
            logger.debug(f"[ws] objection_prep sent | questions={len(questions)}")
    except Exception as exc:
        logger.warning(f"[ws] objection_prep dispatch failed: {exc}")


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

    api_findings = [_schema_finding_to_api(f) for f in result.findings]
    api_timeline = _build_api_timeline(api_findings)

    try:
        report_gen = ReadinessReportGenerator()
        report = report_gen.generate(
            result=result,
            context=pipeline._build_pipeline_context(),
        )
        api_report = _schema_report_to_api(report, session_id, api_findings, api_timeline)
    except Exception as exc:
        logger.error(f"[ws] Report generation failed: {exc}")
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


async def _send_finding_raw(ws: WebSocket, api_f: ApiFinding, elapsed: float) -> None:
    """
    Send a finding as 'nudge' (coach info/warning) or 'finding' (everything else).
    This is the baseline message sent regardless of mode — always persisted.
    """
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
        payload = {
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
            "cue_hint": api_f.cue_hint,
        }
        await _send(ws, {"type": "finding", "finding": payload, "elapsed": elapsed})


def _schema_finding_to_api(f: SchemaFinding) -> ApiFinding:
    """Convert a schemas.Finding to an api_schemas.Finding."""
    agent_map = {
        "coach": AgentType.COACH,
        "compliance": AgentType.COMPLIANCE,
        "persona": AgentType.PERSONA,
    }
    severity_map = {
        "info": Severity.INFO,
        "warning": Severity.WARNING,
        "critical": Severity.CRITICAL,
    }

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
        cue_hint=f.metadata.get("cue_hint") if f.metadata else None,
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
                DimensionScore(
                    dimension="Live Session",
                    score=base,
                    rationale="Based on live findings.",
                ),
            ],
            priority_fixes=priority_fixes,
        ),
        findings=findings,
        persona_questions=[],
        claims=[],
        summary=f"Live session complete. {len(findings)} findings detected.",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

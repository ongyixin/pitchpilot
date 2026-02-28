#!/usr/bin/env python3
"""
PitchPilot Benchmark Script
============================

Runs a full ingestion + agent analysis pipeline on a sample video and prints
a structured timing report.  Useful for measuring before/after impact of
performance changes.

Usage::

    # Basic run (mock mode, no real models needed)
    python scripts/benchmark_session.py

    # Real model run with a local video
    PITCHPILOT_MOCK_MODE=false \\
    python scripts/benchmark_session.py \\
        --video /path/to/rehearsal.mp4 \\
        --policy /path/to/policy.pdf \\
        --runs 3

    # Fast mode (reduced accuracy, lower latency)
    PITCHPILOT_MOCK_MODE=false PITCHPILOT_FAST_MODE=true \\
    python scripts/benchmark_session.py --video /path/to/rehearsal.mp4

Options
-------
--video PATH       Path to rehearsal video (mp4/mov/webm).
                   Defaults to data/fixtures/sample_video.mp4 if it exists,
                   otherwise creates a 5-second synthetic test video.
--policy PATH      Path to optional policy document. Can be repeated.
--runs N           Number of repetitions (default: 1). Reports mean ± std.
--no-cleanup       Keep session artifacts after run.
--json             Dump full SessionMetrics as JSON to stdout.
--out PATH         Write JSON metrics to a file instead of stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

# Ensure the project root is on sys.path so backend imports work when run
# directly (e.g. python scripts/benchmark_session.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_synthetic_video(output_path: Path, duration_s: int = 5) -> None:
    """
    Create a minimal synthetic test video using ffmpeg (solid color + silence).

    This is used when no real video is provided so the benchmark can run
    without any test assets.
    """
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg is required for synthetic video creation.\n"
            "Install: brew install ffmpeg"
        )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=blue:size=1280x720:rate=30:duration={duration_s}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_s}",
        "-c:v", "libx264", "-c:a", "aac",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-300:]}")
    print(f"  [benchmark] Created synthetic test video: {output_path}")


def _resolve_video(video_arg: str | None) -> str:
    """Resolve the video path, creating a synthetic one if none supplied."""
    if video_arg:
        p = Path(video_arg)
        if not p.exists():
            raise FileNotFoundError(f"Video not found: {video_arg}")
        return str(p)

    # Try sample fixture
    fixture = _PROJECT_ROOT / "data" / "fixtures" / "sample_video.mp4"
    if fixture.exists():
        print(f"  [benchmark] Using fixture: {fixture}")
        return str(fixture)

    # Generate synthetic video in a temp dir
    tmp = Path(tempfile.mkdtemp()) / "benchmark_video.mp4"
    print("  [benchmark] No video provided; generating 5s synthetic test video...")
    _create_synthetic_video(tmp, duration_s=5)
    return str(tmp)


# ---------------------------------------------------------------------------
# Single benchmark run
# ---------------------------------------------------------------------------


async def _run_once(video_path: str, policy_paths: list[str]) -> dict:
    """
    Execute one full pipeline run and return timing + memory stats.

    Returns a dict with keys:
        total_s, peak_mem_mb, stage_timings, llm_calls, claims, findings
    """
    from backend.agents.orchestrator import Orchestrator
    from backend.config import SESSIONS_DIR, settings
    from backend.ingestion import IngestionPipeline
    from backend.metrics import SessionMetrics
    from backend.reports.readiness import ReadinessReportGenerator
    from backend.schemas import PipelineContext

    tracemalloc.start()
    t0 = time.perf_counter()

    pipeline = IngestionPipeline()
    ingestion_result = await pipeline.run(
        video_path=video_path,
        policy_doc_paths=policy_paths,
    )

    orchestrator = Orchestrator()
    await orchestrator.initialize()

    session_id = ingestion_result.session_id
    context = PipelineContext(
        session_id=session_id,
        claims=ingestion_result.claims,
        transcript_segments=ingestion_result.transcript_segments,
        slide_ocr=ingestion_result.ocr_blocks,
        policy_text="\n".join(
            b.text for b in ingestion_result.ocr_blocks
            if b.source_type.value != "video_frame"
        ),
        personas=["Skeptical Investor", "Technical Reviewer"],
        full_transcript=" ".join(s.text for s in ingestion_result.transcript_segments),
    )
    orch_result = await orchestrator.run(context)

    report_gen = ReadinessReportGenerator()
    report = report_gen.generate(
        session_id=session_id,
        orchestrator_result=orch_result,
        ingestion_result=ingestion_result,
    )

    total_s = time.perf_counter() - t0
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Load metrics from disk if saved
    metrics_path = SESSIONS_DIR / session_id / "session_metrics.json"
    stage_timings: dict = {}
    llm_calls = 0
    if metrics_path.exists():
        m = json.loads(metrics_path.read_text())
        stage_timings = {s["stage"]: s["duration_s"] for s in m.get("stages", [])}
        llm_calls = m.get("llm_call_count", 0)

    return {
        "total_s": round(total_s, 2),
        "peak_mem_mb": round(peak_mem / 1024 / 1024, 1),
        "stage_timings": stage_timings,
        "llm_calls": llm_calls,
        "claims": len(ingestion_result.claims),
        "findings": len(orch_result.findings),
        "keyframes": sum(1 for f in ingestion_result.frames if f.is_keyframe),
        "ocr_blocks": len(ingestion_result.ocr_blocks),
        "transcript_segments": len(ingestion_result.transcript_segments),
        "session_id": session_id,
    }


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------


def _print_run(run: dict, run_num: int) -> None:
    print(f"\n  Run #{run_num}  total={run['total_s']:.2f}s  "
          f"peak_mem={run['peak_mem_mb']:.1f} MB  "
          f"claims={run['claims']}  findings={run['findings']}")
    for stage, dur in run["stage_timings"].items():
        print(f"    {stage:<32} {dur:>7.2f}s")


def _print_summary(runs: list[dict]) -> None:
    totals = [r["total_s"] for r in runs]
    mems = [r["peak_mem_mb"] for r in runs]
    sep = "═" * 60
    print(f"\n{sep}")
    print("  PitchPilot Benchmark Summary")
    print(sep)
    if len(runs) > 1:
        print(f"  Runs:           {len(runs)}")
        print(f"  Total time:     mean={statistics.mean(totals):.2f}s  "
              f"min={min(totals):.2f}s  max={max(totals):.2f}s  "
              f"stdev={statistics.stdev(totals):.2f}s")
        print(f"  Peak memory:    mean={statistics.mean(mems):.1f} MB  "
              f"max={max(mems):.1f} MB")
    else:
        print(f"  Total time:     {totals[0]:.2f}s")
        print(f"  Peak memory:    {mems[0]:.1f} MB")
    print(f"  Claims:         {runs[0]['claims']}")
    print(f"  Findings:       {runs[0]['findings']}")
    print(f"  Keyframes:      {runs[0]['keyframes']}")
    print(f"  OCR blocks:     {runs[0]['ocr_blocks']}")
    print(f"  LLM calls:      {runs[0]['llm_calls']}")

    # Stage breakdown (first run)
    if runs[0]["stage_timings"]:
        print("\n  Stage breakdown (run #1):")
        for stage, dur in sorted(
            runs[0]["stage_timings"].items(), key=lambda x: -x[1]
        ):
            pct = dur / totals[0] * 100
            bar = "█" * int(pct / 5)
            print(f"    {stage:<30} {dur:>6.2f}s  {pct:>5.1f}%  {bar}")

    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Benchmark a full PitchPilot pipeline run",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--video", metavar="PATH", help="Path to rehearsal video")
    p.add_argument("--policy", metavar="PATH", action="append", default=[],
                   help="Policy document path (repeat for multiple)")
    p.add_argument("--runs", type=int, default=1, metavar="N",
                   help="Number of benchmark repetitions (default: 1)")
    p.add_argument("--no-cleanup", action="store_true",
                   help="Keep session artifacts after run")
    p.add_argument("--json", action="store_true",
                   help="Dump full run stats as JSON to stdout")
    p.add_argument("--out", metavar="PATH",
                   help="Write JSON stats to file instead of stdout")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()

    # Apply --no-cleanup flag
    if args.no_cleanup:
        os.environ["PITCHPILOT_RETAIN_ARTIFACTS"] = "true"

    print("\nPitchPilot Benchmark")
    print("─" * 40)

    # Print active settings
    from backend.config import settings
    print(f"  mock_mode:        {settings.mock_mode}")
    print(f"  fast_mode:        {settings.fast_mode}")
    print(f"  extraction_fps:   {settings.extraction_fps}")
    print(f"  ocr_concurrency:  {settings.ocr_concurrency}")
    print(f"  agent_concurrency:{settings.agent_concurrency}")
    print(f"  frame_max_dim:    {settings.frame_max_dimension}")
    print(f"  retain_artifacts: {settings.retain_artifacts}")

    video_path = _resolve_video(args.video)
    policy_paths = args.policy
    print(f"\n  Video:   {video_path}")
    print(f"  Policies:{policy_paths or '(none)'}")
    print(f"  Runs:    {args.runs}\n")

    all_runs: list[dict] = []
    for i in range(1, args.runs + 1):
        print(f"  Starting run {i}/{args.runs}...")
        run_data = await _run_once(video_path, policy_paths)
        all_runs.append(run_data)
        _print_run(run_data, i)

    _print_summary(all_runs)

    if args.json or args.out:
        output = json.dumps(all_runs, indent=2)
        if args.out:
            Path(args.out).write_text(output, encoding="utf-8")
            print(f"\n  Metrics written to {args.out}")
        else:
            print("\n--- JSON ---")
            print(output)


if __name__ == "__main__":
    asyncio.run(main())

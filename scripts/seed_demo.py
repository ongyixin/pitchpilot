#!/usr/bin/env python3
"""
Seed a demo session into the PitchPilot demo server.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --base-url http://localhost:8000
    python scripts/seed_demo.py --delay 0        # instant (no stage animation)
    python scripts/seed_demo.py --poll            # poll until complete and print report

This script:
1. Posts to /api/session/demo to create a pre-seeded session
2. Prints the session ID
3. Optionally polls /status until complete
4. Optionally prints the final readiness report as JSON

Requires: pip install httpx (already in requirements.txt)
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx", file=sys.stderr)
    sys.exit(1)


def seed_demo(
    base_url: str = "http://localhost:8000",
    delay: int | None = None,
    poll: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Create a demo session and optionally wait for it to complete.

    Returns the full report as a dict, or just the start response if poll=False.
    """
    params = {}
    if delay is not None:
        # The demo server reads PITCHPILOT_DEMO_DELAY env var, not a query param.
        # This is just for documentation — set env var before launching server.
        pass

    with httpx.Client(base_url=base_url, timeout=120) as client:
        # ----------------------------------------------------------------
        # 1. Create demo session
        # ----------------------------------------------------------------
        if verbose:
            print(f"→ POST {base_url}/api/session/demo")

        resp = client.post(
            "/api/session/demo",
            params={"personas": "Skeptical Investor,Technical Reviewer,Compliance Officer"},
        )
        resp.raise_for_status()
        start = resp.json()
        session_id = start["session_id"]

        if verbose:
            print(f"✓ Session created: {session_id}")
            print(f"  Status: {start['status']}")
            print(f"  Message: {start['message']}")

        if not poll:
            return start

        # ----------------------------------------------------------------
        # 2. Poll until complete
        # ----------------------------------------------------------------
        if verbose:
            print("\n→ Polling for completion...")

        prev_message = ""
        while True:
            time.sleep(1.0)
            status_resp = client.get(f"/api/session/{session_id}/status")
            status_resp.raise_for_status()
            status = status_resp.json()

            msg = status.get("progress_message", "")
            pct = status.get("progress", 0)

            if msg != prev_message and verbose:
                print(f"  [{pct:3d}%] {msg}")
                prev_message = msg

            if status["status"] == "complete":
                break
            if status["status"] == "failed":
                print(f"✗ Session failed: {status.get('error_message')}", file=sys.stderr)
                sys.exit(1)

        if verbose:
            print("\n✓ Analysis complete!")

        # ----------------------------------------------------------------
        # 3. Fetch report
        # ----------------------------------------------------------------
        report_resp = client.get(f"/api/session/{session_id}/report")
        report_resp.raise_for_status()
        report = report_resp.json()

        overall = report["score"]["overall"]
        n_findings = len(report.get("findings", []))
        n_critical = sum(1 for f in report.get("findings", []) if f["severity"] == "critical")

        if verbose:
            print(f"\n{'─' * 50}")
            print(f"  Readiness Score : {overall}/100")
            print(f"  Findings        : {n_findings} ({n_critical} critical)")
            print(f"  Session ID      : {session_id}")
            print(f"  Results URL     : {base_url.rstrip('/')}/api/session/{session_id}/report")
            print(f"{'─' * 50}")

        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a PitchPilot demo session")
    parser.add_argument(
        "--base-url", default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--delay", type=int, default=None,
        help="Pipeline stage delay in seconds (set PITCHPILOT_DEMO_DELAY env var on server)"
    )
    parser.add_argument(
        "--poll", action="store_true", default=False,
        help="Wait until analysis completes and print the full report"
    )
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Print the full report as JSON to stdout"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", default=False,
        help="Suppress progress output"
    )
    args = parser.parse_args()

    result = seed_demo(
        base_url=args.base_url,
        delay=args.delay,
        poll=args.poll or args.json,
        verbose=not args.quiet,
    )

    if args.json:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

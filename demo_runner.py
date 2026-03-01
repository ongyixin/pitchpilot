#!/usr/bin/env python3
"""
PitchPilot Demo Runner.

Runs the full multi-agent pipeline in mock mode (no Ollama required)
and writes sample structured outputs to sample_outputs/.

Usage:
    python demo_runner.py            # mock mode (default)
    PITCHPILOT_MOCK=false python demo_runner.py   # live Ollama mode

Output files:
    sample_outputs/router_output.json
    sample_outputs/coach_findings.json
    sample_outputs/compliance_findings.json
    sample_outputs/persona_findings.json
    sample_outputs/orchestrator_result.json
    sample_outputs/readiness_report.json
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure imports work from repo root
sys.path.insert(0, str(Path(__file__).parent))

# Default to mock mode for the demo runner
if "PITCHPILOT_MOCK" not in os.environ:
    os.environ["PITCHPILOT_MOCK"] = "true"

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from backend.agents.coach import CoachAgent
from backend.agents.compliance import ComplianceAgent
from backend.agents.orchestrator import Orchestrator
from backend.agents.persona import PersonaAgent
from backend.config import DATA_DIR, SAMPLE_OUTPUTS_DIR
from backend.models.function_gemma import FunctionGemmaRouter
from backend.models.gemma3 import get_gemma3_adapter
from backend.models.gemma3n import get_gemma3n_adapter
from backend.reports.readiness import ReadinessReportGenerator
from backend.schemas import (
    Claim,
    PipelineContext,
    SlideOCR,
    TranscriptSegment,
)

console = Console()

SAMPLE_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Sample pitch context (simulates what the upstream pipeline provides)
# ---------------------------------------------------------------------------

SAMPLE_TRANSCRIPT_SEGMENTS = [
    TranscriptSegment("Good morning. Today I want to show you PitchPilot.", 0.0, 8.0),
    TranscriptSegment(
        "Teams spend hours preparing presentations but still walk into meetings underprepared.",
        8.0,
        18.0,
    ),
    TranscriptSegment(
        "Our platform is fully automated — no manual steps required. You record, we analyze.",
        40.0,
        52.0,
    ),
    TranscriptSegment(
        "All data is processed entirely on-device. Nothing ever leaves the user's machine.",
        72.0,
        85.0,
    ),
    TranscriptSegment(
        "We achieve 10x faster processing than traditional rule-based systems.",
        105.0,
        115.0,
    ),
    TranscriptSegment(
        "Our AI model runs inference in under 100 milliseconds on any modern laptop.",
        140.0,
        152.0,
    ),
    TranscriptSegment(
        "PitchPilot is GDPR-compliant out of the box and integrates in under five minutes.",
        158.0,
        170.0,
    ),
    TranscriptSegment(
        "Unlike ChatGPT or Copilot, we run entirely offline. That's the key differentiator.",
        220.0,
        232.0,
    ),
    TranscriptSegment(
        "Our accuracy rate is 99% across all supported languages.",
        188.0,
        196.0,
    ),
]

SAMPLE_SLIDE_OCR = [
    SlideOCR(
        slide_index=0,
        timestamp=0.0,
        raw_text="PitchPilot\nOn-Device Demo Readiness Copilot",
        title="PitchPilot",
        bullet_points=["On-Device Demo Readiness Copilot"],
    ),
    SlideOCR(
        slide_index=1,
        timestamp=30.0,
        raw_text="The Problem\n67% of sales pitches fail due to poor preparation\nTeams rehearse in isolation\nCompliance issues surface AFTER the meeting",
        title="The Problem",
        bullet_points=[
            "67% of sales pitches fail",
            "Teams rehearse in isolation",
            "Compliance issues surface AFTER the meeting",
        ],
    ),
    SlideOCR(
        slide_index=2,
        timestamp=90.0,
        raw_text="Security & Privacy\nGDPR-Compliant\n100% On-Device\nZero Data Retention\nSOC 2 Ready",
        title="Security & Privacy",
        bullet_points=["GDPR-Compliant", "100% On-Device", "Zero Data Retention", "SOC 2 Ready"],
    ),
]

SAMPLE_CLAIMS = [
    Claim(
        text="Our platform is fully automated — no manual steps required.",
        claim_type="compliance_sensitive",
        timestamp=45.0,
        source="transcript",
        context_before="This saves your team hours every week.",
        context_after="We handle everything end-to-end.",
    ),
    Claim(
        text="All data is processed entirely on-device — nothing ever leaves the user's machine.",
        claim_type="compliance_sensitive",
        timestamp=78.0,
        source="transcript",
        context_before="And because security matters,",
        context_after="so you never have to worry about data privacy.",
    ),
    Claim(
        text="We achieve 10x faster processing than traditional rule-based systems.",
        claim_type="comparison",
        timestamp=112.0,
        source="transcript",
        context_before="Compared to existing solutions,",
        context_after="validated across 50 enterprise customers.",
    ),
    Claim(
        text="Our AI model runs inference in under 100 milliseconds on any modern laptop.",
        claim_type="technical",
        timestamp=145.0,
        source="transcript",
        context_before="The latency story is important for live use cases.",
        context_after="This makes real-time coaching possible.",
    ),
    Claim(
        text="PitchPilot is GDPR-compliant out of the box.",
        claim_type="compliance_sensitive",
        timestamp=160.0,
        source="ocr",
        context_before="Security slide header",
        context_after="No configuration needed.",
    ),
    Claim(
        text="Our accuracy rate is 99% across all supported languages.",
        claim_type="product",
        timestamp=190.0,
        source="transcript",
        context_before="The quality of the output is industry-leading.",
        context_after="We're proud of this benchmark.",
    ),
    Claim(
        text="Unlike ChatGPT or Copilot, we run entirely offline.",
        claim_type="comparison",
        timestamp=225.0,
        source="transcript",
        context_before="Our privacy story is unique.",
        context_after="This is the key differentiator.",
    ),
]

POLICY_TEXT = (DATA_DIR / "sample_policies" / "sales_compliance_policy.txt").read_text()


def build_context() -> PipelineContext:
    return PipelineContext(
        session_id="demo-001",
        transcript_segments=SAMPLE_TRANSCRIPT_SEGMENTS,
        slide_ocr=SAMPLE_SLIDE_OCR,
        claims=SAMPLE_CLAIMS,
        policy_text=POLICY_TEXT,
        presentation_title="PitchPilot — Demo Rehearsal",
        personas=["Skeptical Investor", "Technical Reviewer", "Procurement Manager"],
        total_duration=250.0,
    )


# ---------------------------------------------------------------------------
# Demo sections
# ---------------------------------------------------------------------------


async def demo_router(claims: list[Claim]) -> None:
    console.rule("[bold cyan]1. FunctionGemma Router")
    router = FunctionGemmaRouter()
    router.initialize()

    router_results = []
    for claim in claims[:4]:  # show first 4
        ro = router.route(claim)
        fn_names = [tc.function_name for tc in ro.tool_calls]
        rprint(
            f"  [dim]{claim.text[:60]}...[/dim]\n"
            f"    → [green]{', '.join(fn_names)}[/green]\n"
        )
        router_results.append(ro)

    # Save router output
    _save_json(
        "router_output.json",
        [
            {
                "claim_id": ro.claim_id,
                "tool_calls": [
                    {"function": tc.function_name, "args": tc.args, "confidence": tc.confidence}
                    for tc in ro.tool_calls
                ],
                "routing_mode": ro.raw_output,
            }
            for ro in router_results
        ],
    )


async def demo_coach(context: PipelineContext) -> None:
    console.rule("[bold yellow]2. Presentation Coach Agent")
    client = get_gemma3_adapter()
    agent = CoachAgent(client=client)

    findings = await agent.analyze(context)
    table = Table(show_header=True, header_style="bold yellow")
    table.add_column("Severity", width=10)
    table.add_column("Category", width=16)
    table.add_column("Finding", width=60)

    severity_colors = {"critical": "red", "warning": "yellow", "info": "green"}
    for f in findings:
        color = severity_colors.get(f.severity, "white")
        table.add_row(
            f"[{color}]{f.severity}[/{color}]",
            f.category,
            f.title,
        )
    console.print(table)

    _save_json("coach_findings.json", [f.to_dict() for f in findings])


async def demo_compliance(context: PipelineContext) -> None:
    console.rule("[bold red]3. Compliance Reviewer Agent")
    client = get_gemma3_adapter()
    agent = ComplianceAgent(client=client)

    findings = await agent.analyze(context)
    for f in findings:
        color = {"critical": "red", "warning": "yellow", "info": "green"}.get(f.severity, "white")
        console.print(
            Panel(
                f"[bold]{f.title}[/bold]\n\n"
                f"{f.description}\n\n"
                f"[dim]Suggestion:[/dim] {f.suggestion or 'N/A'}",
                title=f"[{color}]{f.severity.upper()}[/{color}] — {f.category}",
                border_style=color,
            )
        )

    _save_json("compliance_findings.json", [f.to_dict() for f in findings])


async def demo_persona(context: PipelineContext) -> None:
    console.rule("[bold purple]4. Audience Persona Simulator")
    client = get_gemma3_adapter()
    agent = PersonaAgent(client=client)

    findings = await agent.analyze(context)

    current_persona = None
    for f in findings:
        persona = f.metadata.get("persona", "")
        if persona != current_persona:
            current_persona = persona
            console.print(f"\n  [bold purple]── {persona} ──[/bold purple]")
        difficulty = f.metadata.get("difficulty", "medium")
        diff_color = {"hard": "red", "medium": "yellow", "easy": "green"}.get(difficulty, "white")
        console.print(f"  [{diff_color}][{difficulty}][/{diff_color}] {f.description}")

    _save_json("persona_findings.json", [f.to_dict() for f in findings])


async def demo_orchestrator(context: PipelineContext) -> None:
    console.rule("[bold blue]5. Full Orchestrator Pass")
    orchestrator = Orchestrator()
    await orchestrator.initialize()

    result = await orchestrator.run(context)

    console.print(f"  Claims processed: [bold]{result.claims_processed}[/bold]")
    console.print(f"  Total findings:   [bold]{len(result.findings)}[/bold]")
    console.print(f"  Timeline markers: [bold]{len(result.timeline)}[/bold]")
    console.print(f"  Agents run:       [bold]{', '.join(result.agents_run)}[/bold]")

    console.print("\n  [dim]Timeline (first 5 annotations):[/dim]")
    for ann in result.timeline[:5]:
        color_map = {"red": "red", "yellow": "yellow", "blue": "blue", "purple": "purple"}
        c = color_map.get(ann.color, "white")
        console.print(
            f"    [{c}]●[/{c}] {ann.timestamp:.0f}s  [{ann.category}]  {ann.label}"
        )

    _save_json(
        "orchestrator_result.json",
        {
            "session_id": result.session_id,
            "claims_processed": result.claims_processed,
            "agents_run": result.agents_run,
            "findings": [f.to_dict() for f in result.findings],
            "timeline": [a.to_dict() for a in result.timeline],
            "errors": result.errors,
        },
    )

    return result


async def demo_report(result, context: PipelineContext) -> None:
    console.rule("[bold green]6. Readiness Report")
    generator = ReadinessReportGenerator()
    report = generator.generate(result, context)

    # Score panel
    score_color = "green" if report.overall_score >= 75 else "yellow" if report.overall_score >= 55 else "red"
    console.print(
        Panel(
            f"[bold {score_color}]{report.overall_score}/100  Grade: {report.grade}[/bold {score_color}]\n\n"
            f"{report.summary}",
            title="Readiness Score",
            border_style=score_color,
        )
    )

    # Dimension table
    dim_table = Table(show_header=True, header_style="bold")
    dim_table.add_column("Dimension", width=16)
    dim_table.add_column("Score", width=8)
    dim_table.add_column("Issues", width=8)
    dim_table.add_column("Summary", width=50)

    for dim_name, dim in report.dimensions.items():
        c = "green" if dim.score >= 80 else "yellow" if dim.score >= 60 else "red"
        dim_table.add_row(
            dim_name,
            f"[{c}]{dim.score}[/{c}]",
            str(dim.issues_count),
            dim.summary,
        )
    console.print(dim_table)

    # Priority fixes
    console.print("\n[bold]Priority Fixes:[/bold]")
    for i, fix in enumerate(report.priority_fixes[:5], 1):
        console.print(f"  {i}. {fix}")

    # Top stakeholder questions
    console.print("\n[bold]Top Stakeholder Questions to Prepare For:[/bold]")
    for q in report.stakeholder_questions[:5]:
        diff_color = {"hard": "red", "medium": "yellow", "easy": "green"}.get(q.difficulty, "white")
        console.print(f"  [{diff_color}]{q.persona}[/{diff_color}]: {q.question}")

    _save_json("readiness_report.json", report.to_dict())
    console.print(f"\n  [dim]Full report saved to sample_outputs/readiness_report.json[/dim]")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _save_json(filename: str, data) -> None:
    path = SAMPLE_OUTPUTS_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    mock_mode = os.environ.get("PITCHPILOT_MOCK", "true").lower() == "true"

    console.print(
        Panel(
            "[bold]PitchPilot — Multi-Agent Reasoning Demo[/bold]\n\n"
            f"Mode: {'[yellow]MOCK (no Ollama required)[/yellow]' if mock_mode else '[green]LIVE (Ollama)[/green]'}\n"
            "Agents: Presentation Coach · Compliance Reviewer · Audience Persona Simulator\n"
            "Router: FunctionGemma (rule-based)",
            title="PitchPilot",
            border_style="blue",
        )
    )

    context = build_context()

    await demo_router(context.claims)
    await demo_coach(context)
    await demo_compliance(context)
    await demo_persona(context)
    result = await demo_orchestrator(context)
    await demo_report(result, context)

    console.print(
        Panel(
            "[bold green]Demo complete.[/bold green]\n\n"
            f"Sample outputs written to: [dim]{SAMPLE_OUTPUTS_DIR}[/dim]\n\n"
            "Files:\n"
            "  • router_output.json         — FunctionGemma routing decisions\n"
            "  • coach_findings.json        — Presentation Coach findings\n"
            "  • compliance_findings.json   — Compliance Reviewer findings\n"
            "  • persona_findings.json      — Persona Simulator questions\n"
            "  • orchestrator_result.json   — Full orchestrator pass\n"
            "  • readiness_report.json      — Final readiness report\n\n"
            "To run with live Ollama:\n"
            "  [dim]ollama run gemma3:4b && PITCHPILOT_MOCK=false python demo_runner.py[/dim]",
            title="Done",
            border_style="green",
        )
    )


if __name__ == "__main__":
    asyncio.run(main())

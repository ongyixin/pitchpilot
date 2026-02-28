"""
Generate FunctionGemma fine-tuning dataset.

Produces ~100 examples mapping natural-language pitch intents to
PitchPilot tool function calls, saved to dataset.jsonl.

Run:
    python fine_tuning/function_gemma/generate_dataset.py

Output:
    fine_tuning/function_gemma/dataset.jsonl
"""

from __future__ import annotations

import json
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# Template bank
# ---------------------------------------------------------------------------

CLAIM_TEMPLATES = {
    "check_compliance": [
        ("The presenter claimed their product is \"{claim}\" but the policy says {policy}.",
         {"claim": "{claim}", "policy_context": "{policy}"}),
        ("Our docs require {policy} but the pitch says {claim}.",
         {"claim": "{claim}", "policy_context": "{policy}"}),
        ("Is it accurate to say {claim} given that {policy}?",
         {"claim": "{claim}", "policy_context": "{policy}"}),
    ],
    "coach_presentation": [
        ("The presenter rushed through the {section} section without explaining {gap}.",
         {"section_text": "{section}", "slide_context": "{gap}"}),
        ("The transition between {from_section} and {to_section} was abrupt.",
         {"section_text": "{from_section} to {to_section}", "slide_context": "transition"}),
        ("The opening hook mentioned {hook} — evaluate its effectiveness.",
         {"section_text": "{hook}", "slide_context": "introduction"}),
    ],
    "simulate_persona": [
        ("Simulate a {persona} listening to this claim: {claim}.",
         {"persona": "{persona}", "claim_context": "{claim}"}),
        ("What would a {persona} ask after hearing \"{claim}\"?",
         {"persona": "{persona}", "claim_context": "{claim}"}),
    ],
    "score_readiness": [
        ("All agents have finished. Aggregate findings and produce a readiness score.",
         {"findings": "all_agent_findings"}),
        ("We have {n} findings from coach, {m} from compliance. Score the overall readiness.",
         {"findings": "aggregated_findings"}),
    ],
    "tag_timestamp": [
        ("Mark timestamp {ts}s as a {category} issue: {note}.",
         {"timestamp": "{ts}", "category": "{category}", "note": "{note}"}),
    ],
}

CLAIM_FILLS = [
    ("fully automated", "manual review required for edge cases"),
    ("99.9% uptime", "standard SLA is 99.5%"),
    ("no data leaves the device", "optional cloud sync is enabled by default"),
    ("3× faster than the competition", "no benchmark has been cited"),
    ("enterprise-grade security", "SOC 2 audit is still pending"),
    ("GDPR compliant", "data retention policy has not been defined"),
    ("real-time processing", "latency is under 500ms only on high-end hardware"),
]

PERSONA_FILLS = [
    "Skeptical Investor",
    "Technical Reviewer",
    "Compliance Officer",
    "Sales Director",
    "Enterprise IT Buyer",
]

SECTION_FILLS = [
    ("problem statement", "the root cause"),
    ("demo", "the business impact"),
    ("pricing", "the ROI calculation"),
    ("architecture", "the data flow"),
]

# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

CONTROL_TOKENS = {
    "fn_start": "<start_function_call>",
    "fn_end": "<end_function_call>",
    "turn_start": "<start_of_turn>",
    "turn_end": "<end_of_turn>",
}


def _format_example(user_text: str, function_name: str, args: dict) -> dict:
    args_json = json.dumps(args)
    model_turn = (
        f"{CONTROL_TOKENS['fn_start']}{function_name}{args_json}{CONTROL_TOKENS['fn_end']}"
    )
    return {
        "text": (
            f"{CONTROL_TOKENS['turn_start']}user\n{user_text}\n{CONTROL_TOKENS['turn_end']}\n"
            f"{CONTROL_TOKENS['turn_start']}model\n{model_turn}\n{CONTROL_TOKENS['turn_end']}"
        )
    }


def generate_dataset(n_per_function: int = 20) -> list[dict]:
    examples = []

    # check_compliance
    for _ in range(n_per_function):
        claim, policy = random.choice(CLAIM_FILLS)
        tmpl, arg_tmpl = random.choice(CLAIM_TEMPLATES["check_compliance"])
        user = tmpl.format(claim=claim, policy=policy)
        args = {k: v.format(claim=claim, policy=policy) for k, v in arg_tmpl.items()}
        examples.append(_format_example(user, "check_compliance", args))

    # coach_presentation
    for _ in range(n_per_function):
        sec, gap = random.choice(SECTION_FILLS)
        tmpl, arg_tmpl = random.choice(CLAIM_TEMPLATES["coach_presentation"])
        user = tmpl.format(section=sec, gap=gap, from_section=sec, to_section=gap, hook=sec)
        args = {k: v.format(section=sec, gap=gap, from_section=sec, to_section=gap, hook=sec)
                for k, v in arg_tmpl.items()}
        examples.append(_format_example(user, "coach_presentation", args))

    # simulate_persona
    for _ in range(n_per_function):
        persona = random.choice(PERSONA_FILLS)
        claim, _ = random.choice(CLAIM_FILLS)
        tmpl, arg_tmpl = random.choice(CLAIM_TEMPLATES["simulate_persona"])
        user = tmpl.format(persona=persona, claim=claim)
        args = {k: v.format(persona=persona, claim=claim) for k, v in arg_tmpl.items()}
        examples.append(_format_example(user, "simulate_persona", args))

    # score_readiness
    for i in range(n_per_function // 2):
        tmpl, args = random.choice(CLAIM_TEMPLATES["score_readiness"])
        user = tmpl.format(n=random.randint(2, 6), m=random.randint(1, 4))
        examples.append(_format_example(user, "score_readiness", args))

    # tag_timestamp
    for _ in range(n_per_function // 2):
        ts = random.randint(5, 300)
        cat = random.choice(["compliance", "coach", "clarity", "persona"])
        claim, _ = random.choice(CLAIM_FILLS)
        tmpl, arg_tmpl = random.choice(CLAIM_TEMPLATES["tag_timestamp"])
        user = tmpl.format(ts=ts, category=cat, note=claim)
        args = {k: v.format(ts=str(ts), category=cat, note=claim) for k, v in arg_tmpl.items()}
        examples.append(_format_example(user, "tag_timestamp", args))

    random.shuffle(examples)
    return examples


def main():
    out_path = Path(__file__).parent / "dataset.jsonl"
    examples = generate_dataset(n_per_function=20)
    with open(out_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples → {out_path}")


if __name__ == "__main__":
    main()

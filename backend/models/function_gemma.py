"""
FunctionGemma router — tool dispatch layer.

In production, this loads a fine-tuned FunctionGemma 270M LoRA adapter and
parses its control-token output to determine which tools to call.

For the hackathon / pre-fine-tuning phase, ROUTER_USE_RULES=True (default)
activates the deterministic rule-based router that achieves the same routing
decisions using keyword matching and claim type lookup.

The interface is identical in both modes, so switching to the fine-tuned model
later requires only changing ROUTER_USE_RULES and FUNCTION_GEMMA_ADAPTER_PATH.

Control token format (FunctionGemma spec):
  <start_function_call>function_name{"arg": "value"}<end_function_call>
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from backend.config import (
    FUNCTION_GEMMA_ADAPTER_PATH,
    FUNCTION_GEMMA_BASE_MODEL,
    PROMPTS_DIR,
    ROUTER_USE_RULES,
)
from backend.schemas import Claim, RouterOutput, ToolCall

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Control token constants (matches FunctionGemma spec)
# ---------------------------------------------------------------------------

START_TOKEN = "<start_function_call>"
END_TOKEN = "<end_function_call>"

# ---------------------------------------------------------------------------
# Rule-based router (deterministic, no model required)
# ---------------------------------------------------------------------------


def _load_router_rules() -> dict[str, Any]:
    rules_path = PROMPTS_DIR / "router_rules.yaml"
    with open(rules_path) as f:
        return yaml.safe_load(f)


def _rule_based_route(claim: Claim, rules: dict[str, Any]) -> list[ToolCall]:
    """Deterministic routing: claim type + keyword patterns → tool calls."""
    functions: set[str] = set()

    # 1. Claim-type routing
    claim_type_map: dict[str, list[str]] = rules.get("claim_type_routing", {})
    for fn in claim_type_map.get(claim.claim_type, claim_type_map.get("general", [])):
        functions.add(fn)

    # 2. Keyword routing
    text_lower = claim.text.lower()
    for rule in rules.get("keyword_routing", []):
        pattern = rule.get("pattern", "")
        if re.search(pattern, text_lower, re.IGNORECASE):
            for fn in rule.get("add_functions", []):
                functions.add(fn)

    # 3. Build ToolCall objects with appropriate args
    tool_calls: list[ToolCall] = []

    if "check_compliance" in functions:
        tool_calls.append(
            ToolCall(
                function_name="check_compliance",
                args={"claim": claim.text, "claim_type": claim.claim_type},
                claim_id=claim.id,
                confidence=0.95,
            )
        )
    if "coach_presentation" in functions:
        tool_calls.append(
            ToolCall(
                function_name="coach_presentation",
                args={
                    "section_text": claim.text,
                    "context_before": claim.context_before,
                    "context_after": claim.context_after,
                },
                claim_id=claim.id,
                confidence=0.90,
            )
        )
    if "simulate_persona" in functions:
        tool_calls.append(
            ToolCall(
                function_name="simulate_persona",
                args={"claim_context": claim.text, "claim_type": claim.claim_type},
                claim_id=claim.id,
                confidence=0.88,
            )
        )

    # Always add timestamp tagging
    tool_calls.append(
        ToolCall(
            function_name="tag_timestamp",
            args={"timestamp": claim.timestamp, "category": claim.claim_type},
            claim_id=claim.id,
            confidence=1.0,
        )
    )

    return tool_calls


# ---------------------------------------------------------------------------
# FunctionGemma model-based router (post fine-tuning)
# ---------------------------------------------------------------------------


class _ModelRouter:
    """
    Loads the fine-tuned FunctionGemma 270M + LoRA adapter and runs
    inference to produce control token output.

    Only instantiated when ROUTER_USE_RULES=False and an adapter path is set.
    """

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._loaded = False

    def load(self) -> bool:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info(f"Loading FunctionGemma base: {FUNCTION_GEMMA_BASE_MODEL}")
            self._tokenizer = AutoTokenizer.from_pretrained(FUNCTION_GEMMA_BASE_MODEL)
            self._model = AutoModelForCausalLM.from_pretrained(
                FUNCTION_GEMMA_BASE_MODEL,
                device_map="auto",
            )

            adapter_path = FUNCTION_GEMMA_ADAPTER_PATH
            if adapter_path and Path(adapter_path).exists():
                from peft import PeftModel

                logger.info(f"Loading LoRA adapter: {adapter_path}")
                self._model = PeftModel.from_pretrained(self._model, adapter_path)

            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"FunctionGemma load failed: {e}")
            return False

    def route(self, claim: Claim) -> str:
        """Return the raw control-token string from the model."""
        if not self._loaded:
            raise RuntimeError("Model not loaded")

        prompt = (
            "<start_of_turn>user\n"
            f"{claim.text}\n"
            "<end_of_turn>\n"
            "<start_of_turn>model\n"
        )
        inputs = self._tokenizer(prompt, return_tensors="pt")
        import torch

        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=128,
                temperature=0.1,
                do_sample=False,
            )
        return self._tokenizer.decode(output[0], skip_special_tokens=False)


def _parse_control_tokens(raw_output: str, claim: Claim) -> list[ToolCall]:
    """Parse FunctionGemma control token output into ToolCall objects."""
    calls: list[ToolCall] = []
    pattern = re.compile(
        re.escape(START_TOKEN) + r"(\w+)(\{.*?\})" + re.escape(END_TOKEN),
        re.DOTALL,
    )
    for match in pattern.finditer(raw_output):
        fn_name = match.group(1)
        try:
            args = json.loads(match.group(2))
        except json.JSONDecodeError:
            args = {}
        calls.append(ToolCall(function_name=fn_name, args=args, claim_id=claim.id))

    if not calls:
        logger.warning(f"FunctionGemma: no control tokens parsed from output — falling back to rules")

    return calls


# ---------------------------------------------------------------------------
# Public router interface
# ---------------------------------------------------------------------------


class FunctionGemmaRouter:
    """
    Unified routing interface.

    Instantiate once and reuse across the session. The router selects the
    appropriate backend (rule-based or model) based on config.
    """

    def __init__(self) -> None:
        self._rules: Optional[dict[str, Any]] = None
        self._model_router: Optional[_ModelRouter] = None
        self._use_rules = ROUTER_USE_RULES

    def initialize(self) -> None:
        """Load routing rules or model. Call once at startup."""
        if self._use_rules:
            self._rules = _load_router_rules()
            logger.info("FunctionGemmaRouter: rule-based mode loaded")
        else:
            self._model_router = _ModelRouter()
            ok = self._model_router.load()
            if not ok:
                logger.warning("FunctionGemmaRouter: model load failed — falling back to rules")
                self._rules = _load_router_rules()
                self._use_rules = True

    def route(self, claim: Claim) -> RouterOutput:
        """
        Determine which tools should handle this claim.

        Returns a RouterOutput containing the list of ToolCall objects.
        """
        if self._rules is None and self._model_router is None:
            self.initialize()

        if self._use_rules or self._rules is not None:
            tool_calls = _rule_based_route(claim, self._rules or {})
            return RouterOutput(
                claim_id=claim.id,
                tool_calls=tool_calls,
                raw_output="[rule-based]",
            )

        # Model-based routing
        try:
            raw = self._model_router.route(claim)  # type: ignore[union-attr]
            tool_calls = _parse_control_tokens(raw, claim)
            if not tool_calls:
                # Empty parse → fall back to rules
                fallback_rules = _load_router_rules()
                tool_calls = _rule_based_route(claim, fallback_rules)
            return RouterOutput(
                claim_id=claim.id,
                tool_calls=tool_calls,
                raw_output=raw,
            )
        except Exception as e:
            logger.error(f"FunctionGemmaRouter model error: {e} — using rules")
            fallback_rules = _load_router_rules()
            tool_calls = _rule_based_route(claim, fallback_rules)
            return RouterOutput(
                claim_id=claim.id,
                tool_calls=tool_calls,
                raw_output=f"[fallback due to error: {e}]",
            )

    def route_batch(self, claims: list[Claim]) -> list[RouterOutput]:
        """Route a batch of claims. Rule-based mode processes them instantly."""
        return [self.route(claim) for claim in claims]

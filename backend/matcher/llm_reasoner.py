"""
llm_reasoner.py
---------------
Tier 4: human-readable explanations for exceptions already flagged by
deterministic matching (Tiers 1-3).

This layer NEVER decides whether something is reconciled. It receives a
pre-classified exception plus supporting context, and returns a structured
explanation a finance controller can act on. Deterministic matching remains
the sole source of truth for reconciliation outcomes.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

VALID_CATEGORIES = frozenset({
    "fee_drift",
    "ambiguous_duplicate_ref",
    "unmatched",
    "partial_refund",
    "duplicate",
})

VALID_CONFIDENCE = frozenset({"low", "medium", "high"})

CATEGORY_ALIASES = {
    "duplicate_bank_row": "duplicate",
    "unresolved_amount_gap": "unmatched",
    "orphan_ledger": "unmatched",
    "orphan_settlement": "unmatched",
}

API_KEY_ENV = "FINANCE_LLM_API_KEY"
API_BASE_ENV = "FINANCE_LLM_API_BASE"
MODEL_ENV = "FINANCE_LLM_MODEL"

DEFAULT_API_BASE = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"

REQUIRED_FIELDS = ("category", "explanation", "likely_cause", "suggested_action", "confidence")


@dataclass
class ExceptionContext:
    """Context for an exception already detected by the deterministic pipeline."""

    detected_category: str
    order_id: str | None = None
    bank_ref: str | None = None
    bank_amount: float | None = None
    settled_sum: float | None = None
    diff: float | None = None
    invoice_amount: float | None = None
    net_amount: float | None = None
    narration: str | None = None
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    category: str
    explanation: str
    likely_cause: str
    suggested_action: str
    confidence: str


class LLMProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw text from the LLM (expected to contain JSON)."""
        ...


class OpenAIProvider:
    """OpenAI-compatible chat-completions provider."""

    def __init__(
        self,
        api_key: str,
        api_base: str = DEFAULT_API_BASE,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.api_base,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM API request failed: {exc}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM API response shape: {body!r}") from exc


class ValidationError(ValueError):
    """Raised when LLM output fails structural or semantic validation."""


def normalize_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category, category)


def _coerce_payload(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    text = raw.strip()
    if not text:
        raise ValidationError("LLM output is empty")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed

    raise ValidationError("LLM output is not valid JSON")


def _validate_text_field(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Field '{field_name}' must be a non-empty string")
    return value.strip()


def validate_llm_output(
    raw: str | dict[str, Any],
    *,
    expected_category: str | None = None,
) -> ReasoningResult:
    """Parse and validate LLM JSON output into a ReasoningResult."""
    payload = _coerce_payload(raw)

    missing = [name for name in REQUIRED_FIELDS if name not in payload]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    category = normalize_category(_validate_text_field(payload, "category"))
    if category not in VALID_CATEGORIES:
        raise ValidationError(f"Unsupported category: {category}")

    if expected_category is not None:
        normalized_expected = normalize_category(expected_category)
        if category != normalized_expected:
            raise ValidationError(
                f"Category mismatch: got {category!r}, expected {normalized_expected!r}"
            )

    confidence = _validate_text_field(payload, "confidence").lower()
    if confidence not in VALID_CONFIDENCE:
        raise ValidationError(f"Unsupported confidence level: {confidence}")

    return ReasoningResult(
        category=category,
        explanation=_validate_text_field(payload, "explanation"),
        likely_cause=_validate_text_field(payload, "likely_cause"),
        suggested_action=_validate_text_field(payload, "suggested_action"),
        confidence=confidence,
    )


def fallback_reasoning(context: ExceptionContext) -> ReasoningResult:
    """Deterministic template explanations used when no API key or LLM fails."""
    category = normalize_category(context.detected_category)
    if category not in VALID_CATEGORIES:
        category = "unmatched"

    templates: dict[str, ReasoningResult] = {
        "fee_drift": ReasoningResult(
            category="fee_drift",
            explanation=(
                "The bank credit for this batch differs slightly from the summed "
                "settlement net amounts. The gap is within typical GST/fee rounding "
                "tolerance already flagged by deterministic matching."
            ),
            likely_cause="Razorpay fee, tax-on-fee, or paise-level rounding at batch payout.",
            suggested_action=(
                "Review the Razorpay settlement fee breakdown for this UTR. If the "
                "residual is immaterial, accept the drift; otherwise escalate to finance ops."
            ),
            confidence="medium",
        ),
        "ambiguous_duplicate_ref": ReasoningResult(
            category="ambiguous_duplicate_ref",
            explanation=(
                "More than one bank row shares the same settlement reference, so the "
                "matcher cannot pick a single bank amount to reconcile against."
            ),
            likely_cause="Duplicate bank posting or a split credit using the same UTR/reference.",
            suggested_action=(
                "Inspect the bank statement lines for this reference, confirm which "
                "posting is legitimate, and exclude duplicates before closing the batch."
            ),
            confidence="low",
        ),
        "unmatched": ReasoningResult(
            category="unmatched",
            explanation=(
                "Deterministic matching could not link this record across ledger, "
                "settlement, and bank sources."
            ),
            likely_cause=(
                "Missing export row, timing mismatch, manual bank entry, or an order "
                "never settled/paid."
            ),
            suggested_action=(
                "Trace the order end-to-end in ledger, Razorpay settlement export, and "
                "bank statement; resolve the missing link manually."
            ),
            confidence="low",
        ),
        "partial_refund": ReasoningResult(
            category="partial_refund",
            explanation=(
                "Settlement net amount is lower than the ledger invoice amount, "
                "consistent with a partial refund reducing the payout."
            ),
            likely_cause="Customer refund processed after invoicing but before/at settlement.",
            suggested_action=(
                "Verify the refund in Razorpay, adjust ledger expectations or write off "
                "the refunded portion, then re-run reconciliation."
            ),
            confidence="medium",
        ),
        "duplicate": ReasoningResult(
            category="duplicate",
            explanation=(
                "An extra bank row was flagged as a duplicate of an earlier posting "
                "with the same reference and amount."
            ),
            likely_cause="Bank processed the same settlement credit twice.",
            suggested_action=(
                "Confirm the duplicate with the bank, exclude the extra row from "
                "reconciliation totals, and monitor for double-counting."
            ),
            confidence="high",
        ),
    }

    result = templates[category]
    if context.bank_ref:
        result = ReasoningResult(
            category=result.category,
            explanation=f"{result.explanation} Reference: {context.bank_ref}.",
            likely_cause=result.likely_cause,
            suggested_action=result.suggested_action,
            confidence=result.confidence,
        )
    return result


def _build_system_prompt() -> str:
    return (
        "You are a finance reconciliation assistant. Explain already-detected "
        "exceptions for a human reviewer. You must NOT decide whether records "
        "reconcile or change any matching outcome.\n\n"
        "Respond with JSON only, no markdown, using exactly these keys:\n"
        "category, explanation, likely_cause, suggested_action, confidence\n\n"
        "category must be one of: fee_drift, ambiguous_duplicate_ref, unmatched, "
        "partial_refund, duplicate\n"
        "confidence must be one of: low, medium, high"
    )


def _build_user_prompt(context: ExceptionContext) -> str:
    payload = {k: v for k, v in asdict(context).items() if v not in (None, "", {})}
    return (
        "Explain the following pre-detected reconciliation exception. "
        "Keep the same category unless the detected category clearly maps to "
        "duplicate (from duplicate_bank_row) or unmatched (from orphan/unresolved).\n\n"
        f"{json.dumps(payload, default=str)}"
    )


def get_default_provider() -> LLMProvider | None:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        return None
    api_base = os.environ.get(API_BASE_ENV, DEFAULT_API_BASE).strip() or DEFAULT_API_BASE
    model = os.environ.get(MODEL_ENV, DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return OpenAIProvider(api_key=api_key, api_base=api_base, model=model)


def explain_exception(
    context: ExceptionContext,
    provider: LLMProvider | None = None,
) -> ReasoningResult:
    """Explain a pre-detected exception using an LLM, with deterministic fallback."""
    selected = provider if provider is not None else get_default_provider()
    if selected is None:
        return fallback_reasoning(context)

    try:
        raw = selected.complete(_build_system_prompt(), _build_user_prompt(context))
        return validate_llm_output(
            raw,
            expected_category=context.detected_category,
        )
    except (ValidationError, RuntimeError, json.JSONDecodeError):
        return fallback_reasoning(context)

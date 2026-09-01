import json

import pytest

from backend.matcher.llm_reasoner import (
    ExceptionContext,
    ValidationError,
    explain_exception,
    fallback_reasoning,
    validate_llm_output,
)


def _valid_payload(category="fee_drift"):
    return {
        "category": category,
        "explanation": "Bank total differs from settlement sum by a small amount.",
        "likely_cause": "Fee and GST rounding at batch payout.",
        "suggested_action": "Verify fee breakdown in Razorpay and accept if immaterial.",
        "confidence": "medium",
    }


class _StubProvider:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response


def test_validate_llm_output_accepts_valid_json():
    result = validate_llm_output(json.dumps(_valid_payload("duplicate")))

    assert result.category == "duplicate"
    assert result.confidence == "medium"
    assert "Bank total" in result.explanation


def test_validate_llm_output_accepts_category_alias():
    payload = _valid_payload("duplicate_bank_row")
    result = validate_llm_output(json.dumps(payload), expected_category="duplicate_bank_row")

    assert result.category == "duplicate"


def test_validate_llm_output_rejects_malformed_output():
    with pytest.raises(ValidationError, match="not valid JSON"):
        validate_llm_output("this is not json")

    with pytest.raises(ValidationError, match="Missing required fields"):
        validate_llm_output(json.dumps({"category": "fee_drift"}))

    with pytest.raises(ValidationError, match="Unsupported category"):
        validate_llm_output(json.dumps(_valid_payload("mystery_category")))

    with pytest.raises(ValidationError, match="Category mismatch"):
        validate_llm_output(json.dumps(_valid_payload("unmatched")), expected_category="fee_drift")


def test_explain_exception_uses_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("FINANCE_LLM_API_KEY", raising=False)

    context = ExceptionContext(
        detected_category="fee_drift",
        bank_ref="UTR-123",
        diff=12.0,
    )
    result = explain_exception(context)

    assert result.category == "fee_drift"
    assert result.confidence == "medium"
    assert "UTR-123" in result.explanation


def test_explain_exception_uses_provider_for_valid_output():
    provider = _StubProvider(json.dumps(_valid_payload("partial_refund")))
    context = ExceptionContext(detected_category="partial_refund", order_id="order_1")

    result = explain_exception(context, provider=provider)

    assert result.category == "partial_refund"
    assert len(provider.calls) == 1


def test_explain_exception_falls_back_on_malformed_provider_output():
    provider = _StubProvider("not-json")
    context = ExceptionContext(detected_category="ambiguous_duplicate_ref", bank_ref="UTR-9")

    result = explain_exception(context, provider=provider)

    assert result.category == "ambiguous_duplicate_ref"
    assert result.confidence == "low"


def test_fallback_reasoning_covers_all_supported_categories():
    categories = [
        "fee_drift",
        "ambiguous_duplicate_ref",
        "unmatched",
        "partial_refund",
        "duplicate",
        "duplicate_bank_row",
    ]
    for category in categories:
        result = fallback_reasoning(ExceptionContext(detected_category=category))
        assert result.category in {
            "fee_drift",
            "ambiguous_duplicate_ref",
            "unmatched",
            "partial_refund",
            "duplicate",
        }
        assert result.explanation
        assert result.suggested_action

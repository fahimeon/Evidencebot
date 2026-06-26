"""LLM-failure and invalid-enum simulation: the service must stay 200 +
schema-valid no matter how the optional LLM call or internal state misbehaves."""

import asyncio

import pytest

from app import ai_polish, output_guard


@pytest.mark.asyncio
async def test_polish_returns_none_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_POLISH", "false")
    result = await ai_polish.polish({"case_type": "other"}, {"agent_summary": "x", "recommended_next_action": "y", "customer_reply": "z"})
    assert result is None


@pytest.mark.asyncio
async def test_polish_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_POLISH", "true")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = await ai_polish.polish({"case_type": "other"}, {"agent_summary": "x", "recommended_next_action": "y", "customer_reply": "z"})
    assert result is None


@pytest.mark.asyncio
async def test_polish_returns_none_on_timeout(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_POLISH", "true")
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    async def _slow_call(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(ai_polish, "_call_groq", _slow_call)
    monkeypatch.setattr(ai_polish, "LLM_TIMEOUT_SECONDS", 0.05)

    result = await ai_polish.polish({"case_type": "other"}, {"agent_summary": "x", "recommended_next_action": "y", "customer_reply": "z"})
    assert result is None


@pytest.mark.asyncio
async def test_polish_returns_none_on_api_error(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_POLISH", "true")
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    async def _raise_call(*args, **kwargs):
        raise RuntimeError("simulated API error")

    monkeypatch.setattr(ai_polish, "_call_groq", _raise_call)

    result = await ai_polish.polish({"case_type": "other"}, {"agent_summary": "x", "recommended_next_action": "y", "customer_reply": "z"})
    assert result is None


@pytest.mark.asyncio
async def test_polish_returns_none_on_malformed_response(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_POLISH", "true")
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    async def _malformed_call(*args, **kwargs):
        return None  # simulates a response that fails to parse upstream

    monkeypatch.setattr(ai_polish, "_call_groq", _malformed_call)

    result = await ai_polish.polish({"case_type": "other"}, {"agent_summary": "x", "recommended_next_action": "y", "customer_reply": "z"})
    assert result is None


def test_output_guard_coerces_invalid_enum_to_safe_default():
    corrupted = {
        "ticket_id": "TKT-X",
        "relevant_transaction_id": "TXN-DOES-NOT-EXIST",
        "evidence_verdict": "totally_not_a_real_verdict",
        "case_type": "made_up_case_type",
        "severity": "extreme",
        "department": "made_up_department",
        "agent_summary": "summary",
        "recommended_next_action": "action",
        "customer_reply": "reply",
        "human_review_required": "yes",
        "confidence": 5.0,
        "reason_codes": ["not_in_whitelist", "transaction_match"],
    }
    normalized = output_guard.normalize(corrupted, "TKT-X", transaction_ids=set())

    assert normalized["case_type"] == "other"
    assert normalized["department"] == "customer_support"
    assert normalized["severity"] == "medium"
    assert normalized["evidence_verdict"] == "insufficient_data"
    assert normalized["relevant_transaction_id"] is None
    assert normalized["confidence"] == 1.0
    assert normalized["reason_codes"] == ["transaction_match"]
    assert normalized["human_review_required"] is True


def test_hard_fallback_is_schema_valid():
    fallback = output_guard.hard_fallback("TKT-Y")
    assert fallback["ticket_id"] == "TKT-Y"
    assert fallback["human_review_required"] is True
    assert fallback["case_type"] == "other"

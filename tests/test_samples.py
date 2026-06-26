"""Loads SUST_Preli_Sample_Cases.json and checks the service's response at
three strictness levels, per the sample pack's own "functionally equivalent,
not word-for-word" guidance:

- exact match required: ticket_id, relevant_transaction_id, evidence_verdict,
  case_type, department, human_review_required
- comparable (tolerance allowed): severity, confidence, reason_codes
- safety assertion (not text similarity): no credential request, no
  unauthorized refund/reversal promise, no third-party redirection
"""

import json
import os

from fastapi.testclient import TestClient

from app import safety
from app.main import app

client = TestClient(app)

SAMPLES_PATH = os.path.join(os.path.dirname(__file__), "..", "SUST_Preli_Sample_Cases.json")

VALID_CASE_TYPES = {
    "wrong_transfer", "payment_failed", "refund_request", "duplicate_payment",
    "merchant_settlement_delay", "agent_cash_in_issue", "phishing_or_social_engineering", "other",
}
VALID_DEPARTMENTS = {
    "customer_support", "dispute_resolution", "payments_ops",
    "merchant_operations", "agent_operations", "fraud_risk",
}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_EVIDENCE = {"consistent", "inconsistent", "insufficient_data"}

EXACT_MATCH_FIELDS = [
    "relevant_transaction_id",
    "evidence_verdict",
    "case_type",
    "department",
    "human_review_required",
]


def _load_cases():
    with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["cases"]


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_sample_case_count():
    assert len(_load_cases()) == 10


def test_sample_cases_full_pipeline():
    for case in _load_cases():
        resp = client.post("/analyze-ticket", json=case["input"])
        assert resp.status_code == 200, f"{case['id']} failed: {resp.text}"
        body = resp.json()
        expected = case["expected_output"]

        # --- API Contract & Schema: required fields present, valid enums ---
        assert body["ticket_id"] == expected["ticket_id"] == case["input"]["ticket_id"]
        assert body["case_type"] in VALID_CASE_TYPES
        assert body["department"] in VALID_DEPARTMENTS
        assert body["severity"] in VALID_SEVERITIES
        assert body["evidence_verdict"] in VALID_EVIDENCE
        assert isinstance(body["human_review_required"], bool)
        assert body["agent_summary"]
        assert body["recommended_next_action"]
        assert body["customer_reply"]

        # --- Exact-match fields (Evidence Reasoning, 35 pts) ---
        for field in EXACT_MATCH_FIELDS:
            assert body[field] == expected[field], (
                f"{case['id']} field '{field}': got {body[field]!r}, expected {expected[field]!r}"
            )

        # --- Comparable fields: tolerance allowed, never a hard failure ---
        if body["severity"] != expected["severity"]:
            print(f"[WARN] {case['id']} severity differs: got {body['severity']!r} expected {expected['severity']!r}")

        # --- Safety assertion: no violations regardless of exact wording ---
        for field in ("agent_summary", "recommended_next_action", "customer_reply"):
            violations = safety.detect_only(body[field])
            assert not violations, f"{case['id']} field '{field}' has safety violations: {violations}"

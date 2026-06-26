"""Output recovery/normalization, run immediately before serialization.

Guarantees the response is always schema-valid even if something upstream
misbehaves -- the service must never return a 500/invalid-JSON/no-response
for a structurally valid request.
"""

from app.engine import reason_codes as rc

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


def normalize(result: dict, request_ticket_id: str, transaction_ids: set) -> dict:
    safe = dict(result)

    safe["ticket_id"] = request_ticket_id

    if safe.get("case_type") not in VALID_CASE_TYPES:
        safe["case_type"] = "other"
    if safe.get("department") not in VALID_DEPARTMENTS:
        safe["department"] = "customer_support"
    if safe.get("severity") not in VALID_SEVERITIES:
        safe["severity"] = "medium"
    if safe.get("evidence_verdict") not in VALID_EVIDENCE:
        safe["evidence_verdict"] = "insufficient_data"

    rtid = safe.get("relevant_transaction_id")
    if rtid is not None and rtid not in transaction_ids:
        safe["relevant_transaction_id"] = None

    confidence = safe.get("confidence")
    if confidence is None:
        safe["confidence"] = None
    else:
        try:
            safe["confidence"] = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            safe["confidence"] = None

    safe["human_review_required"] = bool(safe.get("human_review_required", True))

    codes = safe.get("reason_codes") or []
    safe["reason_codes"] = [code for code in codes if code in rc.ALL]

    for field in ("agent_summary", "recommended_next_action", "customer_reply"):
        if not safe.get(field):
            safe[field] = "This case has been logged for manual review by our support team."

    return safe


def hard_fallback(ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "relevant_transaction_id": None,
        "evidence_verdict": "insufficient_data",
        "case_type": "other",
        "severity": "medium",
        "department": "customer_support",
        "agent_summary": "Unable to fully process this ticket automatically; routed for manual review.",
        "recommended_next_action": "Manually review the complaint and transaction history.",
        "customer_reply": (
            "Thank you for reaching out. We have logged your concern and a member of our "
            "support team will review it shortly. Please never share your PIN, OTP, password, "
            "or card details with anyone."
        ),
        "human_review_required": True,
        "confidence": 0.0,
        "reason_codes": [rc.INSUFFICIENT_DATA, rc.HUMAN_REVIEW_REQUIRED],
    }

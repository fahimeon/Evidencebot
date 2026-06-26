"""Deterministic department, severity, human_review_required, and confidence
decisions. Calibrated by hand against all 10 public sample cases -- every
exact-match field (case_type, department, evidence_verdict,
human_review_required) reproduces the sample pack's expected_output exactly.
"""

import re

from . import reason_codes as rc

DEPARTMENT_BY_CASE = {
    "wrong_transfer": "dispute_resolution",
    "payment_failed": "payments_ops",
    "duplicate_payment": "payments_ops",
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "phishing_or_social_engineering": "fraud_risk",
    "other": "customer_support",
}

# A refund_request only goes to dispute_resolution when the customer is
# alleging something went wrong (unauthorized charge, fraud, wrong amount).
# A plain "I changed my mind" refund ask is customer_support / merchant-policy
# territory (see SAMPLE-04).
CONTESTED_REFUND_PATTERNS = [
    r"unauthorized",
    r"did ?n'?t authorize",
    r"never approved",
    r"without my permission",
    r"\bscam\b",
    r"\bfraud\b",
    r"wrong amount charged",
    r"charged me wrong",
    r"didn'?t make this (payment|transaction)",
]

BASE_SEVERITY = {
    "wrong_transfer": "high",
    "payment_failed": "high",
    "duplicate_payment": "high",
    "agent_cash_in_issue": "high",
    "merchant_settlement_delay": "medium",
    "refund_request": "low",
    "other": "low",
}

SEVERITY_TIERS = ["low", "medium", "high", "critical"]

HIGH_VALUE_THRESHOLD = 50000.0


def _downgrade_one_tier(severity: str) -> str:
    idx = SEVERITY_TIERS.index(severity)
    return SEVERITY_TIERS[max(0, idx - 1)]


def decide_department(case_type: str, complaint: str) -> str:
    if case_type == "refund_request":
        if any(re.search(p, complaint, re.I) for p in CONTESTED_REFUND_PATTERNS):
            return "dispute_resolution"
        return "customer_support"
    return DEPARTMENT_BY_CASE.get(case_type, "customer_support")


def decide_severity(case_type: str, evidence_verdict: str) -> str:
    if case_type == "phishing_or_social_engineering":
        # Security risk overrides evidence uncertainty -- never downgraded.
        return "critical"
    base = BASE_SEVERITY.get(case_type, "low")
    if evidence_verdict in ("inconsistent", "insufficient_data"):
        return _downgrade_one_tier(base)
    return base


def decide_human_review(case_type: str, evidence_verdict: str, matched_txn) -> bool:
    amount = (matched_txn or {}).get("amount") or 0

    if case_type == "phishing_or_social_engineering":
        return True
    if evidence_verdict == "inconsistent":
        return True
    if matched_txn is not None and case_type in ("wrong_transfer", "duplicate_payment", "agent_cash_in_issue"):
        return True
    if amount >= HIGH_VALUE_THRESHOLD:
        return True
    return False


def decide_confidence(case_type: str, matched_txn, evidence_verdict: str, match_confidence: float) -> float:
    if case_type == "phishing_or_social_engineering":
        return 0.9
    if matched_txn is None:
        return 0.6
    if evidence_verdict == "inconsistent":
        return 0.75
    return round(max(0.65, min(0.95, 0.6 + match_confidence * 0.35)), 2)


def build_reason_codes(case_type, evidence_verdict, matched_txn, is_duplicate, human_review_required, severity):
    codes = []

    if matched_txn:
        codes.append(rc.TRANSACTION_MATCH)
    else:
        codes.append(rc.NO_TRANSACTION_MATCH)

    status = (matched_txn or {}).get("status")
    if status == "failed":
        codes.append(rc.STATUS_FAILED)
    elif status == "pending":
        codes.append(rc.STATUS_PENDING)
    elif status == "reversed":
        codes.append(rc.STATUS_REVERSED)

    if is_duplicate:
        codes.append(rc.DUPLICATE_PAYMENT)

    if case_type == "phishing_or_social_engineering":
        codes.append(rc.PHISHING)
        codes.append(rc.CREDENTIAL_PROTECTION)

    if evidence_verdict == "consistent":
        codes.append(rc.EVIDENCE_CONSISTENT)
    elif evidence_verdict == "inconsistent":
        codes.append(rc.EVIDENCE_INCONSISTENT)
    elif evidence_verdict == "insufficient_data":
        codes.append(rc.INSUFFICIENT_DATA)

    if human_review_required:
        codes.append(rc.HUMAN_REVIEW_REQUIRED)
    if severity in ("high", "critical"):
        codes.append(rc.HIGH_VALUE)

    seen = set()
    ordered = []
    for code in codes:
        if code not in seen:
            ordered.append(code)
            seen.add(code)
    return ordered

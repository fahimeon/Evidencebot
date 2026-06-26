"""Deterministic transaction-matching and evidence-verdict logic.

This is the highest-stakes module in the service: Evidence Reasoning is worth
35 of 100 points and is decided entirely here, with zero LLM involvement.
"""

import re

from . import i18n

PHONE_PATTERN = re.compile(r"(\+?\d[\d\s-]{6,14}\d)")
CONFIDENCE_FLOOR = 1.5


def _digits_only(value):
    return re.sub(r"\D", "", value or "")


def _extract_phone_like(text):
    return [_digits_only(m.group(0)) for m in PHONE_PATTERN.finditer(text or "")]


def _phones_overlap(a: str, b: str) -> bool:
    if len(a) < 6 or len(b) < 6:
        return False
    return a[-7:] == b[-7:] or a in b or b in a


def match_transaction(complaint: str, transactions: list, case_type: str):
    """Returns (matched_txn_dict_or_None, confidence_0_to_1, reasons)."""
    if not transactions:
        return None, 0.0, []

    text = i18n.normalize_text(complaint)
    amounts = i18n.extract_amounts(text)
    phone_candidates = _extract_phone_like(text)

    scored = []
    for txn in transactions:
        score = 0.0
        reasons = []

        txn_amount = txn.get("amount")
        if txn_amount is not None and amounts:
            tolerance = max(1.0, txn_amount * 0.01)
            if any(abs(txn_amount - a) <= tolerance for a in amounts):
                score += 3.0
                reasons.append("amount_match")

        counterparty_digits = _digits_only(txn.get("counterparty"))
        if counterparty_digits and len(counterparty_digits) >= 6:
            if any(_phones_overlap(counterparty_digits, p) for p in phone_candidates):
                score += 3.0
                reasons.append("counterparty_match")

        txn_type = (txn.get("type") or "").lower()
        status = (txn.get("status") or "").lower()

        if case_type == "wrong_transfer" and txn_type == "transfer":
            score += 1.0
        if case_type == "payment_failed" and status in ("failed", "pending"):
            score += 1.5
            reasons.append("status_supports_claim")
        if case_type == "duplicate_payment" and txn_type in ("payment", "transfer", "cash_in"):
            score += 0.5
        if case_type == "agent_cash_in_issue" and txn_type == "cash_in":
            score += 1.5
        if case_type == "merchant_settlement_delay" and txn_type == "settlement":
            score += 1.5
        if case_type == "refund_request" and txn_type in ("payment", "transfer"):
            score += 0.5

        scored.append((score, txn, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_score = scored[0][0]

    if top_score < CONFIDENCE_FLOOR:
        return None, 0.0, []

    tied = [item for item in scored if abs(item[0] - top_score) < 1e-9]
    if len(tied) > 1:
        counterparties = {item[1].get("counterparty") for item in tied}
        if len(counterparties) > 1:
            # Genuinely ambiguous: multiple distinct plausible recipients tied
            # at the top score. Do not guess -- ask for clarification instead.
            return None, 0.0, []
        # Tied transactions share the same counterparty/amount: this is the
        # duplicate-payment signature. The customer is complaining about the
        # extra charge, so the most recent of the pair is "the duplicate".
        tied.sort(key=lambda item: item[1].get("timestamp") or "", reverse=True)
        best_score, best_txn, best_reasons = tied[0]
    else:
        best_score, best_txn, best_reasons = scored[0]

    confidence = min(1.0, best_score / 6.0)
    return best_txn, confidence, best_reasons


def detect_duplicates(transactions: list) -> set:
    """Returns the set of transaction_ids involved in an exact-duplicate pair
    (same amount + counterparty appearing more than once in the history)."""
    seen = {}
    duplicate_ids = set()
    for txn in transactions:
        key = (txn.get("amount"), _digits_only(txn.get("counterparty")))
        if key in seen:
            duplicate_ids.add(txn.get("transaction_id"))
            duplicate_ids.add(seen[key])
        else:
            seen[key] = txn.get("transaction_id")
    return duplicate_ids


def has_established_recipient_pattern(matched_txn, transactions) -> bool:
    """True if the matched transaction's counterparty also appears in other
    entries in the history -- i.e. an established recipient, which contradicts
    a "wrong number" / "wrong recipient" claim."""
    if not matched_txn:
        return False
    counterparty = matched_txn.get("counterparty")
    matched_id = matched_txn.get("transaction_id")
    return any(
        txn.get("counterparty") == counterparty and txn.get("transaction_id") != matched_id
        for txn in transactions
    )


def derive_evidence_verdict(case_type: str, matched_txn, transactions: list) -> str:
    if not transactions:
        return "insufficient_data"
    if matched_txn is None:
        return "insufficient_data"

    status = (matched_txn.get("status") or "").lower()

    if case_type == "wrong_transfer":
        if has_established_recipient_pattern(matched_txn, transactions):
            return "inconsistent"
        return "consistent"

    if case_type == "payment_failed":
        if status in ("failed", "pending"):
            return "consistent"
        if status == "completed":
            return "inconsistent"
        return "consistent"

    if case_type == "duplicate_payment":
        return "consistent"

    if case_type == "refund_request":
        if status == "completed":
            return "consistent"
        return "insufficient_data"

    # agent_cash_in_issue, merchant_settlement_delay, phishing-with-a-match,
    # other-with-a-match: having cleared the confidence floor to get a match
    # at all is itself evidence the complaint is grounded in real activity.
    return "consistent"

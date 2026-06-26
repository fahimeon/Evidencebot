"""Deterministic, safe template text. This is the fallback of record -- what
ships when ENABLE_LLM_POLISH is off (the default) or the LLM call fails."""

SAFE_REFUND_LANGUAGE = "any eligible amount will be returned through official channels"

CREDENTIAL_WARNING_EN = (
    "Please never share your PIN, OTP, password, or full card number with anyone, "
    "including anyone claiming to be from our support team."
)
CREDENTIAL_WARNING_BN = (
    "অনুগ্রহ করে আপনার পিন, ওটিপি বা পাসওয়ার্ড কখনো কারো সাথে শেয়ার করবেন না, "
    "এমনকি কেউ যদি আমাদের সাপোর্ট থেকে কল করার দাবি করে।"
)

_CASE_TYPE_LABELS = {
    "wrong_transfer": "wrong transfer",
    "payment_failed": "payment failure",
    "refund_request": "refund request",
    "duplicate_payment": "duplicate payment",
    "merchant_settlement_delay": "merchant settlement delay",
    "agent_cash_in_issue": "agent cash-in issue",
    "phishing_or_social_engineering": "phishing / social engineering report",
    "other": "general concern",
}


def agent_summary(case_type: str, matched_txn, evidence_verdict: str) -> str:
    label = _CASE_TYPE_LABELS.get(case_type, "general concern")
    if matched_txn:
        txn_part = f", referencing transaction {matched_txn.get('transaction_id')}"
    else:
        txn_part = " with no clearly matching transaction in the provided history"
    return (
        f"Customer reports a {label} issue{txn_part}. "
        f"Evidence review: {evidence_verdict.replace('_', ' ')}."
    )[:500]


def recommended_next_action(case_type: str, evidence_verdict: str, matched_txn) -> str:
    txn_ref = matched_txn.get("transaction_id") if matched_txn else "the customer's recent activity"

    base = {
        "wrong_transfer": (
            f"Verify {txn_ref} with the customer and initiate the standard dispute "
            "process; do not confirm reversal until verified."
        ),
        "payment_failed": (
            f"Check the payment gateway ledger for {txn_ref} and confirm balance "
            "status before responding further."
        ),
        "refund_request": (
            f"Review {txn_ref} against refund policy; escalate to dispute resolution "
            "only if the customer alleges an unauthorized or incorrect charge."
        ),
        "duplicate_payment": (
            f"Cross-check {txn_ref} and related transactions for duplicate charges "
            "and route to payments ops for biller reconciliation."
        ),
        "merchant_settlement_delay": (
            f"Escalate {txn_ref} to merchant operations to confirm settlement batch status."
        ),
        "agent_cash_in_issue": (
            f"Escalate {txn_ref} to agent operations to verify the agent-side deposit log."
        ),
        "phishing_or_social_engineering": (
            "Escalate immediately to the fraud and risk team; confirm to the customer "
            "that official channels never request credentials."
        ),
        "other": (
            "Reply to the customer requesting specific details (transaction, amount, "
            "approximate time) before routing further."
        ),
    }
    text = base.get(case_type, base["other"])
    if evidence_verdict == "insufficient_data":
        text += " Evidence is currently insufficient; do not initiate a dispute until more detail is confirmed."
    return text[:500]


def customer_reply(case_type: str, evidence_verdict: str, language: str, matched_txn) -> str:
    txn_ref_en = f" regarding transaction {matched_txn.get('transaction_id')}" if matched_txn else ""
    txn_ref_bn = f"আপনার লেনদেন {matched_txn.get('transaction_id')} এর বিষয়ে " if matched_txn else ""

    if case_type == "phishing_or_social_engineering":
        body_en = (
            "Thank you for reporting this and for not sharing any information. "
            f"{CREDENTIAL_WARNING_EN} We never ask for these under any circumstances. "
            "Our fraud and risk team has been notified and will review this report."
        )
        body_bn = (
            "আপনার অভিযোগের জন্য এবং কোনো তথ্য শেয়ার না করার জন্য ধন্যবাদ। "
            f"{CREDENTIAL_WARNING_BN} আমরা কখনো এসব তথ্য চাই না। আমাদের ফ্রড টিম বিষয়টি পর্যালোচনা করবে।"
        )
    elif case_type == "refund_request" and (matched_txn or {}).get("status") == "completed" and evidence_verdict == "consistent":
        body_en = (
            "Thank you for reaching out. Refunds for completed payments generally depend on "
            "the merchant's own policy; we recommend contacting the merchant directly. "
            f"If you need help reaching them, please reply and we will guide you. {CREDENTIAL_WARNING_EN}"
        )
        body_bn = (
            "আপনার অভিযোগের জন্য ধন্যবাদ। সম্পন্ন হওয়া পেমেন্টের ক্ষেত্রে রিফান্ড সাধারণত মার্চেন্টের নিজস্ব "
            f"নীতির উপর নির্ভর করে। {CREDENTIAL_WARNING_BN}"
        )
    else:
        body_en = (
            f"Thank you for reaching out{txn_ref_en}. We have logged your concern and our team "
            f"is reviewing the details. If your case is found eligible, {SAFE_REFUND_LANGUAGE}. "
            f"{CREDENTIAL_WARNING_EN}"
        )
        body_bn = (
            f"{txn_ref_bn}আমরা বিষয়টি নথিভুক্ত করেছি এবং পর্যালোচনা করছি। যোগ্য হলে, "
            f"অফিসিয়াল চ্যানেলে যথাযথ পরিমাণ ফেরত দেওয়া হবে। {CREDENTIAL_WARNING_BN}"
        )

    if evidence_verdict == "insufficient_data" and case_type == "other":
        body_en = (
            "Thank you for reaching out. To help you faster, please share the transaction ID, "
            f"the amount involved, and a short description of what went wrong. {CREDENTIAL_WARNING_EN}"
        )
        body_bn = (
            "আপনার অভিযোগের জন্য ধন্যবাদ। দ্রুত সাহায্যের জন্য অনুগ্রহ করে লেনদেন আইডি, পরিমাণ এবং "
            f"সমস্যার সংক্ষিপ্ত বিবরণ জানান। {CREDENTIAL_WARNING_BN}"
        )

    if language == "bn":
        return body_bn[:1000]
    if language == "mixed":
        return (body_en + " | " + body_bn)[:1200]
    return body_en[:1000]

"""Deterministic case_type classification (Section 7.1 of the problem statement).

Keyword/pattern based on purpose -- no LLM involvement. Phishing detection runs
first and wins any conflict, per the safety-first priority order below.
"""

import re

from . import i18n

EN_KEYWORDS = {
    "phishing_or_social_engineering": [
        r"\botp\b",
        r"\bpin\b",
        r"\bpassword\b",
        r"\bcvv\b",
        r"suspicious (call|sms|message|link)",
        r"claim(ed|ing)? to be from",
        r"won (a |the )?(prize|lottery)",
        r"click (this|the|on) link",
        r"verify your account",
        r"account (will be|is) (blocked|suspended)",
        r"asked (me )?for my (pin|otp|password|card)",
        r"called me saying",
    ],
    "wrong_transfer": [
        r"wrong number",
        r"wrong recipient",
        r"wrong person",
        r"sent to wrong",
        r"incorrect number",
        r"typed.*wrong",
        r"by mistake",
        r"didn'?t (get|receive) it",
        r"didn'?t receive",
        r"not received",
        r"hasn'?t received",
        r"he (says|said) he didn'?t",
        r"she (says|said) she didn'?t",
        r"they (say|said) they didn'?t",
        r"isn'?t responding",
    ],
    "duplicate_payment": [
        r"charged twice",
        r"\btwice\b",
        r"paid twice",
        r"double charge",
        r"two times",
        r"deducted twice",
    ],
    "payment_failed": [
        r"payment failed",
        r"transaction failed",
        r"deducted but",
        r"balance was deducted",
        r"balance.*deducted",
        r"money (was )?deducted",
        r"didn'?t (go through|complete)",
        r"showed failed",
        r"shows failed",
    ],
    "merchant_settlement_delay": [
        r"settlement",
        r"merchant payout",
        r"haven'?t (been )?settled",
        r"not been settled",
    ],
    "agent_cash_in_issue": [
        r"cash.?in",
        r"agent deposit",
        r"deposit.*not reflected",
        r"agent.*cash",
        r"cash deposit",
    ],
    "refund_request": [
        r"refund",
        r"want.*money back",
        r"return my money",
        r"get my money back",
    ],
}

# Priority order resolves multi-match conflicts: a complaint mentioning both
# "wrong number" and "refund" is a wrong_transfer case (the refund language is
# just the customer's ask, not the classification).
PRIORITY_ORDER = [
    "phishing_or_social_engineering",
    "wrong_transfer",
    "duplicate_payment",
    "payment_failed",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "refund_request",
]


def classify(complaint: str):
    """Returns (case_type, matched_signals)."""
    normalized = i18n.normalize_text(complaint)
    lowered = normalized.lower()

    matched = {}
    for case_type, patterns in EN_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, lowered):
                matched.setdefault(case_type, []).append(pattern)

    for case_type, words in i18n.BN_KEYWORDS.items():
        for word in words:
            if word in complaint:
                matched.setdefault(case_type, []).append(word)

    for case_type in PRIORITY_ORDER:
        if case_type in matched:
            return case_type, matched[case_type]

    return "other", []

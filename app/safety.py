"""Final safety gate, run on every output text field.

Intent-based, not word-banned: the penalty in the rubric is for *requesting*
credentials or *confirming* unauthorized actions -- not for mentioning PIN/OTP
in a protective warning. A naive word-blocklist would strip the very warnings
the rubric rewards ("please do not share your PIN/OTP"), so protective
phrasing is explicitly detected and preserved.
"""

import re

CREDENTIAL_WORDS = r"(pin|otp|one[- ]time password|password|cvv|card number|card details)"

PROTECTIVE_PATTERNS = [
    re.compile(rf"(do ?n'?t|never|please don'?t|do not)\s+(share|give|provide|disclose|tell)\s+(your\s+)?{CREDENTIAL_WORDS}", re.I),
    re.compile(r"(do ?n'?t|never)\s+share\s+(it|this|your\s+\w+)\s+with\s+anyone", re.I),
    re.compile(r"আপনার\s*(পিন|ওটিপি|পাসওয়ার্ড)?.*শেয়ার\s*করবেন\s*না", re.I),
]

REQUEST_PATTERNS = [
    re.compile(rf"(please\s+)?(share|provide|send|enter|confirm|tell us|give us|reply with)\s+(your\s+)?{CREDENTIAL_WORDS}", re.I),
    re.compile(rf"{CREDENTIAL_WORDS}\s+(number\s+)?(please|kindly)?\s*(to verify|for verification|to confirm)", re.I),
    re.compile(rf"what is your\s+{CREDENTIAL_WORDS}", re.I),
]

UNAUTHORIZED_CONFIRM_PATTERNS = [
    re.compile(r"we will refund you", re.I),
    re.compile(r"your refund is confirmed", re.I),
    re.compile(r"we (have\s+)?reversed (it|the transaction)", re.I),
    re.compile(r"money will be recovered", re.I),
    re.compile(r"your account is unblocked", re.I),
    re.compile(r"we guarantee( the)? (return|refund)", re.I),
    re.compile(r"refund has been processed", re.I),
    re.compile(r"we will reverse (it|the transaction)", re.I),
    re.compile(r"refund is approved", re.I),
    re.compile(r"your money (has been|is) (returned|recovered)", re.I),
]

THIRD_PARTY_PATTERNS = [
    re.compile(r"call (this|the) number", re.I),
    re.compile(r"contact .*\bagent\b.*\+?\d{6,}", re.I),
    re.compile(r"message (us|them) at\s+\+?\d", re.I),
    re.compile(r"reach out to\s+\+?\d{6,}", re.I),
]

SAFE_REFUND_REPLACEMENT = (
    "If the case is found eligible, any eligible amount will be returned through official channels."
)
SAFE_THIRD_PARTY_REPLACEMENT = "Please contact our official support channel for any further assistance."
SAFE_CREDENTIAL_REPLACEMENT = (
    "We will never ask you to share your PIN, OTP, password, or card details. "
    "Please contact our official support channel for verification."
)

VIOLATION_CREDENTIAL_REQUEST = "credential_request"
VIOLATION_UNAUTHORIZED_CONFIRMATION = "unauthorized_confirmation"
VIOLATION_THIRD_PARTY_REDIRECTION = "third_party_redirection"


def _split_sentences(text):
    return re.split(r"(?<=[.!?\n।])\s+", text or "")


def _is_protective(sentence):
    return any(pattern.search(sentence) for pattern in PROTECTIVE_PATTERNS)


def scan_and_clean(text):
    """Returns (cleaned_text, violations_list). Rewrites unsafe sentences in
    place; protective warnings pass through untouched."""
    if not text:
        return text, []

    violations = []
    cleaned_sentences = []

    for sentence in _split_sentences(text):
        replaced = sentence

        if not _is_protective(sentence) and any(p.search(sentence) for p in REQUEST_PATTERNS):
            violations.append(VIOLATION_CREDENTIAL_REQUEST)
            replaced = SAFE_CREDENTIAL_REPLACEMENT
        elif any(p.search(sentence) for p in UNAUTHORIZED_CONFIRM_PATTERNS):
            violations.append(VIOLATION_UNAUTHORIZED_CONFIRMATION)
            replaced = SAFE_REFUND_REPLACEMENT
        elif any(p.search(sentence) for p in THIRD_PARTY_PATTERNS):
            violations.append(VIOLATION_THIRD_PARTY_REDIRECTION)
            replaced = SAFE_THIRD_PARTY_REPLACEMENT

        cleaned_sentences.append(replaced)

    return " ".join(cleaned_sentences), violations


def detect_only(text):
    """Pure detection pass (no rewrite) -- used for the final pre-serialization assertion."""
    _, violations = scan_and_clean(text)
    return violations

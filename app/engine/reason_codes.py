"""Fixed whitelist of reason_codes. Engine-controlled only -- the LLM polish
step never sees or touches this field, so it stays machine-checkable."""

TRANSACTION_MATCH = "transaction_match"
NO_TRANSACTION_MATCH = "no_transaction_match"
AMOUNT_MATCH = "amount_match"
AMOUNT_MISMATCH = "amount_mismatch"
STATUS_FAILED = "status_failed"
STATUS_PENDING = "status_pending"
STATUS_REVERSED = "status_reversed"
DUPLICATE_PAYMENT = "duplicate_payment"
PHISHING = "phishing"
CREDENTIAL_PROTECTION = "credential_protection"
EVIDENCE_CONSISTENT = "evidence_consistent"
EVIDENCE_INCONSISTENT = "evidence_inconsistent"
INSUFFICIENT_DATA = "insufficient_data"
HUMAN_REVIEW_REQUIRED = "human_review_required"
HIGH_VALUE = "high_value"

ALL = {
    TRANSACTION_MATCH, NO_TRANSACTION_MATCH, AMOUNT_MATCH, AMOUNT_MISMATCH,
    STATUS_FAILED, STATUS_PENDING, STATUS_REVERSED, DUPLICATE_PAYMENT, PHISHING,
    CREDENTIAL_PROTECTION, EVIDENCE_CONSISTENT, EVIDENCE_INCONSISTENT,
    INSUFFICIENT_DATA, HUMAN_REVIEW_REQUIRED, HIGH_VALUE,
}

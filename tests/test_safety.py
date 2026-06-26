from app import safety


def test_protective_pin_warning_is_preserved():
    text = "Please do not share your PIN or OTP with anyone, including our staff."
    cleaned, violations = safety.scan_and_clean(text)
    assert violations == []
    assert "do not share" in cleaned.lower()


def test_credential_request_is_rewritten():
    text = "Please share your OTP to verify your identity."
    cleaned, violations = safety.scan_and_clean(text)
    assert safety.VIOLATION_CREDENTIAL_REQUEST in violations
    assert "otp" not in cleaned.lower() or "never ask" in cleaned.lower()


def test_credential_request_variants():
    samples = [
        "Please provide your PIN number to verify.",
        "Kindly confirm your password to continue.",
        "What is your CVV?",
        "Enter your card number for verification.",
    ]
    for text in samples:
        _, violations = safety.scan_and_clean(text)
        assert safety.VIOLATION_CREDENTIAL_REQUEST in violations, f"missed: {text}"


def test_unauthorized_refund_confirmation_is_rewritten():
    samples = [
        "We will refund you within 24 hours.",
        "Your refund is confirmed.",
        "We have reversed the transaction.",
        "Your account is unblocked now.",
        "Refund has been processed.",
        "We guarantee the refund.",
    ]
    for text in samples:
        cleaned, violations = safety.scan_and_clean(text)
        assert safety.VIOLATION_UNAUTHORIZED_CONFIRMATION in violations, f"missed: {text}"
        assert "official channels" in cleaned.lower()


def test_safe_refund_language_is_not_flagged():
    text = "If your case is found eligible, any eligible amount will be returned through official channels."
    _, violations = safety.scan_and_clean(text)
    assert violations == []


def test_third_party_redirection_is_rewritten():
    text = "Please call this number +8801712345678 to resolve it quickly."
    cleaned, violations = safety.scan_and_clean(text)
    assert safety.VIOLATION_THIRD_PARTY_REDIRECTION in violations
    assert "official support" in cleaned.lower()


def test_detect_only_does_not_mutate_caller_expectations():
    text = "We will refund you immediately."
    violations = safety.detect_only(text)
    assert safety.VIOLATION_UNAUTHORIZED_CONFIRMATION in violations


def test_clean_text_has_no_violations():
    text = "Thank you for reaching out. Our team is reviewing your case."
    _, violations = safety.scan_and_clean(text)
    assert violations == []

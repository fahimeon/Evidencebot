from app.engine import classifier, i18n, matcher, router


def test_classify_wrong_transfer():
    case_type, _ = classifier.classify("I sent money to the wrong number by mistake.")
    assert case_type == "wrong_transfer"


def test_classify_phishing_takes_priority():
    case_type, _ = classifier.classify(
        "Someone called asking for my OTP, and I also want a refund on a wrong transfer."
    )
    assert case_type == "phishing_or_social_engineering"


def test_classify_bangla_agent_cash_in():
    case_type, _ = classifier.classify("আমি এজেন্টের কাছে ক্যাশ ইন করেছি কিন্তু টাকা পাইনি।")
    assert case_type == "agent_cash_in_issue"


def test_classify_vague_complaint_is_other():
    case_type, _ = classifier.classify("Something is wrong with my money. Please check.")
    assert case_type == "other"


def test_extract_amounts_bangla_digits():
    amounts = i18n.extract_amounts("আমি ৫০০০ টাকা পাঠিয়েছি")
    assert 5000.0 in amounts


def test_extract_amounts_ignores_phone_numbers():
    amounts = i18n.extract_amounts("call me at 01712345678 about the 500 taka issue")
    assert 500.0 in amounts
    assert 1712345.0 not in amounts


def test_matcher_amount_match():
    transactions = [
        {"transaction_id": "TXN-1", "amount": 5000, "type": "transfer", "status": "completed", "counterparty": "+8801711111111", "timestamp": "2026-01-01T00:00:00Z"},
        {"transaction_id": "TXN-2", "amount": 10000, "type": "cash_in", "status": "completed", "counterparty": "AGENT-1", "timestamp": "2026-01-01T00:00:00Z"},
    ]
    matched, confidence, _ = matcher.match_transaction("I sent 5000 to the wrong number.", transactions, "wrong_transfer")
    assert matched["transaction_id"] == "TXN-1"
    assert confidence > 0


def test_matcher_no_transaction_history_returns_none():
    matched, confidence, reasons = matcher.match_transaction("anything", [], "other")
    assert matched is None
    assert confidence == 0.0
    assert reasons == []


def test_matcher_ambiguous_different_counterparties_returns_none():
    transactions = [
        {"transaction_id": "TXN-1", "amount": 1000, "type": "transfer", "status": "completed", "counterparty": "+8801711111111", "timestamp": "2026-01-13T11:20:00Z"},
        {"transaction_id": "TXN-2", "amount": 1000, "type": "transfer", "status": "completed", "counterparty": "+8801822222222", "timestamp": "2026-01-13T19:45:00Z"},
    ]
    matched, confidence, _ = matcher.match_transaction("I sent 1000 yesterday but he says he didn't get it.", transactions, "wrong_transfer")
    assert matched is None


def test_matcher_duplicate_same_counterparty_picks_latest():
    transactions = [
        {"transaction_id": "TXN-1", "amount": 850, "type": "payment", "status": "completed", "counterparty": "BILLER-X", "timestamp": "2026-01-14T08:15:30Z"},
        {"transaction_id": "TXN-2", "amount": 850, "type": "payment", "status": "completed", "counterparty": "BILLER-X", "timestamp": "2026-01-14T08:15:42Z"},
    ]
    matched, _, _ = matcher.match_transaction("paid 850 but it deducted twice", transactions, "duplicate_payment")
    assert matched["transaction_id"] == "TXN-2"


def test_established_recipient_pattern_detected():
    matched_txn = {"transaction_id": "TXN-2", "counterparty": "+8801812345678"}
    transactions = [
        matched_txn,
        {"transaction_id": "TXN-1", "counterparty": "+8801812345678"},
    ]
    assert matcher.has_established_recipient_pattern(matched_txn, transactions) is True


def test_router_phishing_always_critical_and_human_review():
    severity = router.decide_severity("phishing_or_social_engineering", "insufficient_data")
    assert severity == "critical"
    human_review = router.decide_human_review("phishing_or_social_engineering", "insufficient_data", None)
    assert human_review is True


def test_router_payment_failed_does_not_force_human_review():
    matched_txn = {"transaction_id": "TXN-1", "amount": 1200, "status": "failed"}
    human_review = router.decide_human_review("payment_failed", "consistent", matched_txn)
    assert human_review is False


def test_router_refund_request_default_department_is_customer_support():
    department = router.decide_department("refund_request", "I changed my mind and want a refund.")
    assert department == "customer_support"


def test_router_contested_refund_routes_to_dispute_resolution():
    department = router.decide_department("refund_request", "This was an unauthorized charge, I never approved it.")
    assert department == "dispute_resolution"


def test_router_severity_downgrades_on_inconsistent_evidence():
    assert router.decide_severity("wrong_transfer", "consistent") == "high"
    assert router.decide_severity("wrong_transfer", "inconsistent") == "medium"

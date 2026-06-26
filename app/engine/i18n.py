"""Bangla/Banglish normalization helpers used by the classifier and matcher."""

import re

BENGALI_DIGIT_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Matches a standalone numeric token (2-7 digits, optional decimal), not embedded
# inside a longer alphanumeric run (so phone numbers and "11am"-style times are
# not mistaken for BDT amounts).
AMOUNT_PATTERN = re.compile(r"(?<![\w.])(\d{2,7}(?:[.,]\d{1,2})?)(?![\w])")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return text.translate(BENGALI_DIGIT_MAP).strip()


def extract_amounts(text: str) -> list:
    normalized = normalize_text(text)
    amounts = []
    for match in AMOUNT_PATTERN.finditer(normalized):
        raw = match.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if value > 0:
            amounts.append(value)
    return amounts


# Bangla/Banglish keyword cues per case_type, used alongside the English
# keyword patterns in classifier.py. Substring containment against the raw
# (non-normalized) complaint text, since Bangla has no case folding concerns.
BN_KEYWORDS = {
    "phishing_or_social_engineering": [
        "ওটিপি", "পিন কোড", "প্রতারণা", "ভুয়া কল", "লিংকে ক্লিক", "পুরস্কার জিতেছেন",
    ],
    "wrong_transfer": [
        "ভুল নম্বর", "ভুল নাম্বার", "ভুল ব্যক্তি", "ভুল জায়গায়",
    ],
    "duplicate_payment": [
        "দুইবার", "ডুপ্লিকেট", "দুই বার কেটেছে",
    ],
    "payment_failed": [
        "টাকা কেটে নিয়েছে", "ব্যর্থ", "পেমেন্ট ফেইল",
    ],
    "merchant_settlement_delay": [
        "সেটেলমেন্ট", "মার্চেন্ট পেমেন্ট",
    ],
    "agent_cash_in_issue": [
        "এজেন্ট", "ক্যাশ ইন",
    ],
    "refund_request": [
        "রিফান্ড", "টাকা ফেরত",
    ],
}

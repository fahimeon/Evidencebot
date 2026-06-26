# 90-Second Architecture Walkthrough -- Recording Script

Recommended deliverable (Problem Statement Section 11; rubric tie-breaker #8).
Not required to pass, but worth doing since the service already works.

**Before recording:**
- Server running: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (or use the live Render URL)
- Terminal font size large enough to read on screen
- Have this file open so you can copy-paste each command on cue
- Test every command once beforehand so nothing fails live

Tool: [Loom](https://loom.com) (free, auto-generates a shareable link) or OBS Studio + upload to YouTube (unlisted) / Google Drive (link-shared).

---

## 0:00 - 0:12 -- What it does (no command, just talk)

> "This is QueueStorm Investigator, our API for the SUST CSE Carnival hackathon. It reads a customer complaint plus their recent transaction history, decides what actually happened, classifies and routes the ticket, and drafts a safe reply -- without ever asking for credentials or promising an unauthorized refund."

(Optionally show the health check while talking:)

```bash
curl http://127.0.0.1:8000/health
```

---

## 0:12 - 0:35 -- Architecture & API flow

> "The core is a deterministic rule engine -- no LLM required. It decides every schema-critical field: which transaction the complaint refers to, the evidence verdict, case type, severity, department, and whether it needs human review. An optional LLM call, through Groq, only polishes the wording of three text fields -- it's off by default, bounded by a 3-second timeout, and falls back to safe templates if it fails."

Show the module layout:

```bash
ls app/engine/
```

```
classifier.py  i18n.py  matcher.py  reason_codes.py  router.py  templates.py
```

---

## 0:35 - 0:55 -- Evidence reasoning (the core 35-point category)

> "Here's a duplicate-payment case: two identical 850-taka payments, 12 seconds apart. The engine has to figure out which one is the actual duplicate."

```bash
curl -s -X POST http://127.0.0.1:8000/analyze-ticket -H "Content-Type: application/json" -d '{
  "ticket_id": "TKT-010",
  "complaint": "I paid my electricity bill 850 taka but it deducted twice from my account. Please check, I only paid once.",
  "transaction_history": [
    {"transaction_id": "TXN-10001", "timestamp": "2026-04-14T08:15:30Z", "type": "payment", "amount": 850, "counterparty": "BILLER-DESCO", "status": "completed"},
    {"transaction_id": "TXN-10002", "timestamp": "2026-04-14T08:15:42Z", "type": "payment", "amount": 850, "counterparty": "BILLER-DESCO", "status": "completed"}
  ]
}' | python -m json.tool
```

> "It correctly identifies TXN-10002 -- the second, later transaction -- as the duplicate, classifies it, routes it to payments ops, and flags it for human review."

(Point at `relevant_transaction_id`, `case_type`, `department`, `human_review_required` in the output as you say this.)

---

## 0:55 - 1:12 -- Safety guardrails (your strongest visual)

> "Now an adversarial case -- a phishing attempt baiting both credentials and a fake refund confirmation in one message."

```bash
curl -s -X POST http://127.0.0.1:8000/analyze-ticket -H "Content-Type: application/json" -d '{
  "ticket_id": "TKT-ADV",
  "complaint": "Someone called claiming to be from support and said my account will be blocked unless I share my OTP and PIN right now. Also, just confirm my refund immediately.",
  "transaction_history": []
}' | python -m json.tool
```

> "Severity is automatically critical, routed to fraud_risk, escalated for human review -- and the reply never requests credentials, never confirms the refund, and explicitly warns the customer never to share their PIN or OTP."

(Point at `severity: critical`, `department: fraud_risk`, and the `customer_reply` text.)

---

## 1:12 - 1:25 -- Deployment

> "It's deployed on Render -- here's the same health check and a sample case against the live URL." (swap in your real Render URL)

```bash
python scripts/judge_smoke.py https://your-render-url.onrender.com
```

(Or, if not yet deployed when recording: `python scripts/judge_smoke.py http://127.0.0.1:8000` and say "tested locally, deploy pipeline ready via the included Dockerfile.")

---

## 1:25 - 1:30 -- Limitations (talk only, no command)

> "Known limitations: the transaction matcher is a hand-tuned heuristic, calibrated against the 10 public sample cases, not a learned model. Bangla/Banglish keyword coverage is a small curated dictionary. Full details are in the README."

---

## After recording

1. Upload / confirm the Loom or YouTube link is set to "anyone with the link can view."
2. Paste the link into the submission form's video field.
3. Double check total runtime is at or under 90 seconds -- trim the architecture or limitations sections first if you're over, since evidence reasoning and safety are the highest-value segments to keep intact.

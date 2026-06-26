"""QueueStorm Investigator -- FastAPI service.

Pipeline order (POST /analyze-ticket), no shortcuts:
  1. validate input (Pydantic)
  2. rule/evidence engine          -> decides all schema-critical fields
  3. template prose generation      -> safe-by-construction draft text
  4. optional LLM polish            -> rewrites prose only, gated + timeout-bounded
  5. safety filter                  -> scans ALL text fields, rewrites unsafe patterns
  6. schema normalizer (output_guard) -> coerces enums/confidence/ids to valid ranges
  7. final safety assertion         -> pure re-check; any residual violation falls back
                                        to the deterministic hard-fallback response
  8. return JSON
"""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

load_dotenv()  # picks up a local .env file; no-op in deployments that set real env vars directly

from app import ai_polish, observability, output_guard, safety
from app.engine import classifier, matcher
from app.engine import router as case_router
from app.engine import templates
from app.models import AnalyzeRequest, AnalyzeResponse

logger = logging.getLogger("queuestorm")

MAX_COMPLAINT_CHARS = 5000
MAX_TRANSACTION_ENTRIES = 50

app = FastAPI(title="QueueStorm Investigator")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Per the problem statement: invalid JSON or missing/invalid required fields -> 400,
    # not FastAPI's default 422 (422 is reserved for semantically invalid input, e.g. empty complaint).
    return JSONResponse(status_code=400, content={"error": "Malformed or invalid request body."})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"error": "Internal server error."})


def _run_engine(payload: AnalyzeRequest) -> dict:
    complaint = (payload.complaint or "")[:MAX_COMPLAINT_CHARS]
    transactions = [t.model_dump() for t in (payload.transaction_history or [])][:MAX_TRANSACTION_ENTRIES]

    case_type, _matched_keywords = classifier.classify(complaint)

    duplicate_ids = matcher.detect_duplicates(transactions)

    matched_txn, match_confidence, _match_reasons = matcher.match_transaction(complaint, transactions, case_type)

    is_duplicate = bool(matched_txn) and matched_txn.get("transaction_id") in duplicate_ids
    if is_duplicate and case_type != "phishing_or_social_engineering":
        case_type = "duplicate_payment"
        # Re-run the match with the corrected case_type so the duplicate-aware
        # scoring bonus and tie-break (pick the later of the pair) applies.
        matched_txn, match_confidence, _match_reasons = matcher.match_transaction(complaint, transactions, case_type)

    evidence_verdict = matcher.derive_evidence_verdict(case_type, matched_txn, transactions)
    severity = case_router.decide_severity(case_type, evidence_verdict)
    department = case_router.decide_department(case_type, complaint)
    human_review_required = case_router.decide_human_review(case_type, evidence_verdict, matched_txn)
    confidence = case_router.decide_confidence(case_type, matched_txn, evidence_verdict, match_confidence)
    reason_codes = case_router.build_reason_codes(
        case_type, evidence_verdict, matched_txn, is_duplicate, human_review_required, severity
    )

    draft_agent_summary = templates.agent_summary(case_type, matched_txn, evidence_verdict)
    draft_next_action = templates.recommended_next_action(case_type, evidence_verdict, matched_txn)
    draft_customer_reply = templates.customer_reply(case_type, evidence_verdict, payload.language, matched_txn)

    result = {
        "ticket_id": payload.ticket_id,
        "relevant_transaction_id": matched_txn.get("transaction_id") if matched_txn else None,
        "evidence_verdict": evidence_verdict,
        "case_type": case_type,
        "severity": severity,
        "department": department,
        "agent_summary": draft_agent_summary,
        "recommended_next_action": draft_next_action,
        "customer_reply": draft_customer_reply,
        "human_review_required": human_review_required,
        "confidence": confidence,
        "reason_codes": reason_codes,
    }
    return result


@app.post("/analyze-ticket", response_model=AnalyzeResponse)
async def analyze_ticket(payload: AnalyzeRequest):
    # FastAPI parses + validates the body against AnalyzeRequest before this function
    # runs; malformed JSON or missing/invalid required fields are caught by the
    # RequestValidationError handler above (-> 400). response_model is declared here
    # purely for accurate OpenAPI/Swagger docs -- the actual response is always
    # returned as an explicit JSONResponse below so the engine's exact-field output
    # (already schema-correct via output_guard) is never re-validated/altered.
    timer = observability.Timer()
    with timer:
        if not payload.complaint or not payload.complaint.strip():
            return JSONResponse(status_code=422, content={"error": "complaint must not be empty."})

        try:
            result = _run_engine(payload)
        except Exception:
            logger.error("engine_failure ticket_id=%s", payload.ticket_id)
            result = output_guard.hard_fallback(payload.ticket_id)

        llm_used = False
        try:
            polished = await ai_polish.polish(
                {
                    "case_type": result["case_type"],
                    "evidence_verdict": result["evidence_verdict"],
                    "relevant_transaction_id": result["relevant_transaction_id"],
                    "complaint": payload.complaint,
                },
                {
                    "agent_summary": result["agent_summary"],
                    "recommended_next_action": result["recommended_next_action"],
                    "customer_reply": result["customer_reply"],
                },
            )
            if polished:
                result["agent_summary"] = polished.get("agent_summary", result["agent_summary"])
                result["recommended_next_action"] = polished.get(
                    "recommended_next_action", result["recommended_next_action"]
                )
                result["customer_reply"] = polished.get("customer_reply", result["customer_reply"])
                llm_used = True
        except Exception:
            pass

        safety_rewrites = 0
        for field in ("agent_summary", "recommended_next_action", "customer_reply"):
            cleaned, violations = safety.scan_and_clean(result.get(field, ""))
            if violations:
                result[field] = cleaned
                safety_rewrites += len(violations)
                result["human_review_required"] = True

        transaction_ids = {
            txn.transaction_id for txn in (payload.transaction_history or []) if txn.transaction_id
        }
        normalized = output_guard.normalize(result, payload.ticket_id, transaction_ids)

        # Step 7: final safety assertion -- pure detection pass, no rewrite.
        final_violations = []
        for field in ("agent_summary", "recommended_next_action", "customer_reply"):
            final_violations.extend(safety.detect_only(normalized.get(field, "")))
        if final_violations:
            normalized = output_guard.hard_fallback(payload.ticket_id)

    observability.log_request(
        ticket_id=payload.ticket_id,
        case_type=normalized.get("case_type"),
        evidence_verdict=normalized.get("evidence_verdict"),
        latency_ms=timer.elapsed_ms,
        llm_used=llm_used,
        safety_rewrites_count=safety_rewrites,
    )

    return JSONResponse(status_code=200, content=normalized)

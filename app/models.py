from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionEntry(BaseModel):
    """Lenient on purpose: malformed/unexpected values must never crash the API."""

    model_config = ConfigDict(extra="ignore")

    transaction_id: Optional[str] = None
    timestamp: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    counterparty: Optional[str] = None
    status: Optional[str] = None


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    complaint: str
    language: Optional[str] = None
    channel: Optional[str] = None
    user_type: Optional[str] = None
    campaign_context: Optional[str] = None
    transaction_history: Optional[List[TransactionEntry]] = Field(default_factory=list)
    metadata: Optional[dict] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    """Strict on purpose: the judge's schema checker should see exactly these fields, nothing extra."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    relevant_transaction_id: Optional[str] = None
    evidence_verdict: str
    case_type: str
    severity: str
    department: str
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: Optional[float] = None
    reason_codes: Optional[List[str]] = Field(default_factory=list)

from datetime import date, datetime
from enum import StrEnum
from ipaddress import ip_address
from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Status(StrEnum):
    queued = "queued"
    running = "running"
    awaiting_review = "awaiting_review"
    approved = "approved"
    rejected = "rejected"
    insufficient_information = "insufficient_information"
    conflicting_evidence = "conflicting_evidence"
    no_relevant_signal = "no_relevant_signal"
    failed = "failed"


class RunInput(Schema):
    prospect_name: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    designation: str = Field(min_length=1, max_length=200)
    company_website: str | None = Field(default=None, max_length=2048)
    product_service: str = Field(min_length=1, max_length=500)
    value_proposition: str = Field(min_length=1, max_length=2000)

    @field_validator("company_website")
    @classmethod
    def public_url(cls, v):
        if v is not None:
            validate_url(v)
        return v


def validate_url(v):
    u = urlsplit(v)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise ValueError("Public HTTP(S) URL required")
    host = u.hostname.lower()
    if (
        host == "localhost"
        or "." not in host
        or host.endswith((".local", ".internal", ".localhost"))
    ):
        raise ValueError("Public host required")
    try:
        addr = ip_address(host)
    except ValueError:
        return v
    if not addr.is_global:
        raise ValueError("Public host required")
    return v


class Source(Schema):
    id: str
    url: str
    title: str
    publisher: str
    origin_group: str
    source_type: Literal["primary", "reporting", "aggregator"]
    passage: str = Field(min_length=1, max_length=1500)
    published_at: date | None
    event_at: date | None
    date_basis: Literal["event", "publication", "unknown"]
    planned: bool

    @field_validator("url")
    @classmethod
    def url_valid(cls, v):
        return validate_url(v)


class Claim(Schema):
    id: str
    text: str
    source_ids: list[str] = Field(min_length=1)
    entity_match: bool
    verification: Literal["supported", "disputed", "unsupported"]
    kind: Literal["identity", "event", "context"]
    conflict_group: str | None


class Evidence(Schema):
    sources: list[Source] = Field(max_length=12)
    claims: list[Claim] = Field(max_length=30)
    identity_confidence: Literal["high", "low", "unknown"]
    material_identity_conflict: bool
    warnings: list[str]


class IdentityCheck(Schema):
    status: Literal["verified", "unverified", "equivalent", "mismatch", "conflicting"]
    claim_ids: list[str]
    source_ids: list[str]
    reasons: list[str]


class IdentityChecks(Schema):
    prospect_identity: IdentityCheck
    company_association: IdentityCheck
    title_match: IdentityCheck
    role_currentness: IdentityCheck
    role_claim_ids: list[str]


class ReviewedEvidence(Evidence):
    # Derived after semantic review; never requested as extraction-model output.
    identity_checks: IdentityChecks | None = None


class ExcerptSelection(Schema):
    passage_id: str | None
    claims: list[Claim] = Field(max_length=30)


class ClaimAssessment(Schema):
    claim_id: str
    source_ids: list[str]
    verification: Literal["supported", "disputed", "unsupported"]
    current_identity: bool
    designation_match: Literal["equivalent", "mismatch", "unverified", "not_applicable"]
    role_assertion: bool
    reason: str


class EvidenceReview(Schema):
    claims: list[ClaimAssessment] = Field(max_length=30)
    identity_confidence: Literal["high", "low", "unknown"]
    company_association_confidence: Literal["high", "low", "unknown"]
    identity_claim_ids: list[str]
    material_identity_conflict: bool
    warnings: list[str]


class Candidate(Schema):
    id: str
    claim_ids: list[str] = Field(min_length=1)
    fact_summary: str
    implication: str
    role_reason: str
    offer_reason: str
    role_relevance: int = Field(ge=0, le=3)
    offer_fit: int = Field(ge=0, le=3)


class Candidates(Schema):
    signals: list[Candidate] = Field(max_length=8)


class ClaimRef(Schema):
    field: Literal["subject", "body"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    claim_ids: list[str] = Field(min_length=1)


class DraftContent(Schema):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    claim_refs: list[ClaimRef]


class Quality(Schema):
    valid: bool
    findings: list[str]
    claim_refs: list[ClaimRef]


class Login(Schema):
    access_code: str = Field(max_length=200)


class Edit(Schema):
    expected_version: int = Field(ge=1)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class Decision(Schema):
    draft_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class Regenerate(Decision):
    instructions: str | None = Field(default=None, max_length=1000)


class ResearchResult(Schema):
    summary: str
    urls: dict[str, str]
    provider_call_id: str

    @field_validator("urls")
    @classmethod
    def valid_urls(cls, values):
        # Discard unsafe provider-discovered links; never retrieve them.
        accepted = {}
        for url, title in values.items():
            try:
                validate_url(url)
            except ValueError:
                continue
            accepted[url] = title
        return accepted


class ExtractionInput(Schema):
    input: RunInput
    pages: list[dict]
    today: str


class ReasoningProspect(Schema):
    prospect_name: str
    company_name: str
    designation: str | None
    company_website: str | None
    product_service: str
    value_proposition: str


class ReasoningSource(Schema):
    id: str
    source_type: Literal["primary", "reporting", "aggregator"]
    published_at: date | None
    event_at: date | None
    date_basis: Literal["event", "publication", "unknown"]
    planned: bool


class ReasoningEvidence(Schema):
    sources: list[ReasoningSource]
    claims: list[Claim]
    identity_checks: dict[str, str]
    relevance_basis: Literal["verified_role", "verified_company_context"]


class RelevanceInput(Schema):
    input: ReasoningProspect
    evidence: ReasoningEvidence


class GenerationInput(RelevanceInput):
    selected_signal: dict
    instructions: str | None
    prior_findings: list[str]


class AuditEvidence(ReasoningEvidence):
    passages: dict[str, str]


class QualityInput(RelevanceInput):
    evidence: AuditEvidence
    draft: DraftContent


# API output contracts. These are also published through /openapi.json.


class QueuedRun(Schema):
    run_id: str
    status: Status
    events_url: str


class RunSummary(Schema):
    id: str
    prospect_name: str
    company_name: str
    status: Status
    stage: str | None
    created_at: datetime
    finished_at: datetime | None
    outcome_reason: str | None


class RunHistory(Schema):
    items: list[RunSummary]
    next_cursor: str | None


class SourceView(Source):
    retrieved_at: datetime | None


class ScoredSignal(Candidate):
    quality: float
    age_days: int | None
    score: float
    eligible: bool
    rejection_reasons: list[str]
    selected: bool
    relevance_basis: Literal["verified_role", "verified_company_context"] | None = None


class DraftView(DraftContent):
    id: str
    version: int
    validation_status: Literal["pending", "valid", "invalid"]
    validation_findings: list[str]
    origin: Literal["generated", "edited"]
    created_at: datetime


class ReviewView(Schema):
    id: str
    draft_id: str
    action: Literal["approved", "rejected"]
    reason: str | None
    created_at: datetime


class SignalEvaluation(Schema):
    state: Literal["blocked", "evaluated"]
    reason: str | None
    gate_reasons: list[str]
    candidate_count: int
    eligible_count: int
    selected_signal_id: str | None
    relevance_basis: Literal["verified_role", "verified_company_context"] | None = None
    excluded_role_claim_ids: list[str] = Field(default_factory=list)


class RetrievalSource(Schema):
    url: str
    available: bool
    error: str | None = None


class RetrievalAttempt(Schema):
    phase: Literal["retrieval", "extraction"] | None = None
    followup: bool | None = None
    sources: list[RetrievalSource]
    selected_urls: list[str] = Field(default_factory=list)


class SourceDecision(Schema):
    source_id: str
    url: str
    accepted: bool
    reasons: list[str]
    quality: float | None
    fresh_signal_eligible: bool | None = None
    age_days: int | None = None
    date_warnings: list[str] = Field(default_factory=list)


class ClaimDecision(Schema):
    claim_id: str
    eligible: bool
    reasons: list[str]
    original_source_ids: list[str] = Field(default_factory=list)
    explanation: str | None = None
    designation_match: Literal["equivalent", "mismatch", "unverified", "not_applicable"] | None = None
    current_role_verified: bool | None = None


class EvidenceVerification(Schema):
    sources: list[SourceDecision]
    claims: list[ClaimDecision]
    identity_confidence: str
    gate_outcome: str | None
    gate_reasons: list[str]
    followup_requested: bool
    identity_checks: IdentityChecks | None = None


class ResearchDiagnostics(Schema):
    retrieval_attempts: list[RetrievalAttempt]
    verification_attempts: list[EvidenceVerification]


class RunDetail(RunSummary):
    input: RunInput
    prospect_id: str
    parent_run_id: str | None
    warnings: list[str]
    error: dict | None
    current_draft_id: str | None
    sources: list[SourceView]
    claims: list[Claim]
    identity_confidence: Literal["high", "low", "unknown"] | None
    identity_checks: IdentityChecks | None = None
    signals: list[ScoredSignal]
    drafts: list[DraftView]
    reviews: list[ReviewView]
    policy_version: str
    model_versions: dict
    provider_calls: list[dict]
    signal_evaluation: SignalEvaluation | None = None
    research_diagnostics: ResearchDiagnostics | None = None


class DashboardStats(Schema):
    prospects_researched: int
    drafts_generated: int
    pending_reviews: int
    incomplete_runs: int
    total_runs: int
    status_counts: dict[Status, int]

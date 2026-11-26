"""Verified-fact projection for scoring/writing; raw evidence stays in storage."""
from app.schemas import ReasoningProspect, ReasoningEvidence, ReasoningSource, AuditEvidence
from app.policy import usable_claims, relevance_basis, verified_role_claim_ids


def reasoning_context(prospect, evidence, audit=False):
    if getattr(evidence, "identity_checks", None) is None:
        raise RuntimeError("evidence_review_required")
    allowed = list(usable_claims(evidence).values())
    source_ids = {sid for c in allowed for sid in c.source_ids}
    sources = [s for s in evidence.sources if s.id in source_ids]
    checks = evidence.identity_checks
    states = {name: getattr(checks, name).status for name in (
        "prospect_identity", "company_association", "title_match", "role_currentness",
    )}
    if not verified_role_claim_ids(evidence):
        states["role_currentness"] = "unverified"
    # Never let the submitted title or role-bearing source titles/passages leak
    # into scoring or generation. The independent auditor can inspect original
    # retained quotations, but only allowed claims can support an assertion.
    subject = ReasoningProspect(**{**prospect, "designation": None, "company_website": None})
    values = dict(sources=[ReasoningSource(**{k: getattr(s, k) for k in ReasoningSource.model_fields}) for s in sources],
                  claims=allowed, identity_checks=states, relevance_basis=relevance_basis(evidence))
    context = AuditEvidence(**values, passages={s.id: s.passage for s in sources}) if audit else ReasoningEvidence(**values)
    return subject, context

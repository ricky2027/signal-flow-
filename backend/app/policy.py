from datetime import date
from app.schemas import Evidence, Candidate, DraftContent
from app.dates import date_in_text

QUALITY = {"primary": 1.0, "reporting": 0.8, "aggregator": 0.4}


def source_freshness(source, today=None):
    today = today or date.today()
    when = None if source.date_basis == "unknown" else source.event_at or source.published_at
    age = (today - when).days if when else None
    return age, age is not None and (0 <= age <= 180 or age < 0 and source.planned)


def has_fresh_event(evidence, today=None):
    """True when a supported, entity-matched event claim is backed by a source
    still inside the freshness window. Used to decide whether a follow-up pass
    should go hunting for a recent dated business event (the basis for a signal),
    independently of identity or role-currentness status."""
    sources = {s.id: s for s in evidence.sources}
    return any(
        c.kind == "event" and c.verification == "supported" and c.entity_match
        and any(sid in sources and source_freshness(sources[sid], today)[1] for sid in c.source_ids)
        for c in evidence.claims
    )


def eligible_claims(evidence: Evidence):
    sources = {s.id: s for s in evidence.sources}
    return {
        c.id: c
        for c in evidence.claims
        if c.entity_match
        and c.verification == "supported"
        and c.source_ids
        and all(i in sources for i in c.source_ids)
    }


def dated_primary(source, today=None):
    today = today or date.today()
    when = source.published_at or (source.event_at if source.date_basis == "event" else None)
    return source.source_type == "primary" and source.date_basis != "unknown" and when is not None and 0 <= (today - when).days <= 180 and date_in_text(when, source.passage)


def identity_verified(evidence):
    claims = eligible_claims(evidence)
    sources = {s.id: s for s in evidence.sources}
    checks = getattr(evidence, "identity_checks", None)
    if checks is None:
        ids = set(claims) if evidence.identity_confidence == "high" else set()
    else:
        if checks.prospect_identity.status != "verified" or checks.company_association.status != "verified":
            return False
        ids = set(checks.prospect_identity.claim_ids) & set(checks.company_association.claim_ids)
    return any(c.id in ids and c.kind == "identity" and any(sources[sid].source_type == "primary" for sid in c.source_ids) for c in claims.values())


def role_claim_ids(evidence):
    checks = getattr(evidence, "identity_checks", None)
    return {c.id for c in evidence.claims if c.kind == "identity"} | (set(checks.role_claim_ids) if checks else set())


def verified_role_claim_ids(evidence, today=None):
    checks = getattr(evidence, "identity_checks", None)
    if not checks or checks.role_currentness.status != "verified" or checks.title_match.status != "equivalent":
        return set()
    claims = eligible_claims(evidence)
    sources = {s.id: s for s in evidence.sources}
    return {cid for cid in checks.role_currentness.claim_ids if cid in claims and any(dated_primary(sources[sid], today) for sid in claims[cid].source_ids)}


def usable_claims(evidence, today=None):
    roles = role_claim_ids(evidence)
    verified = verified_role_claim_ids(evidence, today)
    return {cid: c for cid, c in eligible_claims(evidence).items() if cid not in roles or cid in verified}


def relevance_basis(evidence, today=None):
    return "verified_role" if verified_role_claim_ids(evidence, today) else "verified_company_context"


def evidence_gate(evidence: Evidence):
    claims = eligible_claims(evidence)
    reasons = []
    if evidence.material_identity_conflict:
        reasons.append("material_identity_conflict")
    checks = getattr(evidence, "identity_checks", None)
    if checks is None:
        if evidence.identity_confidence != "high":
            reasons.append("identity_confidence_not_high")
    else:
        if checks.prospect_identity.status != "verified":
            reasons.append("prospect_identity_unverified")
        if checks.company_association.status != "verified":
            reasons.append("company_association_unverified")
    if not any(c.kind == "identity" for c in claims.values()):
        reasons.append("no_supported_identity_claim")
    if not claims:
        reasons.append("no_eligible_claims")
    if not identity_verified(evidence) and not reasons:
        reasons.append("no_primary_identity_corroboration")
    outcome = (
        "conflicting_evidence" if evidence.material_identity_conflict
        else "insufficient_information" if reasons else None
    )
    return outcome, reasons


def rank(evidence: Evidence, candidates: list[Candidate], today: date | None = None):
    today = today or date.today()
    claims = usable_claims(evidence, today)
    sources = {s.id: s for s in evidence.sources}
    identity = identity_verified(evidence)
    rows = []
    for c in candidates:
        reasons = []
        if set(c.claim_ids) & (role_claim_ids(evidence) - verified_role_claim_ids(evidence, today)):
            reasons.append("unverified_role_reference")
        referenced = [claims[i] for i in c.claim_ids if i in claims]
        if len(referenced) != len(c.claim_ids) or not any(
            x.kind == "event" for x in referenced
        ):
            reasons.append("unsupported_event")
        event_sources = {
            sid: sources[sid]
            for claim in referenced
            if claim.kind == "event"
            for sid in claim.source_ids
        }
        dates = [None if s.date_basis == "unknown" else s.event_at or s.published_at for s in event_sources.values()]
        age = None
        if not dates or any(d is None for d in dates):
            reasons.append("unknown_date")
        else:
            age = max(0, max((today - d).days for d in dates))
            if any((today - (s.event_at or s.published_at)).days < 0 and not s.planned for s in event_sources.values()):
                reasons.append("unlabelled_future_event")
            if age > 180:
                reasons.append("outdated")
        quality = min(
            (QUALITY[s.source_type] for s in event_sources.values()), default=0
        )
        primary = any(s.source_type == "primary" for s in event_sources.values())
        origins = {
            s.origin_group
            for s in event_sources.values()
            if s.source_type == "reporting"
        }
        if quality < 0.8 or not (primary or len(origins) >= 2):
            reasons.append("weak_source_quality")
        if not identity:
            reasons.append("identity_unverified")
        if c.role_relevance < 2:
            reasons.append("low_role_relevance")
        if c.offer_fit < 2:
            reasons.append("low_offer_fit")
        score = round(
            10 * c.role_relevance
            + 10 * c.offer_fit
            + 25 * quality
            + 15 * max(0, 1 - (age if age is not None else 180) / 180),
            2,
        )
        if score < 70:
            reasons.append("below_threshold")
        rows.append(
            {
                **c.model_dump(),
                "quality": quality,
                "age_days": age,
                "score": score,
                "eligible": not reasons,
                "rejection_reasons": reasons,
                "selected": False,
                "relevance_basis": relevance_basis(evidence, today),
            }
        )
    rows.sort(
        key=lambda r: (
            -r["score"],
            -r["quality"],
            r["age_days"] if r["age_days"] is not None else 999999,
            r["id"],
        )
    )
    best = next((r for r in rows if r["eligible"]), None)
    precondition, _ = evidence_gate(evidence)
    if precondition:
        return rows, precondition
    if not best:
        disputed = {c.id for c in evidence.claims if c.verification == "disputed"}
        if any(
            disputed.intersection(c.claim_ids)
            and c.role_relevance >= 2
            and c.offer_fit >= 2
            for c in candidates
        ):
            return rows, "conflicting_evidence"
        return rows, "no_relevant_signal"
    best["selected"] = True
    return rows, None


def validate_refs(draft: DraftContent, evidence: Evidence):
    claims = usable_claims(evidence)
    issues = []
    for ref in draft.claim_refs:
        text = getattr(draft, ref.field)
        if ref.start >= ref.end or ref.end > len(text):
            issues.append("invalid_reference_offsets")
        if not set(ref.claim_ids).issubset(claims):
            issues.append("unsupported_claim_reference")
        sources = {s.id: s for s in evidence.sources}
        for key in ref.claim_ids:
            claim = claims.get(key)
            if claim and claim.kind == "event":
                for sid in claim.source_ids:
                    source = sources[sid]
                    date_value = None if source.date_basis == "unknown" else source.event_at or source.published_at
                    if date_value is None or (date.today() - date_value).days > 180:
                        issues.append("stale_or_undated_event_reference")
                    elif date_value > date.today() and not source.planned:
                        issues.append("unlabelled_future_event")
    if not draft.claim_refs:
        issues.append("missing_claim_references")
    return sorted(set(issues))

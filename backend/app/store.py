from sqlalchemy import select, func
from app.models import (
    Event,
    Artifact,
    Draft,
    Review,
    SourceRecord,
    ClaimRecord,
    ClaimSource,
    SignalRecord,
    ProviderCall,
    uid,
)


def event(db, run, kind, stage=None, payload=None):
    run.event_sequence += 1
    db.add(
        Event(
            run_id=run.id,
            sequence=run.event_sequence,
            type=kind,
            stage=stage,
            payload=payload or {},
        )
    )


def save_artifact(db, run_id, kind, data):
    if kind in ("evidence", "preliminary_evidence"):
        from app.schemas import ReviewedEvidence
        from app.retrieval import canonical_url

        parsed = ReviewedEvidence.model_validate(data)
        source_ids = {s.id for s in parsed.sources}
        if len(source_ids) != len(parsed.sources) or len({canonical_url(s.url) for s in parsed.sources}) != len(parsed.sources):
            raise ValueError("duplicate_evidence_source")
        if len({c.id for c in parsed.claims}) != len(parsed.claims):
            raise ValueError("duplicate_evidence_claim")
        if any(not set(c.source_ids).issubset(source_ids) for c in parsed.claims):
            raise ValueError("dangling_evidence_source_reference")
    db.add(Artifact(run_id=run_id, kind=kind, data=data))
    if kind == "evidence":
        sources = {}
        for source in data["sources"]:
            row = SourceRecord(
                id=uid(),
                run_id=run_id,
                source_key=source["id"],
                url=source["url"],
                data=source,
            )
            sources[source["id"]] = row.id
            db.add(row)
        db.flush()
        for claim in data["claims"]:
            row = ClaimRecord(
                id=uid(), run_id=run_id, claim_key=claim["id"], data=claim
            )
            db.add(row)
            db.flush()
            for source_key in set(claim["source_ids"]):
                db.add(ClaimSource(claim_id=row.id, source_id=sources[source_key]))
    elif kind == "signals":
        for signal in data["signals"]:
            db.add(SignalRecord(run_id=run_id, data=signal))


def latest(db, run_id, kind):
    rows = db.scalars(
        select(Artifact)
        .where(Artifact.run_id == run_id, Artifact.kind == kind)
        .order_by(Artifact.created_at, Artifact.id)
    ).all()
    return rows[-1].data if rows else None


def new_draft(db, run, data, origin, valid=False, findings=None):
    version = (
        db.scalar(select(func.max(Draft.version)).where(Draft.run_id == run.id)) or 0
    ) + 1
    draft = Draft(
        id=uid(),
        run_id=run.id,
        version=version,
        data=data,
        origin=origin,
        validation_status="valid" if valid else "pending",
        validation_findings=findings or [],
    )
    db.add(draft)
    run.current_draft_id = draft.id
    run.status = "awaiting_review"
    event(db, run, "draft.created", payload={"version": version})
    return draft


def draft_json(d):
    return {
        "id": d.id,
        "version": d.version,
        **d.data,
        "validation_status": d.validation_status,
        "validation_findings": d.validation_findings,
        "origin": d.origin,
        "created_at": d.created_at,
    }


def summary(r):
    return {
        "id": r.id,
        "prospect_name": r.input["prospect_name"],
        "company_name": r.input["company_name"],
        "status": r.status,
        "stage": r.stage,
        "created_at": r.created_at,
        "finished_at": r.finished_at,
        "outcome_reason": r.outcome_reason,
    }


def detail(db, r):
    evidence = latest(db, r.id, "evidence") or {}
    confidence = evidence.get("identity_confidence")
    identity_checks = latest(db, r.id, "identity_checks") or evidence.get("identity_checks")
    if identity_checks:
        confidence = "high" if identity_checks["prospect_identity"]["status"] == "verified" else "low"
    warnings = list(r.warnings)
    signals = latest(db, r.id, "signals") or {}
    diagnostics = db.scalars(select(Artifact).where(
        Artifact.run_id == r.id,
        Artifact.kind.in_(("retrieval_summary", "evidence_verification", "extraction_failures")),
    ).order_by(Artifact.created_at, Artifact.id)).all()
    reviews = db.scalars(
        select(Review).where(Review.run_id == r.id).order_by(Review.created_at)
    ).all()
    source_rows = {
        s.source_key: s
        for s in db.scalars(select(SourceRecord).where(SourceRecord.run_id == r.id))
    }
    # Preserve historical artifacts, but do not expose dangling source links as
    # usable API evidence. Never upgrade an old claim while trimming its refs.
    present = {s["id"] for s in evidence.get("sources", []) if s["id"] in source_rows}
    visible_claims = []
    for claim in evidence.get("claims", []):
        refs = [sid for sid in claim["source_ids"] if sid in present]
        missing = len(refs) != len(claim["source_ids"])
        if missing:
            warnings.append("stored_claim_references_missing_source")
        if refs:
            visible_claims.append({**claim, "source_ids": refs, "verification": "unsupported" if missing else claim["verification"]})
    if confidence == "high" and not any(
        c["kind"] == "identity" and c["verification"] == "supported" and c["entity_match"]
        for c in visible_claims
    ):
        confidence = "low" if evidence.get("claims") else "unknown"
        warnings.append("stored_identity_confidence_not_supported_by_retained_claims")
    return {
        **summary(r),
        "input": r.input,
        "prospect_id": r.prospect_id,
        "parent_run_id": r.parent_run_id,
        "warnings": list(dict.fromkeys(warnings)),
        "error": r.error,
        "current_draft_id": r.current_draft_id,
        "sources": [
            {
                **s,
                "retrieved_at": source_rows[s["id"]].retrieved_at
                if s["id"] in source_rows
                else None,
            }
            for s in evidence.get("sources", []) if s["id"] in present
        ],
        "claims": visible_claims,
        "identity_confidence": confidence,
        "identity_checks": identity_checks,
        "signals": signals.get("signals", []),
        "signal_evaluation": latest(db, r.id, "signal_evaluation"),
        "research_diagnostics": {
            "retrieval_attempts": [a.data for a in diagnostics if a.kind in ("retrieval_summary", "extraction_failures")],
            "verification_attempts": [a.data for a in diagnostics if a.kind == "evidence_verification"],
        },
        "drafts": [
            draft_json(d)
            for d in db.scalars(
                select(Draft).where(Draft.run_id == r.id).order_by(Draft.version)
            )
        ],
        "reviews": [
            {
                "id": x.id,
                "draft_id": x.draft_id,
                "action": x.action,
                "reason": x.reason,
                "created_at": x.created_at,
            }
            for x in reviews
        ],
        "policy_version": r.policy_version,
        "model_versions": r.model_versions,
        "provider_calls": [
            c.data
            for c in db.scalars(
                select(ProviderCall)
                .where(ProviderCall.run_id == r.id)
                .order_by(ProviderCall.created_at)
            )
        ],
    }

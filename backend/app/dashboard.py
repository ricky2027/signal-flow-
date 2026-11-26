"""Session-scoped aggregates; never infer drafts or research from run counts."""

from sqlalchemy import select, func
from app.models import Run, Draft
from app.schemas import Status


def dashboard(db, session_id):
    counts = dict(
        db.execute(
            select(Run.status, func.count())
            .where(Run.session_id == session_id)
            .group_by(Run.status)
        ).all()
    )
    researched = (
        "awaiting_review",
        "approved",
        "rejected",
        "insufficient_information",
        "conflicting_evidence",
        "no_relevant_signal",
    )
    # Run retries create new prospect IDs, so deduplicate explicit name/company input pairs.
    pairs = db.execute(
        select(Run.input).where(
            Run.session_id == session_id, Run.status.in_(researched)
        )
    ).scalars()
    unique = {
        (p["prospect_name"].strip().casefold(), p["company_name"].strip().casefold())
        for p in pairs
    }
    generated = (
        db.scalar(
            select(func.count())
            .select_from(Draft)
            .join(Run, Draft.run_id == Run.id)
            .where(Run.session_id == session_id, Draft.origin == "generated")
        )
        or 0
    )
    return {
        "prospects_researched": len(unique),
        "drafts_generated": generated,
        "pending_reviews": counts.get("awaiting_review", 0),
        "incomplete_runs": sum(
            counts.get(s, 0)
            for s in (
                "queued",
                "running",
                "failed",
                "insufficient_information",
                "conflicting_evidence",
                "no_relevant_signal",
            )
        ),
        "total_runs": sum(counts.values()),
        "status_counts": {s.value: counts.get(s.value, 0) for s in Status},
    }

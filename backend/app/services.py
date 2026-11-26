"""Transactional run/review services and deterministic admission controls."""

import hashlib
import json
from sqlalchemy import select, text
from app.config import settings
from app.errors import fail
from app.models import Quota, Idempotency, Prospect, Run, Job, Draft, uid, now
from app.store import event


def quota(db, key, limit):
    # PostgreSQL advisory xact locks serialize creation and increment across processes.
    if db.bind.dialect.name == "postgresql":
        lock_id = int.from_bytes(
            hashlib.sha256(key.encode()).digest()[:8], "big", signed=True
        )
        db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": lock_id})
    row = db.get(Quota, key, with_for_update=True)
    if not row:
        row = Quota(key=key, count=0)
        db.add(row)
        db.flush()
    if row.count >= limit:
        fail("quota_exceeded", "Daily quota reached", 429)
    row.count += 1


def check_idempotency(db, session, key, body):
    if not key or len(key) > 200:
        fail("idempotency_required", "Idempotency-Key (1–200 characters) required", 422)
    lock = f"idempotency:{session.id}:{key}"
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:id)"),
            {
                "id": int.from_bytes(
                    hashlib.sha256(lock.encode()).digest()[:8], "big", signed=True
                )
            },
        )
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    prior = db.scalar(
        select(Idempotency).where(
            Idempotency.session_id == session.id, Idempotency.key == key
        )
    )
    if prior and prior.fingerprint != fingerprint:
        fail("idempotency_conflict", "Key already used with another request")
    return prior, fingerprint


def reserve(db, session):
    day = now().date().isoformat()
    quota(db, "global:" + day, settings().global_daily_run_limit)
    quota(db, session.id + ":" + day, settings().max_runs_per_session_per_day)


def queued(run):
    return {
        "run_id": run.id,
        "status": run.status,
        "events_url": f"/api/v1/runs/{run.id}/events",
    }


def create_run(db, session, data, key, parent=None, scope="create"):
    prior, fp = check_idempotency(
        db, session, key, {"scope": scope, "input": data.model_dump()}
    )
    if prior:
        return db.get(Run, prior.run_id)
    reserve(db, session)
    prospect = Prospect(
        id=uid(),
        session_id=session.id,
        data={
            k: v
            for k, v in data.model_dump().items()
            if k not in ("product_service", "value_proposition")
        },
    )
    db.add(prospect)
    db.flush()
    run = Run(
        id=uid(),
        session_id=session.id,
        prospect_id=prospect.id,
        parent_run_id=parent,
        input=data.model_dump(),
        status="queued",
        event_sequence=0,
        model_versions={
            "research": settings().openai_research_model,
            "reasoning": settings().openai_reasoning_model,
            "prompt": "v1",
        },
    )
    db.add(run)
    db.flush()
    db.add(Job(run_id=run.id, kind="research"))
    db.add(Idempotency(session_id=session.id, key=key, fingerprint=fp, run_id=run.id))
    event(db, run, "run.queued", "validate")
    return run


def editable(db, run, version):
    if run.status not in ("awaiting_review", "approved", "rejected"):
        fail("invalid_state", "Run has no editable draft")
    draft = db.get(Draft, run.current_draft_id)
    if not draft or draft.version != version:
        fail("version_conflict", "Refresh the current draft")
    return draft


def reserve_approval(db, session):
    day = now().date().isoformat()
    quota(db, "approval-global:" + day, settings().global_daily_run_limit * 10)
    quota(
        db,
        "approval:" + session.id + ":" + day,
        settings().max_runs_per_session_per_day * 10,
    )

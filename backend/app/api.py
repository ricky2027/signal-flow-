import asyncio
import hashlib
import hmac
import json
import secrets
from types import SimpleNamespace
from datetime import timedelta
from uuid import uuid4
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession
from app.errors import fail
from app.services import (
    quota,
    check_idempotency,
    reserve,
    queued,
    create_run,
    reserve_approval,
    editable,
)
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Session,
    Run,
    Job,
    Review,
    Event,
    Idempotency,
    now,
)
from app.schemas import (
    DashboardStats,
    QueuedRun,
    RunHistory,
    RunDetail,
    DraftView,
    RunInput,
    Login,
    Edit,
    Decision,
    Regenerate,
    DraftContent,
    ReviewedEvidence as Evidence,
    Status,
)
from app.store import event, detail, summary, latest, new_draft, draft_json
from app.provider import OpenAIProvider
from app.agents.writing import check_draft

app = FastAPI(title="SIGNALFLOW", version="0.1.0")
prefix = "/api/v1"


@app.middleware("http")
async def safeguards(request, call_next):
    request.state.request_id = str(uuid4())
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("origin") != settings().app_origin:
            return JSONResponse(
                {
                    "error": {
                        "code": "origin_rejected",
                        "message": "Valid Origin required",
                        "retryable": False,
                        "request_id": request.state.request_id,
                    }
                },
                status_code=403,
            )
        # A custom header prevents cross-site HTML form submissions, including login CSRF.
        if request.headers.get("x-signalflow-client") != "web":
            return JSONResponse(
                {
                    "error": {
                        "code": "csrf_rejected",
                        "message": "X-Signalflow-Client: web required",
                        "retryable": False,
                        "request_id": request.state.request_id,
                    }
                },
                status_code=403,
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    data = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "http_error", "message": str(exc.detail), "retryable": False}
    )
    return JSONResponse(
        {"error": {**data, "request_id": request.state.request_id}},
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = {".".join(str(x) for x in e["loc"]): [e["msg"]] for e in exc.errors()}
    return JSONResponse(
        {
            "error": {
                "code": "validation_error",
                "message": "Invalid input",
                "field_errors": fields,
                "retryable": False,
                "request_id": request.state.request_id,
            }
        },
        status_code=422,
    )


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    return JSONResponse(
        {
            "error": {
                "code": "internal_error",
                "message": "Request failed; retry or inspect server health",
                "retryable": True,
                "request_id": getattr(request.state, "request_id", "unknown"),
            }
        },
        status_code=500,
    )


def db_session():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise


def digest(token):
    return hmac.new(
        settings().session_secret.get_secret_value().encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def owner(request: Request, db: DBSession = Depends(db_session)):
    token = request.cookies.get("signalflow_session")
    if not token:
        fail("session_required", "Sign in to continue", 401)
    session = db.scalar(
        select(Session).where(
            Session.token_hash == digest(token), Session.expires_at > now()
        )
    )
    if not session:
        fail("session_expired", "Sign in again", 401)
    return session


def owned(db, run_id, session, lock=False):
    stmt = select(Run).where(Run.id == run_id, Run.session_id == session.id)
    run = db.scalar(stmt.with_for_update() if lock else stmt)
    if not run:
        fail("not_found", "Run not found", 404)
    return run


@app.post(prefix + "/session")
def login(
    body: Login,
    request: Request,
    response: Response,
    db: DBSession = Depends(db_session),
):
    cfg = settings()
    if (
        len(cfg.session_secret.get_secret_value()) < 32
        or not cfg.demo_access_code.get_secret_value()
    ):
        fail(
            "configuration_missing",
            "Configure session secret and demo access code",
            503,
        )
    # Persistent per-client hourly attempts, including unsuccessful logins.
    client = request.client.host if request.client else "unknown"
    quota(
        db,
        "login:"
        + hashlib.sha256(client.encode()).hexdigest()
        + ":"
        + now().strftime("%Y-%m-%d-%H"),
        20,
    )
    db.commit()
    if not secrets.compare_digest(
        body.access_code, cfg.demo_access_code.get_secret_value()
    ):
        fail("invalid_access_code", "Invalid access code", 401)
    token = secrets.token_urlsafe(32)
    db.add(Session(token_hash=digest(token), expires_at=now() + timedelta(days=7)))
    db.commit()
    response.set_cookie(
        "signalflow_session",
        token,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="strict",
        max_age=604800,
    )
    return {"authenticated": True}


@app.post(prefix + "/runs", status_code=202, response_model=QueuedRun)
def submit(
    body: RunInput,
    session=Depends(owner),
    db: DBSession = Depends(db_session),
    idempotency_key: str | None = Header(None),
):
    run = create_run(db, session, body, idempotency_key)
    db.commit()
    return queued(run)


@app.get(prefix + "/runs", response_model=RunHistory)
def history(
    session=Depends(owner),
    db: DBSession = Depends(db_session),
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    status: Status | None = None,
):
    stmt = select(Run).where(Run.session_id == session.id)
    if status:
        stmt = stmt.where(Run.status == status.value)
    if cursor:
        last = owned(db, cursor, session)
        stmt = stmt.where(
            (Run.created_at < last.created_at)
            | ((Run.created_at == last.created_at) & (Run.id < last.id))
        )
    rows = db.scalars(
        stmt.order_by(Run.created_at.desc(), Run.id.desc()).limit(limit + 1)
    ).all()
    return {
        "items": [summary(r) for r in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }


@app.get(prefix + "/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, session=Depends(owner), db: DBSession = Depends(db_session)):
    return detail(db, owned(db, run_id, session))


@app.get(prefix + "/runs/{run_id}/events")
def stream(
    run_id: str,
    session=Depends(owner),
    db: DBSession = Depends(db_session),
    after: int = Query(0, ge=0),
    last_event_id: int | None = Header(None, ge=0),
):
    owned(db, run_id, session)
    stream_owner = SimpleNamespace(id=session.id)
    db.rollback()

    async def events():
        cursor = max(after, last_event_id or 0)
        ticks = 0
        while True:
            # Never keep a request DB transaction alive while waiting on a browser.
            with SessionLocal() as connection:
                run = owned(connection, run_id, stream_owner)
                rows = connection.scalars(
                    select(Event)
                    .where(Event.run_id == run_id, Event.sequence > cursor)
                    .order_by(Event.sequence)
                    .limit(100)
                ).all()
                frames = []
                for row in rows:
                    cursor = row.sequence
                    payload = jsonable_encoder(
                        {
                            "run_id": run_id,
                            "sequence": row.sequence,
                            "type": row.type,
                            "stage": row.stage,
                            "occurred_at": row.occurred_at,
                            "payload": row.payload,
                        }
                    )
                    frames.append(
                        f"id: {row.sequence}\nevent: {row.type}\ndata: {json.dumps(payload)}\n\n"
                    )
                done = (
                    run.status not in ("queued", "running")
                    and cursor >= run.event_sequence
                )
            for frame in frames:
                yield frame
            if done:
                return
            ticks += 1
            if ticks % 15 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )


@app.patch(prefix + "/runs/{run_id}/draft", response_model=DraftView)
def edit(
    run_id: str, body: Edit, session=Depends(owner), db: DBSession = Depends(db_session)
):
    run = owned(db, run_id, session, True)
    editable(db, run, body.expected_version)
    draft = new_draft(
        db,
        run,
        {"subject": body.subject, "body": body.body, "claim_refs": []},
        "edited",
    )
    db.commit()
    return draft_json(draft)


@app.post(prefix + "/runs/{run_id}/reject", response_model=RunDetail)
def reject(
    run_id: str,
    body: Decision,
    session=Depends(owner),
    db: DBSession = Depends(db_session),
):
    run = owned(db, run_id, session, True)
    draft = editable(db, run, body.draft_version)
    db.add(
        Review(
            run_id=run.id,
            draft_id=draft.id,
            session_id=session.id,
            action="rejected",
            reason=body.reason,
        )
    )
    run.status = "rejected"
    event(db, run, "run.status_changed", payload={"status": "rejected"})
    db.commit()
    return detail(db, run)


@app.post(prefix + "/runs/{run_id}/approve", response_model=RunDetail)
async def approve(
    run_id: str,
    body: Decision,
    session=Depends(owner),
    db: DBSession = Depends(db_session),
):
    run = owned(db, run_id, session)
    draft = editable(db, run, body.draft_version)
    if run.status == "approved":
        return detail(db, run)
    reserve_approval(db, session)
    db.commit()
    snapshot = DraftContent.model_validate(draft.data)
    evidence = Evidence.model_validate(latest(db, run_id, "evidence"))
    prospect = run.input
    original_draft_id = draft.id
    original_sequence = run.event_sequence
    # Release DB transaction during paid provider validation; recheck version/state after.
    db.rollback()
    from app.models import ProviderCall

    def audit(data):
        with SessionLocal.begin() as audit_db:
            audit_db.add(ProviderCall(run_id=run_id, data=data))

    try:
        provider = OpenAIProvider(audit)
        try:
            async with asyncio.timeout(60):
                corrected, issues = await check_draft(
                    provider, snapshot, evidence, prospect
                )
        finally:
            await provider.close()
    except Exception:
        fail(
            "approval_validation_unavailable",
            "Grounding validation unavailable; draft remains unapproved",
            503,
        )
    run = owned(db, run_id, session, True)
    draft = editable(db, run, body.draft_version)
    if draft.id != original_draft_id or run.event_sequence != original_sequence:
        fail("version_conflict", "Run changed during validation")
    draft.data = corrected.model_dump(mode="json")
    draft.validation_findings = issues
    draft.validation_status = "invalid" if issues else "valid"
    if issues:
        db.commit()
        fail("unsupported_content", "; ".join(issues), 422)
    run.status = "approved"
    db.add(
        Review(
            run_id=run.id,
            draft_id=draft.id,
            session_id=session.id,
            action="approved",
            reason=body.reason,
        )
    )
    event(db, run, "run.status_changed", payload={"status": "approved"})
    db.commit()
    return detail(db, run)


@app.post(
    prefix + "/runs/{run_id}/regenerate", status_code=202, response_model=QueuedRun
)
def regenerate(
    run_id: str,
    body: Regenerate,
    session=Depends(owner),
    db: DBSession = Depends(db_session),
    idempotency_key: str | None = Header(None),
):
    prior, fp = check_idempotency(
        db,
        session,
        idempotency_key,
        {"scope": run_id + ":regenerate", **body.model_dump()},
    )
    if prior:
        return queued(owned(db, prior.run_id, session))
    run = owned(db, run_id, session, True)
    editable(db, run, body.draft_version)
    from app.policy import rank
    from app.schemas import Candidate

    evidence = Evidence.model_validate(latest(db, run_id, "evidence"))
    stored = latest(db, run_id, "signals")["signals"]
    candidates = [
        Candidate.model_validate(
            {k: v for k, v in s.items() if k in Candidate.model_fields}
        )
        for s in stored
    ]
    _, outcome = rank(evidence, candidates)
    if outcome:
        fail("evidence_expired", "Start a new research run")
    reserve(db, session)
    run.status = "queued"
    run.error = None
    run.finished_at = None
    db.add(Job(run_id=run.id, kind="regenerate", instructions=body.instructions))
    db.add(
        Idempotency(
            session_id=session.id, key=idempotency_key, fingerprint=fp, run_id=run.id
        )
    )
    event(db, run, "run.queued", payload={"kind": "regenerate"})
    db.commit()
    return queued(run)


@app.post(prefix + "/runs/{run_id}/retry", status_code=202, response_model=QueuedRun)
def retry(
    run_id: str,
    session=Depends(owner),
    db: DBSession = Depends(db_session),
    idempotency_key: str | None = Header(None),
):
    original = owned(db, run_id, session)
    if original.status != "failed":
        fail("invalid_state", "Only failed runs can be retried")
    run = create_run(
        db,
        session,
        RunInput.model_validate(original.input),
        idempotency_key,
        parent=run_id,
        scope=run_id + ":retry",
    )
    db.commit()
    return queued(run)


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: DBSession = Depends(db_session)):
    cfg = settings()
    if (
        not cfg.openai_api_key.get_secret_value()
        or len(cfg.session_secret.get_secret_value()) < 32
        or not cfg.demo_access_code.get_secret_value()
    ):
        fail("configuration_missing", "Set OpenAI key and session configuration", 503)
    try:
        db.execute(text("SELECT 1 FROM runs LIMIT 1"))
    except Exception:
        fail("database_unavailable", "Database or migrations unavailable", 503)
    return {"status": "ready", "provider_access": "not_checked"}


@app.get(prefix + "/dashboard", response_model=DashboardStats)
def get_dashboard(session=Depends(owner), db: DBSession = Depends(db_session)):
    from app.dashboard import dashboard

    return dashboard(db, session.id)

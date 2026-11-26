"""Durable PostgreSQL queue worker. Run separately from HTTP process."""

import asyncio
from contextlib import suppress
from datetime import timedelta
from sqlalchemy import select
from app.db import SessionLocal
from app.config import settings
from app.models import Run, Job, ProviderCall, now, uid
from app.store import event, save_artifact, latest, new_draft
from app.provider import OpenAIProvider
from app.graph import build_graph

LEASE_SECONDS = 45


class LostLease(RuntimeError):
    pass


class Context:
    def __init__(self, factory, run_id, job_id, owner, provider=None):
        self.factory = factory
        self.run_id = run_id
        self.job_id = job_id
        self.owner = owner
        self.config = settings()
        self.provider = provider or OpenAIProvider(self.audit, self.config)

    def locked(self, db):
        job = db.scalar(select(Job).where(Job.id == self.job_id).with_for_update())
        if (
            not job
            or job.status != "leased"
            or job.lease_owner != self.owner
            or job.lease_expires_at <= now()
        ):
            raise LostLease()
        return db.scalar(select(Run).where(Run.id == self.run_id).with_for_update())

    def event(self, kind, stage, payload=None):
        with self.factory.begin() as db:
            run = self.locked(db)
            run.stage = stage
            event(db, run, kind, stage, payload)

    def save(self, kind, data):
        with self.factory.begin() as db:
            run = self.locked(db)
            save_artifact(db, run.id, kind, data)
            event(
                db,
                run,
                "research.updated" if kind == "research" else "stage.result",
                run.stage,
                {"artifact": kind},
            )

    def audit(self, data):
        with self.factory.begin() as db:
            self.locked(db)
            db.add(ProviderCall(run_id=self.run_id, data=data))


def reap(factory=SessionLocal):
    with factory.begin() as db:
        jobs = db.scalars(
            select(Job)
            .where(Job.status == "leased", Job.lease_expires_at < now())
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            job.status = "failed"
            run = db.scalar(select(Run).where(Run.id == job.run_id).with_for_update())
            run.status = "failed"
            run.finished_at = now()
            run.error = {"code": "worker_interrupted", "retryable": True}
            event(db, run, "run.failed", run.stage, run.error)


def claim(factory=SessionLocal):
    reap(factory)
    with factory.begin() as db:
        job = db.scalar(
            select(Job)
            .where(Job.status == "queued")
            .order_by(Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.status = "leased"
        job.lease_owner = uid()
        job.lease_expires_at = now() + timedelta(seconds=LEASE_SECONDS)
        run = db.scalar(select(Run).where(Run.id == job.run_id).with_for_update())
        run.status = "running"
        run.started_at = now()
        run.finished_at = None
        event(db, run, "run.status_changed", payload={"status": "running"})
        return job.id, job.run_id, job.lease_owner, job.kind, job.instructions


async def heartbeat(ctx):
    while True:
        await asyncio.sleep(10)
        with ctx.factory.begin() as db:
            ctx.locked(db)
            job = db.get(Job, ctx.job_id)
            job.lease_expires_at = now() + timedelta(seconds=LEASE_SECONDS)


async def execute(ticket, factory=SessionLocal, provider=None):
    job_id, run_id, owner, kind, instructions = ticket
    ctx = None
    beat = None
    try:
        ctx = Context(factory, run_id, job_id, owner, provider)
        beat = asyncio.create_task(heartbeat(ctx))
        with factory() as db:
            run = db.get(Run, run_id)
            initial = {"input": run.input, "instructions": instructions}
            if kind == "regenerate":
                initial["evidence"] = latest(db, run_id, "evidence")
        async with asyncio.timeout(ctx.config.run_timeout_seconds):
            result = await build_graph(ctx, kind == "regenerate").ainvoke(initial)
        with factory.begin() as db:
            run = ctx.locked(db)
            run.status = result.get("outcome") or "awaiting_review"
            run.outcome_reason = (
                (result.get("outcome_reason") or run.status)
                if run.status != "awaiting_review"
                else None
            )
            run.finished_at = now()
            run.warnings = result.get("evidence", {}).get("warnings", [])
            if run.status == "awaiting_review":
                new_draft(db, run, result["draft"], "generated", valid=True)
            if run.status == "failed":
                run.error = {
                    "code": "draft_grounding_failed",
                    "retryable": False,
                    "findings": result.get("findings", []),
                }
            db.get(Job, job_id).status = "done"
            event(db, run, "run.status_changed", run.stage, {"status": run.status})
    except Exception as exc:
        with factory.begin() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job and job.status == "leased" and job.lease_owner == owner:
                job.status = "failed"
                run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
                run.status = "failed"
                run.finished_at = now()
                code = (
                    "run_timeout"
                    if isinstance(exc, TimeoutError)
                    else (
                        str(exc)
                        if isinstance(exc, RuntimeError)
                        and str(exc)
                        in (
                            "openai_credentials_missing",
                            "research_budget_exceeded",
                            "search_tool_not_executed",
                            "provider_response_incomplete",
                            "provider_schema_or_refusal",
                            "evidence_extraction_failed",
                        )
                        else type(exc).__name__
                    )
                )
                run.error = {"code": code, "retryable": True}
                event(db, run, "run.failed", run.stage, run.error)
    finally:
        if beat:
            beat.cancel()
            with suppress(asyncio.CancelledError, LostLease):
                await beat
        if ctx and hasattr(ctx.provider, "close"):
            await ctx.provider.close()


async def main():
    while True:
        ticket = claim()
        if ticket:
            await execute(ticket)
        else:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())

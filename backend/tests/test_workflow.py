import asyncio
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.models import Session, Prospect, Run, Job, Event, now, uid, Draft, SignalRecord
from app.store import detail, latest
from app.worker import claim, execute, reap
from tests.fixtures import INPUT, FixtureProvider, PASSAGE


def enqueue(factory):
    with factory.begin() as db:
        owner = Session(
            id=uid(), token_hash=uid(), expires_at=now() + timedelta(days=1)
        )
        db.add(owner)
        db.flush()
        prospect = Prospect(id=uid(), session_id=owner.id, data=INPUT)
        db.add(prospect)
        db.flush()
        run = Run(
            id=uid(),
            session_id=owner.id,
            prospect_id=prospect.id,
            input=INPUT,
            status="queued",
        )
        db.add(run)
        db.flush()
        db.add(Job(run_id=run.id))
        return run.id


@pytest.mark.parametrize(
    "case,status",
    [
        ("happy", "awaiting_review"),
        ("missing", "insufficient_information"),
        ("conflict", "conflicting_evidence"),
        ("stale", "no_relevant_signal"),
        ("irrelevant", "no_relevant_signal"),
        ("bad_quality", "failed"),
        ("invented_passage", "insufficient_information"),
    ],
)
def test_graph_persistence(factory, monkeypatch, case, status):
    async def fetch(url):
        return PASSAGE

    monkeypatch.setattr("app.retrieval.fetch", fetch)
    run_id = enqueue(factory)
    provider = FixtureProvider(case)
    ticket = claim(factory)
    assert ticket
    asyncio.run(execute(ticket, factory, provider))
    with factory() as db:
        run = db.get(Run, run_id)
        assert run.status == status, run.error
        events = db.scalars(
            select(Event).where(Event.run_id == run_id).order_by(Event.sequence)
        ).all()
        assert events and [x.sequence for x in events] == list(
            range(1, len(events) + 1)
        )
        drafts = db.scalars(select(Draft).where(Draft.run_id == run_id)).all()
        assert bool(drafts) == (status == "awaiting_review")
        output = detail(db, run)
        assert output["signals"] == [s.data for s in db.scalars(select(SignalRecord).where(SignalRecord.run_id == run_id))]
        if case in ("missing", "conflict", "invented_passage"):
            assert output["signal_evaluation"]["state"] == "blocked"
            assert output["signal_evaluation"]["gate_reasons"]
            assert not any(e.stage == "draft" for e in events)
            evaluation = next(e for e in events if e.stage == "evaluate_signals" and e.type == "stage.completed")
            assert evaluation.payload["evaluation_state"] == "blocked"
        if case == "invented_passage":
            decisions = output["research_diagnostics"]["verification_attempts"]
            assert len(decisions) == 2
            assert "passage_not_found" in decisions[-1]["sources"][0]["reasons"]
            assert decisions[-1]["claims"][0]["eligible"] is False
        if case == "happy":
            assert output["signals"][0]["selected"] is True
            assert output["signals"][0]["score"] >= 70
            assert output["signal_evaluation"]["candidate_count"] == 1
            assert output["signal_evaluation"]["selected_signal_id"] == "candidate"
            assert output["drafts"][0]["validation_status"] == "valid"
            assert output["drafts"][0]["claim_refs"][0]["claim_ids"] == ["event"]
            assert {"draft", "validate_draft"} <= {e.stage for e in events}
            assert latest(db, run_id, "evidence")["sources"][0]["url"] == output["sources"][0]["url"]
        if case == "bad_quality":
            assert (
                provider.quality_calls == 2
                and run.error["code"] == "draft_grounding_failed"
            )


def test_crash_reaper(factory):
    run_id = enqueue(factory)
    ticket = claim(factory)
    with factory.begin() as db:
        db.get(Job, ticket[0]).lease_expires_at = now() - timedelta(seconds=1)
    reap(factory)
    with factory() as db:
        assert db.get(Run, run_id).error["code"] == "worker_interrupted"

import asyncio
from datetime import timedelta
from app.models import Run, Job, now
from app.worker import claim, execute, Context, LostLease
from tests.test_workflow import enqueue
from tests.fixtures import FixtureProvider


def test_worker_deadline_persists_failure(factory, monkeypatch):
    class Slow(FixtureProvider):
        async def search(self, prospect):
            await asyncio.sleep(10)

    from app.config import settings

    monkeypatch.setattr(settings(), "run_timeout_seconds", 0.02)
    run_id = enqueue(factory)
    asyncio.run(execute(claim(factory), factory, Slow()))
    with factory() as db:
        assert db.get(Run, run_id).error["code"] == "run_timeout"


def test_lease_ownership_prevents_late_write(factory):
    import pytest

    run_id = enqueue(factory)
    ticket = claim(factory)
    ctx = Context(factory, run_id, ticket[0], ticket[2], FixtureProvider())
    with factory.begin() as db:
        db.get(Job, ticket[0]).lease_expires_at = now() - timedelta(seconds=1)
    with pytest.raises(LostLease):
        ctx.save("late", {"result": "must not persist"})

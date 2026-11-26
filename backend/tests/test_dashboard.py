import asyncio
from app.worker import claim, execute
from tests.fixtures import FixtureProvider, PASSAGE
from tests.test_api import client as client, create


def test_dashboard_aggregates(client, factory, monkeypatch):
    async def fetch(url):
        return PASSAGE

    monkeypatch.setattr("app.retrieval.fetch", fetch)
    assert client.get("/api/v1/dashboard").json()["total_runs"] == 0
    run_id = create(client)
    asyncio.run(execute(claim(factory), factory, FixtureProvider()))
    # A manual edit must not inflate generated draft counts.
    client.patch(
        f"/api/v1/runs/{run_id}/draft",
        json={"expected_version": 1, "subject": "Edited", "body": "Edited content"},
    )
    create(client, "duplicate-prospect")
    asyncio.run(execute(claim(factory), factory, FixtureProvider("missing")))
    data = client.get("/api/v1/dashboard").json()
    assert data["total_runs"] == 2
    assert data["prospects_researched"] == 1
    assert data["drafts_generated"] == 1
    assert data["pending_reviews"] == 1
    assert data["incomplete_runs"] == 1
    # Login creates a distinct owner, not a shared dashboard.
    client.post("/api/v1/session", json={"access_code": "test-access"})
    assert client.get("/api/v1/dashboard").json()["total_runs"] == 0

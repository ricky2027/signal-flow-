import asyncio
import pytest
from fastapi.testclient import TestClient
from app import api
from app.worker import claim, execute
from tests.fixtures import INPUT, FixtureProvider, PASSAGE

HEADERS = {"origin": "http://localhost:3000", "x-signalflow-client": "web"}


@pytest.fixture
def client(factory, monkeypatch):
    monkeypatch.setattr(api, "SessionLocal", factory)
    with TestClient(api.app, headers=HEADERS) as c:
        response = c.post("/api/v1/session", json={"access_code": "test-access"})
        assert response.status_code == 200, response.text
        yield c


def create(client, key="test-create"):
    result = client.post("/api/v1/runs", json=INPUT, headers={"Idempotency-Key": key})
    assert result.status_code == 202, result.text
    return result.json()["run_id"]


def test_submission_history_ownership(client, factory):
    run_id = create(client)
    assert create(client) == run_id
    conflict = client.post(
        "/api/v1/runs",
        json={**INPUT, "designation": "CEO"},
        headers={"Idempotency-Key": "test-create"},
    )
    assert conflict.status_code == 409
    history = client.get("/api/v1/runs").json()
    assert len(history["items"]) == 1 and history["items"][0]["status"] == "queued"
    assert client.get("/api/v1/runs/" + run_id).json()["input"] == INPUT
    assert (
        client.post("/api/v1/session", json={"access_code": "test-access"}).status_code
        == 200
    )
    assert client.get("/api/v1/runs/" + run_id).status_code == 404
    assert client.get("/api/v1/runs").json()["items"] == []


def test_review_edit_regenerate_events(client, factory, monkeypatch):
    async def fetch(url):
        return PASSAGE

    monkeypatch.setattr("app.retrieval.fetch", fetch)
    run_id = create(client)
    ticket = claim(factory)
    asyncio.run(execute(ticket, factory, FixtureProvider()))
    detail = client.get("/api/v1/runs/" + run_id).json()
    assert detail["status"] == "awaiting_review"
    assert len(detail["sources"]) == 1
    monkeypatch.setattr(api, "OpenAIProvider", lambda audit: FixtureProvider())
    approve = client.post(f"/api/v1/runs/{run_id}/approve", json={"draft_version": 1})
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
    edit = client.patch(
        f"/api/v1/runs/{run_id}/draft",
        json={
            "expected_version": 1,
            "subject": "Edited",
            "body": "Example Corp announced a new region. Could cost visibility help?",
        },
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["version"] == 2 and edit.json()["validation_status"] == "pending"
    assert (
        client.post(
            f"/api/v1/runs/{run_id}/approve", json={"draft_version": 1}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/runs/{run_id}/reject",
            json={"draft_version": 2, "reason": "Revise tone"},
        ).json()["status"]
        == "rejected"
    )
    regenerated = client.post(
        f"/api/v1/runs/{run_id}/regenerate",
        json={"draft_version": 2},
        headers={"Idempotency-Key": "regen"},
    )
    assert regenerated.status_code == 202, regenerated.text
    asyncio.run(execute(claim(factory), factory, FixtureProvider()))
    result = client.get("/api/v1/runs/" + run_id).json()
    assert result["status"] == "awaiting_review" and len(result["drafts"]) == 3
    stream = client.get(f"/api/v1/runs/{run_id}/events", headers={"Last-Event-ID": "0"})
    assert (
        stream.status_code == 200
        and "event: stage.started" in stream.text
        and "id: 1\n" in stream.text
    )
    last = int(stream.text.split("id: ")[-1].split("\n")[0])
    assert client.get(f"/api/v1/runs/{run_id}/events?after={last}").text == ""


def test_invalid_and_csrf(client):
    assert (
        client.post(
            "/api/v1/runs", json={**INPUT, "company_website": "http://127.0.0.1"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/runs", json=INPUT, headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/runs", json=INPUT).status_code == 422
    assert client.get("/api/v1/runs?limit=0").status_code == 422


def test_unsupported_edit_cannot_approve(client, factory, monkeypatch):
    async def fetch(url):
        return PASSAGE

    monkeypatch.setattr("app.retrieval.fetch", fetch)
    run_id = create(client)
    asyncio.run(execute(claim(factory), factory, FixtureProvider()))
    client.patch(
        f"/api/v1/runs/{run_id}/draft",
        json={
            "expected_version": 1,
            "subject": "False claim",
            "body": "Invented facts",
        },
    )
    monkeypatch.setattr(
        api, "OpenAIProvider", lambda audit: FixtureProvider("bad_quality")
    )
    result = client.post(f"/api/v1/runs/{run_id}/approve", json={"draft_version": 2})
    assert result.status_code == 422, result.text
    assert client.get("/api/v1/runs/" + run_id).json()["status"] == "awaiting_review"


def test_quota_and_retry(client, factory, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings(), "max_runs_per_session_per_day", 1)
    run_id = create(client)
    second = client.post(
        "/api/v1/runs", json=INPUT, headers={"Idempotency-Key": "second"}
    )
    assert second.status_code == 429
    assert create(client) == run_id  # replay never consumes quota
    monkeypatch.setattr(settings(), "max_runs_per_session_per_day", 10)

    class Broken(FixtureProvider):
        async def search(self, prospect):
            raise RuntimeError("provider_schema_or_refusal")

    asyncio.run(execute(claim(factory), factory, Broken()))
    result = client.get("/api/v1/runs/" + run_id).json()
    assert (
        result["status"] == "failed"
        and result["error"]["code"] == "provider_schema_or_refusal"
    )
    retried = client.post(
        f"/api/v1/runs/{run_id}/retry", headers={"Idempotency-Key": "retry"}
    )
    assert retried.status_code == 202
    child = client.get("/api/v1/runs/" + retried.json()["run_id"]).json()
    assert child["parent_run_id"] == run_id


def test_pagination_and_readiness(client):
    create(client, "one")
    create(client, "two")
    first = client.get("/api/v1/runs?limit=1").json()
    assert first["next_cursor"]
    second = client.get("/api/v1/runs?limit=1&cursor=" + first["next_cursor"]).json()
    assert (
        first["items"][0]["id"] != second["items"][0]["id"]
        and second["next_cursor"] is None
    )
    assert client.get("/health/live").json() == {"status": "ok"}

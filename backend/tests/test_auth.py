from datetime import timedelta
from http.cookies import SimpleCookie

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app import api
from app.config import settings
from app.models import Session, now

HEADERS = {"origin": "http://localhost:3000", "x-signalflow-client": "web"}


def test_login_retains_session_across_requests_and_clients(factory, monkeypatch):
    monkeypatch.setattr(api, "SessionLocal", factory)
    with TestClient(api.app, headers=HEADERS) as client:
        assert client.get("/api/v1/runs?limit=1").json()["error"]["code"] == "session_required"
        response = client.post("/api/v1/session", json={"access_code": "test-access"})
        assert response.status_code == 200
        cookie = SimpleCookie(response.headers["set-cookie"])["signalflow_session"]
        assert cookie["httponly"] and cookie["samesite"] == "strict"
        assert cookie["path"] == "/" and cookie["domain"] == ""
        assert cookie["max-age"] == "604800" and not cookie["secure"]
        assert client.get("/api/v1/runs?limit=1").status_code == 200
        assert client.get("/api/v1/dashboard").status_code == 200
        with factory() as db:
            session = db.scalar(select(Session))
            assert session.token_hash == api.digest(cookie.value)
            assert session.token_hash != cookie.value
            assert now() + timedelta(days=6) < session.expires_at <= now() + timedelta(days=7)
        # A browser reload must use the persisted row, not Python request memory.
        with TestClient(api.app, cookies=client.cookies) as reopened:
            assert reopened.get("/api/v1/runs?limit=1").status_code == 200


def test_invalid_code_creates_no_session_or_cookie(factory, monkeypatch):
    monkeypatch.setattr(api, "SessionLocal", factory)
    with TestClient(api.app, headers=HEADERS) as client:
        response = client.post("/api/v1/session", json={"access_code": "wrong-test-code"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_access_code"
        assert "set-cookie" not in response.headers
        assert client.get("/api/v1/runs?limit=1").status_code == 401
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(Session)) == 0


def test_expired_and_tampered_sessions_are_rejected(factory, monkeypatch):
    monkeypatch.setattr(api, "SessionLocal", factory)
    with TestClient(api.app, headers=HEADERS) as client:
        client.post("/api/v1/session", json={"access_code": "test-access"})
        with factory() as db:
            db.scalar(select(Session)).expires_at = now() - timedelta(seconds=1)
            db.commit()
        assert client.get("/api/v1/runs?limit=1").json()["error"]["code"] == "session_expired"
    with TestClient(api.app, cookies={"signalflow_session": "invalid-token"}) as client:
        assert client.get("/api/v1/runs?limit=1").status_code == 401


def test_production_cookie_remains_secure(factory, monkeypatch):
    monkeypatch.setattr(api, "SessionLocal", factory)
    monkeypatch.setattr(settings(), "cookie_secure", True)
    with TestClient(api.app, headers=HEADERS, base_url="https://testserver") as client:
        response = client.post("/api/v1/session", json={"access_code": "test-access"})
        assert SimpleCookie(response.headers["set-cookie"])["signalflow_session"]["secure"]
        assert client.get("/api/v1/runs?limit=1").status_code == 200

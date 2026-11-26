"""Real, secret-safe setup checks. No fixtures or fallback database.

Run from backend/: python -m app.check_setup --migrate --check-persistence
The minimal OpenAI Responses request incurs actual API usage.
"""

import argparse
import json
import secrets
from datetime import timedelta
from pathlib import Path

import httpx
from sqlalchemy import text

from app.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--check-persistence", action="store_true")
    args = parser.parse_args()
    cfg = settings()
    results = {
        "database_configured": bool(cfg.database_url),
        "openai_key_configured": bool(cfg.openai_api_key.get_secret_value()),
        "session_configured": len(cfg.session_secret.get_secret_value()) >= 32
        and bool(cfg.demo_access_code.get_secret_value()),
    }
    engine = None
    try:
        from app.db import make_engine

        engine = make_engine(cfg.database_url)
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT 1")) == 1
        results["database_connection"] = "passed"
        if args.migrate:
            from alembic import command
            from alembic.config import Config

            root = Path(__file__).resolve().parents[1]
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "alembic"))
            command.upgrade(config, "head")
            results["migrations"] = "passed"
        with engine.connect() as conn:
            results["migration_revision"] = conn.scalar(text("SELECT version_num FROM alembic_version"))
        if args.check_persistence:
            from sqlalchemy.orm import Session as DBSession
            from app.models import Session, now, uid

            # A private login-session probe, never a prospect/research result.
            probe_id, token = uid(), secrets.token_hex(32)
            try:
                with DBSession(engine) as db:
                    db.add(Session(id=probe_id, token_hash=token, expires_at=now() + timedelta(minutes=1)))
                    db.commit()
                engine.dispose()  # Read on a new connection after committed write.
                with DBSession(engine) as db:
                    probe = db.get(Session, probe_id)
                    assert probe is not None and secrets.compare_digest(probe.token_hash, token)
                results["committed_write_and_reconnected_read"] = "passed"
            finally:
                with DBSession(engine) as db:
                    probe = db.get(Session, probe_id)
                    if probe is not None:
                        db.delete(probe)
                        db.commit()
                results["probe_cleanup"] = "passed"
    except Exception as exc:
        # Raw DB/HTTP exception strings can contain credentials or connection URLs.
        results["database_error"] = type(exc).__name__
    finally:
        if engine is not None:
            engine.dispose()

    try:
        if not cfg.openai_api_key.get_secret_value():
            raise RuntimeError("missing_key")
        with httpx.Client(timeout=20) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": "Bearer " + cfg.openai_api_key.get_secret_value()},
                json={"model": cfg.openai_reasoning_model, "input": "Reply with OK.", "max_output_tokens": 16},
            )
            results["openai_http_status"] = response.status_code
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "completed":
                raise RuntimeError("incomplete_response")
            results["openai_minimal_response"] = "passed"
    except Exception as exc:
        results["openai_error"] = type(exc).__name__
    print(json.dumps(results, indent=2))
    return 1 if "database_error" in results or "openai_error" in results else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Test-only ASGI bridge for Node integration tests where TCP listeners are denied.
Uses real FastAPI/SQLAlchemy and an isolated database; never substitutes a provider.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from fastapi.testclient import TestClient
from app.api import app
from app.db import engine
from app.models import Base
from app.worker import claim, execute

Base.metadata.create_all(engine)
payload = json.loads(sys.stdin.read())
if payload.get("mode") == "events":
    from sqlalchemy import select
    from app.models import Event
    from app.db import SessionLocal

    with SessionLocal() as db:
        print(
            json.dumps(
                [
                    {
                        "run_id": e.run_id,
                        "sequence": e.sequence,
                        "type": e.type,
                        "stage": e.stage,
                        "occurred_at": e.occurred_at.isoformat(),
                        "payload": e.payload,
                    }
                    for e in db.scalars(
                        select(Event)
                        .where(Event.run_id == payload["run_id"])
                        .order_by(Event.sequence)
                    )
                ]
            )
        )
elif payload.get("mode") == "worker":
    ticket = claim()
    if ticket:
        asyncio.run(execute(ticket))
    print(json.dumps({"worked": bool(ticket)}))
else:
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.request(
            payload["method"],
            payload["path"],
            headers=payload.get("headers", {}),
            content=payload.get("body") or None,
        )
        try:
            body = response.json()
        except ValueError:
            body = response.text
        print(
            json.dumps(
                {
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": body,
                }
            )
        )

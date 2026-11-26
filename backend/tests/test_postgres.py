"""Optional real PostgreSQL integration, isolated in its own temporary schema."""

import os
from uuid import uuid4
import pytest


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not configured; real PostgreSQL not available",
)
def test_postgres_queue_and_json():
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.models import Base, Run
    from app.worker import claim
    from tests.test_workflow import enqueue

    schema = "sf_test_" + uuid4().hex
    admin = create_engine(os.environ["TEST_DATABASE_URL"])
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(
        os.environ["TEST_DATABASE_URL"],
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        run_id = enqueue(factory)
        assert claim(factory)[1] == run_id
        assert claim(factory) is None
        with factory() as db:
            run = db.get(Run, run_id)
            assert run.status == "running" and run.input["designation"] == "CFO"
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()

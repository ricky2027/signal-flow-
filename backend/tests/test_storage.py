from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from app.models import Base


def test_migration_upgrade_downgrade(tmp_path, monkeypatch):
    from app import db

    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    monkeypatch.setattr(db, "engine", engine)
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    command.upgrade(cfg, "head")
    assert set(Base.metadata.tables).issubset(inspect(engine).get_table_names())
    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()


def test_relational_evidence(factory, monkeypatch):
    import asyncio
    from sqlalchemy import select, func
    from app.models import SourceRecord, ClaimRecord, ClaimSource, SignalRecord
    from app.worker import claim, execute
    from tests.test_workflow import enqueue
    from tests.fixtures import FixtureProvider, PASSAGE

    async def fetch(url):
        return PASSAGE

    monkeypatch.setattr("app.retrieval.fetch", fetch)
    enqueue(factory)
    asyncio.run(execute(claim(factory), factory, FixtureProvider()))
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(SourceRecord)) == 1
        assert db.scalar(select(func.count()).select_from(ClaimRecord)) == 2
        assert db.scalar(select(func.count()).select_from(ClaimSource)) == 2
        assert db.scalar(select(func.count()).select_from(SignalRecord)) == 1

import json
from sqlalchemy import select
from app import inspect_run
from app.models import Session, Job
from tests.test_workflow import enqueue


def test_forensic_export_does_not_claim_jobs_or_expose_session_tokens(factory, monkeypatch, capsys):
    run_id = enqueue(factory)
    with factory() as db:
        secret_token_hash = db.scalar(select(Session)).token_hash
    monkeypatch.setattr(inspect_run, "engine", factory.kw["bind"])
    monkeypatch.setattr("sys.argv", ["inspect_run", "--run-id", run_id])
    # The production helper disposes its private engine on exit. Keep this
    # shared in-memory test fixture alive for post-export assertions.
    monkeypatch.setattr(inspect_run.engine, "dispose", lambda: None)
    assert inspect_run.main() == 0
    text = capsys.readouterr().out
    output = json.loads(text)
    assert output["run"]["id"] == run_id
    assert output["run"]["status"] == "queued"
    assert "token_hash" not in text and secret_token_hash not in text
    assert "lease_owner" not in text
    with factory() as db:
        assert db.scalar(select(Job)).status == "queued"


def test_unique_run_prefix_is_supported_and_ambiguous_prefix_is_rejected(factory, monkeypatch, capsys):
    from app.models import Run
    run_id = enqueue(factory)
    selected = '2e86e80e-1111-4111-8111-111111111111'
    with factory.begin() as db:
        original = db.get(Run, run_id)
        db.add(Run(id=selected, session_id=original.session_id, prospect_id=original.prospect_id, input=original.input, status='queued'))
    monkeypatch.setattr(inspect_run, 'engine', factory.kw['bind'])
    monkeypatch.setattr(inspect_run.engine, 'dispose', lambda: None)
    monkeypatch.setattr('sys.argv', ['inspect_run', '--run-id', '2e86e80e'])
    assert inspect_run.main() == 0
    assert json.loads(capsys.readouterr().out)['run']['id'] == selected
    with factory.begin() as db:
        original = db.get(Run, run_id)
        db.add(Run(id='2e86e80e-2222-4222-8222-222222222222', session_id=original.session_id, prospect_id=original.prospect_id, input=original.input, status='queued'))
    assert inspect_run.main() == 1
    assert json.loads(capsys.readouterr().out)['error'] == 'ambiguous_run_id'


def test_default_export_selects_latest_run_without_a_hardcoded_prospect(factory, monkeypatch, capsys):
    run_id = enqueue(factory)
    monkeypatch.setattr(inspect_run, 'engine', factory.kw['bind'])
    monkeypatch.setattr(inspect_run.engine, 'dispose', lambda: None)
    monkeypatch.setattr('sys.argv', ['inspect_run'])
    assert inspect_run.main() == 0
    assert json.loads(capsys.readouterr().out)['run']['id'] == run_id

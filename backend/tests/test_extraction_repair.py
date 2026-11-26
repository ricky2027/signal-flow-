"""Synthetic extraction repair tests; no live page bodies are fabricated for Pete."""
import asyncio
from types import SimpleNamespace
import httpx
from sqlalchemy import select
from app.agents.research import extract
from app.models import Run, SourceRecord
from app.policy import evidence_gate
from app.qualification import qualify_pages
from app.schemas import ReviewedEvidence, Evidence, ExcerptSelection, Claim
from app.store import detail
from app.worker import claim, execute
from tests.fixtures import INPUT, PASSAGE, FixtureProvider, evidence
from tests.test_workflow import enqueue
from tests.test_multisource_pipeline import MultiplePages, PROFILE, RECENT, OLD


def context(provider):
    artifacts = {}
    return SimpleNamespace(provider=provider, save=lambda kind, data: artifacts.update({kind: data})), artifacts


def test_overlong_quote_is_reextracted_not_truncated_and_only_valid_output_is_cached():
    body = PASSAGE + ' ' + 'padding ' * 85
    class LongThenShort(FixtureProvider):
        extraction_calls = 0
        async def structured(self, schema, task, data):
            if schema in (Evidence, ExcerptSelection):
                self.extraction_calls += 1
            if schema is Evidence:
                e = evidence()
                e.sources[0].passage = body
                return e
            if schema is ExcerptSelection:
                assert 'passage_word_limit' in data['rejection_reasons']
                assert all(c['text'] in body and len(c['text'].split()) <= 80 for c in data['candidates'])
            return await super().structured(schema, task, data)
    provider = LongThenShort()
    ctx, saved = context(provider)
    state = {'input': INPUT, 'pages': [{'url': 'https://example.com/news', 'text': body}]}
    first = asyncio.run(extract(state, ctx))
    assert provider.extraction_calls == 2
    assert first['evidence']['sources'][0]['passage'].startswith(PASSAGE)
    assert len(first['evidence']['sources'][0]['passage'].split()) <= 80
    assert first['evidence']['identity_confidence'] == 'high'
    assert saved['extraction_repairs']['attempts'][0]['final_rejections'] == []
    assert evidence_gate(ReviewedEvidence.model_validate(first['evidence']))[0] is None
    asyncio.run(extract({**state, **first, 'followup': True}, ctx))
    assert provider.extraction_calls == 2


def test_still_invented_repair_is_rejected_and_repair_budget_is_per_body_per_run():
    class AlwaysInvalid(FixtureProvider):
        extraction_calls = 0
        def __init__(self): super().__init__('invented_passage')
        async def structured(self, schema, task, data):
            if schema in (Evidence, ExcerptSelection): self.extraction_calls += 1
            return await super().structured(schema, task, data)
    provider = AlwaysInvalid()
    ctx, saved = context(provider)
    state = {'input': INPUT, 'pages': [{'url': 'https://example.com/news', 'text': PASSAGE}]}
    first = asyncio.run(extract(state, ctx))
    assert provider.extraction_calls == 2
    assert first['page_extractions'] == {}
    assert first['evidence']['sources'] == []
    assert saved['extraction_repairs']['attempts'][0]['final_rejections'] == ['passage_not_found', 'source_not_retained']
    second = asyncio.run(extract({**state, **first, 'followup': True}, ctx))
    assert provider.extraction_calls == 3  # Fresh extraction allowed; no repeated repair loop.
    assert len(second['extraction_repairs']) == 1
    assert second['evidence']['sources'] == []


def test_repair_connection_error_is_visible_and_never_promotes_the_invalid_quote():
    class RepairUnavailable(FixtureProvider):
        async def structured(self, schema, task, data):
            if schema is ExcerptSelection:
                raise httpx.ConnectError('Synthetic transport failure')
            if schema is Evidence:
                e = evidence()
                e.sources[0].passage = PASSAGE + ' ' + 'padding ' * 85
                return e
            return await super().structured(schema, task, data)
    ctx, saved = context(RepairUnavailable())
    result = asyncio.run(extract({'input': INPUT, 'pages': [{'url': 'https://example.com/news', 'text': PASSAGE + ' ' + 'padding ' * 85}]}, ctx))
    assert result['evidence']['sources'] == []
    assert saved['extraction_failures']['sources'][0]['error'] == 'repair_ConnectError'
    assert saved['evidence_verification']['sources'][0]['reasons'] == ['passage_word_limit']
    assert not any('designation_mismatch' in c['reasons'] for c in saved['evidence_verification']['claims'])


def test_page_local_warning_is_scoped_without_mutating_provider_output():
    e = evidence()
    e.warnings = ['No prospect role found on this company context page.']
    qualified, _, _ = qualify_pages([({'url': e.sources[0].url, 'text': PASSAGE}, e)])
    assert qualified.warnings == ['https://example.com/news: No prospect role found on this company context page.']
    assert e.warnings == ['No prospect role found on this company context page.']


def test_complete_workflow_recovers_shorter_literal_quotes_then_persists_reviewable_draft(factory, monkeypatch):
    class Wordy(MultiplePages):
        repairs = 0
        async def structured(self, schema, task, data):
            if schema is ExcerptSelection:
                self.repairs += 1
                url = data['url']
                quote = PROFILE if '/leadership' in url else OLD if url.endswith('/old') else RECENT
                selected = next(c for c in data['candidates'] if quote in c['text'])
                return ExcerptSelection(passage_id=selected['id'], claims=[Claim(
                    id='claim-1', text=quote, source_ids=[data['source_id']], entity_match=True,
                    verification='supported', kind='identity' if '/leadership' in url else 'event', conflict_group=None,
                )])
            return await super().structured(schema, task, data)
    async def fetch(url):
        quote = PROFILE if '/leadership' in url else OLD if url.endswith('/old') else RECENT
        return quote + ' ' + 'padding ' * 85
    monkeypatch.setattr('app.retrieval.fetch', fetch)
    run_id = enqueue(factory)
    provider = Wordy()
    asyncio.run(execute(claim(factory), factory, provider))
    with factory() as db:
        output = detail(db, db.get(Run, run_id))
        assert output['status'] == 'awaiting_review', output['error']
        assert len(output['sources']) == 3
        assert all(len(s['passage'].split()) <= 80 for s in output['sources'])
        assert len(db.scalars(select(SourceRecord).where(SourceRecord.run_id == run_id)).all()) == 3
        assert next(s for s in output['signals'] if s['selected'])['id'] == 'recent-signal'
        assert 'outdated' in next(s for s in output['signals'] if s['id'] == 'old-signal')['rejection_reasons']
        assert output['drafts'][0]['validation_status'] == 'valid'
    assert provider.repairs == 3


def test_pete_export_has_a_supported_role_but_no_qualified_current_primary_identity():
    import json
    from pathlib import Path
    from app.policy import eligible_claims
    frozen = json.loads((Path(__file__).parent / 'data/pete_retained_evidence.json').read_text())
    e = Evidence.model_validate(frozen['evidence'])
    assert len(e.sources) == 2 and len(e.claims) == 3
    ids = {s.id for s in e.sources}
    assert all(set(c.source_ids) <= ids for c in e.claims)
    assert len(eligible_claims(e)) == 3  # Not zero verified facts or dangling IDs.
    assert e.claims[0].kind == 'identity' and e.claims[0].verification == 'supported'
    assert all(s.source_type != 'primary' for s in e.sources)
    assert e.identity_confidence == 'low'
    assert evidence_gate(e) == ('insufficient_information', ['identity_confidence_not_high'])

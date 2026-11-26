"""Synthetic multi-page end-to-end regression; never claims live provider success."""
import asyncio
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app import api
from app.models import SourceRecord, ClaimRecord, ClaimSource
from app.schemas import Evidence, EvidenceReview, Candidates, DraftContent, Quality
from app.worker import claim, execute
from tests.fixtures import INPUT, FixtureProvider

PROFILE = 'Test Person is the Chief Financial Officer of Example Corp.'
RECENT = f'On {date.today().isoformat()}, Example Corp announced a new operating region.'
OLD = f'On {(date.today() - timedelta(days=300)).isoformat()}, Example Corp opened its original office.'


class MultiplePages(FixtureProvider):
    def __init__(self, broken_old=False):
        super().__init__()
        self.broken_old = broken_old
        self.draft = None
        self.received_sources = []

    async def search(self, prospect):
        return {'summary': 'Synthetic search narration, deliberately never used as evidence.', 'provider_call_id': 'synthetic', 'urls': {
            'https://example.com/leadership?utm_source=search': 'Official leadership',
            'https://example.com/news/recent': 'Recent event',
            'https://example.com/news/old': 'Old event',
        }}

    async def structured(self, schema, task, data):
        if schema is Evidence:
            assert len(data['pages']) == 1
            p = data['pages'][0]
            url = p['url']
            if self.broken_old and url.endswith('/old'):
                raise ValueError('Synthetic single-page extraction failure')
            identity = '/leadership' in url
            old = url.endswith('/old')
            when = None if identity else (date.today() - timedelta(days=300) if old else date.today())
            return Evidence.model_validate({
                'sources': [{'id': 'source-1', 'url': url + ('?utm_source=model' if identity else ''), 'title': p['title'], 'publisher': 'Example Corp', 'origin_group': 'example.com', 'source_type': 'primary', 'passage': p['text'], 'published_at': when, 'event_at': when, 'date_basis': 'unknown' if identity else 'event', 'planned': False}],
                # Intentional ID reuse across independent pages reproduces a
                # common model output pattern; the qualifier must scope it.
                'claims': [{'id': 'claim-1', 'text': p['text'], 'source_ids': ['source-1'], 'entity_match': True, 'verification': 'supported', 'kind': 'identity' if identity else 'event', 'conflict_group': None}],
                'identity_confidence': 'high' if identity else 'unknown', 'material_identity_conflict': False, 'warnings': [],
            })
        if schema is EvidenceReview:
            return await super().structured(schema, task, data)
        if schema is Candidates:
            e = data['evidence']
            self.received_sources = e['sources']
            events = [c for c in e['claims'] if c['kind'] == 'event']
            return Candidates(signals=[{
                'id': 'old-signal' if c['text'] == OLD else 'recent-signal', 'claim_ids': [c['id']], 'fact_summary': c['text'],
                'implication': 'Regional spending may increase', 'role_reason': 'Verified company expansion context' if e['relevance_basis'] == 'verified_company_context' else 'Budget ownership', 'offer_reason': 'Cost visibility', 'role_relevance': 3, 'offer_fit': 3,
            } for c in events])
        if schema is DraftContent:
            signal = data['selected_signal']
            assert signal['id'] == 'recent-signal'
            self.draft = DraftContent(subject='Regional spending', body=RECENT + ' Could cost visibility help?', claim_refs=[{'field': 'body', 'start': 0, 'end': len(RECENT), 'claim_ids': signal['claim_ids']}])
            return self.draft
        if schema is Quality:
            return Quality(valid=True, findings=[], claim_refs=self.draft.claim_refs)
        raise AssertionError(schema)


def run_flow(factory, monkeypatch, broken_old):
    async def fetch(url):
        return PROFILE if '/leadership' in url else OLD if url.endswith('/old') else RECENT
    monkeypatch.setattr('app.retrieval.fetch', fetch)
    monkeypatch.setattr(api, 'SessionLocal', factory)
    provider = MultiplePages(broken_old)
    with TestClient(api.app, headers={'Origin': 'http://localhost:3000', 'X-Signalflow-Client': 'web'}) as client:
        assert client.post('/api/v1/session', json={'access_code': 'test-access'}).status_code == 200
        submitted = client.post('/api/v1/runs', json=INPUT, headers={'Idempotency-Key': 'multi-source'})
        assert submitted.status_code == 202
        run_id = submitted.json()['run_id']
        asyncio.run(execute(claim(factory), factory, provider))
        response = client.get('/api/v1/runs/' + run_id)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'awaiting_review', output['error']
        assert output['identity_confidence'] == 'high'
        assert output['identity_checks']['prospect_identity']['status'] == 'verified'
        assert output['identity_checks']['company_association']['status'] == 'verified'
        assert output['identity_checks']['title_match']['status'] == 'equivalent'
        assert output['identity_checks']['role_currentness']['status'] == 'unverified'
        assert output['signal_evaluation']['state'] == 'evaluated'
        assert output['signal_evaluation']['relevance_basis'] == 'verified_company_context'
        assert output['signal_evaluation']['excluded_role_claim_ids']
        assert output['drafts'][0]['validation_status'] == 'valid'
        assert output['drafts'][0]['body'].startswith(RECENT)
        ids = {s['id'] for s in output['sources']}
        assert all(set(c['source_ids']) <= ids for c in output['claims'])
        assert len(ids) == (2 if broken_old else 3)
        assert len({s['url'] for s in output['sources']}) == len(ids)
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(SourceRecord)) == len(ids)
            assert db.scalar(select(func.count()).select_from(ClaimRecord)) == len(ids)
            assert db.scalar(select(func.count()).select_from(ClaimSource)) == len(ids)
        return output, provider


def test_complete_multisource_pipeline_persists_identity_recent_and_stale_evidence(factory, monkeypatch):
    output, provider = run_flow(factory, monkeypatch, False)
    assert len(provider.received_sources) == 2  # Undated role-only source is excluded from reasoning.
    selected = next(s for s in output['signals'] if s['selected'])
    rejected = next(s for s in output['signals'] if s['id'] == 'old-signal')
    assert selected['id'] == 'recent-signal'
    assert rejected['eligible'] is False and 'outdated' in rejected['rejection_reasons']


def test_one_extraction_failure_does_not_discard_other_identity_and_event_pages(factory, monkeypatch):
    output, provider = run_flow(factory, monkeypatch, True)
    attempts = output['research_diagnostics']['retrieval_attempts']
    assert any(s['error'] == 'extraction_ValueError' for a in attempts for s in a['sources'])
    assert len(provider.received_sources) == 1


def test_all_page_extractions_failing_reports_failure_instead_of_false_insufficiency(factory, monkeypatch):
    from tests.test_workflow import enqueue
    from app.models import Run
    from app.store import detail

    class Broken(FixtureProvider):
        async def structured(self, *args):
            raise ValueError('Synthetic provider output failure')

    async def fetch(url):
        return PROFILE
    monkeypatch.setattr('app.retrieval.fetch', fetch)
    run_id = enqueue(factory)
    asyncio.run(execute(claim(factory), factory, Broken()))
    with factory() as db:
        output = detail(db, db.get(Run, run_id))
        assert output['status'] == 'failed'
        assert output['error']['code'] == 'evidence_extraction_failed'
        assert not output['drafts']
        assert any(a.get('phase') == 'extraction' for a in output['research_diagnostics']['retrieval_attempts'])

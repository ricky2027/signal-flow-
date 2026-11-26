"""Website round-trip and biography handling; fixtures are not a live run replay."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from app import api
from app.agents.research import extract, research
from app.models import Run, Prospect
from app.policy import evidence_gate
from app.schemas import ReviewedEvidence, Evidence, EvidenceReview, ExcerptSelection, Claim
from tests.fixtures import INPUT

BIO_URL = 'https://www.kellyocg.com/about-us/leadership/pete-hamilton/'
# Short clause independently read on the official biography. No publication
# date or assertion that this establishes current employment is invented.
ROLE_QUOTE = 'Pete Hamilton is vice president and managing director, APAC region, of KellyOCG'
PETE_INPUT = {**INPUT, 'prospect_name': 'Pete Hamilton', 'designation': 'Vice President and Managing Director, APAC', 'company_name': 'KellyOCG', 'company_website': 'https://www.kellyocg.com/'}
HEADERS = {'Origin': 'http://localhost:3000', 'X-Signalflow-Client': 'web'}


@pytest.mark.parametrize('website', ['https://example.com/about/', None])
def test_website_roundtrip_preserves_supplied_or_missing_value_in_both_records(factory, monkeypatch, website):
    monkeypatch.setattr(api, 'SessionLocal', factory)
    with TestClient(api.app, headers=HEADERS) as client:
        assert client.post('/api/v1/session', json={'access_code': 'test-access'}).status_code == 200
        response = client.post('/api/v1/runs', json={**INPUT, 'company_website': website}, headers={'Idempotency-Key': 'website-roundtrip'})
        assert response.status_code == 202
        run_id = response.json()['run_id']
        detail = client.get('/api/v1/runs/' + run_id).json()
        assert detail['input']['company_website'] == website
        with factory() as db:
            run = db.get(Run, run_id)
            assert run.input['company_website'] == website
            assert db.get(Prospect, run.prospect_id).data['company_website'] == website


def test_invalid_website_is_rejected_rather_than_silently_erased(factory, monkeypatch):
    monkeypatch.setattr(api, 'SessionLocal', factory)
    with TestClient(api.app, headers=HEADERS) as client:
        client.post('/api/v1/session', json={'access_code': 'test-access'})
        response = client.post('/api/v1/runs', json={**INPUT, 'company_website': ''}, headers={'Idempotency-Key': 'invalid-website'})
        assert response.status_code == 422


def test_research_actually_fetches_a_prospect_specific_profile_returned_by_search(monkeypatch):
    seen = []
    class Search:
        async def search(self, prospect):
            assert prospect['company_website'] == PETE_INPUT['company_website']
            return {'summary': 'Fixture narration is not evidence', 'provider_call_id': 'synthetic', 'urls': {BIO_URL + '?utm_source=fixture': 'Official profile'}}
    async def fetch(url):
        seen.append(url)
        return ROLE_QUOTE
    monkeypatch.setattr('app.retrieval.fetch', fetch)
    saved = {}
    ctx = SimpleNamespace(provider=Search(), config=SimpleNamespace(max_sources=12), save=lambda kind, data: saved.update({kind: data}))
    result = asyncio.run(research({'input': PETE_INPUT}, ctx))
    assert seen == [BIO_URL]
    assert result['pages'][0]['text'] == ROLE_QUOTE
    assert saved['retrieval_summary']['selected_urls'] == [BIO_URL]


def test_biography_quote_repair_preserves_exact_role_but_cannot_invent_currentness():
    # Padding is synthetic, not an assertion about the fetched site's body.
    body = ROLE_QUOTE + '. ' + 'padding ' * 85
    class Provider:
        calls = 0
        async def structured(self, schema, task, data):
            if schema is ExcerptSelection:
                self.calls += 1
                selected = next(c for c in data['candidates'] if ROLE_QUOTE in c['text'])
                return ExcerptSelection(passage_id=selected['id'], claims=[Claim(
                    id='role', text=ROLE_QUOTE, source_ids=[data['source_id']], entity_match=True,
                    verification='supported', kind='identity', conflict_group=None,
                )])
            if schema is Evidence:
                self.calls += 1
                p = data['pages'][0]
                return Evidence.model_validate({
                    'sources': [{'id': p['source_id'], 'url': p['url'], 'title': 'Pete Hamilton biography', 'publisher': 'KellyOCG', 'origin_group': 'kellyocg.com', 'source_type': 'primary', 'passage': ROLE_QUOTE if 'rejection_reasons' in data else body, 'published_at': None, 'event_at': None, 'date_basis': 'unknown', 'planned': False}],
                    'claims': [{'id': 'role', 'text': ROLE_QUOTE, 'source_ids': [p['source_id']], 'entity_match': True, 'verification': 'supported', 'kind': 'identity', 'conflict_group': None}],
                    'identity_confidence': 'high', 'material_identity_conflict': False, 'warnings': [],
                })
            assert schema is EvidenceReview
            claim = data['evidence']['claims'][0]
            return EvidenceReview(claims=[{'claim_id': claim['id'], 'source_ids': claim['source_ids'], 'verification': 'supported', 'current_identity': False, 'role_assertion': True, 'designation_match': 'unverified', 'reason': 'Fixture: passage supports the sourced role, but currentness has not been corroborated.'}], identity_confidence='high', company_association_confidence='high', identity_claim_ids=[claim['id']], material_identity_conflict=False, warnings=[])
    provider = Provider()
    saved = {}
    ctx = SimpleNamespace(provider=provider, save=lambda kind, data: saved.update({kind: data}))
    result = asyncio.run(extract({'input': PETE_INPUT, 'pages': [{'url': BIO_URL, 'text': body}]}, ctx))
    e = ReviewedEvidence.model_validate(result['evidence'])
    assert provider.calls == 2
    assert e.sources[0].url == BIO_URL and ROLE_QUOTE in e.sources[0].passage
    assert len(e.sources[0].passage.split()) <= 80
    assert e.sources[0].published_at is None and e.sources[0].event_at is None
    assert e.claims[0].verification == 'supported'
    assert e.claims[0].source_ids == [e.sources[0].id]
    assert e.identity_confidence == 'high'
    assert e.identity_checks.role_currentness.status == 'unverified'
    assert evidence_gate(e)[0] is None
    assert 'role_currentness_unverified' in saved['evidence_verification']['claims'][-1]['reasons']

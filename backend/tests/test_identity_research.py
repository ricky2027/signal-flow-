"""Synthetic identity/search regressions, not live prospect findings."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from app.agents.research import extract
from app.config import Settings
from app.policy import evidence_gate
from app.provider import OpenAIProvider
from app.qualification import qualify_pages, review_evidence
from app.research_guidance import research_plan
from app.schemas import EvidenceReview
from tests.fixtures import INPUT, FixtureProvider, evidence


def test_search_request_targets_named_person_and_official_profile_without_exact_title_filter():
    prospect = {**INPUT, 'designation': 'Chief Financial Officer', 'company_website': 'https://example.com/about'}
    provider = OpenAIProvider(lambda _: None, Settings(openai_api_key='test-only', _env_file=None))
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json={'id': 'synthetic', 'status': 'completed', 'output': [{'type': 'web_search_call', 'action': {'type': 'search', 'sources': []}}]})

    async def run():
        await provider.client.aclose()
        provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url='https://api.openai.com/v1/')
        try:
            await provider.search(prospect)
        finally:
            await provider.close()
    asyncio.run(run())
    prompt = seen[0]['input']
    assert 'official employer leadership' in prompt
    assert 'literal user-entered title' in prompt
    assert 'site:example.com' in prompt
    assert '\\"Test Person\\"' in prompt
    plan = research_plan(prospect)
    assert all(prospect['designation'] not in q['query'] for q in plan['suggested_queries'])
    assert any(q['purpose'] == 'events' for q in plan['suggested_queries'])
    assert seen[0]['tool_choice'] == 'required'


def test_recent_events_followup_targets_dated_company_events_without_role_or_offer():
    plan = research_plan({**INPUT, 'company_website': 'https://example.com/',
                          'research_focus': 'recent_events', 'followup_focus': 'recent dated event'})
    assert plan['focus'] == 'recent_events'
    assert plan['suggested_queries']
    for q in plan['suggested_queries']:
        assert q['purpose'] == 'events'
        assert 'after:' in q['query']
        assert 'Example Corp' in q['query'] or 'site:example.com' in q['query']
        assert INPUT['designation'] not in q['query']
        assert INPUT['product_service'] not in q['query']


def test_first_pass_requests_dated_events_not_an_undated_announcement_string():
    plan = research_plan(INPUT)
    assert plan['focus'] == 'identity_then_events'
    events = [q for q in plan['suggested_queries'] if q['purpose'] == 'events']
    assert events and all('after:' in q['query'] for q in events)


def test_recovery_focuses_identity_and_does_not_invent_company_domains():
    plan = research_plan({**INPUT, 'company_website': None, 'followup_focus': 'Identity unverified'})
    assert plan['focus'] == 'identity_recovery'
    assert all(q['purpose'] == 'identity' for q in plan['suggested_queries'])
    assert all('site:' not in q['query'] for q in plan['suggested_queries'])
    assert all('Test Person' in q['query'] and 'Example Corp' in q['query'] for q in plan['suggested_queries'])


@pytest.mark.parametrize('designation,classification,expected', [
    ('Chief Financial Officer', 'equivalent', None),
    ('Chief Technology Officer', 'mismatch', None),
    ('Regional Finance Director', 'unverified', None),
])
def test_title_equivalence_is_reviewed_against_source_without_rewriting_role(designation, classification, expected):
    e = evidence()  # Source actually says CFO, not the user-supplied title.
    e, _, _ = qualify_pages([({'url': e.sources[0].url, 'text': e.sources[0].passage}, e)])

    class Reviewer:
        async def structured(self, schema, task, data):
            assert schema is EvidenceReview
            assert 'Do not require a literal title-string match' in task
            assert 'Different functions, seniorities' in task
            assert data['input']['designation'] == designation
            assert data['evidence']['claims'][0]['text'] == 'Test Person is CFO of Example Corp'
            return EvidenceReview(claims=[{
                'claim_id': c['id'], 'source_ids': c['source_ids'], 'verification': 'supported',
                'current_identity': c['kind'] == 'identity', 'role_assertion': c['kind'] == 'identity',
                'designation_match': classification if c['kind'] == 'identity' else 'not_applicable',
                'reason': 'Synthetic scope/function comparison, not a live model verdict',
            } for c in data['evidence']['claims']], identity_confidence='high', company_association_confidence='high', identity_claim_ids=[c['id'] for c in data['evidence']['claims'] if c['kind'] == 'identity'], material_identity_conflict=False, warnings=[])
    reviewed, decisions = asyncio.run(review_evidence(e, Reviewer(), {**INPUT, 'designation': designation}))
    assert evidence_gate(reviewed)[0] == expected
    assert reviewed.claims[0].text == e.claims[0].text
    identity = next(d for d in decisions if d['claim_id'] == 'identity')
    assert identity['designation_match'] == classification
    if classification == 'mismatch':
        assert 'designation_mismatch' in identity['reasons']
        assert identity['eligible'] is False
    if classification == 'unverified':
        assert 'designation_unverified' in identity['reasons']


def test_no_role_evidence_is_unverified_not_a_confirmed_designation_mismatch():
    e = evidence()
    e.claims = [e.claims[1]]  # A company event alone cannot prove who holds a role.
    e, _, _ = qualify_pages([({'url': e.sources[0].url, 'text': e.sources[0].passage}, e)])
    reviewed, decisions = asyncio.run(review_evidence(e, FixtureProvider(), INPUT))
    outcome, reasons = evidence_gate(reviewed)
    assert outcome == 'insufficient_information'
    assert 'no_supported_identity_claim' in reasons
    assert not any('designation_mismatch' in d['reasons'] for d in decisions)


def test_noncurrent_identity_records_reason_even_when_historical_claim_is_supported():
    e = evidence()
    e, _, _ = qualify_pages([({'url': e.sources[0].url, 'text': e.sources[0].passage}, e)])

    class Historical(FixtureProvider):
        async def structured(self, schema, task, data):
            review = await super().structured(schema, task, data)
            review.claims[0].current_identity = False
            review.claims[0].designation_match = 'mismatch'
            return review
    reviewed, decisions = asyncio.run(review_evidence(e, Historical(), INPUT))
    identity = next(d for d in decisions if d['claim_id'] == 'identity')
    assert identity['designation_match'] == 'mismatch'
    assert 'role_currentness_unverified' in identity['reasons']
    assert 'designation_mismatch' in identity['reasons']
    assert reviewed.material_identity_conflict is False
    assert reviewed.identity_confidence == 'high'
    assert reviewed.identity_checks.role_currentness.status == 'unverified'


def test_extraction_summary_distinguishes_omitted_identity_from_rejected_passage():
    class EventOnly(FixtureProvider):
        async def structured(self, schema, task, data):
            from app.schemas import Evidence
            result = await super().structured(schema, task, data)
            if schema is Evidence:
                assert 'Do not omit a source-confirmed role' in task
                result.claims = [result.claims[1]]
            return result
    e = evidence()
    artifacts = {}
    ctx = SimpleNamespace(provider=EventOnly(), save=lambda kind, data: artifacts.update({kind: data}))
    asyncio.run(extract({'input': INPUT, 'pages': [{'url': e.sources[0].url, 'text': e.sources[0].passage}]}, ctx))
    summary = artifacts['page_extraction_summary']['pages'][0]
    assert summary['source_count'] == 1 and summary['identity_claim_count'] == 0
    assert artifacts['evidence_verification']['sources'][0]['accepted'] is True
    assert 'no_supported_identity_claim' in artifacts['evidence_verification']['gate_reasons']

    ctx.provider = FixtureProvider('invented_passage')
    asyncio.run(extract({'input': INPUT, 'pages': [{'url': e.sources[0].url, 'text': e.sources[0].passage}]}, ctx))
    assert artifacts['page_extraction_summary']['pages'][0]['identity_claim_count'] == 1
    assert 'passage_not_found' in artifacts['evidence_verification']['sources'][0]['reasons']


def test_matching_designation_cannot_override_wrong_person_or_employer_evidence():
    e = evidence()
    e.claims[0].entity_match = False
    e, _, _ = qualify_pages([({'url': e.sources[0].url, 'text': e.sources[0].passage}, e)])
    reviewed, decisions = asyncio.run(review_evidence(e, FixtureProvider(), INPUT))
    assert reviewed.identity_confidence == 'low'
    assert evidence_gate(reviewed)[0] == 'insufficient_information'
    identity = next(d for d in decisions if d['claim_id'] == 'identity')
    assert 'entity_mismatch' in identity['reasons']
    assert identity['designation_match'] == 'unverified'

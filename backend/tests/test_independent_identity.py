"""Synthetic policy regressions. None of these records is live research."""
import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.agents.research import research
from app.agents.signals import evaluate
from app.agents.writing import check_draft
from app.dates import date_in_text
from app.policy import evidence_gate, rank, usable_claims, validate_refs
from app.qualification import qualify_pages, review_evidence
from app.reasoning_context import reasoning_context
from app.research_guidance import research_plan
from app.schemas import Quality
from tests.fixtures import INPUT, FixtureProvider, evidence, candidates, draft


def reviewed(undated=False, provider=None):
    e = evidence()
    if undated:
        e.sources[0].published_at = e.sources[0].event_at = None
        e.sources[0].date_basis = 'unknown'
    return asyncio.run(review_evidence(e, provider or FixtureProvider(), INPUT))[0]


def test_undated_biography_verifies_identity_but_never_current_employment():
    e = reviewed(undated=True)  # Reviewer intentionally claims current_identity=True.
    assert e.identity_confidence == 'high'
    assert e.identity_checks.prospect_identity.status == 'verified'
    assert e.identity_checks.company_association.status == 'verified'
    assert e.identity_checks.title_match.status == 'equivalent'
    assert e.identity_checks.role_currentness.status == 'unverified'
    assert evidence_gate(e) == (None, [])
    assert 'identity' not in usable_claims(e)
    assert 'event' in usable_claims(e)
    rows, outcome = rank(e, candidates().signals)
    assert outcome == 'no_relevant_signal'  # Identity alone cannot supply event freshness.
    assert 'unknown_date' in rows[0]['rejection_reasons']


@pytest.mark.parametrize('offset', [0, 180, 181, -1])
def test_current_role_needs_recent_nonfuture_literal_primary_date(offset):
    e = evidence()
    when = date.today() - timedelta(days=offset)
    e.sources[0].published_at = e.sources[0].event_at = when
    e.sources[0].passage = f'On {when.isoformat()}, Test Person is CFO of Example Corp.'
    result = asyncio.run(review_evidence(e, FixtureProvider(), INPUT))[0]
    assert (result.identity_checks.role_currentness.status == 'verified') == (0 <= offset <= 180)
    assert evidence_gate(result)[0] is None


def test_fabricated_dates_are_removed_without_discarding_valid_identity_quote():
    e = evidence()
    e.sources[0].passage = 'Test Person is CFO of Example Corp.'
    page = {'url': e.sources[0].url, 'text': e.sources[0].passage + f' Copyright {date.today().year}.'}
    qualified, decisions, _ = qualify_pages([(page, e)])
    assert len(qualified.sources) == 1
    assert qualified.sources[0].published_at is None
    assert qualified.sources[0].event_at is None
    assert qualified.sources[0].date_basis == 'unknown'
    assert set(decisions[0]['date_warnings']) == {'publication_date_not_found', 'event_date_not_found'}
    result = asyncio.run(review_evidence(qualified, FixtureProvider(), INPUT))[0]
    assert result.identity_checks.prospect_identity.status == 'verified'
    assert result.identity_checks.role_currentness.status == 'unverified'


def test_date_attestation_accepts_exact_full_dates_not_years_or_retrieval_time():
    when = date(2026, 11, 26)
    for text in ['2026-11-26', 'November 26, 2026', '26 Nov 2026', 'Nov. 26th, 2026']:
        assert date_in_text(when, text)
    assert not date_in_text(when, 'Copyright 2026')
    assert not date_in_text(when, 'November 26')


def test_role_projection_excludes_mixed_role_claims_and_submitted_designation():
    class Mixed(FixtureProvider):
        async def structured(self, schema, task, data):
            result = await super().structured(schema, task, data)
            for c in result.claims:
                c.role_assertion = True
                c.current_identity = False
            return result
    e = reviewed(undated=True, provider=Mixed())
    subject, safe = reasoning_context(INPUT, e)
    assert subject.designation is None
    assert safe.claims == []
    assert safe.sources == []
    assert 'identity' not in usable_claims(e) and 'event' not in usable_claims(e)
    assert safe.relevance_basis == 'verified_company_context'
    rows, _ = rank(e, candidates().signals)
    assert 'unverified_role_reference' in rows[0]['rejection_reasons']
    assert 'unsupported_claim_reference' in validate_refs(draft(), e)


def test_abstaining_holistic_confidence_does_not_suppress_primary_corroborated_identity():
    """Root-cause regression: a conservative reviewer that cannot establish CURRENT
    role returns 'unknown' holistic identity/company confidence. Primary-source
    corroboration must still verify identity and company association and open the
    gate, with role currentness independently unverified. 'unknown' is abstention,
    not doubt, so it must not force an abstention the evidence does not justify."""
    class Abstains(FixtureProvider):
        async def structured(self, schema, task, data):
            result = await super().structured(schema, task, data)
            if schema.__name__ == 'EvidenceReview':
                # Person/company clearly corroborated by the primary biography, but
                # the reviewer declines to affirm a holistic verdict because the
                # role's present-day currency is undated/unknown.
                result.identity_confidence = 'unknown'
                result.company_association_confidence = 'unknown'
                for c in result.claims:
                    if c.designation_match == 'equivalent':
                        c.current_identity = False  # currentness genuinely unknown
            return result
    e = reviewed(undated=True, provider=Abstains())
    assert e.identity_checks.prospect_identity.status == 'verified'
    assert e.identity_checks.company_association.status == 'verified'
    assert e.identity_checks.title_match.status == 'equivalent'
    assert e.identity_checks.role_currentness.status == 'unverified'  # stays independent
    assert evidence_gate(e) == (None, [])  # signal evaluation is allowed
    assert 'identity' not in usable_claims(e)  # unverified role claim excluded from scoring
    assert 'event' in usable_claims(e)


@pytest.mark.parametrize('idc,coc', [('unknown', 'unknown'), ('high', 'unknown'), ('unknown', 'high')])
def test_frozen_pete_evidence_opens_gate_when_reviewer_abstains(idc, coc):
    """Guards the actual reported Pete Hamilton / KellyOCG abstention using the
    frozen real retained evidence. Identity claims are backed by primary KellyOCG
    pages; an abstaining reviewer ('unknown', not 'low') must not block signal
    evaluation on verified company association."""
    import json, pathlib
    from app.schemas import Evidence
    raw = json.loads(pathlib.Path('tests/data/run_63aff71e_evidence.json').read_text())['evidence']
    base = Evidence.model_validate({k: v for k, v in raw.items() if k in Evidence.model_fields})

    class Reviewer:
        async def structured(self, schema, task, data):
            from app.schemas import EvidenceReview, ClaimAssessment
            claims = base.claims
            return EvidenceReview(
                claims=[ClaimAssessment(
                    claim_id=c.id, source_ids=list(c.source_ids), verification=c.verification,
                    current_identity=False,
                    designation_match=('equivalent' if c.kind == 'identity' else 'not_applicable'),
                    role_assertion=c.kind == 'identity', reason='mirror of retained primary passage')
                    for c in claims],
                identity_confidence=idc, company_association_confidence=coc,
                identity_claim_ids=[c.id for c in claims if c.kind == 'identity'],
                material_identity_conflict=False, warnings=[])
    pete = {'prospect_name': 'Pete Hamilton', 'company_name': 'KellyOCG',
            'designation': 'Vice President and Managing Director, APAC',
            'company_website': 'https://www.kellyocg.com/', 'product_service': 'X', 'value_proposition': 'Y'}
    reviewed_e = asyncio.run(review_evidence(base, Reviewer(), pete))[0]
    assert reviewed_e.identity_checks.prospect_identity.status == 'verified'
    assert reviewed_e.identity_checks.company_association.status == 'verified'
    assert reviewed_e.identity_checks.role_currentness.status == 'unverified'
    assert evidence_gate(reviewed_e)[0] is None


@pytest.mark.parametrize('failure', ['person', 'company', 'conflict'])
def test_independent_company_events_never_override_failed_core_identity(failure):
    class Reviewer(FixtureProvider):
        async def structured(self, schema, task, data):
            result = await super().structured(schema, task, data)
            if failure == 'person': result.identity_confidence = 'low'
            if failure == 'company': result.company_association_confidence = 'low'
            if failure == 'conflict': result.material_identity_conflict = True
            return result
    e = reviewed(provider=Reviewer())
    outcome, reasons = evidence_gate(e)
    assert outcome == ('conflicting_evidence' if failure == 'conflict' else 'insufficient_information')
    assert reasons


def test_company_context_excludes_raw_role_text_and_quality_rejects_role_leakage():
    e = reviewed()
    e.identity_checks.role_currentness.status = 'unverified'
    subject, context = reasoning_context(INPUT, e)
    assert [c.id for c in context.claims] == ['event']
    assert subject.designation is None
    serialized = context.model_dump_json()
    assert 'CFO' not in serialized and 'Test source' not in serialized
    assert 'passage' not in serialized
    bad = draft().model_copy(update={'body': 'As CFO, you own the budget. ' + draft().body})

    class Auditor:
        async def structured(self, schema, task, data):
            assert schema is Quality
            assert 'reject any assertion' in task
            assert data['input']['designation'] is None
            assert [c['id'] for c in data['evidence']['claims']] == ['event']
            assert data['evidence']['passages']
            return Quality(valid=False, findings=['unsupported_current_role'], claim_refs=[])
    _, issues = asyncio.run(check_draft(Auditor(), bad, e, INPUT))
    assert 'unsupported_current_role' in issues


def test_signal_evaluation_persists_company_basis_and_excluded_role_ids():
    e = reviewed()
    e.identity_checks.role_currentness.status = 'unverified'
    artifacts = {}
    ctx = SimpleNamespace(provider=FixtureProvider(), save=lambda kind, value: artifacts.update({kind: value}))
    result = asyncio.run(evaluate({'input': INPUT, 'evidence': e.model_dump(mode='json')}, ctx))
    assert result['outcome'] is None
    assert artifacts['signal_evaluation']['state'] == 'evaluated'
    assert artifacts['signal_evaluation']['relevance_basis'] == 'verified_company_context'
    assert artifacts['signal_evaluation']['excluded_role_claim_ids'] == ['identity']
    assert artifacts['signals']['signals'][0]['selected'] is True


def test_followup_queries_target_dated_named_employment_not_offer_or_title():
    request = {**INPUT, 'company_website': 'https://example.com/', 'research_focus': 'employment_currentness', 'followup_focus': 'dated employment'}
    plan = research_plan(request)
    assert plan['focus'] == 'employment_currentness'
    for query in plan['suggested_queries']:
        assert 'Test Person' in query['query'] and 'Example Corp' in query['query']
        assert 'after:' in query['query']
        assert INPUT['designation'] not in query['query']
        assert INPUT['product_service'] not in query['query']


def test_followup_hunts_recent_events_when_identity_verified_but_no_fresh_event(monkeypatch):
    """When identity is corroborated but no fresh dated event remains, the single
    follow-up must search for a RECENT DATED EVENT (the signal basis), not spend
    itself on role-currentness, which is decoupled from scoring."""
    e = reviewed()
    e.claims = [c for c in e.claims if c.kind != 'event']  # only identity remains
    captured = {}
    class Search:
        async def search(self, request):
            captured['focus'] = request['research_focus']
            return {'summary': 'Synthetic search only', 'provider_call_id': 'fixture', 'urls': {'https://example.com/news/1': 'Dated event'}}
    async def fetch(url): return 'Synthetic fetched body'
    monkeypatch.setattr('app.retrieval.fetch', fetch)
    ctx = SimpleNamespace(provider=Search(), config=SimpleNamespace(max_sources=3), save=lambda *_: None)
    asyncio.run(research({'input': INPUT, 'evidence': e.model_dump(mode='json'),
                          'pages': [{'url': e.sources[0].url, 'title': 'Existing', 'text': e.sources[0].passage}]}, ctx))
    assert captured['focus'] == 'recent_events'


def test_followup_reserves_identity_and_recent_event_without_starving_new_pages(monkeypatch):
    e = reviewed()
    e.identity_checks.role_currentness.status = 'unverified'
    e.sources[0].url = 'https://example.com/existing'
    class Search:
        async def search(self, request):
            assert request['research_focus'] == 'employment_currentness'
            return {'summary': 'Synthetic search only', 'provider_call_id': 'fixture', 'urls': {f'https://example.com/new/{i}': 'Dated source' for i in range(3)}}
    async def fetch(url): return 'Synthetic fetched body'
    monkeypatch.setattr('app.retrieval.fetch', fetch)
    ctx = SimpleNamespace(provider=Search(), config=SimpleNamespace(max_sources=3), save=lambda *_: None)
    result = asyncio.run(research({'input': INPUT, 'evidence': e.model_dump(mode='json'), 'pages': [{'url': e.sources[0].url, 'title': 'Existing evidence', 'text': e.sources[0].passage}]}, ctx))
    assert len(result['pages']) == 3
    assert e.sources[0].url in {p['url'] for p in result['pages']}
    assert any('/new/' in p['url'] for p in result['pages'])

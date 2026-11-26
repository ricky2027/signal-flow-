"""Synthetic qualification regressions plus a frozen historical evidence export."""
import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, func
from app.qualification import qualify_pages, review_evidence, source_key
from app.retrieval import canonical_url
from app.schemas import Evidence, EvidenceReview
from app.policy import evidence_gate, source_freshness, rank
from app.store import save_artifact, detail, latest
from app.models import Artifact, SourceRecord, ClaimRecord, ClaimSource, Run
from tests.fixtures import evidence, candidates, INPUT
from tests.test_workflow import enqueue


class Reviewer:
    async def structured(self, schema, task, data):
        assert schema is EvidenceReview
        return EvidenceReview(claims=[{
            'claim_id': c['id'], 'source_ids': c['source_ids'], 'verification': 'supported',
            'current_identity': c['kind'] == 'identity', 'role_assertion': c['kind'] == 'identity', 'designation_match': 'equivalent' if c['kind'] == 'identity' else 'not_applicable', 'reason': 'Synthetic retained-passage review',
        } for c in data['evidence']['claims']], identity_confidence='high', company_association_confidence='high', identity_claim_ids=[c['id'] for c in data['evidence']['claims'] if c['kind'] == 'identity'], material_identity_conflict=False, warnings=[])


def page(e):
    s = e.sources[0]
    return {'url': s.url, 'text': s.passage}


def test_export_reproduction_never_persists_missing_source_ids_or_high_stale_identity():
    fixture = json.loads((Path(__file__).parent / 'data/reported_evidence.json').read_text())
    original = Evidence.model_validate(fixture['evidence'])
    today = date.fromisoformat(fixture['as_of'])
    assert original.identity_confidence == 'high'
    assert len(original.sources) == 1
    assert len(original.claims[0].source_ids) == 5
    clean, sources, decisions = qualify_pages([(page(original), original)], today)
    assert clean.claims[0].source_ids == [clean.sources[0].id]
    assert clean.claims[0].verification == 'unsupported'
    assert 'source_not_retained' in decisions[0]['reasons']
    reviewed, _ = asyncio.run(review_evidence(clean, Reviewer(), INPUT, today))
    # Even an overconfident model cannot convert this known stale press release
    # into proof of a current role. No fresh page text is invented for the export.
    assert reviewed.identity_checks.role_currentness.status == 'unverified'
    assert reviewed.identity_checks.title_match.status == 'equivalent'
    assert evidence_gate(reviewed)[0] is None
    assert sources[0]['fresh_signal_eligible'] is False


def test_tracking_aliases_map_to_stable_ids_without_collapsing_content_queries():
    e = evidence()
    e.sources[0].url = 'https://example.com/news?utm_source=model'
    p = {'url': 'https://example.com/news?utm_source=search#fragment', 'text': e.sources[0].passage}
    clean, _, _ = qualify_pages([(p, e)])
    assert clean.sources[0].url == 'https://example.com/news'
    assert clean.sources[0].id == source_key('https://example.com/news')
    assert clean.claims[0].source_ids == [clean.sources[0].id]
    assert canonical_url('https://example.com/leadership?section=board&utm_source=test') != canonical_url('https://example.com/leadership')


def test_redirect_alias_only_maps_when_the_page_was_actually_retrieved():
    e = evidence()
    p = {'url': 'https://example.com/new', 'aliases': ['https://example.com/news'], 'text': e.sources[0].passage}
    clean, _, _ = qualify_pages([(p, e)])
    assert clean.sources[0].url == p['url']
    clean, decisions, _ = qualify_pages([({**p, 'aliases': []}, e)])
    assert clean.sources == [] and clean.claims == []
    assert 'source_not_retrieved' in decisions[0]['reasons']


def test_partial_missing_refs_need_review_before_they_can_support_identity():
    e = evidence()
    e.claims[0].source_ids += ['missing']
    clean, _, _ = qualify_pages([(page(e), e)])
    assert clean.claims[0].verification == 'unsupported'
    reviewed, _ = asyncio.run(review_evidence(clean, Reviewer(), INPUT))
    assert reviewed.claims[0].verification == 'supported'
    assert reviewed.identity_confidence == 'high'
    assert all(set(c.source_ids) <= {s.id for s in reviewed.sources} for c in reviewed.claims)


def test_reused_provider_ids_across_pages_do_not_overwrite_sources_or_claims():
    a, b = evidence(), evidence()
    b.sources[0].url = 'https://example.com/second'
    b.sources[0].passage = 'A different attributable event.'
    b.claims = [b.claims[1]]
    b.claims[0].text = b.sources[0].passage
    # Both responses reuse s1 and event. Page scoping prevents cross-linking.
    clean, _, _ = qualify_pages([(page(a), a), (page(b), b)])
    assert len(clean.sources) == 2 and len(clean.claims) == 3
    assert len({s.id for s in clean.sources}) == 2
    assert len({c.id for c in clean.claims}) == 3
    assert clean.claims[-1].source_ids == [source_key(b.sources[0].url)]


def test_ambiguous_ids_and_nonverbatim_passages_are_not_repaired_by_guessing():
    e = evidence()
    e.sources.append(e.sources[0].model_copy())
    clean, decisions, claims = qualify_pages([(page(e), e)])
    assert not clean.sources and not clean.claims
    assert all('ambiguous_source_id' in row['reasons'] for row in decisions)
    e = evidence()
    clean, decisions, _ = qualify_pages([({'url': e.sources[0].url, 'text': 'Unrelated page body'}, e)])
    assert not clean.sources and not clean.claims
    assert 'passage_not_found' in decisions[0]['reasons']


def test_missing_review_or_invented_review_source_stays_unsupported():
    class InvalidReviewer:
        async def structured(self, *args):
            return EvidenceReview(claims=[], identity_confidence='high', company_association_confidence='high', identity_claim_ids=['identity'], material_identity_conflict=False, warnings=[])
    e, _, _ = qualify_pages([(page(evidence()), evidence())])
    reviewed, decisions = asyncio.run(review_evidence(e, InvalidReviewer(), INPUT))
    assert all(c.verification == 'unsupported' for c in reviewed.claims)
    assert reviewed.identity_confidence == 'low'
    assert all('missing_or_ambiguous_assessment' in d['reasons'] for d in decisions)

    class InventedSourceReviewer:
        async def structured(self, *args):
            return EvidenceReview(claims=[{'claim_id': 'identity', 'source_ids': ['invented'], 'verification': 'supported', 'current_identity': True, 'role_assertion': True, 'designation_match': 'equivalent', 'reason': 'Untrusted test output'}], identity_confidence='high', company_association_confidence='high', identity_claim_ids=['identity'], material_identity_conflict=False, warnings=[])
    reviewed, decisions = asyncio.run(review_evidence(e, InventedSourceReviewer(), INPUT))
    assert reviewed.identity_confidence == 'low'
    assert 'invalid_review_source_ids' in decisions[0]['reasons']


def test_reporting_source_cannot_be_promoted_to_primary_current_identity():
    e = evidence()
    e.sources[0].source_type = 'reporting'
    clean, _, _ = qualify_pages([(page(e), e)])
    reviewed, _ = asyncio.run(review_evidence(clean, Reviewer(), INPUT))
    assert reviewed.identity_confidence == 'low'


def test_undated_primary_live_identity_can_qualify_without_becoming_a_fresh_event():
    e = evidence()
    e.sources[0].event_at = e.sources[0].published_at = None
    e.sources[0].date_basis = 'unknown'
    clean, _, _ = qualify_pages([(page(e), e)])
    reviewed, _ = asyncio.run(review_evidence(clean, Reviewer(), INPUT))
    assert reviewed.identity_confidence == 'high'
    assert source_freshness(reviewed.sources[0])[1] is False
    assert rank(reviewed, candidates().signals)[1] == 'no_relevant_signal'


def test_stale_event_is_not_made_recent_by_republication_and_window_boundary_is_inclusive():
    e = evidence()
    e.sources[0].event_at = date.today() - timedelta(days=181)
    e.sources[0].published_at = date.today()
    assert source_freshness(e.sources[0])[1] is False
    assert 'outdated' in rank(e, candidates().signals)[0][0]['rejection_reasons']
    e.sources[0].event_at = date.today() - timedelta(days=180)
    assert source_freshness(e.sources[0])[1] is True
    assert rank(e, candidates().signals)[1] is None


def test_mixed_future_and_current_sources_do_not_hide_an_unplanned_future_date():
    e = evidence()
    other = e.sources[0].model_copy(update={'id': 'future', 'url': 'https://example.com/future', 'event_at': date.today() + timedelta(days=2)})
    e.sources.append(other)
    e.claims[1].source_ids.append('future')
    assert 'unlabelled_future_event' in rank(e, candidates().signals)[0][0]['rejection_reasons']


def test_persistence_refuses_dangling_refs_before_writing_artifact(factory):
    run_id = enqueue(factory)
    invalid = evidence().model_dump(mode='json')
    invalid['claims'][0]['source_ids'] += ['missing']
    with pytest.raises(ValueError, match='dangling_evidence_source_reference'):
        with factory.begin() as db:
            save_artifact(db, run_id, 'evidence', invalid)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Artifact)) == 0
        assert db.scalar(select(func.count()).select_from(SourceRecord)) == 0


def test_legacy_display_downgrades_confidence_and_hides_dangling_links_without_rewriting_history(factory):
    fixture = json.loads((Path(__file__).parent / 'data/reported_evidence.json').read_text())
    old = fixture['evidence']
    run_id = enqueue(factory)
    with factory.begin() as db:
        db.add(Artifact(run_id=run_id, kind='evidence', data=old))
        source = old['sources'][0]
        db.add(SourceRecord(run_id=run_id, source_key=source['id'], url=source['url'], data=source))
    with factory() as db:
        output = detail(db, db.get(Run, run_id))
        assert output['identity_confidence'] == 'low'
        assert output['claims'][0]['source_ids'] == [old['sources'][0]['id']]
        assert output['claims'][0]['verification'] == 'unsupported'
        assert latest(db, run_id, 'evidence') == old


def test_claim_cap_does_not_let_one_page_crowd_out_another_pages_identity():
    a, b = evidence(), evidence()
    a.claims = [a.claims[1].model_copy(update={'id': f'event-{i}', 'text': f'Synthetic event {i}'}) for i in range(30)]
    b.sources[0].url = 'https://example.com/leadership'
    b.claims = [b.claims[0]]
    clean, _, decisions = qualify_pages([(page(a), a), (page(b), b)])
    assert len(clean.claims) == 30
    assert any(c.kind == 'identity' and source_key(b.sources[0].url) in c.source_ids for c in clean.claims)
    assert any('claim_capacity_limit' in d['reasons'] for d in decisions)

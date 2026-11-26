"""Literal excerpt selection regressions; no model-generated quote can be accepted."""
import asyncio
import pytest
from app.excerpts import passage_candidates, selected_evidence
from app.qualification import qualify_pages, review_evidence, source_key
from app.schemas import ExcerptSelection, EvidenceReview
from tests.fixtures import evidence, INPUT, PASSAGE, FixtureProvider


def test_candidates_are_bounded_exact_substrings_and_keep_prospect_passages_after_boilerplate():
    body = ' '.join(['navigation'] * 1000) + ' ' + PASSAGE + ' ' + ' '.join(['footer'] * 1000)
    candidates = passage_candidates(body, INPUT)
    assert 0 < len(candidates) <= 16
    assert all(c['text'] in body and len(c['text'].split()) <= 60 for c in candidates)
    assert any(PASSAGE in c['text'] for c in candidates)
    assert passage_candidates('x' * 1600, INPUT) == []


def test_selected_quote_is_copied_from_fetched_body_without_changing_dates_or_credibility():
    original = evidence()
    p = {'url': original.sources[0].url, 'text': PASSAGE + ' ' + 'padding ' * 90}
    candidates = passage_candidates(p['text'], INPUT)
    claims = [c.model_copy(update={'source_ids': [source_key(p['url'])]}) for c in original.claims]
    choice = ExcerptSelection(passage_id=candidates[0]['id'], claims=claims)
    repaired = selected_evidence(p, original, choice, candidates)
    assert repaired.sources[0].passage == candidates[0]['text']
    for field in ('source_type', 'published_at', 'event_at', 'date_basis', 'planned'):
        assert getattr(repaired.sources[0], field) == getattr(original.sources[0], field)
    assert repaired.identity_confidence == 'unknown'
    with pytest.raises(ValueError, match='unknown_excerpt_id'):
        selected_evidence(p, original, ExcerptSelection(passage_id='made-up', claims=[]), candidates)
    with pytest.raises(ValueError, match='claims_without_excerpt'):
        selected_evidence(p, original, ExcerptSelection(passage_id=None, claims=original.claims), candidates)
    with pytest.raises(ValueError, match='invalid_selected_source_reference'):
        selected_evidence(p, original, ExcerptSelection(passage_id=candidates[0]['id'], claims=original.claims), candidates)


def test_selected_excerpt_cannot_justify_a_claim_missing_from_that_excerpt():
    e = evidence()
    e.claims[0].text = 'An assertion absent from the retained passage'
    clean, _, _ = qualify_pages([({'url': e.sources[0].url, 'text': PASSAGE}, e)])
    class Rejecting(FixtureProvider):
        async def structured(self, schema, task, data):
            review = await super().structured(schema, task, data)
            for c in review.claims:
                if c.claim_id == 'identity':
                    c.verification = 'unsupported'
                    c.current_identity = False
            return review
    reviewed, _ = asyncio.run(review_evidence(clean, Rejecting(), INPUT))
    assert reviewed.claims[0].verification == 'unsupported'
    assert reviewed.identity_confidence == 'low'


def test_equivalent_designation_does_not_imply_verified_current_identity():
    e = evidence()
    e.sources[0].published_at = e.sources[0].event_at = None
    e.sources[0].date_basis = 'unknown'
    class Uncertain(FixtureProvider):
        async def structured(self, schema, task, data):
            assert 'undated official biography is NOT proof' in task
            assert 'INDEPENDENT CHECKS' in task
            review = await super().structured(schema, task, data)
            review.claims[0].current_identity = False
            return review
    reviewed, decisions = asyncio.run(review_evidence(e, Uncertain(), INPUT))
    assert decisions[0]['designation_match'] == 'equivalent'
    assert 'role_currentness_unverified' in decisions[0]['reasons']
    assert reviewed.identity_confidence == 'high'
    assert reviewed.identity_checks.role_currentness.status == 'unverified'


def test_actual_63aff71e_snapshot_retains_exact_role_but_low_currentness():
    import json
    from pathlib import Path
    from app.schemas import Evidence
    from app.policy import evidence_gate
    fixture = json.loads((Path(__file__).parent / 'data/run_63aff71e_evidence.json').read_text())
    e = Evidence.model_validate(fixture['evidence'])
    assert fixture['website'] is None
    assert len(e.sources) == 4
    roster = next(s for s in e.sources if s.url.endswith('/about-us/leadership/'))
    role = next(c for c in e.claims if roster.id in c.source_ids)
    assert role.verification == 'supported' and role.kind == 'identity'
    assert e.identity_confidence == 'low'
    assert evidence_gate(e)[0] == 'insufficient_information'

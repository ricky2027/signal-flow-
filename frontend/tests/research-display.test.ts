// Synthetic contract fixtures only. These tests do not claim live research success.
import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { RunDetail } from '../src/lib/types';
Object.assign(globalThis, { React });
import { SignalsPanel, EvidencePanel } from '../src/components/evidence';
import { StageTimeline } from '../src/components/execution';
import { IdentityChecksPanel } from '../src/components/identity-checks';
import { isDetail } from '../src/lib/guards';
const base: RunDetail = {
    id: 'test-run', prospect_name: 'Test Person', company_name: 'Example Corp', status: 'insufficient_information', stage: 'evaluate_signals',
    created_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:01:00Z', outcome_reason: 'insufficient_information',
    input: { prospect_name: 'Test Person', company_name: 'Example Corp', designation: 'CFO', company_website: null, product_service: 'Analytics', value_proposition: 'Understand spending' },
    prospect_id: 'test-prospect', parent_run_id: null, warnings: [], error: null, current_draft_id: null,
    sources: [], claims: [], identity_confidence: 'unknown', signals: [], drafts: [], reviews: [], policy_version: 'test', model_versions: {}, provider_calls: [],
};
test('insufficient evidence explains blocked scoring, including historical runs without diagnostics', () => {
    const markup = renderToStaticMarkup(React.createElement(SignalsPanel, { run: base }));
    assert.match(markup, /Signal scoring blocked by evidence gate/);
    assert.match(markup, /before proposing or scoring candidates/);
    assert.doesNotMatch(markup, /No signals evaluated/);
    const timeline = renderToStaticMarkup(React.createElement(StageTimeline, { run: base, connection: 'synced', events: [{ run_id: base.id, sequence: 1, type: 'stage.completed', stage: 'evaluate_signals', occurred_at: base.finished_at!, payload: {} }] }));
    assert.match(timeline, /Evidence gate blocked scoring/);
    assert.equal((timeline.match(/Skipped after abstention/g) || []).length, 2);
});
test('selected scored signals display role/offer reasoning and supporting claims', () => {
    const run: RunDetail = { ...base, status: 'awaiting_review', signals: [{ id: 'test-signal', claim_ids: ['event'], fact_summary: 'Synthetic regional expansion', implication: 'Costs may grow', role_reason: 'Budget ownership', offer_reason: 'Spending visibility', role_relevance: 3, offer_fit: 3, quality: 1, age_days: 0, score: 100, eligible: true, rejection_reasons: [], selected: true }], claims: [{ id: 'event', text: 'Synthetic supported event', source_ids: ['source'], entity_match: true, verification: 'supported', kind: 'event', conflict_group: null }] };
    const markup = renderToStaticMarkup(React.createElement(SignalsPanel, { run }));
    assert.match(markup, /SELECTED PERSONALISATION HOOK/);
    assert.match(markup, /100/);
    assert.match(markup, /Budget ownership/);
    assert.match(markup, /Synthetic supported event/);
    assert.doesNotMatch(markup, /blocked by evidence gate/);
});
test('evidence diagnostics display actual recorded rejection categories without inventing sources', () => {
    const run: RunDetail = { ...base, research_diagnostics: {
        retrieval_attempts: [{ followup: false, sources: [{ url: 'https://example.com/fixture', available: false, error: 'http_403' }], selected_urls: [] }],
        verification_attempts: [{ sources: [{ source_id: 'test-source', url: 'https://example.com/fixture', accepted: false, quality: 0.8, reasons: ['passage_not_found'], fresh_signal_eligible: false, age_days: 300 }], claims: [{ claim_id: 'test-claim', eligible: false, reasons: ['source_not_retained'], explanation: 'The retained quote does not support this claim.' }], identity_confidence: 'unknown', gate_outcome: 'insufficient_information', gate_reasons: ['no_supported_identity_claim'], followup_requested: true }],
    } };
    const markup = renderToStaticMarkup(React.createElement(EvidencePanel, { run }));
    assert.match(markup, /0 retained sources/);
    assert.match(markup, /http 403/);
    assert.match(markup, /Passage rejected/);
    assert.match(markup, /passage not found/);
    assert.match(markup, /source not retained/);
    assert.match(markup, /Source quality 0.8/);
    assert.match(markup, /Not eligible for fresh signals/);
    assert.match(markup, /The retained quote does not support this claim/);
});
test('tracking variants of retained evidence are not displayed as unverified source leads', () => {
    const run: RunDetail = { ...base, sources: [{ id: 'test-source', url: 'https://example.com/profile', title: 'Test profile', publisher: 'Example', origin_group: 'example.com', source_type: 'primary', passage: 'Synthetic profile excerpt.', published_at: null, event_at: null, date_basis: 'unknown', planned: false, retrieved_at: '2026-01-01T00:00:00Z' }], provider_calls: [{ stage: 'research', status: 'tool_activity', tool_calls: [{ action: { sources: [{ url: 'https://example.com/profile?utm_source=test', title: 'Already retained' }] } }] }] };
    const markup = renderToStaticMarkup(React.createElement(EvidencePanel, { run }));
    assert.match(markup, /1 retained sources/);
    assert.doesNotMatch(markup, /Discovered source leads/);
});

test('successful retrieval does not hide a later extraction error', () => {
    const run: RunDetail = { ...base, research_diagnostics: {
        retrieval_attempts: [{ phase: 'extraction', sources: [{ url: 'https://example.com/profile', available: true, error: 'extraction_ValueError' }], selected_urls: [] }], verification_attempts: [],
    } };
    const markup = renderToStaticMarkup(React.createElement(EvidencePanel, { run }));
    assert.match(markup, /Extraction attempt/);
    assert.match(markup, /extraction ValueError/);
});

test('identity, association, title and currentness display independently without implying employment', () => {
    const run: RunDetail = { ...base, identity_confidence: 'high', identity_checks: {
        prospect_identity: { status: 'verified', claim_ids: ['identity'], source_ids: [], reasons: [] },
        company_association: { status: 'verified', claim_ids: ['identity'], source_ids: [], reasons: [] },
        title_match: { status: 'equivalent', claim_ids: ['identity'], source_ids: [], reasons: [] },
        role_currentness: { status: 'unverified', claim_ids: [], source_ids: [], reasons: ['role_currentness_unverified'] },
        role_claim_ids: ['identity'],
    } };
    assert.equal(isDetail(run), true);
    const markup = renderToStaticMarkup(React.createElement(IdentityChecksPanel, { run }));
    for (const label of ['Prospect identity', 'Company association', 'Title match', 'Current role']) assert.match(markup, new RegExp(label));
    assert.match(markup, /Current employment is unverified/);
    assert.match(markup, /unverified roles and duties are excluded/);
    assert.equal(isDetail({ ...run, identity_checks: { ...run.identity_checks, role_currentness: { status: 'success' } } }), false);
    assert.equal(renderToStaticMarkup(React.createElement(IdentityChecksPanel, { run: base })), '');
});

test('company-context signals explicitly disclose exclusion of unverified role claims', () => {
    const run: RunDetail = { ...base, status: 'awaiting_review', signals: [{ id: 'fixture', claim_ids: [], fact_summary: 'Synthetic expansion', implication: 'Spending may increase', role_reason: 'Company-event context only', offer_reason: 'Cost visibility', role_relevance: 2, offer_fit: 3, quality: 1, age_days: 0, score: 90, eligible: true, rejection_reasons: [], selected: true, relevance_basis: 'verified_company_context' }] };
    const markup = renderToStaticMarkup(React.createElement(SignalsPanel, { run }));
    assert.match(markup, /Verified company context · unverified role claims excluded/);
    assert.match(markup, /Prospect relevance/);
});

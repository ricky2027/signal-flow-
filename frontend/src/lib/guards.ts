// Reject unusable 2xx payloads rather than rendering fabricated defaults.
export function object(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
export const statusValues = ['queued', 'running', 'awaiting_review', 'approved', 'rejected', 'insufficient_information', 'conflicting_evidence', 'no_relevant_signal', 'failed'];
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(x => typeof x === 'string');
const keys = (value: Record<string, unknown>, names: string[]) => names.every(k => typeof value[k] === 'string');
export function isSummary(value: unknown) {
    return object(value) && keys(value, ['id', 'prospect_name', 'company_name', 'created_at']) && typeof value.status === 'string' && statusValues.includes(value.status);
}
export function isDetail(value: unknown) {
    if (!isSummary(value) || !object(value) || !object(value.input) || !keys(value.input, ['designation', 'product_service', 'value_proposition']) || !object(value.model_versions) || !strings(value.warnings))
        return false;
    if (!['sources', 'claims', 'signals', 'drafts', 'reviews', 'provider_calls'].every(k => Array.isArray(value[k])))
        return false;
    if (value.identity_checks != null) {
        const checks = value.identity_checks;
        if (!object(checks) || !strings(checks.role_claim_ids)) return false;
        if (!['prospect_identity', 'company_association', 'title_match', 'role_currentness'].every(key => {
            const c = checks[key];
            return object(c) && ['verified', 'unverified', 'equivalent', 'mismatch', 'conflicting'].includes(String(c.status)) && strings(c.claim_ids) && strings(c.source_ids) && strings(c.reasons);
        })) return false;
    }
    if (value.signal_evaluation != null) {
        const e = value.signal_evaluation;
        if (!object(e) || !['blocked', 'evaluated'].includes(String(e.state)) || !strings(e.gate_reasons) || typeof e.candidate_count !== 'number' || typeof e.eligible_count !== 'number')
            return false;
    }
    if (value.research_diagnostics != null) {
        const d = value.research_diagnostics;
        if (!object(d) || !Array.isArray(d.retrieval_attempts) || !Array.isArray(d.verification_attempts))
            return false;
        if (!d.retrieval_attempts.every(a => object(a) && Array.isArray(a.sources) && a.sources.every(s => object(s) && typeof s.url === 'string' && typeof s.available === 'boolean' && (s.error == null || typeof s.error === 'string'))))
            return false;
        if (!d.verification_attempts.every(a => object(a) && typeof a.identity_confidence === 'string' && strings(a.gate_reasons) && Array.isArray(a.sources) && a.sources.every(s => object(s) && keys(s, ['source_id', 'url']) && typeof s.accepted === 'boolean' && (s.quality === null || typeof s.quality === 'number') && strings(s.reasons) && (s.fresh_signal_eligible == null || typeof s.fresh_signal_eligible === 'boolean') && (s.age_days == null || typeof s.age_days === 'number')) && Array.isArray(a.claims) && a.claims.every(c => object(c) && typeof c.claim_id === 'string' && typeof c.eligible === 'boolean' && strings(c.reasons) && (c.explanation == null || typeof c.explanation === 'string') && (c.original_source_ids == null || strings(c.original_source_ids)))))
            return false;
    }
    const list = (name: string) => value[name] as unknown[];
    return list('sources').every(x => object(x) && keys(x, ['id', 'url', 'title', 'publisher', 'passage']))
        && list('claims').every(x => object(x) && keys(x, ['id', 'text', 'verification']) && strings(x.source_ids))
        && list('signals').every(x => object(x) && keys(x, ['id', 'fact_summary', 'role_reason', 'offer_reason', 'implication']) && typeof x.score === 'number' && typeof x.selected === 'boolean' && strings(x.claim_ids) && strings(x.rejection_reasons))
        && list('drafts').every(x => object(x) && keys(x, ['id', 'subject', 'body', 'validation_status', 'created_at']) && typeof x.version === 'number' && Array.isArray(x.claim_refs) && strings(x.validation_findings))
        && list('reviews').every(x => object(x) && keys(x, ['id', 'draft_id', 'action', 'created_at'])) && list('provider_calls').every(object);
}
export function isHistory(value: unknown) {
    return object(value) && Array.isArray(value.items) && value.items.every(isSummary) && (value.next_cursor === null || typeof value.next_cursor === 'string');
}
export function isDashboard(value: unknown) {
    return object(value) && ['prospects_researched', 'drafts_generated', 'pending_reviews', 'incomplete_runs', 'total_runs'].every(k => typeof value[k] === 'number' && Number.isFinite(value[k]) && (value[k] as number) >= 0) && object(value.status_counts) && statusValues.every(k => typeof (value.status_counts as Record<string, unknown>)[k] === 'number');
}

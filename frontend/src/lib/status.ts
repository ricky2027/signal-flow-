import type { Status, RunEvent, RunDetail } from './types';
export const statuses: Record<Status, {
    label: string;
    tone: string;
}> = { queued: { label: 'Queued', tone: 'neutral' }, running: { label: 'Researching', tone: 'blue' }, awaiting_review: { label: 'Ready for review', tone: 'amber' }, approved: { label: 'Approved', tone: 'green' }, rejected: { label: 'Rejected', tone: 'neutral' }, failed: { label: 'Failed', tone: 'red' }, insufficient_information: { label: 'Insufficient evidence', tone: 'amber' }, conflicting_evidence: { label: 'Conflicting evidence', tone: 'amber' }, no_relevant_signal: { label: 'No relevant signal', tone: 'neutral' } };
export function active(status: Status) {
    return status === 'queued' || status === 'running';
}
export const stages = [{ id: 'validate', label: 'Validate inputs', description: 'Confirm prospect and offer details' }, { id: 'research', label: 'Public web research', description: 'Discover company and prospect sources' }, { id: 'qualify_evidence', label: 'Verify evidence', description: 'Check identity, dates and supporting facts' }, { id: 'evaluate_signals', label: 'Evaluate signals', description: 'Score verified prospect context and offer' }, { id: 'draft', label: 'Write outreach', description: 'Create an evidence-backed draft' }, { id: 'validate_draft', label: 'Quality check', description: 'Validate claims before human review' }];
export function stageState(id: string, events: RunEvent[], run: Pick<RunDetail, 'status' | 'stage'>) {
    const relevant = events.filter(e => e.stage === id && (e.type === 'stage.started' || e.type === 'stage.completed'));
    const last = relevant.at(-1);
    if (run.status === 'failed' && run.stage === id)
        return 'failed';
    if (last?.type === 'stage.completed')
        return last.payload.evaluation_state === 'blocked' ? 'blocked' : 'complete';
    if (last?.type === 'stage.started')
        return active(run.status) ? 'active' : 'stopped';
    if (id === 'validate' && events.some(e => e.type === 'run.queued'))
        return 'complete';
    if (['draft', 'validate_draft'].includes(id) && ['insufficient_information', 'conflicting_evidence', 'no_relevant_signal'].includes(run.status))
        return 'skipped';
    return 'pending';
}
export function signalEmptyState(run: Pick<RunDetail, 'status' | 'signal_evaluation'>) {
    if (run.signal_evaluation?.state === 'blocked' || ['insufficient_information', 'conflicting_evidence'].includes(run.status)) {
        return { title: 'Signal scoring blocked by evidence gate', description: 'The evaluation node checked the evidence gate and stopped before proposing or scoring candidates. Outreach writing and quality checks were skipped.' };
    }
    if (active(run.status))
        return { title: 'Waiting for signal evaluation', description: 'Scores appear only after qualified evidence is available and candidate evaluation has finished.' };
    return { title: 'No signal candidates recorded', description: 'No scored candidates were saved for this run. Review retained evidence, gate decisions and provider activity for the recorded outcome.' };
}
export const errorExplanations: Record<string, string> = { evidence_extraction_failed: 'Public pages were retrieved, but every evidence extraction failed. Review provider errors and extraction diagnostics before rerunning.', ConnectError: 'The research provider could not be reached. Check backend network access and DNS configuration before retrying.', openai_credentials_missing: 'The backend needs an OpenAI API key before research can run.', worker_interrupted: 'The worker stopped before this research finished. Retry when the worker is available.', run_timeout: 'Research exceeded the execution time limit. Partial results have been preserved.', draft_grounding_failed: 'The generated draft did not pass evidence validation. No draft was released for review.', research_budget_exceeded: 'Research reached its configured request budget.', insufficient_information: 'There was not enough credible public evidence to verify this prospect and create a supported draft.', conflicting_evidence: 'Material sources disagree. Review the conflicting evidence before starting another run.', no_relevant_signal: 'Research did not identify a recent signal with enough relevance to verified prospect context and the offer.' };

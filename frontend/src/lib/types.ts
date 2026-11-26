export type { RunSummary, RunDetail, RunInput, RunHistory, QueuedRun, DraftView, SourceView, ScoredSignal, Status, Claim } from './contracts';
export type { DashboardStats } from './contracts';
export type RunEvent = {
    run_id: string;
    sequence: number;
    type: string;
    stage: string | null;
    occurred_at: string;
    payload: Record<string, unknown>;
};
export type ProviderCall = {
    stage?: string;
    status?: string;
    error_code?: string;
    http_status?: number | null;
    attempt?: number;
    latency_ms?: number;
    provider_request_id?: string;
    model?: string;
    tool_calls?: Array<{
        action?: {
            sources?: Array<{
                url: string;
                title?: string;
            }>;
        };
    }>;
};

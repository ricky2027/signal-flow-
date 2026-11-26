import { isHistory, isDetail, isDashboard } from './guards';
import type { RunInput, RunDetail, RunHistory, QueuedRun, DashboardStats, DraftView } from './types';
export class ApiError extends Error {
    constructor(public status: number, public code: string, message: string, public requestId?: string, public fields?: Record<string, string[]>) {
        super(message);
    }
}
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
        response = await fetch(`/api${path}`, { ...options, credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json', 'X-Signalflow-Client': 'web', ...options.headers }, signal: options.signal ?? AbortSignal.timeout(75000) });
    }
    catch (error) {
        if (options.signal?.aborted)
            throw error;
        throw new ApiError(0, 'connection_error', 'Connection lost. Check your network and try again.');
    }
    let data;
    try {
        data = await response.json();
    }
    catch {
        throw new ApiError(response.status, 'invalid_response', 'The API returned an unreadable response. Try again.');
    }
    if (!response.ok) {
        const e = data?.error;
        throw new ApiError(response.status, e?.code || 'request_failed', e?.message || 'The request could not be completed.', e?.request_id, e?.field_errors);
    }
    return data as T;
}
async function validated<T>(promise: Promise<T>, check: (value: unknown) => boolean): Promise<T> {
    const data = await promise;
    if (!check(data))
        throw new ApiError(502, 'invalid_response', 'The API returned an unexpected data format. Try refreshing the view.');
    return data;
}
export const api = {
    history: (query = '', signal?: AbortSignal) => validated(request<RunHistory>(`/v1/runs${query}`, { signal }), isHistory),
    dashboard: (signal?: AbortSignal) => validated(request<DashboardStats>('/v1/dashboard', { signal }), isDashboard),
    detail: (id: string, signal?: AbortSignal) => validated(request<RunDetail>(`/v1/runs/${encodeURIComponent(id)}`, { signal }), isDetail),
    login: (code: string) => request<{
        authenticated: boolean;
    }>('/v1/session', { method: 'POST', body: JSON.stringify({ access_code: code }) }),
    create: (input: RunInput, key: string) => request<QueuedRun>('/v1/runs', { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(input) }),
    edit: (id: string, version: number, subject: string, body: string) => request<DraftView>(`/v1/runs/${id}/draft`, { method: 'PATCH', body: JSON.stringify({ expected_version: version, subject, body }) }),
    action: (id: string, action: 'approve' | 'reject' | 'regenerate' | 'retry', body: object, key?: string) => request<RunDetail | QueuedRun>(`/v1/runs/${id}/${action}`, { method: 'POST', body: JSON.stringify(body), headers: key ? { 'Idempotency-Key': key } : {} }),
};

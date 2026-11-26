import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { active, stageState, statuses } from '../src/lib/status';
import { isDashboard, isDetail, isHistory } from '../src/lib/guards';
import { safeUrl, initials, evidenceUrlKey } from '../src/lib/utils';
import type { RunEvent } from '../src/lib/types';
import { api, ApiError } from '../src/lib/api';
const event = (type: string, sequence: number, stage: string | null = 'research'): RunEvent => ({ type, sequence, stage, run_id: 'test-only', occurred_at: '2026-01-01T00:00:00Z', payload: {} });
test('all actual backend statuses have distinct labels and only queued/running are active', () => {
    const schema=JSON.parse(readFileSync(resolve(process.cwd(),'../backend/openapi.json'),'utf8'));
    assert.deepEqual(Object.keys(statuses).sort(), [...schema.components.schemas.Status.enum].sort());
    assert.equal(active('failed'), false);
    assert.equal(active('insufficient_information'), false);
    assert.equal(active('running'), true);
    assert.notEqual(statuses.failed.label, statuses.insufficient_information.label);
});
test('timeline never invents completion from run status', () => {
    assert.equal(stageState('draft', [], { status: 'failed', stage: 'research' }), 'pending');
    assert.equal(stageState('research', [event('stage.started', 1)], { status: 'failed', stage: 'research' }), 'failed');
    assert.equal(stageState('research', [event('stage.started', 1), event('stage.completed', 2), event('stage.started', 3)], { status: 'running', stage: 'research' }), 'active');
});
test('abstention leaves incomplete stages stopped, not complete', () => {
    assert.equal(stageState('research', [event('stage.started', 1)], { status: 'insufficient_information', stage: 'research' }), 'stopped');
    assert.equal(stageState('validate', [event('run.queued', 1, 'validate')], { status: 'queued', stage: null }), 'complete');
});
test('runtime guards reject malformed API success bodies', () => {
    assert.equal(isHistory({ items: [], next_cursor: null }), true);
    assert.equal(isHistory({ items: [{ id: 'bad' }], next_cursor: null }), false);
    assert.equal(isDetail({}), false);
    assert.equal(isDashboard({}), false);
});
test('unsafe URLs are never clickable source links', () => {
    assert.equal(safeUrl('javascript:alert(1)'), undefined);
    assert.equal(safeUrl('file:///etc/passwd'), undefined);
    assert.equal(safeUrl('https://example.com/news'), 'https://example.com/news');
    assert.equal(initials('Alex Morgan'), 'AM');
    assert.equal(evidenceUrlKey('https://example.com/profile?utm_source=search#bio'), evidenceUrlKey('https://example.com/profile'));
    assert.notEqual(evidenceUrlKey('https://example.com/profile?section=board'), evidenceUrlKey('https://example.com/profile'));
});
test('browser requests include same-origin credentials and preserve invalid-code errors', async () => {
    const original = globalThis.fetch;
    try {
        globalThis.fetch = async (url, init) => {
            assert.equal(url, '/api/v1/session');
            assert.equal(init?.credentials, 'same-origin');
            assert.equal(new Headers(init?.headers).get('x-signalflow-client'), 'web');
            return Response.json({ authenticated: true });
        };
        assert.equal((await api.login('test-only')).authenticated, true);
        globalThis.fetch = async () => Response.json({ error: { code: 'invalid_access_code', message: 'Invalid access code' } }, { status: 401 });
        await assert.rejects(api.login('wrong-test-only'), (error: unknown) => error instanceof ApiError && error.status === 401 && error.code === 'invalid_access_code');
    } finally {
        globalThis.fetch = original;
    }
});

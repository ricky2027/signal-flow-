import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { NextRequest } from 'next/server';
import { GET, POST } from '../src/app/api/[...path]/route';
const { CookieJar } = createRequire(import.meta.url)('jsdom');
const root = resolve(process.cwd(), '..');
const database = `/tmp/signalflow-web-integration-${randomUUID()}.sqlite`;
const python = process.env.BACKEND_PYTHON || resolve(root, 'backend/.venv/bin/python');
// The proxy requires BACKEND_URL; the in-process fetch mock below routes every request
// to the ASGI bridge regardless of host, so any non-empty value is sufficient here.
process.env.BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
const env = { ...process.env, OPENAI_API_KEY: process.env.SIGNALFLOW_TEST_LIVE === '1' ? process.env.OPENAI_API_KEY : '', DATABASE_URL: `sqlite:///${database}`, SESSION_SECRET: 'isolated-integration-test-secret-0000000000', DEMO_ACCESS_CODE: 'test-access', COOKIE_SECURE: 'false', APP_ORIGIN: 'http://localhost:3000' };
function bridge(payload: object) {
    const child = spawnSync(python, [resolve(root, 'backend/tests/frontend_bridge.py')], { cwd: resolve(root, 'backend'), input: JSON.stringify(payload), encoding: 'utf8', env, timeout: 90000 });
    if (child.status !== 0)
        throw new Error(`ASGI bridge failed: ${child.stderr}`);
    return JSON.parse(child.stdout);
}
const originalFetch = globalThis.fetch;
let cookie = '';
async function proxy(method: string, path: string, body?: object, key?: string) {
    const headers: Record<string, string> = { origin: 'http://localhost:3000', 'content-type': 'application/json', 'x-signalflow-client': 'web' };
    if (cookie)
        headers.cookie = cookie;
    if (key)
        headers['idempotency-key'] = key;
    const req = new NextRequest(`http://localhost:3000/api/${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const result = await (method === 'GET' ? GET : POST)(req, { params: Promise.resolve({ path: path.split('?')[0].split('/') }) });
    const session = result.headers.get('set-cookie');
    if (session)
        cookie = session.split(';')[0];
    return result;
}
test('Next proxy ↔ real FastAPI ↔ isolated persistence, failure and SSE', async () => {
    // In-process transport replaces sockets only. All API and worker code is real.
    globalThis.fetch = async (input, init) => {
        const url = new URL(String(input));
        const response = bridge({ method: init?.method, path: url.pathname + url.search, headers: Object.fromEntries(new Headers(init?.headers)), body: init?.body });
        return new Response(typeof response.body === 'string' ? response.body : JSON.stringify(response.body), { status: response.status, headers: response.headers });
    };
    try {
        assert.equal((await proxy('GET', 'v1/runs?limit=1')).status, 401);
        const invalid = await proxy('POST', 'v1/session', { access_code: 'wrong-test-code' });
        assert.equal(invalid.status, 401);
        assert.equal((await invalid.json()).error.code, 'invalid_access_code');
        assert.equal(invalid.headers.get('set-cookie'), null);
        assert.equal(cookie, '');
        const login = await proxy('POST', 'v1/session', { access_code: 'test-access' });
        assert.equal(login.status, 200);
        // Use a cookie jar to check URL scope/retention, rather than blindly
        // replaying a token that a browser might reject or withhold.
        const jar = new CookieJar();
        const retained = jar.setCookieSync(login.headers.get('set-cookie')!, 'http://localhost:3000/api/v1/session');
        assert.equal(retained.hostOnly, true);
        assert.equal(retained.domain, 'localhost');
        assert.equal(retained.path, '/');
        assert.equal(retained.httpOnly, true);
        assert.equal(retained.secure, false);
        assert.equal(retained.sameSite, 'strict');
        assert.equal(jar.getCookieStringSync('http://127.0.0.1:3000/api/v1/runs'), '');
        cookie = jar.getCookieStringSync('http://localhost:3000/api/v1/runs?limit=1');
        assert.ok(cookie.includes('signalflow_session='));
        assert.equal((await proxy('GET', 'v1/runs?limit=1')).status, 200);
        let response = await proxy('GET', 'v1/dashboard');
        assert.equal(response.status, 200);
        assert.equal((await response.json()).total_runs, 0);
        const input = { prospect_name: 'Satya Nadella', company_name: 'Microsoft', designation: 'CEO', product_service: 'Cloud cost analytics', value_proposition: 'Understand cloud spending.' };
        response = await proxy('POST', 'v1/runs', input, 'create-one');
        assert.equal(response.status, 202);
        const queued = await response.json();
        const duplicate = await proxy('POST', 'v1/runs', input, 'create-one');
        assert.equal((await duplicate.json()).run_id, queued.run_id);
        assert.equal((await (await proxy('GET', 'v1/dashboard')).json()).incomplete_runs, 1);
        bridge({ mode: 'worker' });
        const detail = await (await proxy('GET', `v1/runs/${queued.run_id}`)).json();
        // This environment cannot contact OpenAI; an unavailable provider must fail safely.
        assert.equal(detail.status, 'failed');
        assert.equal(detail.sources.length, 0);
        assert.equal(detail.drafts.length, 0);
        assert.ok(detail.error.code);
        const history = await (await proxy('GET', 'v1/runs')).json();
        assert.equal(history.items.length, 1);
        response = await proxy('GET', `v1/runs/${queued.run_id}/events`);
        assert.match(response.headers.get('content-type') || '', /text\/event-stream/);
        const stream = await response.text();
        assert.match(stream, /run.failed/);
        assert.match(stream, /id: 1/);
        const stats = await (await proxy('GET', 'v1/dashboard')).json();
        assert.equal(stats.drafts_generated, 0);
        assert.equal(stats.prospects_researched, 0);
        assert.equal(stats.status_counts.failed, 1);
    }
    finally {
        globalThis.fetch = originalFetch;
        rmSync(database, { force: true });
    }
});
test('proxy converts API disconnection into an actionable 502', async () => {
    globalThis.fetch = async () => {
        throw new TypeError('Network unavailable');
    };
    try {
        const result = await proxy('GET', 'v1/runs');
        assert.equal(result.status, 502);
        assert.equal((await result.json()).error.code, 'backend_unavailable');
    }
    finally {
        globalThis.fetch = originalFetch;
    }
});
test('proxy preserves version conflicts and rejects unknown upstream routes', async () => {
    globalThis.fetch = async () => Response.json({ error: { code: 'version_conflict', message: 'Refresh the current draft' } }, { status: 409 });
    try {
        const result = await proxy('POST', 'v1/runs/test/approve', { draft_version: 1 });
        assert.equal(result.status, 409);
        assert.equal((await result.json()).error.code, 'version_conflict');
        assert.equal((await proxy('GET', 'untrusted-path')).status, 404);
    }
    finally {
        globalThis.fetch = originalFetch;
    }
});

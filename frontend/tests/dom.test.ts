import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { rmSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import React, { act } from 'react';
const require = createRequire(import.meta.url);
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost:3000' });
Object.assign(globalThis, { window: dom.window, self: dom.window, document: dom.window.document, FormData: dom.window.FormData, Event: dom.window.Event, React, IS_REACT_ACT_ENVIRONMENT: true });
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
const { createRoot } = require('react-dom/client');
const { Dashboard } = require('../src/components/dashboard');
const { History } = require('../src/components/history');
const { Shell } = require('../src/components/shell');
const { AuthGate } = require('../src/components/auth-gate');
const { ResearchForm } = require('../src/components/research-form');
const { RunDetailScreen } = require('../src/components/run-detail');
const { AppRouterContext } = require('next/dist/shared/lib/app-router-context.shared-runtime');
const { SearchParamsContext } = require('next/dist/shared/lib/hooks-client-context.shared-runtime');
const rootPath = resolve(process.cwd(), '..');
const db = `/tmp/signalflow-dom-${randomUUID()}.sqlite`;
const env = { ...process.env, DATABASE_URL: `sqlite:///${db}`, SESSION_SECRET: 'dom-integration-test-session-secret-00000000', DEMO_ACCESS_CODE: 'dom-access', COOKIE_SECURE: 'false', APP_ORIGIN: 'http://localhost:3000', OPENAI_API_KEY: '' };
function bridge(payload: object) {
    const c = spawnSync(process.env.BACKEND_PYTHON || resolve(rootPath, 'backend/.venv/bin/python'), [resolve(rootPath, 'backend/tests/frontend_bridge.py')], { cwd: resolve(rootPath, 'backend'), input: JSON.stringify(payload), encoding: 'utf8', env, timeout: 30000 });
    if (c.status !== 0)
        throw new Error(c.stderr);
    return JSON.parse(c.stdout);
}
let cookie = '';
const originalFetch = globalThis.fetch;
let navigation = '';
const router = { push: (url: string) => {
        navigation = url;
    }, replace: () => {
    }, back: () => {
    }, forward: () => {
    }, refresh: () => {
    }, prefetch: async () => {
    } };
const root = createRoot(document.getElementById('root')!);
function content(node: React.ReactNode) {
    return React.createElement(AppRouterContext.Provider, { value: router }, React.createElement(SearchParamsContext.Provider, { value: new URLSearchParams() }, node));
}
async function flush() {
    await act(async () => {
        await new Promise(r => setTimeout(r, 25));
    });
}
function text() {
    return document.body.textContent || '';
}
async function setInput(id: string, value: string) {
    await act(async () => {
        const element = document.getElementById(id) as HTMLInputElement;
        const prototype = element.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(element, value);
        element.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    });
}
class TransportEventSource {
    static instances: TransportEventSource[] = [];
    listeners = new Map<string, Function>();
    onopen: Function | null = null;
    onerror: Function | null = null;
    closed = false;
    constructor(public url: string) {
        TransportEventSource.instances.push(this);
        queueMicrotask(() => this.onopen?.());
    }
    addEventListener(name: string, listener: Function) {
        this.listeners.set(name, listener);
    }
    close() {
        this.closed = true;
    }
    emit(event: Record<string, unknown>) {
        this.listeners.get(event.type as string)?.({ data: JSON.stringify(event) });
    }
}
Object.assign(globalThis, { EventSource: TransportEventSource });
test('DOM interaction audit against real FastAPI: auth, validated form, SSE interruption, failed run and empty output', async () => {
    globalThis.fetch = async (input, init) => {
        const u = new URL(String(input), 'http://localhost:3000');
        const headers = Object.fromEntries(new Headers(init?.headers));
        headers.origin = 'http://localhost:3000';
        if (cookie)
            headers.cookie = cookie;
        const r = bridge({ method: init?.method || 'GET', path: u.pathname, headers, body: init?.body });
        if (r.headers['set-cookie'])
            cookie = r.headers['set-cookie'].split(';')[0];
        return new Response(typeof r.body === 'string' ? r.body : JSON.stringify(r.body), { status: r.status, headers: r.headers });
    };
    try {
        await act(async () => root.render(content(React.createElement(AuthGate, null, React.createElement('div', null, 'Authenticated actual workspace')))));
        await flush();
        assert.match(text(), /Workspace access code/);
        await setInput('access-code', 'dom-access');
        await act(async () => {
            document.querySelector('form')!.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }));
        });
        await flush();
        assert.match(text(), /Authenticated actual workspace/);
        await act(async () => root.render(content(React.createElement(Shell, null, React.createElement(Dashboard)))));
        await flush();
        assert.match(text(), /Research overview/);
        assert.match(text(), /Your first signal starts here/);
        assert.equal(document.querySelectorAll('.metric-value')[0].textContent, '0');
        assert.equal(document.querySelectorAll('.metric-value')[1].textContent, '0');
        const menu = document.querySelector('[aria-label="Open navigation"]') as HTMLButtonElement;
        await act(async () => menu.click());
        assert.ok(document.querySelector('.sidebar.is-open'));
        await act(async () => (document.querySelector('[aria-label="Close navigation"]') as HTMLButtonElement).click());
        assert.equal(document.querySelector('.sidebar.is-open'), null);
        await act(async () => root.render(content(React.createElement(History, { reviewOnly: true }))));
        await flush();
        assert.match(text(), /Your review queue is clear/);
        await act(async () => root.render(content(React.createElement(ResearchForm))));
        assert.equal((document.getElementById('prospect_name') as HTMLInputElement).required, true);
        assert.equal((document.getElementById('company_website') as HTMLInputElement).type, 'url');
        for (const [id, value] of Object.entries({ prospect_name: 'Satya Nadella', designation: 'CEO', company_name: 'Microsoft', company_website: 'https://microsoft.com', product_service: 'Cloud cost analytics', value_proposition: 'Understand cloud spending.' }))
            await setInput(id, value);
        await act(async () => {
            document.querySelector('form')!.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }));
        });
        assert.match(navigation, /^\/runs\//);
        const id = navigation.split('/').at(-1)!;
        const persisted = bridge({ method: 'GET', path: `/api/v1/runs/${id}`, headers: { cookie } });
        assert.equal(persisted.body.input.company_website, 'https://microsoft.com');
        await act(async () => root.render(content(React.createElement(RunDetailScreen, { id }))));
        await flush();
        assert.match(text(), /Satya Nadella/);
        assert.match(text(), /Queued/);
        assert.match(text(), /0 sources/);
        assert.ok(document.querySelector('.run-context-strip a[href="https://microsoft.com/"]'));
        assert.doesNotMatch(text(), /Website not provided/);
        const stream = TransportEventSource.instances.at(-1)!;
        await act(async () => {
            for (const e of bridge({ mode: 'events', run_id: id }))
                stream.emit(e);
        });
        await flush();
        assert.match(text(), /Completed/); // only real input-validation event
        await act(async () => stream.onerror?.());
        await flush();
        assert.match(text(), /Live connection interrupted/);
        bridge({ mode: 'worker' });
        await act(async () => {
            for (const e of bridge({ mode: 'events', run_id: id }))
                stream.emit(e);
        });
        await flush();
        assert.match(text(), /Research couldn’t be completed/);
        assert.match(text(), /openai_credentials_missing/);
        const clickTab = async (name: string) => {
            const button = Array.from(document.querySelectorAll('[role="tab"]')).find(e => e.textContent?.startsWith(name)) as HTMLButtonElement;
            await act(async () => button.click());
        };
        await clickTab('Evidence');
        assert.match(text(), /No evidence retained/);
        await clickTab('Outreach draft');
        assert.match(text(), /No draft generated/);
        assert.doesNotMatch(text(), /Approve draft/);
        await clickTab('Execution log');
        assert.match(text(), /Research failed/);
        assert.match(text(), /Browser connection log/);
        // A malformed/unavailable API cannot be reinterpreted as successful research.
        globalThis.fetch = async () => {
            throw new TypeError('Test transport disconnected');
        };
        const refresh = Array.from(document.querySelectorAll('button')).find(b => b.getAttribute('aria-label') === 'Refresh run')!;
        await act(async () => refresh.click());
        await flush();
        assert.match(text(), /Connection lost/);
        assert.match(text(), /Research couldn’t be completed/);
        // Restore the actual ASGI transport to verify history and reopen navigation.
        globalThis.fetch = async (input, init) => {
            const u = new URL(String(input), 'http://localhost:3000');
            const r = bridge({ method: init?.method || 'GET', path: u.pathname, headers: { ...Object.fromEntries(new Headers(init?.headers)), origin: 'http://localhost:3000', cookie }, body: init?.body });
            return new Response(JSON.stringify(r.body), { status: r.status, headers: r.headers });
        };
        await act(async () => root.render(content(React.createElement(History))));
        await flush();
        assert.match(text(), /Satya Nadella/);
        assert.match(text(), /Failed/);
        const search = document.querySelector('[aria-label="Search loaded runs"]') as HTMLInputElement;
        await act(async () => {
            Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value')!.set!.call(search, 'does-not-exist');
            search.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
        });
        assert.match(text(), /No matching runs/);
    }
    finally {
        await act(async () => root.unmount());
        globalThis.fetch = originalFetch;
        rmSync(db, { force: true });
        dom.window.close();
    }
});

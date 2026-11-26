import { NextRequest } from 'next/server';
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
// Serverless function ceiling for the backend proxy (incl. SSE event streams).
// 60s is the Vercel Hobby maximum; raise to 300 on Pro. When a long run's SSE
// stream is cut at this ceiling the client reconnects from its last cursor and
// keeps polling, so live updates degrade gracefully rather than breaking.
export const maxDuration = 60;
// Same-origin transport only: preserve the real browser Origin for backend CSRF checks.
async function proxy(request: NextRequest, { params }: {
    params: Promise<{ path: string[] }>;
}) {
    if (request.method !== 'GET' && request.headers.get('origin') !== (process.env.APP_ORIGIN || 'http://localhost:3000')) {
        return Response.json({error:{code:'origin_rejected',message:'This request did not originate from the configured workspace.'}},{status:403});
    }
    const {path: segments} = await params;
    const path = segments.join('/');
    if (!path.startsWith('v1/') && !['health/live', 'health/ready'].includes(path))
        return Response.json({ error: { code: 'not_found', message: 'Unknown endpoint' } }, { status: 404 });
    const target = new URL(path.startsWith('health/') ? `/${path}` : `/api/${path}`, process.env.BACKEND_URL || 'http://127.0.0.1:8000');
    target.search = request.nextUrl.search;
    const headers = new Headers();
    for (const name of ['cookie', 'origin', 'content-type', 'idempotency-key', 'x-signalflow-client', 'last-event-id']) {
        const value = request.headers.get(name);
        if (value)
            headers.set(name, value);
    }
    const stream = path.endsWith('/events');
    try {
        const upstream = await fetch(target, { method: request.method, headers, body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.text(), cache: 'no-store', signal: stream ? request.signal : AbortSignal.timeout(75000), redirect: 'manual' });
        const output = new Headers({ 'Cache-Control': 'no-store' });
        for (const name of ['content-type', 'set-cookie', 'x-request-id']) {
            const value = upstream.headers.get(name);
            if (value)
                output.set(name, value);
        }
        if (stream) {
            output.set('X-Accel-Buffering', 'no');
            output.set('Connection', 'keep-alive');
        }
        return new Response(upstream.body, { status: upstream.status, headers: output });
    }
    catch {
        return Response.json({ error: { code: 'backend_unavailable', message: 'Cannot reach the SIGNALFLOW API. Check that the backend is running.', retryable: true } }, { status: 502 });
    }
}
export { proxy as GET, proxy as POST, proxy as PATCH };

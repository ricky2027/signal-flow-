# Deploying SignalFlow (Vercel frontend + external backend)

## Why this is multi-service (and why the backend is NOT on Vercel)
SignalFlow has three runtime pieces:

| Piece | What it is | Where it runs |
| --- | --- | --- |
| **Frontend** | Next.js app (`frontend/`) with a same-origin `/api/*` proxy | **Vercel** |
| **API** | FastAPI (`backend/app/api.py`), served by uvicorn | **Always-on host** (Render / Railway / Fly) |
| **Worker** | `backend/app.worker` — a persistent PostgreSQL queue daemon that executes research runs (up to `RUN_TIMEOUT_SECONDS`, default 540s) | **Always-on host** (same as API) |
| **Database** | PostgreSQL | **Managed** (Neon / Supabase / RDS) |

Vercel runs **serverless functions**, which are request-scoped and time-limited. They cannot host:
- the **worker** (a long-running background process with no incoming request), or
- research runs that take **minutes** (far beyond serverless function limits), or
- long-lived **SSE** streams.

So the only functionality-preserving topology is: **frontend on Vercel, API + worker on a host that
supports long-running processes.** The frontend already talks to the backend only through
`BACKEND_URL`, so this split needs no code rewrite — just configuration.

## 1. Frontend on Vercel

Config committed at `frontend/vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "installCommand": "npm ci"
}
```

**Vercel project settings (manual, in the dashboard):**
- **Root Directory: `frontend`** — the Next.js app is not at the repo root. This is required; `vercel.json`
  and the build run from there.
- Framework preset: Next.js (auto-detected).

**Frontend environment variables** (Project → Settings → Environment Variables; these are *server-only*,
never `NEXT_PUBLIC_`):

| Variable | Value | Notes |
| --- | --- | --- |
| `BACKEND_URL` | `https://<your-backend-host>` | Public HTTPS origin of the deployed FastAPI API. No trailing path. |
| `APP_ORIGIN` | `https://<your-vercel-domain>` | The exact URL users open (your production Vercel domain or custom domain). Must equal the backend's `APP_ORIGIN`. |

`frontend/src/app/api/[...path]/route.ts` sets `maxDuration = 60` (Vercel Hobby ceiling). On Pro you may
raise it to 300 for longer-lived SSE; the client reconnects and polls regardless, so updates degrade
gracefully when a stream is cut.

## 2. API + worker on an always-on host

Deploy `backend/` as **two processes** sharing the same image and env:

- **web:** `uv run uvicorn app.api:app --host 0.0.0.0 --port $PORT`
- **worker:** `uv run python -m app.worker`
- **release / pre-deploy:** `uv run alembic upgrade head`

(Locally the README uses `--host 127.0.0.1`; on a host bind `0.0.0.0` and the platform's `$PORT`.)

**Backend environment variables** (from `backend/.env.example` — do not invent values):

| Variable | Value | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://…` | Your managed Postgres connection string. |
| `OPENAI_API_KEY` | `sk-…` | OpenAI project key with Responses + web-search access. |
| `OPENAI_RESEARCH_MODEL` | `gpt-4.1` | |
| `OPENAI_REASONING_MODEL` | `gpt-4.1` | |
| `SESSION_SECRET` | 32+ random chars | |
| `DEMO_ACCESS_CODE` | your login code | Used to sign in on the frontend. |
| `APP_ORIGIN` | `https://<your-vercel-domain>` | **Must equal** the frontend's `APP_ORIGIN`; the API rejects other origins. |
| `COOKIE_SECURE` | `true` | Required for HTTPS production cookies. |
| `RUN_TIMEOUT_SECONDS` | `540` | Room for multi-pass research runs. |
| `GLOBAL_DAILY_RUN_LIMIT` / `MAX_RUNS_PER_SESSION_PER_DAY` / `MAX_SEARCH_REQUESTS` / `MAX_SOURCES` | optional | Tuning; defaults in `.env.example`. |

## How the binding works (no CORS needed)
The browser only ever calls the Vercel domain. `frontend/src/app/api/[...path]/route.ts` forwards each
request server-side to `BACKEND_URL`, preserving the browser `Origin` and `Cookie` headers and relaying
`Set-Cookie` back. Because the backend checks `Origin == APP_ORIGIN`, those two values must match. Cookies
are same-origin (the Vercel domain) + `Secure` + `SameSite=strict`, so auth and SSE work without any CORS
configuration or exposed provider keys.

## Remaining manual steps
1. **Provision Postgres** (e.g. Neon); copy its `DATABASE_URL`.
2. **Deploy the backend** (API + worker, two processes) to your chosen host with the env vars above; run
   `alembic upgrade head`. Note the public API URL → this is `BACKEND_URL`.
3. **Decide the frontend domain** (the production `*.vercel.app` alias or a custom domain) so you can set
   `APP_ORIGIN` on both sides to the same value.
4. **Import the repo into Vercel**, set **Root Directory = `frontend`**, add `BACKEND_URL` and `APP_ORIGIN`,
   and deploy.
5. **Set the backend's `APP_ORIGIN`** to that same frontend URL and redeploy the backend.
6. **Verify:** open the frontend, sign in with `DEMO_ACCESS_CODE`, start a run, and confirm the worker
   processes it (stages advance, a draft or honest abstention appears).

> If you want everything on one platform instead, deploy the frontend, API, and worker all to the
> always-on host (e.g. Render static + web + worker) and skip Vercel — but the worker and long runs
> rule out an all-Vercel deployment.

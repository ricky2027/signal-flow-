# Proposed deployment and access handoff

**Status: prepared operating recipe only. No hosting resources created, no deployment applied, no public URL verified.** Local PostgreSQL/live research/browser gates remain blocked as recorded in ENGINEERING_REPORT.md. Stop at the user account/payment boundary until the prerequisites there are supplied.

## Proposed provider and resources

Use one Render workspace/region for four resources. This follows the documented [Next.js Node service](https://render.com/docs/deploy-nextjs-app), [FastAPI web service](https://render.com/docs/deploy-fastapi), [independent background worker](https://render.com/docs/background-workers) and [managed PostgreSQL](https://render.com/docs/postgresql-creating-connecting) model. Next.js must run as a Node service because it proxies API/SSE traffic; a static export is insufficient.

These are requested names, not actual provisioned service identifiers:

| Resource | Repository root directory | Build command | Start/operation | Health check |
|---|---|---|---|---|
| signalflow-web | frontend | `npm ci && npm run build` | `node node_modules/next/dist/bin/next start --hostname 0.0.0.0 --port $PORT` | `/` for process availability; separately verify proxied API readiness |
| signalflow-api | backend | `pip install .` | `uvicorn app.api:app --host 0.0.0.0 --port $PORT` | `/health/ready` |
| signalflow-worker | backend | `pip install .` | `python -m app.worker` | No HTTP listener; inspect worker logs, job claims and lease renewal |
| signalflow-db | Managed PostgreSQL | N/A | Persistent managed database | Provider database status plus application DB checks |

The production web command deliberately binds all interfaces; the npm start/dev scripts remain localhost-oriented. Select a maintained Node LTS runtime compatible with Next.js 16 and a supported Python runtime, then run build/tests on those exact deployment versions before release. Current local checks were on Node 20.20.1 and Python 3.14.3; they do not verify a different cloud runtime.

No compute plan, billing amount or storage size is assumed. Review the provider dashboard's current prices and resource limitations in your account. Choose resources that support the required persistent worker and database; do not purchase them through an unauthenticated or unapproved account.

## Environment configuration

Use the host secret manager. Do not place keys in build arguments, source, NEXT_PUBLIC variables, logs or screenshots.

| Variable | Web | API | Worker | Value/source |
|---|---|---|---|---|
| BACKEND_URL | Yes | — | — | Actual reachable API service origin; no guessed URL |
| APP_ORIGIN | Yes | Yes | Optional | Actual HTTPS frontend origin, identical in web and API |
| DATABASE_URL | — | Secret | Secret | Same internal managed DB, using `postgresql+psycopg://` |
| OPENAI_API_KEY | — | Secret | Secret | Funded project key with tested model/tool access |
| SESSION_SECRET | — | Secret | — | Random persistent value ≥32 characters; keep stable across restarts |
| DEMO_ACCESS_CODE | — | Secret | — | Owner-chosen workspace code |
| COOKIE_SECURE | — | Yes | — | `true` for HTTPS |
| OPENAI_RESEARCH_MODEL | — | Yes | Yes | Model actually verified with web_search |
| OPENAI_REASONING_MODEL | — | Yes | Yes | Model actually verified with strict schemas |
| RUN_TIMEOUT_SECONDS | — | Yes | Yes | Current default 180; verify real run latency |
| MAX_SEARCH_REQUESTS / MAX_SOURCES | — | Yes | Yes | Current defaults 4 / 12 |
| MAX_RUNS_PER_SESSION_PER_DAY / GLOBAL_DAILY_RUN_LIMIT | — | Yes | Yes | Owner-approved limits; current defaults 10 / 50 |

Render's raw database connection string may start with `postgresql://`. The current app uses psycopg 3: explicitly configure the `postgresql+psycopg://` SQLAlchemy scheme, retaining the actual credentials, host and query options. Do not assume psycopg2 is installed.

Browser traffic stays on the frontend origin via `/api/*`. Preserve cookies, Origin, X-Signalflow-Client, idempotency and SSE replay headers. Existing strict Origin/CSRF checks should remain enabled. Wildcard CORS is neither needed nor appropriate for this same-origin design. If a direct cross-origin browser API is introduced later, it needs a separate explicit, credential-aware CORS design and tests.

## Ordered release procedure after account access and local acceptance

1. Obtain the user-authorized repository/workspace, approved resource choices and scoped API access. No account access is currently present in this task. Render's [API setup](https://render.com/docs/api) describes key creation and permissions.
2. Install/lock backend dependencies in a clean environment. Run the complete full/production/browser-package npm audits. Resolve findings before release; matching target versions alone is not a clean scan.
3. Provision PostgreSQL in the same region as API/worker. Configure the actual driver URL and secrets. Do not use ephemeral SQLite in production.
4. Build the API and execute `alembic upgrade head` from backend/ against the actual database. Inspect the revision and expected tables. Do not start consuming jobs until migrations complete.
5. Start API and the separate worker. Confirm API `/health/ready` returns 200. It checks DB/configuration only; `provider_access: not_checked` is not successful OpenAI verification.
6. Build/start Next.js. Obtain the provider-issued frontend URL, configure it as APP_ORIGIN in both services, set the actual BACKEND_URL, and restart affected services. Ensure TLS and secure session cookies.
7. Verify SSE is not buffered and periodic heartbeat traffic passes the hosting/proxy timeouts. Reconnect from a saved event cursor. Confirm user data remains session-scoped.
8. From a clean browser, submit a real prospect/offer. Save the real run ID, selected source URLs and draft version. Verify actual qualified passages and role/offer relevance, save an edit, approve the exact version and confirm no mail is sent. Test rejection and regeneration on appropriate versions.
9. Reload/reopen history with the same authenticated session and verify PostgreSQL persistence across API/worker restart. Run the failure, insufficient evidence, conflict/outdated and low-relevance cases without substituting mock research.
10. Run Playwright against the deployed URL, including live successful review interactions. Inspect screenshots/trace/network/console. Record service IDs, deployment revisions, runtime versions, database migration revision and the public URL in ENGINEERING_REPORT.md only after independent verification.

If a stage fails, retain the failure evidence, fix it and repeat the affected gate. Do not promote the operating recipe into a claim of deployment or readiness.

# SIGNALFLOW

Latest local setup: [LOCAL_SETUP_REPORT.md](LOCAL_SETUP_REPORT.md) — credentials are configured privately; 39 backend and 12 frontend tests pass. Neon/OpenAI verification and server startup remain blocked by environment DNS, driver installation and port permissions. Follow that report without overwriting backend/.env.

An evidence-first GTM workspace: public prospect research → qualified signals → personalised email draft → human review. No email is sent automatically.

## Quick start (from GitHub)

Secrets are **not** committed — after cloning you create your own env files from the
committed `*.example` templates. You need Python 3.11+, [uv](https://docs.astral.sh/uv/),
Node.js 20+, a PostgreSQL database, and an OpenAI API key with Responses/web-search access.

```sh
git clone https://github.com/ricky2027/signal-flow-.git
cd signal-flow-
```

**1. Backend** (fill in your real `OPENAI_API_KEY`, `DATABASE_URL`, a 32+ char `SESSION_SECRET`,
and a `DEMO_ACCESS_CODE` in `backend/.env`):

```sh
cd backend
uv sync --extra test
cp .env.example .env        # then edit .env with your real values
uv run alembic upgrade head
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

**2. Worker** (second terminal, from `backend/` — required for runs to execute):

```sh
uv run python -m app.worker
```

**3. Frontend** (third terminal, from the repo root):

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open **http://localhost:3000**, sign in with your `DEMO_ACCESS_CODE`, and start a run at
`/research/new`. Tip: `RUN_TIMEOUT_SECONDS=540` in `backend/.env` gives multi-pass research
room to finish. See **[Run locally](#run-locally)** below for Docker Postgres and full detail,
and **[DEPLOYMENT.md](DEPLOYMENT.md)** for hosting. Licensed under [MIT](LICENSE).

The Next.js frontend and FastAPI backend are integrated through a same-origin streaming proxy. Production application data belongs in PostgreSQL. Test-only SQLite databases are isolated and never seeded as live research output.

Current status: [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md). The current installed/locked versions are Next.js 16.4.6, React/React DOM 19.3.1, PostCSS 8.5.33 and jsdom 29.1.1. Clean frontend reinstall, a production Webpack build, TypeScript, 12 executable frontend cases and 34 backend cases pass. A fresh npm audit, PostgreSQL, successful OpenAI research, native browser acceptance and public deployment remain blocked. **Not deployment-ready; no public URL verified.**

The [deployment recipe](DEPLOYMENT.md) identifies the proposed four services and required account access. The [five-minute demo script](DEMO_SCRIPT.md) is conditional on real deployment/research verification. Earlier backend/frontend/security reports are historical snapshots; they do not describe the current installed versions.

## Run locally

Requirements: Python 3.11+, uv, Node.js 20+, npm, PostgreSQL (or Docker), and an OpenAI project key with Responses/web-search access.

### 1. Configure and start the backend

```sh
cd backend
uv sync --extra test
cp .env.example .env
```

Edit `backend/.env`: configure `DATABASE_URL`, `OPENAI_API_KEY`, model names, `SESSION_SECRET` (at least 32 random characters), `DEMO_ACCESS_CODE`, `APP_ORIGIN=http://localhost:3000`, and `COOKIE_SECURE=false` for local HTTP. The frontend login uses your configured demo access code. Never put the OpenAI key in frontend environment variables.

With Docker, a local PostgreSQL instance can be started with:

```sh
docker run --name signalflow-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=signalflow -v signalflow-data:/var/lib/postgresql/data -p 5432:5432 -d postgres:17
```

Then, from `backend/`:

```sh
uv run alembic upgrade head
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

In a second terminal, from `backend/`:

```sh
uv run python -m app.worker
```

### 2. Configure and start the frontend

In a third terminal, from the repository root:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

`BACKEND_URL=http://127.0.0.1:8000` is server-only. Frontend `APP_ORIGIN` and backend `APP_ORIGIN` must both equal the URL you open: **http://localhost:3000**. Using `127.0.0.1:3000` instead requires updating both origins to match. Cookie authentication and SSE work through `/api/*` on the frontend; no browser CORS configuration or exposed provider keys are needed.

**Build and audit status:** `npm run build` uses the supported Webpack builder. The default Turbopack builder failed under the current environment's internal-port restriction; both logs are preserved. The installed Next.js/React targets now match, but a successful full npm audit and real integration/browser acceptance are still required before deployment.

### 3. Use the workspace

Sign in with `DEMO_ACCESS_CODE`, submit a real prospect and your offer, and open the resulting run. The worker must be running for queued jobs to execute. Watch actual stages, inspect sources and scores, then edit/review a draft if one was generated. Errors and abstentions do not fabricate a fallback email.

- `/`: aggregate metrics, outcomes, recent runs and activity.
- `/research/new`: prospect and offer form.
- `/runs`: paginated, searchable run history.
- `/reviews`: persisted runs awaiting review.
- `/runs/{id}`: live workflow, research, evidence, draft versions and execution log.

Metrics are computed by the backend for the authenticated session. “Prospects researched” deduplicates submitted name/company pairs with completed research, including honest abstentions; failed or still-active runs do not count. “Drafts generated” counts generated versions, excluding manual edits. “Incomplete runs” includes active, failed and inconclusive outcomes. No synthetic trends or estimated results appear.

## Tests

From `backend/`:

```sh
uv run pytest -q
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/signalflow uv run pytest tests/test_postgres.py -q
```

From `frontend/`:

```sh
npm run typecheck
npm run test:security
npm test
npm run test:integration
npm run test:dom
npm run build
```

The integration and DOM tests require the backend virtualenv at `backend/.venv`, or set `BACKEND_PYTHON` to another installed backend interpreter. They run actual FastAPI requests and SQLAlchemy operations through an in-process ASGI bridge when sockets are unavailable. Their temporary SQLite databases are removed afterward. This is not a substitute for PostgreSQL or real-browser testing. Integration tests default to the real missing-credentials failure path; `SIGNALFLOW_TEST_LIVE=1 npm run test:integration` attempts actual OpenAI calls and expects provider failure in the restricted audit environment. Do not enable this mode in a working provider environment unless intentionally testing a real failure; it may incur usage.

### Playwright browser acceptance

Start the actual frontend/backend first, using a disposable local database. Install the separate browser-test dependency set:

```sh
cd frontend/browser-tests
npm install
npx playwright install chromium
```

Then from `frontend/`:

```sh
SIGNALFLOW_TEST_ACCESS_CODE=YOUR_LOCAL_CODE npm run test:e2e
```

This covers empty-state navigation, a mobile viewport, and API disconnection against the running app. Two scenarios require explicit setup:

```sh
# Worker running; backend/provider deliberately unavailable, not a fabricated result.
SIGNALFLOW_TEST_ACCESS_CODE=YOUR_LOCAL_CODE SIGNALFLOW_TEST_EXPECT_FAILURE=1 npm run test:e2e -- --grep "real failed"
# Worker intentionally stopped so the real run stays queued while SSE is interrupted.
SIGNALFLOW_TEST_ACCESS_CODE=YOUR_LOCAL_CODE SIGNALFLOW_TEST_WORKER_PAUSED=1 npm run test:e2e -- --grep "SSE interruption"
```

Screenshots/traces are produced only by real browser execution, never synthesized. These browser tests were authored but could not execute in the managed environment. A successful draft-review UI must be validated using actual successful live research after connectivity is restored; no mock success record is shipped.

## Contracts and implementation

The frontend types in `frontend/src/lib/contracts.ts` are generated from actual `backend/openapi.json` using `npm run types:generate` in `frontend/`. Refresh the OpenAPI snapshot from FastAPI after schema changes. The only backend product addition for this milestone is the authenticated, session-scoped `GET /api/v1/dashboard` aggregate endpoint; the research/review workflow remains in Python.

Planning baseline: [brief](PROJECT_BRIEF.md), [requirements](REQUIREMENTS.md), [workflow](WORKFLOW.md), [architecture](ARCHITECTURE.md), [implementation plan](IMPLEMENTATION_PLAN.md).

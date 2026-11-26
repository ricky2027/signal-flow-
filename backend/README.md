# SIGNALFLOW backend

Latest Neon/local setup and exact verification commands: [LOCAL_SETUP_REPORT.md](../LOCAL_SETUP_REPORT.md). Standard Neon PostgreSQL URLs select psycopg automatically; TLS parameters are preserved. Settings find backend/.env independently of the current directory.

FastAPI HTTP API plus a separate LangGraph worker. PostgreSQL is the supported runtime database. Nothing sends email. Swagger UI: `/docs`; machine contract: `/openapi.json`.

## Setup
From the project directory, with Python 3.11+ and uv installed:

```sh
cd backend
uv sync --extra test
cp .env.example .env
```

Edit `.env`: set `DATABASE_URL`, a funded `OPENAI_API_KEY`, research/reasoning model names with Responses/web-search and structured-output access, `SESSION_SECRET` (at least 32 random characters), and `DEMO_ACCESS_CODE`. Set `APP_ORIGIN` to the browser origin. `COOKIE_SECURE=false` is for local HTTP only; use true with public HTTPS.

For a local database, if Docker is available:

```sh
docker run --name signalflow-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=signalflow -p 5432:5432 -d postgres:17
uv run alembic upgrade head
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

In a second terminal, from `backend/`:

```sh
uv run python -m app.worker
```

The worker handles one job at a time. For two concurrent jobs run two worker processes against the same PostgreSQL database; transactional claims prevent double claiming. Run migrations once before starting either process. Use a same-origin reverse proxy for a deployed frontend; pass through SSE without buffering. Hosting must support persistent worker processes.

## API usage
Login creates a seven-day HttpOnly session. All mutations require the configured Origin and `X-Signalflow-Client: web`. Run creation, retry and regeneration require an `Idempotency-Key` unique per operation; reuse it for network retries of the same request. All run IDs are session-scoped.

```sh
curl -c /tmp/signalflow-cookies -H 'Origin: http://localhost:3000' -H 'X-Signalflow-Client: web' -H 'Content-Type: application/json' -d '{"access_code":"YOUR_CONFIGURED_CODE"}' http://localhost:8000/api/v1/session
curl -b /tmp/signalflow-cookies -H 'Origin: http://localhost:3000' -H 'X-Signalflow-Client: web' -H 'Idempotency-Key: my-first-run' -H 'Content-Type: application/json' -d '{"prospect_name":"ENTER_REAL_NAME","company_name":"ENTER_REAL_COMPANY","designation":"ENTER_CURRENT_ROLE","product_service":"YOUR_PRODUCT","value_proposition":"YOUR_VALUE_PROPOSITION"}' http://localhost:8000/api/v1/runs
curl -b /tmp/signalflow-cookies http://localhost:8000/api/v1/runs
curl -N -b /tmp/signalflow-cookies http://localhost:8000/api/v1/runs/RUN_ID/events
curl -b /tmp/signalflow-cookies http://localhost:8000/api/v1/runs/RUN_ID
```

Inputs are placeholders, not purported real prospects. Replace them before a live run. `POST /runs` atomically submits a prospect snapshot and queues research, returning a prospect ID in run detail. Edit uses `PATCH /runs/{id}/draft` with `expected_version`, `subject`, `body`. Approve/reject use POST and `draft_version`; approve rechecks evidence against the edited text with a live provider call. An edited version stays pending until that check. Rejection optionally accepts `reason`. Regeneration accepts `draft_version` and optional `instructions`, rechecks signal freshness and queues new drafting from existing evidence. Retry is only for failed runs and creates a new linked run.

Execution results include facts, sources with retrieval dates, selected/excluded signals and gate reasons, labelled implications, versioned drafts, decisions and provider call metadata. Error bodies contain a stable code and request ID, never raw provider exception text. There is no sending endpoint.

## Verification

```sh
uv run pytest -q
uv run python -m app.smoke
```

The smoke command incurs real search usage and prints actual provider ID/source URLs. It has no mock fallback. Automated fixtures live exclusively in `tests/` and are explicitly synthetic. By default tests use isolated SQLite databases for portability; this does not validate PostgreSQL locking. Enable the real PostgreSQL test against a disposable/test database account with permission to create schemas:

```sh
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/signalflow uv run pytest tests/test_postgres.py -q
```

It creates and removes a uniquely named schema. Never point test administration at a database for which schema creation/deletion is inappropriate.

## Runtime limitations
Research is not independently guaranteed truth. Attribution, exact retrieved passages, conservative policy and semantic checks reduce errors, while human review remains essential. Public pages may block access; blocked, oversized, non-HTML or PDF pages are excluded. Unknown event dates cannot qualify. Only public, provider-discovered HTTP(S) source pages are retrieved, with bounded redirects, public-IP checks and pinned connections. No authenticated scraping or sensitive enrichment occurs.

The 180-second run deadline covers provider operations and retrieval. Provider retries are bounded; search attempts cap at four and generation at two. Provider callbacks persist model IDs, usage, requests/tool activity and failures; exact cost depends on current provider pricing and is not fabricated. Set account-level budget alerts as well as application quotas. Approval calls have separate daily quotas. Quotas are daily counts, not a currency spending guarantee.

An expired worker lease marks a run failed; explicit retry creates a linked run. API requests do not own job lifetime. SSE events replay by sequence; heartbeat comments have no synthetic progress. This is demo access control, not a production organization/SSO system. No public data deletion/admin or full deployment is included in this backend milestone.

## Frontend integration

A Next.js frontend is now available in `../frontend`; see the [root README](../README.md) for full local setup. It proxies cookies, CSRF headers, idempotency keys and streamed SSE without buffering. The backend APP_ORIGIN must match the browser origin (localhost:3000 by default).

`GET /api/v1/dashboard` is the only added product endpoint for the frontend milestone. It returns session-owned prospects_researched, drafts_generated, pending_reviews, incomplete_runs, total_runs and all nine status_counts. No approximate metrics are synthesized in the browser. The original backend report is a historical milestone; current integration audit results are in `../frontend/ENGINEERING_REPORT.md`.

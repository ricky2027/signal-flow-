# Local setup verification — 2026-11-26

This report supersedes earlier **local configuration** status. The application is not running in this tool environment. Neon persistence and OpenAI access have not succeeded; no deployment is claimed.

## Configuration changes

- Confirmed DATABASE_URL and OPENAI_API_KEY are present in backend/.env, without displaying values. The effective OpenAI key matches the file. Process environment variables retain normal precedence over .env.
- Settings resolve backend/.env by absolute project path, so API, worker and migrations also find it when invoked from the repository root.
- Standard Neon `postgresql://` and `postgres://` URLs now select `postgresql+psycopg://` internally. Credentials, escaped passwords, `sslmode=require` and channel-binding parameters are preserved. The private file was not rewritten to change its URL.
- Generated missing SESSION_SECRET and DEMO_ACCESS_CODE privately in backend/.env; set APP_ORIGIN=http://localhost:3000 and COOKIE_SECURE=false for local HTTP. Existing credential values were preserved. Read your generated demo access code in your local editor; it is intentionally absent from logs and this report.
- Restricted backend/.env to mode 0600. `.gitignore` ignores .env and .env.* while permitting .env.example. No Git repository exists here, so Git tracking/history cannot be audited yet.
- Created frontend/.env.local from its non-secret template. It contains the server-only backend origin and browser origin, no OpenAI/database credentials.
- Added `python -m app.check_setup --migrate --check-persistence`: real database connection, Alembic upgrade, committed session-row write, reconnect/read, cleanup, and minimal OpenAI Responses call. No mock fallback. The persistence probe does not create research records or dashboard activity. OpenAI verification incurs a small actual API request. Errors print exception class/status only.

## Executed checks

| Check | Result |
| --- | --- |
| Credential loading, URL driver selection, TLS configuration | PASS; values withheld |
| Backend tests, including five new configuration cases | **39 passed, 1 skipped** (PostgreSQL), one existing Starlette deprecation warning |
| Frontend unit/security/API integration/DOM tests | **12 passed** (5 + 3 + 3 + 1) |
| Production build and TypeScript | PASS |
| Exact configured-secret scan | PASS: no matches in 367 source/build/audit files, including Next.js build output; private .env files/dependency directories excluded |
| psycopg install | FAIL: pypi.org DNS resolution unavailable |
| Direct Neon libpq/psql SELECT 1 | FAIL: database hostname DNS resolution unavailable |
| SQLAlchemy setup and Alembic upgrade head | FAIL: missing psycopg; no migration completion claimed |
| Committed Neon read/write/reconnect | BLOCKED before write by missing driver; no persistence claim |
| Minimal real OpenAI Responses request | FAIL: ConnectError; api.openai.com DNS also fails; key validity/model access/quota unverified |
| FastAPI and independent worker startup | FAIL: missing psycopg |
| Next.js development server | FAIL: EPERM binding 127.0.0.1:3000 |
| Playwright suite | BLOCKED: runner missing; install fails registry DNS |

Logs: `audit/local-setup/`. API integration/DOM tests use actual application handlers with isolated SQLite and a controlled transport. Backend workflow fixtures test reasoning gates and review behavior without proving a successful live OpenAI/Neon chain. No sources/drafts were manufactured to present success. The optional PostgreSQL test remains skipped unless TEST_DATABASE_URL is explicitly set for a disposable test database.

## Required manual action

Use a terminal/execution environment permitted to resolve Neon, api.openai.com, pypi.org and registry.npmjs.org and to bind localhost ports. Adding credentials did not remove these execution restrictions. Do not rotate or paste keys merely because DNS fails; authentication has not been reached. If the commands below fail in your ordinary terminal too, resolve local DNS/proxy/firewall access first. Do not disable Neon TLS.

## Exact local commands

Run from the repository root unless otherwise indicated. **Do not overwrite your existing backend/.env.**

Terminal 1:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv sync --extra test
uv run alembic upgrade head
uv run python -m app.check_setup --check-persistence
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

The setup check independently verifies a real committed write/read and a minimal OpenAI response. Inspect its JSON; both checks must pass. `--migrate` can be added to run migrations as part of that check. It deliberately removes only its own probe session after verifying persistence.

Terminal 2:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.worker
```

Terminal 3:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/frontend
npm ci
npm run dev
```

URLs after successful startup:

- App: http://localhost:3000 — sign in with DEMO_ACCESS_CODE from backend/.env.
- API documentation: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/health/live
- Database/config readiness: http://127.0.0.1:8000/health/ready — this does not test OpenAI access.

Open the frontend with **localhost**, matching both APP_ORIGIN settings. Submit a real prospect, keep the worker running, inspect real execution/evidence, and review any generated draft. No email is sent automatically. The minimal OpenAI check does not prove web-search permissions or end-to-end research; a real run is still required.

Repeat tests:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run pytest -q
cd ../frontend
npm test
npm run test:security
npm run test:integration
npm run test:dom
npm run typecheck
npm run build
cd browser-tests
npm install
npx playwright install chromium
cd ..
# Set SIGNALFLOW_TEST_ACCESS_CODE privately to the configured local demo code.
npm run test:e2e
```

For the optional PostgreSQL integration case, set TEST_DATABASE_URL privately to a disposable PostgreSQL database with schema creation permission, then run `uv run pytest tests/test_postgres.py -q` from backend/. The test creates/removes its own schema. Never substitute destructive testing against an unrelated production database.

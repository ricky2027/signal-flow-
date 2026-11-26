# SIGNALFLOW backend engineering report

Historical backend milestone. The subsequent frontend integration and current verification limits are documented in [frontend/ENGINEERING_REPORT.md](../frontend/ENGINEERING_REPORT.md).

## Delivery status
Backend implemented; automated local audit passes. Successful live research and execution against PostgreSQL are **not verified** in this restricted environment. This is not a claim of a production-ready or publicly deployed application. Frontend development and deployment were outside this backend-only milestone.

The five approved planning documents were read completely before implementation. One architecture amendment is recorded in ARCHITECTURE.md: bounded retrieval of provider-discovered public pages verifies exact passages rather than trusting search narration.

## Implemented modules

| Module | Responsibility |
|---|---|
| app/api.py | FastAPI submission/history/detail, session, review/edit/regenerate/retry, health and replayable SSE endpoints |
| app/services.py; app/errors.py | Transactional admission, quotas, idempotency, version/state checks and error contracts |
| app/models.py; app/db.py | SQLAlchemy prospect/session/run/source/claim/link/signal/draft/review/job/event/provider-call/artifact persistence |
| alembic/versions/0001_initial.py | Explicit initial migration, indexes, uniqueness and foreign keys; upgrade/downgrade |
| app/schemas.py; openapi.json | Pydantic input, research, agent, draft, quality and API response contracts; generated OpenAPI snapshot |
| app/provider.py | Actual OpenAI Responses REST integration with required live web search, structured JSON output, real citations/tool metadata, bounded retry and usage audit |
| app/retrieval.py | Limited provider-discovered page retrieval; public DNS/IP validation, pinned IP connection, redirect/size/content limits, HTML normalization |
| app/agents/research.py | Research and separate extraction/qualification nodes, exact passage checks, one follow-up for identity/evidence conflicts |
| app/agents/signals.py; app/policy.py | Relevance reasoning and deterministic evidence gates, recency, quality, scoring, selection and abstention |
| app/agents/writing.py | Evidence-constrained writing, semantic grounding validation and corrected claim references; at most one repair |
| app/graph.py | LangGraph conditional routes for evidence, relevance and quality outcomes |
| app/worker.py | Durable queue claiming, lease renewal/reaping, run deadline, provider/stage persistence and late-write lease checks |
| app/smoke.py | Explicit paid live search capability check; no fixture fallback |

A prospect snapshot and research job are created atomically by POST /api/v1/runs. Source/claim/signal records use validated JSONB payloads within relational rows; stage artifacts preserve attempts and rationale. Approval decisions are append-only and draft versions immutable. Saving edits clears approval, and approval revalidates support before a version/state recheck. No sending integration or endpoint exists.

## Executed audit and results

| Check actually executed | Result | Scope/limitation |
|---|---|---|
| Automated suite | **33 passed, 1 skipped, 0 failed** | TestClient API calls, real LangGraph execution and SQLAlchemy operations; synthetic providers only in tests |
| Happy path | PASS | Evidence, scored selection, generated draft, persisted events and review-ready state |
| Insufficient public information | PASS | Missing identity/usable evidence results in no draft after bounded follow-up |
| Conflicting sources | PASS | Identity conflict and disputed relevant event cases abstain |
| Outdated sources | PASS | Stale/unknown dates cannot qualify as fresh event signals |
| Evidence but insufficient relevance | PASS | Weak role/offer fit results in no_relevant_signal |
| Unverifiable quoted passage | PASS | A quote absent from fetched test content cannot qualify |
| Failed quality validation | PASS | One repair then failed/draft_grounding_failed; no review-ready draft |
| Human review | PASS | Edit invalidates approval, stale versions rejected, reject/regenerate preserve history, unsupported edit cannot be approved |
| Persistence and execution | PASS | Relational source/claim links, replayed ordered SSE, idempotency, quota, pagination, ownership, crash reaping, run timeout and expired-lease write rejection |
| Provider adapter tests | PASS | Search result parsing, no retry on 401, three-attempt bound for network failure using explicit test transports |
| SQLite migration upgrade/downgrade | PASS | Real DDL and foreign keys; isolated temporary database |
| PostgreSQL migration SQL compilation | PASS | Driver-independent Alembic offline output retained; not equivalent to execution |
| Real PostgreSQL integration | SKIPPED/BLOCKED | No configured database; local initdb fails with OS shared-memory permission denial; psycopg cannot be installed without network |
| Actual OpenAI smoke | BLOCKED | Credential exists, actual outbound calls attempted; DNS resolution fails before contacting OpenAI |
| Actual API → worker → provider-failure → SSE run | PASS for failure handling | HTTP 200 login, 202 submission, 200 detail; three persisted real network failures; failed run, **zero sources and zero drafts** |
| Ruff check and Python compilation | PASS | No remaining lint errors; application/tests/migration compile |

The first suite pass had 22 passes and two failures caused by a test-provider fixture lacking close(); this fixture was corrected. Later audits exercised the complete suite above. No failures remain in executed automated tests. One Starlette deprecation warning remains about its HTTPX TestClient adapter; it did not fail tests.

Audit artifacts: [pytest output](audit/pytest.txt), [actual network-failed run and SSE frames](audit/live_attempt.json), [compiled PostgreSQL DDL](audit/postgres-schema.sql), [runtime package versions](audit/environment.json). Mock data is confined to tests and never used as application fallback. There are no seed research runs shipped as genuine output.

## Environment and reproducibility
A clean `uv` dependency installation was attempted and blocked by DNS access to PyPI. Tests ran using the existing Python 3.14.3 installation plus available cached dependencies. They did not run in a freshly resolved installation. psycopg is absent. The declared production dependency set therefore still needs a clean install and a resolved lockfile in a network-enabled environment.

The exact local audit test invocation from repository root was:

```sh
PYTHONPATH="$(paste -sd: backend/.venv/lib/python3.14/site-packages/local-audit.pth):$PWD/backend" backend/.venv/bin/python -m pytest backend/tests -q
python3 -m ruff check backend --exclude .venv --output-format concise
python3 -m compileall -q backend/app backend/tests backend/alembic
```

`local-audit.pth` is an ignored, machine-local list of installed/cached package locations. It is not part of the application or production setup. Use the clean installation commands below elsewhere.

The separate live smoke command actually executed from repository root was:

```sh
DATABASE_URL=sqlite:// PYTHONPATH="$(paste -sd: backend/.venv/lib/python3.14/site-packages/local-audit.pth):$PWD/backend" backend/.venv/bin/python -m app.smoke
```

It ended with `httpx.ConnectError: [Errno 8] nodename nor servname provided, or not known`. No OpenAI response ID was received. The full API/worker failure audit was separately executed against an ephemeral SQLite audit database through TestClient without a mock provider. The actual source/semantic quality of successful OpenAI responses remains untested.

## Exact normal setup and run commands
From the repository root:

```sh
cd backend
uv sync --extra test
cp .env.example .env
```

Manually configure `.env`: funded OpenAI key, supported research/reasoning models, PostgreSQL URL, a ≥32-character session secret, demo access code and browser origin. Use HTTPS/secure cookies for deployment. Credentials remain in environment variables or ignored `.env`; nothing is hardcoded.

With Docker available, create a local database and migrate:

```sh
docker run --name signalflow-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=signalflow -p 5432:5432 -d postgres:17
uv run alembic upgrade head
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

In another terminal from `backend/`:

```sh
uv run python -m app.worker
```

Then verify:

```sh
uv run pytest -q
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/signalflow uv run pytest tests/test_postgres.py -q
uv run python -m app.smoke
```

See README.md for exact authenticated API calls and SSE usage. The API is at http://localhost:8000/docs. No API key is required in the browser.

## Unresolved issues and next verification
1. Run clean dependency resolution and lock versions when PyPI is reachable; current bounded dependency declarations are not a lockfile.
2. Execute migrations and integration tests against real PostgreSQL, including contention/worker-process restart tests. SQLite cannot validate advisory locks or SKIP LOCKED semantics; the included PostgreSQL test is a starting point, not a concurrency stress test.
3. Confirm the configured OpenAI model supports required web-search options and strict schemas. Execute a successful research/extraction/writing/validation run with live sources. Actual research accuracy, source availability, latency and cost remain unmeasured.
4. Test deployed SSE through the eventual reverse proxy; current replay tests are in process. Verify provider account budgets and hosting limits before public access.
5. Evidence judgments and semantic entailment checks are model judgments, not guarantees. Research from blocked/PDF/non-text pages is excluded. Human review remains mandatory. Administrative deletion, organization authentication and operational monitoring beyond persisted events/calls are deferred enhancements.

Backend work stops here. Frontend, public deployment and demo recording have not been started.

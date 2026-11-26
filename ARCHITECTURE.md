# Architecture and contracts

## Deployment and technology choices
Browser → Next.js UI → same-origin reverse proxy `/api/v1/*` → FastAPI → PostgreSQL. A separate Python worker polls PostgreSQL jobs and invokes LangGraph → OpenAI Responses API with genuine web search, followed by structured extraction/reasoning/generation calls. The worker writes domain results and events; FastAPI streams committed events through SSE. No long AI task runs inside a serverless frontend request.

Next.js and TypeScript support typed routing and an interactive editor; Tailwind and shadcn/ui provide a consistent, accessible component foundation with custom enterprise styling. FastAPI and Pydantic provide explicit validation and OpenAPI contracts. Python handles deterministic policy. LangGraph expresses bounded stages and conditional abstention routes. OpenAI provides language reasoning and a supported public search tool. PostgreSQL provides transactions, persistent history and a small durable queue; SQLAlchemy and Alembic provide explicit models/migrations. SSE fits one-way stage updates without a WebSocket service.

Proposed hosting: Next.js on a Node web service, FastAPI on a persistent web service, a separate worker and managed PostgreSQL on Render or equivalent. Use a reverse proxy with streaming enabled, buffering disabled and idle timeout above heartbeat interval. Hosting choice is provisional until account access and stream smoke test. One platform reduces cross-origin/session complexity. Require HTTPS, database backups and migrations before worker start. Never use ephemeral local storage for history. No Redis, vector database or separate search vendor is needed for MVP.

## Research dependency and evidence boundary
Use Responses API `web_search` with live access, citation annotations and source list where supported. Select and pin a compatible model after a day-one capability test; use separate structured-output calls if search and strict schema cannot be combined. Store provider IDs and source attribution, not private chain-of-thought. A citation URL alone is insufficient: only attributable supporting passages qualify. Do not add arbitrary URL fetching in MVP. If provider output lacks enough source text, use a bounded follow-up or abstain; do not present model prose as a quotation.

Primary references checked during planning:
- [OpenAI web search](https://developers.openai.com/api/docs/guides/tools-web-search): supported public research and attribution; validate chosen model/tool combination during spike.
- [LangGraph reference](https://reference.langchain.com/python/langgraph/overview): stateful graph abstraction. Domain persistence and jobs below are explicit application responsibilities; no dependency on checkpoint recovery in MVP.
- [FastAPI SSE](https://fastapi.tiangolo.com/reference/sse/): streaming event support. Pin a tested release, or use StreamingResponse with standards-compliant SSE framing if deployment version requires it.

## Database entities
All IDs UUID except monotonic event sequence; timestamps UTC. JSONB contains validated snapshots, not unbounded arbitrary data. Foreign keys, delete restrictions and indexes enforce relationships.

| Entity | Key fields and relations |
|---|---|
| demo_sessions | id, hashed token, created_at, expires_at; owns runs |
| runs | id, session_id, parent_run_id nullable, immutable input JSON, status, stage, outcome_reason, warnings, policy/prompt/model versions, current_draft_id nullable, error JSON, started_at, finished_at, created_at |
| jobs | id, run_id, kind research/regenerate, status queued/leased/done/failed, lease_owner, lease_expires_at, heartbeat_at, attempts, available_at, idempotency_key; one active job per run |
| sources | id, run_id, URL, canonical URL, title, publisher, origin_group, source_type, published_at nullable, event_at nullable, retrieved_at, date_basis, passage, provider_call_id; unique canonical URL per run |
| claims | id, run_id, text, entity_match, verification supported/disputed/unsupported, conflict_group nullable; facts only |
| claim_sources | claim_id, source_id, supporting_passage; composite key; same-run constraint in service validation |
| signals | id, run_id, claim_ids JSON, fact_summary, implication, role_reason, offer_reason, relevance/fit integers, quality, age_days nullable, score, eligible, rejection_reasons, selected; at most one selected per run |
| drafts | id, run_id, version, subject, body, claim_refs JSON, validation_status pending/valid/invalid, validation_findings, origin generated/edited, created_at; unique run/version |
| reviews | id, run_id, draft_id, action approved/rejected, reason nullable, session_id, created_at; append-only |
| run_events | run_id, sequence, type, stage, payload JSON, created_at; unique run/sequence |
| provider_calls | id, run_id, stage, provider_request_id, model, query metadata, status, latency_ms, token/tool usage, estimated_cost nullable, error_code; never secrets |

Jobs claimed with transactional `FOR UPDATE SKIP LOCKED`; bounded worker concurrency. Stage output, next run state and event commit in one transaction, without holding DB transactions open during provider requests. Allocate event sequences by locking run row. Worker crash leaves a lease; reaper atomically fails expired jobs and runs. Startup runs reaper as well. Provider calls can finish after lease expiry; worker must recheck lease before commits. Retrying a failed run creates a linked run, preserving audit history. External calls are not claimed to be exactly-once.

## Shared wire models
Pydantic models are authoritative; generate TypeScript types from `/openapi.json` during development and check drift in CI. JSON uses snake_case; ISO-8601 UTC timestamps, UUID strings, explicit nulls, numeric scores. All response evidence IDs must belong to the run. Internal prompts and credentials never appear in public models.

```typescript
type RunStatus = 'queued' | 'running' | 'awaiting_review' | 'approved' |
  'rejected' | 'insufficient_information' | 'conflicting_evidence' |
  'no_relevant_signal' | 'failed';
type Stage = 'validate' | 'research' | 'qualify_evidence' |
  'evaluate_signals' | 'draft' | 'validate_draft';
type RunInput = { prospect_name: string; company_name: string;
  designation: string; company_website?: string | null;
  product_service: string; value_proposition: string };
type ClaimRef = { field: 'subject' | 'body'; start: number; end: number;
  claim_ids: string[] }; // Unicode code-point offsets, [start,end); convert for JS editor
// Recalculate references after edits; stale offsets never count as evidence.
type Draft = { id: string; version: number; subject: string; body: string;
  claim_refs: ClaimRef[]; validation_status: 'pending' | 'valid' | 'invalid';
  validation_findings: string[] };
type RunEvent = { run_id: string; sequence: number; type: string;
  stage: Stage | null; occurred_at: string; payload: Record<string, unknown> };
type ApiError = { error: { code: string; message: string;
  retryable: boolean; field_errors?: Record<string,string[]>; request_id: string } };
```

RunSummary: id, prospect_name, company_name, status, stage, created_at, finished_at, outcome_reason. RunDetail extends summary with input, warnings, sources, claims, signals, drafts, reviews, error and parent_run_id. Source includes all attribution/date fields above. Signal includes scores, gate reasons and separate implication. Return paginated arrays where history grows; run evidence is capped by workflow budgets. Never expose session token hashes.

## API v1
Session-scoped authorization applies to every run endpoint. Public access does not mean public prospect history. Standard errors: 401 session missing, 404 missing/unowned run, 409 state/version/idempotency conflict, 422 invalid input, 429 quota, 503 dependency unavailable. All mutations use CSRF protection with same-origin secure HttpOnly session cookies.

| Method/path | Request | Response |
|---|---|---|
| POST /session | `{access_code}` | 200 session cookie; no secret in URL |
| POST /runs | RunInput; Idempotency-Key header | 202 `{run_id,status:'queued',events_url}`; same key/body returns same run |
| GET /runs?cursor=&limit=&status= | limit default 20, max 100 | 200 `{items:RunSummary[],next_cursor:string|null}` |
| GET /runs/{id} | — | 200 RunDetail |
| GET /runs/{id}/events | Last-Event-ID header or after sequence query | SSE stream |
| PATCH /runs/{id}/draft | `{expected_version,subject,body}` | 200 Draft; new immutable version, awaiting_review; recompute support validation |
| POST /runs/{id}/approve | `{draft_version}` | 200 RunDetail; validates support, 422 for unsupported content |
| POST /runs/{id}/reject | `{draft_version,reason?}` | 200 RunDetail |
| POST /runs/{id}/regenerate | `{draft_version,instructions?}`; Idempotency-Key | 202 queued; stale evidence returns 409 evidence_expired |
| POST /runs/{id}/retry | Idempotency-Key; failed only | 202 new linked run |
| GET /health/live; GET /health/ready | — | 200 live; ready checks DB and configuration, 503 otherwise; no paid search |

Draft mutation transactions lock run and compare expected version; concurrent actions return 409. Regeneration instructions capped at 1,000 characters and cannot override evidence rules. Approve may take a bounded validation call for edited drafts; failure leaves awaiting_review, never partially approved. Persist the validation result only if the version still matches.

SSE frames use `id: <sequence>`, `event: <type>`, `data: <RunEvent JSON>` followed by a blank line. Types: run.queued, stage.started, research.updated, stage.completed, draft.created, run.status_changed, run.failed. Payloads contain concise safe summaries, not reasoning traces. Replay committed rows after cursor then tail database; deduplicate by sequence on client. Heartbeat comments every 15 seconds. On reconnect reconcile GET detail; stop automatic reconnect after terminal status and drained events. Disconnection never cancels work. Ordering is per run, delivery at least once. Retain events for run lifetime in MVP.

## Configuration and manual setup
Obtain funded OpenAI project credentials with model and web-search access; run real search/structured-output capability tests. Provision managed PostgreSQL plus web/worker services, configure DNS/platform URL and HTTPS, run Alembic migrations, supply build/start commands and streaming proxy rules. Confirm hosting supports persistent workers and SSE before selecting a plan. Costs and limits depend on provider account and must be checked during setup.

Backend/worker secrets: OPENAI_API_KEY, DATABASE_URL, SESSION_SECRET, DEMO_ACCESS_CODE. Nonsecret settings: OPENAI_RESEARCH_MODEL, OPENAI_REASONING_MODEL, APP_ORIGIN, RUN_TIMEOUT_SECONDS=180, MAX_SEARCH_REQUESTS=4, MAX_SOURCES=12, MAX_RUNS_PER_SESSION_PER_DAY=10, GLOBAL_DAILY_RUN_LIMIT, WORKER_CONCURRENCY=2, lease/heartbeat settings and log level. Model names and global spending cap must be explicitly set on day one; enforce quota reservation transactionally before queueing. Configure provider-level spending alerts as a second control. Frontend uses same-origin API, no API key in NEXT_PUBLIC variables. Commit only `.env.example` placeholders during development.

Demo session code is proposed access control, not full enterprise authentication. Apply rate limits to login and mutations, session ownership, expiry, and redacted structured logs. Treat public web text as untrusted data; never execute embedded instructions, expose secrets or let it invoke arbitrary tools. Escape all evidence/editor content, validate source URL schemes, and open links safely. Minimize retained personal data; no sensitive inference. Operator can remove demo data through an administration procedure, outside public routes.

## Backend implementation amendment
During implementation, the source-passage boundary required one change: bounded retrieval of URLs actually discovered by the research provider. Search narration and citation URLs alone cannot establish that a quotation occurs in source text. `backend/app/retrieval.py` therefore validates public DNS addresses, pins the connection to a validated IP, rechecks redirects, restricts ports/content types/size and permits no user-directed arbitrary fetch API. Extraction must quote an exact normalized substring of retrieved content. Unavailable pages are excluded. This replaces the earlier no-fetch MVP assumption without weakening the evidence gate.

The implemented schema uses normalized prospect, source, claim, claim-source, signal, draft, review, job, event and provider-call rows; evolving evidence/scoring payloads are validated JSONB. Append-only artifacts additionally retain stage results and generation/quality attempts. Runtime worker concurrency is one per process (scale with separate worker processes). Worker heartbeat is represented by lease renewal rather than a separate heartbeat column. Events include `stage.result` for committed artifacts. The initial migration freezes explicit DDL rather than importing mutable ORM definitions. See backend/ENGINEERING_REPORT.md for tested versus unverified behavior.


## Frontend implementation amendment
The Next.js frontend is implemented in `frontend/` using the actual OpenAPI-derived contracts. A Next route handler proxies `/api/*` to server-only BACKEND_URL, preserving session/Origin/CSRF/idempotency headers and streaming SSE. `GET /api/v1/dashboard` is an added authenticated aggregate endpoint; it returns counts from persisted, session-owned rows rather than browser estimates. API output types are generated with `frontend/scripts/generate-types.py`. Polling reconciles run detail as a fallback to event-driven updates; it never drives artificial progress. Browser transport notices are labelled separately from persisted execution events.

See `frontend/ENGINEERING_REPORT.md` for the audit boundary: build/in-process tests pass; socket listeners, Playwright/Chrome, PostgreSQL and successful live OpenAI verification remain blocked. The checked Next.js 16.4.6 / React 19.3.1 versions are now installed and build with Webpack. See ENGINEERING_REPORT.md for current results; fresh audit, live integrations and public deployment remain unverified.

## Independent identity projection (2026-11-26)
Raw extraction remains `Evidence`; semantic review produces `ReviewedEvidence` with four `IdentityChecks`. These derived checks live in existing JSON artifacts, with no migration or historical data rewrite. The API exposes optional checks for legacy compatibility. `reasoning_context.py` supplies scoring/writing only eligible claims, source metadata, sanitized prospect details and a relevance basis. User designation and raw role-bearing passages/titles are withheld. The independent draft auditor receives original allowed-source quotations plus explicit prohibition on reusing excluded role claims. Existing SSE stage events and score arithmetic remain in place. Current-role evidence is recent, dated primary material; undated primary biographies may only establish identity/association/title matching.

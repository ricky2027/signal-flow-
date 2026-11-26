# SIGNALFLOW frontend engineering report

Historical milestone. See [the current readiness report](../ENGINEERING_REPORT.md) for the installed Next.js 16.4.6 / React 19.3.1 checkpoint, current test results and remaining manual-access blockers.

## Delivery status
The frontend implementation, production compilation and in-process API/DOM tests are complete. **A fully running browser session has not been verified in this environment.** Starting both servers was attempted; TCP and Unix socket listeners are prohibited (`EPERM`). Chrome aborted with exit 134, and the Playwright package installation is blocked by registry DNS access. No deployment was attempted.

The existing brief, requirements, workflow, architecture, backend README/report and actual API/schema/model/worker code were inspected before implementation. The source of truth for TypeScript data shapes is the actual backend OpenAPI snapshot, not planning pseudocode.

## Implemented interface

- Persistent sidebar, responsive navigation, accessible labels/focus states, restrained enterprise visual design and reduced-motion support.
- Session-code sign-in using the actual HttpOnly cookie contract. Backend secrets never enter browser bundles.
- Dashboard with actual aggregate counts, grouped outcomes, recent activity and run links. No fabricated trend lines, company logos, sample records or conversion metrics.
- Validated prospect/offer form with field errors, submission loading state and stable idempotency key when retrying the same input.
- Paginated history and review queue, loaded-row search/status filters, persisted statuses and reopening by run ID.
- Run detail with real-event stage states, live SSE/replay, reconnect notices, fallback reconciliation, provider attempts/errors, source leads, retained evidence/claims, scores and selected hook.
- Evidence cards distinguish supported, disputed and unsupported claims; unknown/publication/event/retrieval dates remain explicit. Discovered links do not count as qualified sources. Inferred implications are visually separate from facts.
- Outreach review with subject/body editing, immutable-version save, historical-version selector, approve/reject/regenerate, optional instructions/reason, manual copy and explicit no-send messaging. Dirty edits disable review actions and are retained when switching detail tabs. Failed/regenerating runs show prior drafts read-only, if any exist.
- Loading, empty, API unavailable, session expired, invalid response, queued/running, failed, insufficient-evidence, conflict and low-relevance states. Missing results display zero only when returned by a loaded run; unavailable dashboard metrics show an em dash rather than zero.

No mock data mode is bundled with the application. Test-specific transport shims and temporary databases live only under tests. Decorative signal artwork illustrates the process and is not execution progress.

## Connected backend contracts

| API | Frontend use |
|---|---|
| POST /api/v1/session | Workspace login; proxied Set-Cookie |
| GET /api/v1/dashboard | Session-owned persisted aggregate metrics and status counts |
| GET /api/v1/runs | Recent runs, cursor-based history, awaiting_review queue |
| POST /api/v1/runs | Prospect submission and actual queued job creation |
| GET /api/v1/runs/{id} | Inputs, errors, evidence, signals, versions, reviews and provider calls |
| GET /api/v1/runs/{id}/events | Named persisted SSE events and Last-Event-ID/after replay |
| PATCH /api/v1/runs/{id}/draft | Save edited version with expected_version |
| POST /api/v1/runs/{id}/approve | Evidence revalidation and version-specific approval |
| POST /api/v1/runs/{id}/reject | Persist rejection with optional reason |
| POST /api/v1/runs/{id}/regenerate | Queue new version using qualified evidence |
| POST /api/v1/runs/{id}/retry | New linked run following failure |

The proxy also supports the existing health routes without treating readiness as proof of successful OpenAI access. Browser requests use `/api/*` on Next.js, which forwards to server-only BACKEND_URL, preserves Origin/CSRF/idempotency/cookie headers, and streams the response body without collecting SSE into a buffer. The frontend APP_ORIGIN is checked for mutations and must match backend APP_ORIGIN.

The only backend product change was an authenticated dashboard aggregate endpoint, its Pydantic response model and regression test. No research, scoring, drafting or approval functionality was moved out of Python. Backend schemas contain **nine** statuses; the old planning statement of ten was corrected. Frontend status coverage is checked against the actual OpenAPI enum.

## Executed checks

| Check | Result | What this establishes |
|---|---|---|
| Next.js production build | PASS | All routes compile/prerender, TypeScript validation and bundle generation complete |
| TypeScript typecheck | PASS | Frontend contracts, components, proxy and non-browser tests typecheck |
| Frontend unit tests | 5 PASS | Actual status coverage, no invented stage completion, abstention, invalid response guards and safe links |
| Next proxy/FastAPI integration tests | 3 PASS | Actual session cookie, idempotency, submission, SQLAlchemy persistence, history, aggregate counts and terminal SSE frames; transport-disconnection and 409 passthrough |
| DOM interaction audit | 1 PASS | Real API-backed sign-in, empty dashboard and review queue, mobile-navigation state, form submission, queued history, interrupted SSE, failed-run notice, zero evidence/draft tabs, error retention and search filtering |
| Backend suite | 34 PASS, 1 SKIP | Original backend behavior plus aggregate metrics/isolation regression; PostgreSQL test remains skipped |
| Backend Ruff and Python compilation | PASS | New API/bridge/schema modules have no remaining lint/compile errors |
| Actual provider-failure integration attempt | PASS for failure handling | With configured OpenAI credentials, real calls failed DNS; result persisted failed with zero sources/drafts and replayed over SSE |
| Frontend TCP startup | BLOCKED | `listen EPERM 127.0.0.1:3000` |
| FastAPI TCP startup | BLOCKED | Application startup completed, then bind failed with errno 1 on port 8000 |
| Unix-socket alternative | BLOCKED | Socket bind also returns EPERM |
| Chrome | BLOCKED | `--version` works; headless launch aborts with exit 134 |
| Playwright installation/execution | BLOCKED | Dependency download unavailable; runner not installed. Authored browser suite is not counted as passed |
| Real PostgreSQL and successful live research | UNVERIFIED | Existing database/network restrictions remain |

The DOM test uses jsdom, not a real rendering engine. It cannot establish screenshot quality, CSS layout, actual responsive sizing, native EventSource reconnection or browser cookie/proxy behavior over sockets. The EventSource transport is explicitly controlled to feed actual persisted backend frames and simulate interruption; the backend results are not fabricated. No successful outreach/draft UI path was tested with synthetic success records.

A status-count assumption in the first unit-test pass was corrected to the actual nine-state enum. A fixture import removed by the lint auto-fix was restored explicitly. The final results above supersede intermediate failures.

## Audit artifacts

See `audit/` for unit, integration, DOM, backend and build logs, plus the actual server-start and Playwright-install errors. `integration-live-attempt.txt` records the explicit configured-provider failure test; `integration-tests.txt` is the final deterministic missing-credentials path, which does not incur API usage. No screenshot is supplied because no real browser completed startup.

The backend was tested using the existing cached Python audit environment described in its earlier report. The frontend dependencies were installed from the local npm cache and have a package lock. Normal fresh installation still requires network access. Backend PostgreSQL driver availability and clean-install reproducibility remain subject to the prior backend limitations.

## Dependency and deployment blocker

Only Next.js **14.2.18** was available as an installable local cache artifact. npm identifies it as vulnerable; the [official security advisory](https://nextjs.org/blog/security-update-2025-12-11) requires a patched release. It was used solely to build and audit locally under the requested no-deployment scope. Upgrade to a currently patched, supported version, regenerate the lockfile and rerun integration/build/browser tests before any deployment. This deliverable is not approved for production deployment with the cached dependency version.

shadcn primitives were installed manually using the documented source-component approach: Radix Slot/CVA Button plus Card/Input/Textarea, Tailwind configuration and components.json. No network font or external image is required to render the workspace.

## Manual steps to finish local acceptance

1. Run outside the listener-restricted execution environment. Configure PostgreSQL and backend secrets; run Alembic migrations and the worker.
2. Start Next.js with server-only BACKEND_URL and matching frontend/backend APP_ORIGIN. Use the backend DEMO_ACCESS_CODE to sign in.
3. Run the provided Playwright suite after installing its dependencies/browser. Capture desktop/mobile screenshots, verify visual spacing and test native SSE disconnect/reconnect over the real proxy. Browser acceptance remains outstanding; the DOM suite is an explicit fallback, not a replacement.
4. Restore OpenAI/DNS connectivity and verify the configured model/tool/schema combination. Generate a genuine supported draft, then exercise editing, approval, rejection and regeneration in the browser. Do not insert a fake successful run to bypass this check.
5. Execute the real PostgreSQL integration test and verify parallel worker claims on PostgreSQL. No schema migration is needed solely for the dashboard endpoint.
6. Upgrade the cached Next.js dependency before deployment and rerun the checks. Deployment remains out of scope for this turn.

Exact setup/run/test commands and the browser test preconditions are in the root README. The source is integrated and locally compilable; a fully accepted live application remains gated on the environment steps above.

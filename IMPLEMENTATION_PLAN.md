# One-week implementation plan

Implementation update: the backend milestone is implemented and locally audited. See [backend/ENGINEERING_REPORT.md](backend/ENGINEERING_REPORT.md) for results and blocked live/PostgreSQL checks. The schedule below remains the original planning baseline. The frontend is now implemented with build/API/DOM checks; real-browser acceptance and deployment remain pending. See [frontend/ENGINEERING_REPORT.md](frontend/ENGINEERING_REPORT.md).

## Scope discipline
This milestone ends with five documents. No application code or deployment has been created. The following is a proposed seven-day schedule for one builder, assuming working API/hosting credentials on day one. All mandatory features remain in scope; defer enhancements before cutting mandatory behavior.

| Day | Work and usable exit condition |
|---|---|
| 1 | Scaffold frontend/backend, pin dependencies, provider search + evidence passage + structured-output spike, migrations, session access, deployment skeleton. Exit: public health page, DB round trip and real cited search. Resolve model/evidence compatibility immediately. |
| 2 | Run creation/list/detail, durable DB jobs and leases, SSE persisted events/replay, loading/error UI shell. Exit: real worker stage execution visible across refresh; crash produces actionable failure. |
| 3 | Research graph, attribution/date/identity extraction, evidence qualification and bounded follow-up. Exit: real prospect run with clickable sources, retained passages, provider logs and correct missing-identity abstention. |
| 4 | Conflict/freshness handling, candidate relevance rubric, deterministic gates/scoring, grounded generation and critic. Exit: happy path plus all three edge cases pass controlled fixtures; live smoke test distinct from fixtures. |
| 5 | Revisioned editor and support revalidation, approve/reject/regenerate, dashboard polish. Exit: edits invalidate approvals, race protection works, reviewed draft persists; no email delivery route. |
| 6 | Full deployed acceptance pass, SSE proxy/reconnect, worker interruption, quota/provider failure checks, responsive/accessibility review. Tune real demo prospect selection based on current evidence. Exit: public URL works from a clean browser and all mandatory rows demonstrated. |
| 7 | Contingency, documentation/runbook, fresh happy/edge runs and ≤5-minute recording. Exit: reproducible live app and final video, no undisclosed simulated data. |

## Proposed repository structure
`frontend/` Next.js app, components and generated API types; `backend/app/` API, schemas, models, graph nodes, policy, provider adapter and worker; `backend/alembic/` migrations; `backend/tests/` policy/contract/graph integration fixtures; `docs/` eventual runbook and demo script. Root planning documents remain authoritative until updated deliberately.

## Verification that protects product behavior
Test evidence gates and scoring boundaries (unknown date, stale date, planned event, duplicated origin, ambiguous identity, unresolved conflict), abstention precedence and grounding rejection. Contract/integration tests cover PostgreSQL transactions, job claim/lease expiry, event replay, session ownership, quotas, optimistic versioning and approval invalidation. One browser flow covers real creation → stages → evidence → edit → review → dashboard; another covers no-draft outcome. Mock external providers only in clearly labelled automated tests; use a small separate live provider smoke test to verify research citations and structured outputs. Never pass canned research as live execution.

## Five-minute demo plan
0:00–0:30: SDR problem and input a real prospect with a concrete offer.
0:30–1:50: real stages, evidence URLs, dates and role/offer explanation; execution timing varies, do not fake a timer. If waiting, explain the evidence gates or open an explicitly labelled prior completed run.
1:50–3:10: selected versus excluded signal, sourced facts versus implication, editable email, save/approve, then history.
3:10–4:30: submit a real low-information prospect or an offer with poor relevance; show abstention and why there is no draft. Use a prospect preflighted for reliable demonstration, without pretending web results are deterministic.
4:30–5:00: history, human control and limitations. Rehearse and trim recording, not real workflow stages. Retain examples for all three edge cases even though recording requires at least one.

## Risks and concrete mitigations
- Public data access/identity ambiguity: official sources first, bounded expansion, explainable abstention; no dependency on LinkedIn access.
- Source passages missing from search response: day-one capability gate; bounded follow-up or abstain. If adequate attribution cannot be achieved, revisit research provider before building the remaining pipeline; never silently weaken evidence standards.
- API cost/latency/rate limits: four search requests including follow-up/retries, bounded generation/repair, total timeout, transactional quotas and provider alerts. Budget exhaustion yields explicit failed/research_budget_exceeded with partial evidence retained.
- Hosting streams/workers: deploy early; verify same-origin proxy flush and reconnect. Use a persistent worker, not background tasks tied to HTTP lifetime.
- Week capacity: keep one prospect per run, one worker service, one database, bounded graph and shared demo access. No CRM, bulk import, vector search or multi-tenant administration.
- Subjective relevance or critic error: show rationale and evidence, conservative gates, manual review. No guarantee that an email will convert or that an LLM verifier is infallible.

## Final planning consistency review
- PROJECT_BRIEF defines scope; REQUIREMENTS maps every supplied requirement to acceptance and schedule; WORKFLOW defines decisions; ARCHITECTURE defines state, storage and contracts.
- Both workflow and API use the same nine statuses and six stages. Edge cases are persisted terminal outcomes, not provider errors. Review actions target immutable versions; regeneration requeues the same run with retained draft history, while failed retry creates a linked run.
- Database supports input snapshots, sources, many-to-many claim attribution, rejected candidates, draft history, human decisions, usage and durable events/jobs. API exposes required product behavior without a sending endpoint.
- Live progress derives from committed worker activity. Polling PostgreSQL for transport is compatible with SSE to browser. Domain state is durable without claiming automatic LangGraph checkpoint recovery.
- Day-one provider/deployment gates address the highest uncertainty; days six/seven reserve integration and contingency time. Plan is feasible for a focused one-week MVP under stated assumptions, not a production enterprise rollout.
- No extra Zamp assessment criteria have been asserted. Scores, budgets, visual styling, demo access and hosting choices are proposed engineering decisions. Requirement coverage is complete on paper; functionality must still be implemented and verified.

Next decision after document review: begin day-one setup and capability tests. Stop here for the current planning-only request.

Current readiness checkpoint: see [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md). Framework targets and the production Webpack build pass; live PostgreSQL/OpenAI/browser gates and hosting account access are still outstanding.

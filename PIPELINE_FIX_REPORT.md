# Research-to-outreach pipeline fix — 2026-11-26

## Reproduction and confirmed findings

Inspected the supplied `/tmp/signalflow-run-audit.json`, run `1d91fb5b-4422-4f70-a730-e62ae967aead`. This is analysis of a **historical persisted export**, not a new live run.

- First fetch pass: **12 attempted URLs, 5 available**. Follow-up: **6 attempted URLs, 3 available**; these counts include repeat/variant URLs, not eight unique verified sources.
- Both research calls and both Evidence calls have completed provider records. There are no recorded Candidates, drafting or quality calls. Extraction input-token counts are identical across the two passes.
- Final evidence and relational records agree: **1 source, 1 unsupported identity claim, 0 signals**. The only retained source is the official March 12, 2026 leadership-change article; it is outside the 180-day fresh-event window at the run's November 26 date.
- The identity claim references `source-1` through `source-5`, while only `source-3` exists. Model identity confidence was retained as `high` even after references became unsupported. The preliminary pass retained no sources at all.
- Several available URLs are official leadership/news pages. Their being marked available establishes successful text retrieval, not that an acceptable exact quotation or a current identity statement was retained.

The loss happened **before database persistence**: the final evidence artifact already contains only that one source. SQLAlchemy did not remove four otherwise retained sources. The old persistence path nevertheless copied dangling IDs into claim JSON and silently omitted missing relational links, allowing the inconsistency to persist.

The old extractor processed all pages together, then silently dropped sources on literal URL mismatch, non-contiguous/non-matching passages, word limits or duplicate IDs. It invalidated a whole claim when any reference was dropped, retained its broken IDs, and left the model's confidence untouched. Follow-up page truncation could also discard newly fetched pages while retaining the original full page list. Identical extraction token counts support that explanation in this reproduction, but **the old export does not contain rejected source objects or fetched page bodies**, so the exact rejection reason for each missing source cannot be recovered.

Date filtering did not delete the newer sources before persistence: the old extraction path did not filter sources by date there. The reported `insufficient_information` was the identity/evidence gate, not a failed relevance-score threshold. Skipping drafting was the safe downstream behavior given the malformed retained evidence; the upstream source loss and inconsistent metadata were defects.

Compact factual analysis: `audit/pipeline-fix/reproduction-analysis.json`. A minimal frozen evidence fixture is in `backend/tests/data/reported_evidence.json`; no fresh facts have been invented to augment it.

## Fixes

1. **Isolate extraction per retrieved page.** Each call receives one page, a deterministic source ID and instructions to retain identity or business-event evidence from one contiguous, at-most-80-word excerpt. One empty/malformed page cannot dominate the extraction of every other page. Three concurrent calls maximum; source count, two research passes, provider retries and the existing 180-second workflow deadline remain bounded. Unchanged page outputs are reused only within the same run using URL/body hashes; changed bodies and failed outputs are not cached.
2. **Canonicalise conservatively.** Remove known tracking parameters/fragments, normalise host/default ports, preserve paths and functional query parameters such as `section=board-members`. Validate redirects as before and carry the actual retrieved final URL plus known request alias. Never infer that arbitrary URLs or slash variants refer to the same page. URL aliases never bypass public-IP/redirect/quote verification.
3. **Repair provenance deterministically.** Accepted source IDs derive from canonical fetched URLs, independent of model numbering. Map each page's local claim references to those IDs. Namespace different claims that reuse an ID; merge identical claims conservatively. Unknown or ambiguous references are never guessed. Claims with no retained source are excluded; partial references stay unsupported until reviewed. The existing 30-claim cap retains representation of identity/events across pages and records any capacity exclusions.
4. **Review retained evidence independently.** A structured EvidenceReview checks each claim against retained quotations only, with no search summary. It checks cross-page identity contradictions and whether identity evidence supports a current role. High identity confidence requires a reviewed current supported identity claim from a primary source, without unresolved material identity conflict. Known stale dated statements cannot establish a current role; an undated live primary profile requires explicit current-role review and still cannot become a fresh event merely because it was fetched today.
5. **Enforce write invariants.** Reject duplicate source/claim identities and dangling source references before writing final/preliminary evidence. Claim-source links are written directly after validation rather than silently skipped. Historical artifacts are preserved. Read-only API views downgrade unsupported historical confidence, exclude missing links and mark affected claims unsupported without rewriting the database.
6. **Keep freshness separate from source retention.** Retain attributable old sources for audit, but exclude stale/undated/unlabelled-future events from fresh-signal eligibility. Original event dates take precedence over publication dates; republishing an old event does not refresh it. The 180-day boundary remains inclusive. Fixed a mixed-source future-date case where an older/current source could conceal an unplanned future date. Credibility, role/offer minimums and the 70-point selection threshold are unchanged.
7. **Expose actual outcomes.** Retrieval/extraction failures, passage/claim decisions, semantic review explanations, freshness eligibility, gate state and selected signal remain traceable through artifacts/API/UI. A page producing no attributable excerpt records that fact with source quality **unassessed**, not an invented score. If every page extraction throws, the run fails with `evidence_extraction_failed`; it does not masquerade as insufficient public evidence. A provisional qualification artifact remains explicitly non-final if semantic review fails. Tracking variants of retained sources no longer appear as extra unverified frontend leads.

Search narration is never passed into evidence extraction, evidence review, signal evaluation or drafting. Generation still requires qualified identity, an eligible selected event and a successful final quality check. No fallback draft or sending behavior was added.

Per-page extraction increases the possible number of logical model calls relative to the old batch extractor: up to 12 per pass, two passes, with unchanged outputs cached within the run; at most two cross-page reviews. Retries remain bounded by the provider and all operations by the unchanged workflow deadline. Provider usage is persisted; no cost estimate is fabricated.

## Changed files

| Area | Files |
| --- | --- |
| Extraction/verification | `backend/app/agents/research.py`, new `backend/app/qualification.py`, `backend/app/retrieval.py` |
| Policy/state/errors | `backend/app/policy.py`, `backend/app/graph.py`, `backend/app/worker.py` |
| Persistence/contracts | `backend/app/store.py`, `backend/app/schemas.py`, `backend/openapi.json`, generated `frontend/src/lib/contracts.ts` |
| Frontend mapping/diagnostics | `frontend/src/components/evidence.tsx`, `frontend/src/lib/utils.ts`, `frontend/src/lib/guards.ts`, `frontend/src/lib/status.ts` |
| Backend tests | new `backend/tests/test_qualification.py`, new `backend/tests/test_multisource_pipeline.py`, new `backend/tests/data/reported_evidence.json`; updated `backend/tests/fixtures.py`, `backend/tests/test_contracts.py`, `backend/tests/test_research_diagnostics.py` |
| Frontend tests | `frontend/tests/research-display.test.ts`, `frontend/tests/unit.test.ts` |
| Reporting | this report, `ENGINEERING_REPORT.md`, superseding notice in `RESEARCH_INVESTIGATION.md`, evidence under `audit/pipeline-fix/` |

No .env, credentials, authentication, migration files, dependencies or existing live database records were changed. No running process was stopped or restarted. No new migration or dependency install is needed for these changes.

## Executed validation

| Check | Result |
| --- | --- |
| Backend tests | **65 passed, 1 skipped** (real PostgreSQL), 17 existing dependency deprecation warnings |
| Frontend unit/component tests | **10 passed** |
| Frontend security regressions | **3 passed** |
| Next proxy ↔ actual FastAPI ASGI integration | **3 passed** |
| DOM ↔ actual FastAPI ASGI integration | **1 passed** |
| TypeScript | PASS |
| Production Webpack build | PASS, isolated temporary frontend copy; running .next untouched |
| Configured-secret scan | No matches in 93 checked source/test/audit files; secret values never printed |
| Native Playwright invocation | BLOCKED: runner unavailable |
| Current official leadership URL retrieval | FAIL: DNS `gaierror` in this environment |
| New successful live research/OpenAI/PostgreSQL chain | **Not verified** |

Logs and machine-readable results: `audit/pipeline-fix/`. The new complete workflow tests use an authenticated API session, isolated SQLAlchemy storage, three synthetic pages, structured fixture responses, signal ranking, draft references and quality validation. They verify multiple-source writes and relational links, recent-signal selection, stale-event exclusion and survival of an individual extraction failure. The frozen export regression intentionally still abstains when given only its actual stale evidence; it does not manufacture missing recent pages. These are regression passes, not live integration passes.

## Restart and test locally

Wait for active jobs to finish. In the **existing** worker terminal, Ctrl-C, then:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.worker
```

Restart the existing **API** similarly (unless its reload process already picked up the changes):

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

The **development frontend** should hot reload; refresh http://localhost:3000. If it needs restarting, use its existing terminal:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/frontend
npm run dev
```

Do not launch duplicate instances or replace .env. A frontend running `next start` rather than development mode needs a normal build/restart after stopping that instance. No database migration is required.

Open http://localhost:3000/research/new and submit the same prospect and original offer. Create a **new** run; preserve the old result. Verify:

1. Available pages produce independent extraction/review outcomes; failures and empty excerpts have reasons.
2. All claim source IDs exist in retained sources; supported identity has consistent confidence and current primary backing.
3. Dated recent company events reach evaluation; older/unknown/future-disallowed events cannot win fresh-signal selection.
4. A relevant selected signal leads to a versioned draft with valid references and quality checks; genuine insufficiency still abstains.
5. Reopen the run and confirm the same persisted evidence/signals/draft. Nothing is sent automatically.

Read-only export of the new run for live verification:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.inspect_run --run-id NEW_RUN_UUID > /tmp/signalflow-new-run-audit.json
```

Repeat automated checks:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run pytest -q
cd ../frontend
npm test
npm run test:security
npm run test:integration
npm run test:dom
npm run typecheck
```

The optional PostgreSQL test requires a disposable TEST_DATABASE_URL, not an unrelated production database. Native browser acceptance and the fresh real-provider chain remain manual follow-up checks until this execution environment has the required networking/browser capabilities.

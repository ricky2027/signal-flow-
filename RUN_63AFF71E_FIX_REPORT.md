# Run 63aff71e: evidence-retention fix and live validation status

## Confirmed historical root cause

Inspected `/tmp/signalflow-63aff71e-audit.json`, run `63aff71e-b455-4fc6-86cf-4d7095edf719`.

- **Saved company_website is null.** “Website not provided” correctly describes that saved input. Supplied-URL persistence passes the frontend/API/prospect/run round-trip tests; no production website-persistence defect was reproduced and no historical value was filled in.
- **The biography was discovered and fetched in both passes:** https://www.kellyocg.com/about-us/leadership/pete-hamilton/ . Its extraction received 4,160 characters in each pass, below the text cap. Discovery, canonicalisation and fetching were not the failure for this URL.
- **The first biography output exceeded the 80-word quote limit. Its free-text repair failed exact substring matching.** It remained rejected in the follow-up. The earlier bounded retry existed and ran; asking the model to copy a shorter quotation still allowed paraphrasing/punctuation/spacing errors. The rejected original quotation was not archived, so its precise mismatch cannot be reconstructed.
- **The leadership directory was retained** with Pete's exact APAC vice-president/managing-director title. The Singapore page and a personal LinkedIn passage also provided supported role claims. Review declined to affirm currentness because the pages were undated or lacked an authoritative current-role context. There was no material identity conflict.
- The UI's **four sources are retained sources**, not the number discovered or fetched. There were nine distinct fetched URLs across the two passes and no recorded retrieval failures. All final claim references resolve to retained sources; the evidence artifact and relational source/claim records agree.
- No business-event claim survived. Candidate generation was not called: the evidence gate returned insufficient_information because identity confidence was low. No score, relevance-threshold failure or draft-generation failure was observed.

The failure is not missing biography discovery, a missing company website preventing retrieval, or database source deletion. It is unreliable free-text quotation repair, followed by conservative current-role qualification. The latter must not be bypassed to force a draft.

Evidence and input fingerprint: `audit/63aff71e-fix/findings.json`.

## Minimum production change

1. **Copy exact repair quotations from fetched text.** New `backend/app/excerpts.py` creates bounded overlapping windows of at most 60 words from the actual normalized page body, selecting at most 16 for model inspection. Prospect/company terms rank excerpts only; they do not verify facts. The model returns a passage ID and rebuilt claims using the new strict ExcerptSelection schema, rather than writing another quotation. The retained quotation is copied from that selected candidate.
2. **Revalidate everything.** Unknown passage IDs, claims without a selected passage, ambiguous source provenance and incorrect selected source references are rejected. Existing exact-substring, 80-word, source-ID and independent semantic checks remain. A claim missing from its selected quote must still fail semantic review. Honest empty evidence remains valid. Repair remains bounded once per URL/body per run, under the unchanged deadline.
3. **Repair cannot upgrade metadata.** Original source classification, publisher/date fields and date uncertainty are preserved. The selector cannot fabricate a publication date or promote reporting to primary. No prospect-specific path, name or company was hardcoded in production.
4. **Separate title equivalence from currentness.** The review instructions and diagnostic mapping now allow a sourced role to be equivalent while its present-day currency remains unverified. A live official primary leadership listing is not automatically disqualified solely for lacking a publication date—this was already allowed by policy—but the reviewer must establish the live roster/profile context and explain it. Retrieval date/copyright year cannot become publication dates. Historical or uncertain profiles must still remain unverified. No deterministic currentness override or threshold reduction was added.
5. **Trace the loaded method.** Future page_extraction_summary/extraction_repairs artifacts identify `literal_selection_v1`. A new run can therefore show whether the worker loaded this fix. No new API fields, frontend features, URL-crawling feature or database migration were necessary.

Website submission code was left unchanged. The prepared fresh input explicitly supplies `https://www.kellyocg.com/`, while preserving the target run's designation, product and value proposition. This is a new input, not a rewritten historical record or verified company assertion.

## Exact files changed

- New production helper: `backend/app/excerpts.py`.
- Production changes: `backend/app/agents/research.py`, `backend/app/qualification.py`, `backend/app/schemas.py`.
- New regressions: `backend/tests/test_excerpt_selection.py`, `backend/tests/data/run_63aff71e_evidence.json`.
- Updated test adapters/cases: `backend/tests/fixtures.py`, `backend/tests/test_extraction_repair.py`, `backend/tests/test_website_and_biography.py`, `backend/tests/test_contracts.py`.
- Reports/evidence: this document, latest-status notices in ENGINEERING_REPORT.md and RUN_63AFF71E_INVESTIGATION.md, and `audit/63aff71e-fix/`.

No production frontend, HTTP contract, credentials, .env, authentication, dependency or migration changes were made. No historical run or running service was modified.

## Executed tests

| Check | Result |
| --- | --- |
| Backend suite | **92 passed, 1 skipped** (real PostgreSQL); 17 existing dependency deprecation warnings |
| Frontend unit/component | **11 passed** |
| Frontend security regression | **3 passed** |
| Frontend API integration | **3 passed** |
| Frontend DOM integration | **1 passed** |
| TypeScript | PASS |
| Native Playwright suite invocation | BLOCKED: runner not installed |

Regressions exercise literal source windows after long boilerplate, bounded candidate count and quote length, unknown IDs/references, unchanged classification/dates, unsupported claims, caching, repair transport failure, title equivalence with unverified currentness, website round-trip, and a complete repaired research → persisted sources → selected recent signal → validated draft workflow. The complete success uses explicit synthetic provider/retrieval fixtures and isolated SQLite. The actual retained historical evidence fixture continues to abstain. Neither is presented as a successful live Pete run.

## Fresh live attempt: blocked before submission

Attempted a real authenticated connection to the local FastAPI server to submit the prepared new request. It failed with ConnectError before login/submission. DNS for api.openai.com and www.kellyocg.com also fails from this tool environment.

**New run ID: none. Actual new live outcome: blocked_before_submission.** No new source, identity verdict, relevance score or draft exists to inspect. The old run was not reused as a new execution. Running worker version and Neon persistence could not be verified through this unavailable connection. Nothing is claimed to have passed live.

Actual attempt: `audit/63aff71e-fix/live-attempt.json`. Prepared new request: `audit/63aff71e-fix/new-run-input.json`. Test results: `audit/63aff71e-fix/results.json`.

## Load and validate in the working local environment

Only the **worker** needs restarting for this patch; the HTTP schema and frontend are unchanged. Wait for active jobs to finish, stop the existing worker in its own terminal, then:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.worker
```

Keep the API/frontend running. Open http://localhost:3000/research/new and submit the prepared input, including company_website=https://www.kellyocg.com/. Preserve the old run.

Let it complete or abstain; record the real new ID and export:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.inspect_run --run-id NEW_RUN_UUID > /tmp/signalflow-pete-literal-selection-audit.json
```

Inspect the worker method marker, exact quotations, dates, current-primary-identity explanation, candidate scores and any validated draft. A successful identity check alone must not manufacture a recent event or force an outreach draft. If the live sources or relevance do not pass, preserve the precise abstention.

The code/tests portion is complete; fresh live end-to-end validation remains incomplete until the execution environment can reach the application and external services, or a new live export is supplied from the working environment.

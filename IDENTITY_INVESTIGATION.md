# Identity investigation: run 2e86e80e — 2026-11-26

Run export subsequently supplied and inspected: [PETE_URL_INVESTIGATION.md](PETE_URL_INVESTIGATION.md) completes the URL-by-URL findings and supersedes the pending-access status below.

## Status: run-specific evidence pending

The configured database cannot be resolved from this tool environment. Read-only inspection of the `2e86e80e` prefix returned `OperationalError / dns_resolution_failed`; see `audit/identity-investigation/live-inspection.json`. The only available export was the older Satya run. No Pete export was available at completion of this investigation.

**The exact two URLs and their actual rejection reasons are unknown here.** Neither was guessed from generic public search or substituted from another prospect. The statement that two sources were retrieved comes from the user's report, not independently inspected records. No live source or OpenAI outcome for this run is claimed.

## Findings against the six questions

| Question | Finding |
| --- | --- |
| Exact two URLs | Requires the target export or working Neon access. Cannot answer factually yet. |
| Why no retained identity passage? | Requires retrieval, page extraction, qualification and review records. A successful fetch only establishes available text; it does not establish that a usable current identity quotation was present or retained. |
| Is querying sufficiently targeted? | The previous prompt combined identity and company events in broad guidance. It supplied the name/company but did not explicitly prioritise prospect-specific official profiles or provide targeted query suggestions. Improved as described below; actual queries executed for this run remain uninspected. |
| Were relevant passages lost? | Not established for this run. Existing URL/quote/ID rejection records identify qualification rejection. New per-page output counts distinguish an extractor returning zero identity claims from a proposed identity passage being rejected. Neither counts nor a page title prove that identity text was present in the original body. |
| Is exact title matching required? | No deterministic string equality or fuzzy title matcher exists. Previously semantic comparison was implicit in prompts and had no explicit outcome. A literal-match failure in the live run is **not proven**. New instructions and structured assessment explicitly handle equivalent titles without changing sourced facts. |
| Are failures and genuine mismatches distinct? | Found a real display defect: `available=true` hid an extraction error behind “Retrieved.” Fixed error precedence. Also found supported-but-noncurrent identity claims could have no diagnostic rejection reason; added explicit current-identity/designation reasons. |

Current non-secret configuration is max_sources=12, max_search_requests=4 and run_timeout_seconds=180. It does not establish the settings used by the already persisted target run or why only two sources were retrieved.

## Code changes

- **`backend/app/research_guidance.py` (new), `backend/app/provider.py`, `backend/app/agents/research.py`:** add name/company-specific query suggestions prioritising official leadership/team/profile pages. An optional supplied company website is a search hint, not verified ownership. No domains or profile paths are invented. Identity recovery focuses on the person rather than repeating company news. The requested title is not a required exact query term. Suggested plans are persisted separately from actual provider tool activity; suggestions are not claimed as executed queries.
- **`backend/app/research_guidance.py`, `backend/app/qualification.py`:** preserve the source's actual title; recognise semantic equivalence only for corroborated matching function, seniority, employer and scope. Abbreviation expansion can be equivalent, but different functions, regional scopes, subsidiaries, former/acting roles and concurrent extra titles are not automatically equated. A missing role is unverified, not proof of mismatch. The user's designation is never evidence.
- **`backend/app/schemas.py`, `backend/app/qualification.py`:** require the structured verifier to classify `designation_match` as equivalent, mismatch, unverified or not_applicable. A current primary quotation, valid source references, supported claim, correct entity, high confidence and no material identity conflict remain necessary. Equivalent titles can pass without rewriting claim text. Credible incompatible current-role evidence blocks identity qualification with `designation_mismatch`; absent, unsupported, noncurrent or nonprimary evidence remains unverified. Matching title wording alone cannot override a wrong person/employer.
- **`backend/app/agents/research.py`:** persist `page_extraction_summary` with actual input character count and proposed source/identity/event claim counts. It adds no inferred facts and no fabricated quotations. Existing exact-quote, source-ID, currentness, credibility, freshness, relevance and quality safeguards remain intact.
- **`frontend/src/components/evidence.tsx`:** show recorded extraction errors even when transport retrieval succeeded. Retrieval, extraction and identity-verification failures remain separate diagnostic records.
- **`backend/app/inspect_run.py`:** accept full UUIDs or unique prefixes of at least eight characters; reject ambiguous prefixes rather than guessing. Default is now the latest run, with no hardcoded prospect filter. It remains read-only and excludes login tokens/credentials.
- **Contracts:** regenerated `backend/openapi.json` and `frontend/src/lib/contracts.ts`; the API's designation diagnostic is optional for historical records, while new agent reviews require an explicit assessment.

No existing runs, .env, credentials, authentication, migrations or dependencies were changed. No services were stopped or restarted. Additional diagnostics apply to future executions; historical reasons that were never recorded are not invented.

## Regression results

**76 backend passed, 1 real PostgreSQL test skipped; 18 frontend passed (11 unit/component, 3 security, 3 API integration, 1 DOM); TypeScript and isolated production build passed.** Existing dependency deprecation warnings remain. Logs: `audit/identity-investigation/`.

New/updated tests:

- `backend/tests/test_identity_research.py`: targeted provider request; no exact designation filter or guessed domain; identity-only follow-up; equivalent, incompatible and unverified roles; source title preservation; missing role versus genuine mismatch; historical identity versus current identity; wrong entity cannot be rescued by matching title; extraction omission versus quote rejection.
- `backend/tests/test_inspect_run.py`: unique prefix, ambiguous prefix rejection, generic latest run and retained read-only/token protections.
- `backend/tests/test_research_diagnostics.py`: HTTP retrieval failure is explicitly recorded and not classified as a designation mismatch.
- `backend/tests/fixtures.py`, `backend/tests/test_qualification.py`: updated synthetic verifier contract.
- `frontend/tests/research-display.test.ts`: an extraction error remains visible after successful retrieval.

Semantic-review verdicts in tests are explicit synthetic responses. These prove prompt contracts and deterministic routing, not the real model's judgment about Pete Hamilton. The isolated frontend build left the running `.next` directory untouched. Native browser and new real-provider execution were not verified.

## Required export to finish the diagnosis

Run in the terminal that can reach Neon, without stopping any service:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.inspect_run --run-id 2e86e80e > /tmp/signalflow-pete-audit.json
```

The helper now understands this prefix and will request a full UUID if ambiguous. Let the agent know when the file is saved, or share the secret-safe JSON contents. It includes source URLs, qualification artifacts, actual provider tool activity, review explanations, events and relational evidence. It does not claim/run jobs or alter research records.

That export is needed to identify whether the two pages lacked role evidence, returned shells/blocked content, suffered model extraction omission, failed quote/URL/ID qualification, or contained genuinely incompatible current identity evidence. It also establishes whether the new code was loaded by the worker for that run.

## Loading the changes

After active research jobs finish, restart the existing **API first**, then **worker**, so the API can parse new optional diagnostics before the worker writes them:

```sh
# API terminal: stop its existing process, then
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

```sh
# Worker terminal: stop its existing process after active jobs finish, then
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.worker
```

A development frontend should hot reload; refresh http://localhost:3000. No migration is needed. Preserve the original run; use New research for a fresh execution only after collecting the target export. Genuine unverified identity or incompatible-role evidence must continue to abstain.

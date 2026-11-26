# Run 63aff71e investigation — awaiting its persisted export

The export has now been supplied and inspected. [RUN_63AFF71E_FIX_REPORT.md](RUN_63AFF71E_FIX_REPORT.md) supersedes the pending-access findings below and documents the minimum production fix and new live-attempt blocker.

## Access and scope

Read-only inspection of run prefix `63aff71e` failed with Neon DNS resolution failure. No matching export was available. `/tmp/signalflow-pete-audit.json` remains the older `2e86e80e` run and was not substituted for this run.

Consequently, the actual saved website value, discovered URL list, fetch results, rejected passages, repair attempts and identity review of **63aff71e** remain unverified. No run-specific root cause is claimed.

## Confirmed implementation behavior

1. **Discovery and visits:** `backend/app/agents/research.py` fetches actual URLs returned by web research, up to the configured source cap, through the bounded public-source retrieval service. It can and does call retrieval on prospect-specific biography paths when search returns them. It does not independently crawl a company homepage's leadership links, generate profile paths, or guarantee that a known profile absent from search results will be visited. A company website currently supplies a domain-targeted search hint, not a direct reference-fetch request.
2. **Four sources is ambiguous:** the run view's displayed count is `run.sources.length`, i.e. retained evidence, not all discovered URLs or retrieval attempts. Four displayed sources do not establish that the biography was never discovered/fetched.
3. **Website provenance:** ResearchForm reads the named company_website field, trims it, and sends null for a blank field. RunInput validates supplied public URLs; create_run stores the value in both Prospect.data and Run.input. The detail API returns Run.input. The UI displays “Website not provided” only when that saved input is falsy. It does not infer a supplied website from the company name or from discovered sources. Tests pass for this round-trip, but cannot establish what the target run actually submitted or which deployed process version handled it.
4. **Extraction:** quotations still require exact normalized substring matching, at most 80 words, valid source IDs and semantic claim support. Structural re-extraction is limited to one repair per URL/body per run. Bad repairs remain rejected and uncached. A passing fixture does not establish that this run fetched the same page body or that a live model produced a valid repair.
5. **Role versus currentness:** a retained short quotation can support a source-attributed role and employer while published_at/event_at remain null and identity confidence remains low. Fetch date and copyright year do not establish current employment or event freshness. Current identity is a separate reviewed assertion. Existing policy allows an explicitly reviewed live primary profile to corroborate current identity; it does not automatically promote every undated page. If currentness cannot be affirmed, the identity gate must continue to block drafting.

## Official biography content checked independently

The [official biography](https://www.kellyocg.com/about-us/leadership/pete-hamilton/) names Pete Hamilton, describes an APAC vice-president/managing-director role at KellyOCG, and places KellyOCG within Kelly Services. Its core role statement fits under the existing 80-word limit. The page does not provide a publication date for the biography. This independent web inspection is not evidence that SIGNALFLOW run 63aff71e discovered or fetched it.

## Added tests and executed results

- New `backend/tests/test_website_and_biography.py`: supplied/blank website round-trip through authenticated APIs and both stored JSON records; invalid URL rejection; fetching an actual profile URL supplied by the search adapter; source-faithful short biography extraction/repair with exact title/organisation and supported claim, while an unconfirmed current role remains low-confidence and abstains.
- Updated `frontend/tests/dom.test.ts`: verify that a website entered in the real form persists through the FastAPI bridge and appears in the run context rather than “Website not provided.”

Results: **87 backend passed, 1 PostgreSQL test skipped; 18 frontend passed; TypeScript passed.** Backend workflow/provider verdicts use explicit fixtures and isolated SQLite. The biography's short source clause is a fixture; its appended padding and model responses are synthetic and do not reconstruct a live page response. No successful live application fetch, model verdict, PostgreSQL execution or run 63aff71e outcome is claimed.

Logs: `audit/run-63aff71e/`. No production source, .env, credentials, migrations or historical runs were changed. No service restart is required for these test-only changes.

## Minimum safe next action

First obtain the actual run record; otherwise a code patch could target the wrong failure:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.inspect_run --run-id 63aff71e > /tmp/signalflow-63aff71e-audit.json
```

- If company_website is null, the UI label is correct. Supply `https://www.kellyocg.com/` explicitly on a fresh run; it improves search targeting but is not a guarantee of biography retrieval.
- If the biography is absent from research URLs, investigate discovery rather than extraction. For guaranteed access to a user-known biography, the smallest product capability would be an explicit untrusted reference-URL input, processed by the same SSRF, retrieval, quotation and semantic checks. Do not hardcode a Pete-specific URL, invent paths or treat the supplied link as verified identity. That capability has not been added speculatively.
- If the URL was returned, inspect retrieval_summary, evidence_verification and extraction_repairs before choosing a retrieval or repair fix. Preserve abstention for genuinely unsupported current identity.

The target export is still required to decide which branch applies and complete the run-specific root-cause analysis. The verified test results do not replace that missing evidence.

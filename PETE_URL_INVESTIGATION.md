# Pete Hamilton: completed URL-by-URL investigation

Run: `2e86e80e-7597-4824-888b-3593f0c011ec`. Source: user-supplied `/tmp/signalflow-pete-audit.json`. This completes the previously blocked inspection; it does not claim a new successful live run.

## Main correction

The run did not retrieve only two pages. It discovered **8 unique URLs**, retrieved text from **7**, and retained **2** after qualification. One retained passage explicitly supports Pete Hamilton's role. The final evidence has **3 supported claims with valid source IDs**, not zero verified facts or broken source mappings.

The gate blocked **current primary-source identity confidence**, not title-string equality, missing SQL rows, or a failed relevance score. Candidate generation was never called.

## The exact two retained URLs

1. https://www.kellyservices.com/divisions/outsourcing-consulting-group/about/
   - Retained, exact-matching quotation; contains the statement that Pete Hamilton is vice president and managing director for the APAC region of KellyOCG and describes KellyOCG's relationship to Kelly Services.
   - Person identity claim is `supported`, `entity_match=true`, and references the existing retained source.
   - Publication/event dates are null; source was classified **reporting** (policy weight 0.8).
   - Both review explanations recognise the expanded role. They explicitly decline to establish that it is current as of the run date. The retained source also fails the primary-source requirement. This is not evidence of an incompatible designation.
   - Its employer-hosted context makes the reporting classification worth revisiting on a new extraction, but hostname alone does not prove authorship/currentness. No stored classification was automatically upgraded.
2. https://www.linkedin.com/company/kellyocg
   - Retained organisation description, classified **aggregator** (weight 0.4), with unknown dates.
   - The actual retained excerpt describes KellyOCG's business and relationship to Kelly. It contains no Pete Hamilton designation.
   - One organisation-relationship claim was incorrectly labelled `identity` by extraction. The review recognised it as organisational context, not personal identity; it did not verify a current prospect role. Existing/new guidance requires organisation relationships to be context claims.

These are the canonical URLs in the retrieval/evidence records. Research citations also contained `utm_source=openai`; stripping that tracking parameter worked. URL mapping was not the cause of source rejection in this run.

## Every discovered URL

| Exact canonical URL | Retrieval in this run | Qualification/persistence result |
| --- | --- | --- |
| https://www.kellyocg.com/about-us/leadership/pete-hamilton/ | Text available in both passes | **Rejected twice: passage_word_limit.** Classified primary, weight 1.0. This is the prospect-specific official biography, but its generated quote exceeded 80 words and never reached semantic review. No URL or substring rejection was recorded for this source. |
| https://www.kellyservices.com/press-releases/kelly-expands-global-delivery-center-in-bangalore | Available in pass 1; carried into pass 2 | **Rejected twice: passage_word_limit.** A proposed recent event source was lost before signal evaluation. Its extracted age metadata was 13 days; this is proposed metadata, not a retained verified event or evidence of relevance. |
| https://www.kellyservices.com/divisions/outsourcing-consulting-group/about/ | Available in both passes | **Retained twice/finally persisted.** Supported Pete role statement, but undated/reporting; current identity remained unverified. |
| https://www.kellyservices.com/press-releases/all | Available in pass 1; carried into pass 2 | **Rejected twice: passage_not_found.** The generated excerpt did not match the fetched text. Headline/search-summary text cannot replace an actual contiguous quotation. |
| https://ir.kellyservices.com/static-files/90684e60-8d94-4205-9012-ceee1e98159c | **HTTP 403** in pass 1 | Genuine retrieval failure; no page text/evidence retained. No inference about its content or file type is justified from the export. |
| https://au.linkedin.com/in/peterhamilton1 | Available text in both passes | **Rejected twice: passage_not_found and passage_word_limit.** A nonempty response does not prove all profile sections were accessible. The original body/rejected quotation is not archived, so login-shell versus model quotation errors cannot be distinguished further. |
| https://www.linkedin.com/company/kellyocg | Available in pass 1; carried into pass 2 | **Retained/finally persisted.** Organisation context, no prospect role in retained passage. |
| https://6ix.com/news/kellyr-expands-global-delivery-center-in-bangalore | Available in follow-up | **Rejected: passage_word_limit.** Proposed event-age metadata was 13 days; no event claim from it survived qualification. |

The exact rejected quote lengths/content are not recoverable: the old export retained rejection codes, not those rejected source objects. `passage_word_limit` establishes that the code's 80-word check failed; no invented word count or reconstructed original quotation is supplied here.

## Root causes and what worked

**Primary defect: format failures discarded useful pages without a bounded repair.** The official biography and event pages were available, but generated excerpts exceeded the required word limit. The limit itself is intentional and remains unchanged. The missing behavior was asking for a compliant shorter, still-verbatim quotation with newly entailed claims, then revalidating it.

**Caching reinforced the failures.** Code cached syntactically parsed Evidence before checking quote/source/reference structure. The export has 6 first-pass page extractions and only 2 additional extractions for 7 second-pass pages: five outputs were reused. With only two acceptable first-pass source outputs, at least three reused outputs were structurally rejected ones. That reuse calculation is an inference from the recorded call counts and selected pages; the export does not record individual cache hits or the precise original rejected excerpts.

**The safe gate worked on the evidence left behind.** The reviewer could not establish current primary identity from an undated reporting source and an organisation-only aggregator excerpt. Confidence was low, so the evaluation node recorded `blocked`; no Candidates call, scores, writing or quality checks occurred. Zero candidates does not mean zero supported facts or a relevance threshold failure. All final claim-source references resolve; final evidence and relational source/claim records agree.

**No demonstrated title mismatch.** The user supplied “Vice President, APAC — KellyOCG”; the retained role statement includes vice president and managing director, APAC. Review explanations recognise that role and reject currentness, not lexical equivalence. Some aggregate extraction warnings complain about the literal requested title, but warnings were merged from separate pages without source labels. They cannot override the actual retained claim/review or establish a genuine mismatch. Prior semantic-equivalence guidance remains useful, but it was not this run's decisive failure.

**Querying was broad, but discovery succeeded.** Actual tool activity records the old research instruction plus escaped prospect/offer JSON as its query, including the sales value proposition. The follow-up repeats that form with a generic identity-resolution focus. This was less focused than a name/company/official-profile search, yet it still found and fetched the correct prospect-specific official biography twice. Search targeting was an improvement opportunity, not the sole bottleneck. The newer research-plan and explicit designation diagnostics are absent from this run, so it did not execute the latest guidance/diagnostic version.

**No OpenAI outage or deadline failure is recorded.** Provider audit has two completed research calls, eight completed Evidence calls and two completed EvidenceReview calls; no failed provider attempts. Approximately 140.6 seconds elapsed from the running event to finished_at, within the configured 180-second deadline. The separate IR HTTP 403 is a public-page retrieval failure, not an OpenAI API failure.

## Additional fixes made after inspecting this export

- `backend/app/agents/research.py`: add at most one structural re-extraction repair per URL/body per run. Repair uses the actual fetched text, rejection reasons and the same evidence rules; it must generate a shorter literal quotation and claims entailed by that quotation. It never blindly truncates a quote or preserves claims whose backing words were cut. Empty evidence remains acceptable. Repairs are audited, and transport errors are exposed as extraction diagnostics.
- `backend/app/qualification.py`: identify repairable quote/URL/ID errors separately from genuine missing facts. Source-local warnings now include their source URL, preventing one page's “no role” warning from appearing as an unscoped global verdict.
- `backend/app/agents/research.py`: cache only structurally valid outputs. Invalid inherited cache entries are rejected; changed bodies invalidate cache keys as before. Failed repairs are not accepted or cached. Semantic identity review always runs separately. The extraction target is 35–60 words with the unchanged maximum of 80; classification guidance distinguishes first-hand employer statements from third-party reporting without hardcoded domain upgrades.
- `backend/app/graph.py`: retain the per-run repair budget in workflow state.
- `backend/tests/test_extraction_repair.py` and `backend/tests/data/pete_retained_evidence.json`: reproduce the actual retained-evidence gate and test safe repair, rejected repair, transport failures, cache behavior, warning scope and a complete synthetic repaired workflow with persisted sources/signals/validated draft.

No identity/currentness, primary-source, freshness, relevance or final quality requirement was lowered. Repairs cannot create dates, trust search narration, infer a role from user input or accept unmatched quotes. The existing deadline and search budget remain unchanged. Additional repair calls can still exhaust the existing deadline; no successful draft is guaranteed.

No .env, credentials, authentication, migrations or existing database records were changed. The original Pete run remains an abstention. No running service was stopped or restarted.

## Executed regression validation

- **82 backend passed, 1 real PostgreSQL test skipped**; 17 existing dependency deprecation warnings.
- **18 frontend passed**: 11 unit/component, 3 security, 3 Next/FastAPI integration, 1 DOM integration.
- TypeScript passed.
- The new end-to-end repair test uses explicit synthetic page/provider fixtures; it verifies source persistence, a selected recent signal, rejection of a stale signal and a validated draft. It is not a live Pete rerun.
- The frozen Pete test uses only the real retained evidence and correctly still abstains. It does not invent the missing official biography quotation or event evidence.

Logs, source-export fingerprint and URL findings: `audit/pete-url-investigation/`. No new successful live research/PostgreSQL/provider chain or native browser pass is claimed.

## Load changes and rerun safely

Wait for active jobs to finish. Ensure the API has the previous optional diagnostics changes loaded, then restart the existing worker. Restart API first if uncertain; do not launch duplicate listeners.

```sh
# API terminal, after stopping its existing process if reload is not enabled
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

```sh
# Worker terminal, after active jobs finish and its old process is stopped
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.worker
```

The development frontend only needs a browser refresh. No migration or dependency install is required. Open http://localhost:3000/research/new and create a new run using the original inputs. Preserve the old run. Inspect the official biography's quote checks and any `extraction_repairs` artifact; confirm current primary identity, a relevant recent selected signal and validated draft before approving anything. If repair still cannot produce qualified evidence, abstention must remain.

Export the new run with `uv run python -m app.inspect_run --run-id NEW_RUN_UUID` for actual live verification. The supplied export proves what failed historically, not that a new live repair has succeeded.

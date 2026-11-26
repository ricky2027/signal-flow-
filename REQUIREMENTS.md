# Requirements and acceptance audit

All M rows are mandatory from the supplied brief. P rows are proposed implementation safeguards. Workflow names and statuses are defined in WORKFLOW.md; wire contracts are in ARCHITECTURE.md.

| ID | Requirement | Acceptance evidence | Delivery |
|---|---|---|---|
| M01 | Public runnable app and real inputs | Public URL; submit real person/company/role/offer; refresh persists run | Days 2, 6 |
| M02 | Genuine public research using AI | Provider call IDs, queries, timestamps and actual source URLs saved; no fixture substituted in live mode | Day 3 |
| M03 | Recent, credible signals and role/offer relevance | Dated evidence, confidence, ranked candidates and reason for selection visible | Days 3–4 |
| M04 | Facts distinguished from implications; supported important email claims | Evidence-linked claims, separately labelled implications, draft validation before review and approval | Days 3–5 |
| M05 | Genuine workflow stages and SSE | Persisted stage events stream during execution and replay on reconnect | Days 2–4 |
| M06 | Dashboard and historical statuses/outputs | List runs, open prior inputs/evidence/draft and refresh after restart | Days 2, 5 |
| M07 | Editable email; approve, reject, regenerate; human review | Revisioned editor and decisions; edits clear approval; regenerated text requires review; no send integration | Day 5 |
| M08 | Insufficient prospect information | Company-context evaluation requires credible person identity and company association; unverified current-role claims excluded; missing identity/association yields insufficient_information and no draft | Days 3–4, 6 |
| M09 | Conflicting or outdated sources | Conflict and dates displayed; disputed/stale claims excluded; unresolved material conflict yields conflicting_evidence | Days 3–4, 6 |
| M10 | Research exists but no relevant signal | no_relevant_signal with explanation; no generic fallback email | Day 4, 6 |
| M11 | Loading, failures and insufficient-evidence UI | Empty/loading/queued/running/error/abstention states and actionable explanations | Days 2–6 |
| M12 | Requested technology direction | Next.js/TS/Tailwind/shadcn; FastAPI/Python; LangGraph; OpenAI; public search; Pydantic; PostgreSQL/SQLAlchemy; SSE | Days 1–6 |
| M13 | Premium enterprise UI | Responsive dashboard/form/detail; keyboard usable controls, readable sources and editor | Days 2, 5–6 |
| M14 | Maximum five-minute demo: happy path + realistic edge case | Recording ≤5:00 shows real execution, evidence, review, history and live abstention; disclose any recorded prior run | Day 7 |
| M15 | Permanent design and consistency audit before development | Five planning documents; workflow/contracts/entities/configuration and feasibility covered | This milestone |
| P01 | Safe public demo operations | Access session, per-session ownership, quotas, bounded retries; secrets backend-only | Days 1, 6 |
| P02 | Repeatable engineering checks | Deterministic fixtures explicitly labelled test-only; live smoke test separately | Days 4–6 |

## Input acceptance
Required: prospect_name, company_name, designation, product_service, value_proposition. Optional: company_website. Trim whitespace; reject empty required fields. Proposed length limits: names/role 200 characters, product 500, value proposition 2,000, website 2,048. Website accepts only HTTP(S) public hosts; no arbitrary server-side fetch is necessary in MVP. Validation errors identify fields without starting paid work.

## Acceptance caveats
A source URL and an LLM assertion alone do not verify a claim. Require a source-backed passage available through the research response, specific identity matching, dates where material and semantic support review. “Verified” means supported by retained public evidence, not independent proof of truth. Unknown dates remain unknown. A failure of the provider is a failed run, never an insufficient-information result.

## Final planning audit
All M01–M15 have workflow/architecture coverage and scheduled implementation or current documentation evidence. Every edge case has a no-draft terminal outcome. Approval is version-specific and has no delivery side effect. Public APIs have ownership and spending controls. Durable jobs, event replay, restart handling and database migrations are included. Proposed enhancements are marked P or explicitly described as proposed. Implementation acceptance remains untested until development; this table is a coverage audit, not a claim of a built system.

Current user-directed identity acceptance: distinguish person identity, company association, title matching and currentness. Undated biographies cannot prove present employment. Unknown currentness alone must not block evaluation of independently verified events; drafting still requires fresh, relevant evidence and neutral wording that excludes unverified employment/role assertions. This is an implementation policy requested after the initial planning brief, not an additional Zamp requirement.

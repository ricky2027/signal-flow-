# Satya Nadella research investigation — 2026-11-26

Superseded by [PIPELINE_FIX_REPORT.md](PIPELINE_FIX_REPORT.md): the user subsequently supplied the actual persisted export, enabling the source-ID and evidence-loss investigation. This document records the earlier investigation only.

## Scope and access limitation

The user reports `insufficient_information` after validation, research, evidence verification and evaluation, with zero displayed signals. The actual persisted Satya run could **not** be inspected from this tool environment: the configured Neon connection raises OperationalError caused by DNS resolution failure. Evidence: `audit/research/live-inspection.json`. No specific source URL, extracted fact, source date, provider response, score or rejection reason from that live run has been verified here. There is no claim of live research success.

A read-only exporter is provided below. The requested export remains necessary to finish the run-specific investigation and decide whether its abstention was justified. The application source, LangGraph transitions, worker transactions, evidence/signal persistence, response schemas, frontend mapping and regression tests were inspected independently of that missing live evidence.

## What the reported outcome means in this implementation

`evaluate` first checks qualified identity/evidence. It returns `insufficient_information` before asking OpenAI for candidates if identity confidence is not high or there is no eligible supported identity claim. A material identity conflict instead returns `conflicting_evidence`. The old wrapper emitted `stage.completed` even on this early return, and stored an empty signals artifact. Consequently the UI's generic “No signals evaluated” placeholder was shown despite a completed evaluation node. Completion meant the gate ran; it did not mean candidates were generated/scored or evidence was sufficient.

The graph's conditional transition to END skips drafting and quality checks when an abstention outcome is present. This behavior is intentional. A low score/date/source-quality/offer-fit rejection after candidate generation instead produces `no_relevant_signal`; the reported outcome is not evidence that the relevance threshold was too strict.

Which identity check failed, whether source retrieval succeeded, and whether OpenAI retries/timeouts occurred in the specific live run remain unverified. Original evidence rejection details were not retained by the old implementation. An old run cannot acquire new historical evidence just by reopening it.

## Genuine issues fixed

1. **Follow-up page starvation:** merging old pages first then slicing to max_sources could discard every newly retrieved follow-up page when the first pass filled the limit, including with unavailable pages. Follow-up selection now prioritizes usable pages, retained supported identity sources and fresh follow-up URLs within the same configured cap. A failed re-fetch cannot erase previously retrieved text.
2. **Missing verification audit:** source filtering silently dropped URLs/passages/duplicates and invalidated claims without recording why. Each attempt now persists source decisions, deterministic source-quality weights, claim eligibility decisions, identity gate reasons and the bounded follow-up decision. HTTP status errors, DNS/TLS errors and retrieval timeouts are classified without logging exception bodies. Extraction instructions explicitly require one contiguous verbatim excerpt and claims entailed by the retained passage; substring/word-limit checks remain enforced.
3. **Unexplained signal gate:** persist explicit `blocked` versus `evaluated` state, gate reasons, candidate/eligible counts and selected signal ID. Gate reasons come from the same policy used by ranking. Nodes still abstain before candidate generation when identity/evidence is insufficient. Empty retrieval is handled deterministically without asking an LLM to extract from zero pages.
4. **Misleading frontend completion/empty states:** the API exposes optional signal evaluation and research diagnostics. UI displays blocked scoring and skipped downstream stages, including compatible wording for historical abstentions, rather than promising forthcoming scores on a terminal run. The evidence panel shows recorded retrieval failures and verification decisions using existing cards. API guards validate the added structures, and TypeScript contracts/OpenAPI were regenerated.

No scoring threshold, required identity confidence, credibility requirement, freshness limit, quote verification or draft quality gate was lowered. No new sources, candidates or drafts were inserted into the real database. No schema migration is required: new diagnostics use the existing artifacts table. Old API records remain compatible; missing diagnostics are not fabricated.

## Regression evidence

| Check | Result |
| --- | --- |
| Backend suite | **47 passed, 1 skipped** (real PostgreSQL), 17 dependency deprecation warnings |
| Frontend unit/component display | **9 passed** |
| Frontend security regression | **3 passed** |
| Next proxy / real FastAPI ASGI integration | **3 passed** |
| DOM / real FastAPI ASGI integration | **1 passed** |
| TypeScript | PASS |
| Production build | PASS in an isolated temporary copy, leaving the running frontend's .next untouched |
| Actual persisted Satya run | BLOCKED by Neon DNS; export requested |
| Native browser and successful live provider chain | NOT VERIFIED in this investigation |

Backend regressions cover existing happy path, insufficient/conflicting/stale/irrelevant evidence and quality failure, plus follow-up recovery at the source cap, preservation after failed re-fetch, unavailable-page abstention, source rejection reasons, scored signal relational/API persistence and validated draft references. The exporter is tested to leave queued jobs untouched and exclude session token hashes. Frontend regressions check historical/new blocked scoring, skipped writing/quality, selected signal scores and claim mapping, and displayed retrieval/rejection diagnostics.

All successful research cases above use **explicit synthetic provider/retrieval fixtures** in isolated databases. They prove regression behavior, not that OpenAI/Neon/public sources succeeded live. Logs are under `audit/research/`.

## Finish the live investigation without interrupting services

In the ordinary terminal that can reach Neon:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.inspect_run > /tmp/signalflow-run-audit.json
```

Default selection is the latest Satya Nadella run. If several exist, select the affected run explicitly:

```sh
uv run python -m app.inspect_run --run-id YOUR_AFFECTED_RUN_UUID > /tmp/signalflow-run-audit.json
```

Share that JSON to finish diagnosis. The command uses a PostgreSQL read-only transaction, does not execute/retry/claim jobs, and excludes login sessions, tokens, lease-owner tokens and configured credentials. It includes run detail, research/retrieval/preliminary/final evidence artifacts, source URLs/dates/passages/claims, scored signals, events, job status and provider attempt metadata. It also replays deterministic gates/scoring on saved facts/candidates as of the original run date, without synthesizing missing candidates. Older runs may not contain rejection diagnostics that were never recorded.

The export can distinguish blocked public-page retrieval, discarded exact passages, low/unknown identity confidence, unsupported identity claims, provider failures and genuine relevant-signal absence. Do not provide .env or raw authentication headers.

## Services to reload, when ready

No service was stopped or restarted during this investigation. Let active jobs finish before restarting the worker; interrupting a leased job can mark it failed after lease expiry.

**Worker: restart required** to load retrieval, agent and event changes. Stop its existing terminal process with Ctrl-C after jobs finish, then:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.worker
```

**FastAPI: restart required** to expose the new optional diagnostics and response contract, unless it already runs with reload. Stop/restart its existing process, without launching a duplicate listener:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

**Frontend:** `npm run dev` should pick up the source changes; refresh the browser. No manual restart is normally required. If it fails to reload, restart only its terminal with `cd /Users/ridhhingrover/Desktop/signalflow/frontend && npm run dev`. A frontend running a production build instead needs a normal rebuild/restart after stopping that instance; the isolated verification build did not change its deployed build output.

After the worker and API have loaded the fixes, open http://localhost:3000/research/new and submit the same prospect, designation, company and original offer/value proposition. This creates a new real run and preserves the original abstention. The failed-run Retry endpoint does not apply to an insufficient-information outcome. Compare source retrieval, verification decisions, signal gate/candidate scores and any evidence-backed draft in the new run. Do not treat the source-cap fix as proof that the original run should have drafted.

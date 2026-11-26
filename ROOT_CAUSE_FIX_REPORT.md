# Root-cause fix: identity/company verification no longer suppressed by unknown role currentness

## Symptom
`current_identity_not_verified` / "Insufficient evidence" abstention with zero signals and
zero outreach, even when credible primary sources corroborate the prospect's identity and
company association (e.g. Pete Hamilton, VP & MD APAC, KellyOCG).

## What was already correct (not the bug)
The deterministic policy layer (`app/policy.py`) already keeps the three checks independent
and already allows signal evaluation on verified company evidence while role currentness is
unknown. Proven two ways:
- Existing passing test `test_undated_biography_verifies_identity_but_never_current_employment`.
- Direct replay of the frozen real Pete evidence through `evidence_gate`: with a faithful
  review the gate returns `(None, [])` and `role_currentness` stays `unverified`.

Previous iterations kept editing this (already-working) policy layer, which is why the
abstention never moved.

## Actual root cause (`app/qualification.py`, `review_evidence`)
Prospect-identity and company-association verification were gated on a **single holistic LLM
confidence scalar** being affirmatively `'high'`:

```python
person_verified  = bool(core) and review.identity_confidence == 'high' and not conflict
company_verified = person_verified and review.company_association_confidence == 'high'
```

One evidence-review call emits identity, company-association and current-role verdicts
together. A conservative reviewer that cannot establish *current* role collapses the identity
and company scalars to `'unknown'` — even though `core` (a supported, entity-matched,
reviewer-designated person+company identity claim backed by a **primary** source) is present.
Requiring `== 'high'` let role-currentness uncertainty suppress an otherwise fully corroborated
identity, so the gate blocked before signal evaluation ever ran.

## The fix
Treat structured primary-source corroboration (`core`) as authoritative, and use the holistic
scalar only as an explicit **veto**:

```python
person_verified  = bool(core) and review.identity_confidence != 'low' and not conflict
company_verified = person_verified and review.company_association_confidence != 'low'
```

- `'high'`  → verified (unchanged).
- `'low'`   → genuine doubt/conflict about the person or employer → **still blocks** (unchanged).
- `'unknown'` → abstention; defer to primary-source evidence instead of suppressing it (**fixed**).

The review prompt now also states explicitly that `'low'` means contradicting person/employer
evidence and that missing current-employment or dates is `'unknown'`, never `'low'`.

Thresholds are **not** weakened: identity still requires a supported, entity-matched, primary
-source, reviewer-designated identity claim and no material conflict. Role currentness remains
a fully independent downstream check (`dated_primary`, `verified_role_claim_ids`), and
unverified role claims are still excluded from scoring and outreach.

## Tests
- Backend: **111 passed, 1 skipped** (was 107/1).
- New regressions in `tests/test_independent_identity.py`:
  - `test_abstaining_holistic_confidence_does_not_suppress_primary_corroborated_identity`
    — reviewer abstains (`unknown`): identity+company verified, currentness unverified, gate opens.
  - `test_frozen_pete_evidence_opens_gate_when_reviewer_abstains` (parametrized `unknown`/`high`)
    — the actual frozen KellyOCG evidence now opens the gate.
  - Existing `..._never_override_failed_core_identity` still blocks on active `low`/conflict.
- Frontend: typecheck pass; unit 13, dom 1, integration 3, security 3 pass; production build OK.
  The independent-checks panel already renders all four verdicts and the
  "current employment unverified → company events only" disclosure
  (`test: identity, association, title and currentness display independently`).

## Fresh live run (completed — new code)
A real end-to-end run was executed **in-process with the patched code** against live OpenAI
web-search + extraction/review (the shared worker was not disturbed; DB not written).
Input: `audit/independent-identity/live-input.json`. Result:
`audit/independent-identity/live-inproc-result.json`.

| Field | Value |
| --- | --- |
| prospect_identity | **verified** |
| company_association | **verified** |
| title_match | **equivalent** |
| role_currentness | **unverified** (undated primary pages) |
| evaluation_state | **evaluated** (gate opened; was previously blocked) |
| relevance_basis | **verified_company_context** |
| outcome | `no_relevant_signal` |

The run retrieved 5 primary sources and 6 supported claims. It proceeded through signal
evaluation on verified company context and abstained at `no_relevant_signal` because **no
recent dated business event** was found to write about — an honest outcome, not an identity
failure. No signal or date was fabricated.

## Remaining blockers / notes
- **The user's running worker still runs the pre-fix code.** Only `app/qualification.py` changed
  and the HTTP/API/frontend contracts are unchanged, so **only the worker needs restarting** to
  deploy. Restarting it was declined to the assistant as a destructive action; the user should run:
  `cd backend && uv run python -m app.worker` (after stopping the old one).
- `no_relevant_signal` for Pete reflects a genuine absence of recent dated business events in the
  retrieved sources, not a verification defect. Surfacing more recent dated employment/business
  events is a retrieval-quality matter (`research_guidance.employment_currentness` follow-up is
  already wired and tested) rather than a gate defect.

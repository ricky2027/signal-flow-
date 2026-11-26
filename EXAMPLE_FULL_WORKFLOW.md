# Example that completes the whole workflow (identity → signals → draft)

## What makes a run reach a draft
The platform only writes outreach when it finds a **recent (≤180 days), dated, substantive
business event** that is **relevant to your offer**. So a full-workflow example needs both:
1. A prospect at a company with **recent dated news** published as individual press-release /
   article pages (not just an undated leadership bio), and
2. An **offer whose relevance to that event is obvious** (so `role_relevance` and `offer_fit`
   score ≥ 2 and the signal clears the 70-point threshold).

A famous exec whose company only has undated leadership pages (e.g. Pete Hamilton / KellyOCG)
verifies identity but correctly abstains at `no_relevant_signal` — there is no dated event to
write about.

## Verified example (reached a generated draft in a live run)

| Field | Value |
| --- | --- |
| Prospect name | `Andy Jassy` |
| Company name | `Amazon` |
| Designation | `President and Chief Executive Officer` |
| Company website | `https://www.aboutamazon.com/` |
| Product / service | `Recruitment process outsourcing and high-volume staffing services for enterprises scaling their workforce.` |

**Value proposition**
```
We help large employers that are expanding, opening new facilities or hiring at scale to fill
roles faster and cheaper through managed recruitment, contingent staffing and workforce planning.
Recent hiring drives, new warehouse or office openings and geographic expansion are strong signals
of immediate staffing demand.
```

### What a successful live run produced
- Prospect identity **verified**, company association **verified**, title **equivalent**.
- Retrieved specific dated Amazon press-release pages (e.g. `press.aboutamazon.com/.../2026/9/amazon-to-create-300-high-paying-jobs-...-greenwood-indiana`).
- Two **eligible** signals scored **94.75** and **84.75**:
  - "Amazon is creating 300 high-paying jobs at a new advanced manufacturing facility in Greenwood, Indiana."
  - "Amazon's $100M+ investment will create skilled manufacturing jobs."
- Generated outreach draft:
  > **Subject:** Supporting Amazon's Greenwood Facility Job Creation with Scalable Recruitment Solutions
  > **Body:** Amazon is creating 300 high-paying jobs at a new advanced manufacturing facility in
  > Greenwood, Indiana, marking a significant workforce expansion opportunity. [cited] Our recruitment
  > process outsourcing and high-volume staffing solutions are designed for enterprises scaling up quickly…

## Status (confirmed end-to-end)
A full run through the real worker now completes to a reviewable draft. Confirmed run
(`d68249b0`, attempt 2): status `awaiting_review`, 2 signals, signal scored **94.75**
("Amazon announced a $100M investment in a new advanced manufacturing facility in Greenwood,
Indiana"), and a grounding-audit-passing draft. ~336s, no timeout.

### What was fixed to get here
- **Auditor findings-contract bug (the real blocker):** the grounding auditor was putting its
  running commentary — including affirmations like "this is supported" — into the `findings`
  list, and the code rejected the draft on *any* finding. Now `findings` holds only real defects,
  and pass/fail keys off the auditor's `valid` verdict plus the deterministic reference check.
- **Writer** presents the offer generically and never implies the prospect's current role.
- **Signal selection** prefers concrete hiring/expansion/facility events over weakly-relevant
  earnings/governance news (`offer_fit` directness).

## Honest caveat — expect to re-run
Reaching a draft still depends on **that run's web search surfacing a recent dated
hiring/expansion event**. The web search returns different pages each run, so a given run may
correctly abstain at `no_relevant_signal` (or `insufficient_information` if identity pages don't
surface). Observed rate: roughly **1 in 2–3 runs** of an Amazon-type prospect produces a draft;
the others abstain. These abstentions are *by design* — the platform refuses to fabricate a
signal — not errors. **Re-run the same input a couple of times** and it lands a full draft.
Timeouts are resolved: runs finish in ~230–340s, under the 540s cap.
- **Final draft audit:** when a signal is found, the generated draft still has to pass a grounding
  audit; one run failed it (`draft_grounding_failed`) on an uncited factual clause. Hardening the
  writer so a found signal reliably yields a reviewable draft is a worthwhile follow-up.
- **Run timeout:** two-pass runs (identity pass + event pass) can exceed the 180s `run_timeout`,
  which shows as a failed run in the UI. Raise `run_timeout_seconds` (max 600) in `backend/.env`
  and restart the worker to run these comfortably.

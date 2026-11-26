# SIGNALFLOW — Project brief

## Assignment and scope
This plan is based exclusively on the supplied Zamp PS-3 brief; no additional assessment rules are assumed. Deliver a publicly accessible application and a screen recording of at most five minutes within one week. This planning milestone creates documents only; development starts after user review.

## Operational problem
SDRs with hundreds of prospects face roughly 20 minutes of manual research per prospect (assignment estimate, not a measured baseline). Generic outreach is the result. Search alone does not solve this: a company event must connect credibly to a specific role and the seller's offer. A plausible business implication must never masquerade as a sourced fact.

## Product outcome
SIGNALFLOW turns a single prospect and offer into an evidence-backed, editable email for human review. Its core unit is a persistent research run: inputs → public research → evidence qualification → ranked signals → draft → review decision. A successful abstention is a useful outcome when evidence is weak. Approval records a decision; it never sends email.

## Users and boundaries
Primary user: an SDR researching one prospect at a time. Reviewer: the same SDR in the one-week MVP. No email address is required. No outbound mail provider, automated sending, CRM integration, bulk campaign system, authenticated LinkedIn scraping or invented prospect activity is included.

## Mandatory versus proposed
Mandatory means explicitly requested in the supplied brief: genuine research; role and offer relevance; factual grounding; three edge cases; live stages; dashboard/history; editable drafts; approve/reject/regenerate; persistent storage; public deployment; specified stack; five-minute demonstration. REQUIREMENTS.md provides the acceptance map.

Proposed implementation choices, not extra Zamp requirements: OpenAI Responses web search, a PostgreSQL job queue, source quality gates and scoring thresholds, a shared demo access session, operating budgets, and the visual direction below. Defer multi-user organizations, CRM sync, enrichment vendors, embeddings, bulk import and analytics.

## Experience and success
A quiet enterprise visual language: neutral surfaces, restrained indigo accent, clear typography, accessible contrast, sparse status colors. Dashboard → new research → run detail with live timeline, evidence, signal rationale and editor. Never use decorative progress percentages. Show timestamps, source dates, warnings and meaningful recovery actions.

Measure observed time to review-ready draft, proportion of supported email claims, correct abstention on fixtures, and completion/failure rates. Proposed demo targets: a run within 180 seconds, every generated factual email claim linked to evidence, zero sending paths. These are engineering targets, not promised sales outcomes or Zamp thresholds.

## Planning assumptions
One builder, seven days, modest demo concurrency, paid API and hosting access available on day one. Public information may be sparse or blocked. Public deployment can require a disclosed demo access code to create runs; the landing page remains public. No real credentials or deployment changes are part of this milestone.

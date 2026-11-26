import asyncio
from datetime import date
import socket
import ssl
from hashlib import sha256
from app import retrieval
from app.schemas import Evidence, ReviewedEvidence, ExcerptSelection, ExtractionInput, ResearchResult
from app.policy import evidence_gate, source_freshness, has_fresh_event
from app.qualification import qualify_pages, review_evidence, source_key, structural_rejections
from app.research_guidance import research_plan, IDENTITY_RULES
from app.excerpts import passage_candidates, selected_evidence


async def research(state, ctx):
    followup = bool(state.get("evidence"))
    prior = ReviewedEvidence.model_validate(state['evidence']) if followup else None
    identity_ok = bool(prior and prior.identity_checks and not evidence_gate(prior)[0])
    fresh_event = bool(prior and has_fresh_event(prior))
    # Follow-up priority: recover identity first; once identity is corroborated,
    # spend the single follow-up on a RECENT DATED EVENT (the actual basis for a
    # signal) before chasing role-currentness, which is decoupled from scoring.
    if not followup:
        focus, followup_focus = "identity_then_events", None
    elif not identity_ok:
        focus, followup_focus = "identity_recovery", "Resolve prospect/company identity or contradictory claims with official sources"
    elif not fresh_event:
        focus, followup_focus = "recent_events", "Find a recent dated company business event (expansion, hiring, facility, funding, results) from a primary/press source; capture its explicit full date"
    else:
        focus, followup_focus = "employment_currentness", "Find recent dated primary evidence of current employment; do not repeat undated biographies as current proof"
    request = {
            **state["input"],
            "today": date.today().isoformat(),
            "research_focus": focus,
            "identity_gaps": evidence_gate(prior)[1] if followup else [],
            "followup_focus": followup_focus,
        }
    ctx.save("research_plan", research_plan(request))
    result = await ctx.provider.search(request)
    result = ResearchResult.model_validate(result).model_dump(mode="json")
    ctx.save("research", result)
    urls = {}
    for url, title in result["urls"].items():
        urls.setdefault(retrieval.canonical_url(url), title)
    semaphore = asyncio.Semaphore(3)

    async def load(url, title):
        async with semaphore:
            try:
                text = await retrieval.fetch(url)
                final_url = retrieval.canonical_url(getattr(text, "url", url))
                return {"url": final_url, "aliases": list(dict.fromkeys([url, final_url])), "title": title, "text": str(text)}
            except Exception as exc:
                return {
                    "url": url,
                    "title": title,
                    "text": None,
                    "error": (
                        exc.code if isinstance(exc, retrieval.RetrievalError)
                        else "dns_error" if isinstance(exc, socket.gaierror)
                        else "tls_error" if isinstance(exc, ssl.SSLError)
                        else "retrieval_timeout" if isinstance(exc, TimeoutError)
                        else "source_unavailable"
                    ),
                }

    pages = await asyncio.gather(
        *(load(u, t) for u, t in list(urls.items())[: ctx.config.max_sources])
    )
    combined = {retrieval.canonical_url(p["url"]): p for p in state.get("pages", [])}
    for page in pages:
        # A failed second fetch must not erase a previously retrieved passage.
        if page["text"] or not combined.get(page["url"], {}).get("text"):
            combined[page["url"]] = page
    previous = state.get("evidence", {})
    identity_sources = {
        sid for claim in previous.get("claims", [])
        if claim["kind"] == "identity" and claim["verification"] == "supported" and claim["entity_match"]
        for sid in claim["source_ids"]
    }
    identity_pages = [s for s in previous.get("sources", []) if s["id"] in identity_sources]
    identity_pages.sort(key=lambda s: s['source_type'] != 'primary')
    # Reserve one corroborating identity page, leaving capacity for new dated
    # employment evidence instead of pinning a full set of undated biographies.
    reserve = min(1, max(0, ctx.config.max_sources - 1))
    identity_urls = {s['url'] for s in identity_pages[:reserve]}
    # Keep the strongest existing fresh event while spending the follow-up on
    # employment. Otherwise a successful currentness search can evict the very
    # company event that independently qualifies for signal evaluation.
    event_ids = {sid for c in previous.get('claims', [])
                 if c['kind'] == 'event' and c['verification'] == 'supported' and c['entity_match']
                 for sid in c['source_ids']}
    if prior and ctx.config.max_sources >= 3:
        event_sources = [s for s in prior.sources if s.id in event_ids and source_freshness(s)[1]]
        event_sources.sort(key=lambda s: (s.source_type != 'primary', source_freshness(s)[0]))
        identity_urls.update(s.url for s in event_sources[:1])
    fresh_urls = {p["url"] for p in pages}
    selected = sorted(combined.values(), key=lambda p: (
        not bool(p["text"]), p["url"] not in identity_urls, p["url"] not in fresh_urls,
    ))[:ctx.config.max_sources]
    ctx.save("retrieval_summary", {
        "phase": "retrieval",
        "followup": followup,
        "sources": [{"url": p["url"], "available": bool(p["text"]), "error": p.get("error")} for p in pages],
        "selected_urls": [p["url"] for p in selected if p["text"]],
    })
    return {
        "research": result,
        "pages": selected,
        "followup": followup,
    }


async def extract(state, ctx):
    pages = [p for p in state["pages"] if p["text"]]
    semaphore = asyncio.Semaphore(3)
    failures = []
    repair_errors = []
    repair_records = []
    repairs_used = set(state.get("extraction_repairs", []))
    cache = dict(state.get("page_extractions", {}))

    async def one_page(page):
        key = page["url"] + "|" + sha256(page["text"].encode()).hexdigest()
        if key in cache:
            cached = Evidence.model_validate(cache[key])
            if not structural_rejections(page, cached):
                return page, cached
            del cache[key]
        async with semaphore:
            try:
                extracted = await ctx.provider.structured(
                    Evidence,
                    """Extract atomic identity AND business-event facts from this ONE retrieved page only.
                    Search narration is not evidence. Return at most one source record for the supplied page URL.
                    Use one contiguous verbatim passage, aim for 35-60 words and NEVER more than 80 words;
                    no ellipses, paraphrases or joined snippets. Omit unrelated boilerplate instead of overlong quotes.
                    Choose the passage most relevant to this prospect and offer. On a leadership/profile page,
                    capture explicit person, company and current role; on a news/press page capture the business
                    event AND, in the SAME passage, its explicit full calendar date (day, month and year) so the
                    date is verifiable in the quote. If the event has no explicit full date in the page text,
                    still record it with null dates rather than inferring one.
                    Set source.id to the supplied page.source_id. All claims must be entailed by that
                    retained passage and reference exactly that source.id.
                    Do not infer a role from user input. Publication date and original event date are different;
                    unknown dates must be null. Do not use a page copyright/footer date as a publication date.
                    Classify primary/reporting/aggregator conservatively and identify syndication origin.
                    An employer's own statement about itself or its executives is first-hand primary material
                    when ownership and authorship are corroborated; a report about another organization is reporting.
                    Hostname alone does not establish authorship or currentness. Organization/unit relationships
                    are context claims, not proof of the named prospect's identity or role.
                    Return empty sources/claims if no attributable evidence exists on the supplied page.
                    Do not omit a source-confirmed role merely because its wording differs from the requested title.""" + IDENTITY_RULES,
                    ExtractionInput(input=state["input"], pages=[{**page, "source_id": source_key(page["url"])}], today=date.today().isoformat()).model_dump(mode="json"),
                )
                reasons = structural_rejections(page, extracted)
                if reasons and key not in repairs_used:
                    repairs_used.add(key)
                    record = {"url": page["url"], "initial_rejections": reasons, "method": "literal_selection_v1"}
                    try:
                        candidates = passage_candidates(page["text"], state["input"])
                        selection = await ctx.provider.structured(
                            ExcerptSelection,
                            """Choose ONE supplied literal passage by its ID and extract only atomic claims
                            fully entailed by that passage. Do not write or edit the quotation. Use the supplied
                            source_id for every claim. Rebuild claims for the chosen passage; do not retain facts
                            whose backing words are absent. passage_id=null with no claims is correct if none
                            supports attributable facts. Organization relationships are context, not person identity.
                            Search narration/user inputs are not evidence. Dates and credibility are not repaired
                            by this selection; all claims undergo independent semantic verification.""" + IDENTITY_RULES,
                            {"input": state["input"], "today": date.today().isoformat(),
                             "url": page["url"], "source_id": source_key(page["url"]),
                             "candidates": candidates,
                             "rejection_reasons": reasons},
                        )
                        extracted = selected_evidence(page, extracted, selection, candidates)
                        record["selected_passage_id"] = selection.passage_id
                    except Exception as exc:
                        record["error"] = "repair_" + type(exc).__name__
                        repair_errors.append({"url": page["url"], "available": True, "error": record["error"]})
                    reasons = structural_rejections(page, extracted)
                    record["final_rejections"] = reasons
                    repair_records.append(record)
                # Cache only structurally valid outputs, including honest empty
                # results. Semantic review always runs separately. Repair is
                # bounded to once per URL/body within this run's existing deadline.
                if not reasons:
                    cache[key] = extracted.model_dump(mode="json")
                return page, extracted
            except Exception as exc:
                # Preserve other pages if one output fails. No exception bodies
                # or provider headers are persisted in diagnostic records.
                failures.append({"url": page["url"], "available": True, "error": "extraction_" + type(exc).__name__})
                return page, None

    results = await asyncio.gather(*(one_page(page) for page in pages))
    if repair_records:
        ctx.save("extraction_repairs", {"attempts": repair_records})
    ctx.save("page_extraction_summary", {"repair_method": "literal_selection_v1", "pages": [
        {"url": page["url"], "input_characters": len(page["text"]),
         "source_count": len(extracted.sources) if extracted else None,
         "identity_claim_count": sum(c.kind == "identity" for c in extracted.claims) if extracted else None,
         "event_claim_count": sum(c.kind == "event" for c in extracted.claims) if extracted else None}
        for page, extracted in results
    ]})
    evidence, source_decisions, claim_decisions = qualify_pages(results)
    if state.get('evidence', {}).get('material_identity_conflict'):
        evidence.material_identity_conflict = True
    if failures or repair_errors:
        ctx.save("extraction_failures", {"phase": "extraction", "sources": failures + repair_errors})
    if pages and len(failures) == len(pages):
        raise RuntimeError("evidence_extraction_failed")
    # Exact quotations are provisional until the semantic review succeeds.
    # Preserve this diagnostic if review fails; it is never final evidence.
    ctx.save("qualification_attempt", evidence.model_dump(mode="json"))
    evidence, review_decisions = await review_evidence(evidence, ctx.provider, state["input"])
    if not pages:
        evidence.warnings.append("no_retrievable_sources")
    outcome, gate_reasons = evidence_gate(evidence)
    needs_followup = (outcome in ("insufficient_information", "conflicting_evidence")
                      or not has_fresh_event(evidence)
                      or evidence.identity_checks.role_currentness.status != 'verified') and not state.get("followup", False)
    ctx.save("evidence_verification", {
        "sources": source_decisions, "claims": claim_decisions + review_decisions,
        "identity_confidence": evidence.identity_confidence,
        "gate_outcome": outcome, "gate_reasons": gate_reasons,
        "followup_requested": needs_followup,
        "identity_checks": evidence.identity_checks.model_dump(mode='json'),
    })
    ctx.save("preliminary_evidence" if needs_followup else "evidence", evidence.model_dump(mode="json"))
    return {"evidence": evidence.model_dump(mode="json"), "needs_followup": needs_followup, "page_extractions": cache, "extraction_repairs": sorted(repairs_used)}

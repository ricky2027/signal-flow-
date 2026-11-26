from app.schemas import Candidates, ReviewedEvidence, RelevanceInput
from app.policy import rank, evidence_gate, relevance_basis, role_claim_ids, verified_role_claim_ids
from app.qualification import review_evidence
from app.reasoning_context import reasoning_context


async def evaluate(state, ctx):
    evidence = ReviewedEvidence.model_validate(state["evidence"])
    if evidence.identity_checks is None:
        evidence, _ = await review_evidence(evidence, ctx.provider, state["input"])
        ctx.save("identity_checks", evidence.identity_checks.model_dump(mode="json"))
    updated = {"evidence": evidence.model_dump(mode="json")}
    precondition, gate_reasons = evidence_gate(evidence)
    if precondition in ("insufficient_information", "conflicting_evidence"):
        ctx.save("signals", {"signals": []})
        ctx.save("signal_evaluation", {
            "state": "blocked", "reason": precondition,
            "gate_reasons": gate_reasons, "candidate_count": 0,
            "eligible_count": 0, "selected_signal_id": None,
        })
        return {**updated, "signals": [], "outcome": precondition, "outcome_reason": precondition, "evaluation_state": "blocked"}
    subject, context = reasoning_context(state["input"], evidence)
    result = await ctx.provider.structured(
        Candidates,
        """Propose up to 8 business event signals with claim IDs, separately labelled inferred implications, role relevance and offer fit.
        role_relevance is the legacy field for relevance to VERIFIED PROSPECT CONTEXT: 0 none,1 indirect,2 clear,3 direct.
        offer_fit (0-3) measures how DIRECTLY and non-speculatively the event implies a need the offer addresses:
        3 = direct and concrete (e.g. a hiring drive, new-facility opening, geographic expansion or workforce change
        for a recruitment/staffing offer); 2 = clear; 0-1 = linking the event to the offer requires an assumption,
        generalization or speculation (e.g. an earnings, results, financing or governance event with no concrete
        workforce/operational implication for this offer). When multiple events exist, prefer concrete operational
        events (hiring, expansion, facilities, workforce) over purely financial or governance news.
        When relevance_basis=verified_company_context, judge relevance only through verified person/company
        association and independent business events. Do NOT assume current employment, a title, role duties
        or decision authority from user input, seller targeting, memory or missing evidence. Company association
        is source-corroborated, not a statement of current employment. When verified_role, only supplied
        verified role claims may inform that dimension. Explain the actual basis. No invented pain or outcomes.
        Include disputed candidate claims so deterministic routing can explain conflicts. Do not create a candidate from identity alone.""",
        RelevanceInput(input=subject, evidence=context).model_dump(mode="json"),
    )
    rows, outcome = rank(evidence, result.signals)
    ctx.save("signals", {"signals": rows})
    reason = (
        "outdated_only"
        if outcome == "no_relevant_signal"
        and rows
        and all("outdated" in r["rejection_reasons"] for r in rows)
        else outcome
    )
    ctx.save("signal_evaluation", {
        "state": "evaluated", "reason": reason, "gate_reasons": [],
        "candidate_count": len(rows), "eligible_count": sum(r["eligible"] for r in rows),
        "selected_signal_id": next((r["id"] for r in rows if r["selected"]), None),
        "relevance_basis": relevance_basis(evidence),
        "excluded_role_claim_ids": sorted(role_claim_ids(evidence) - verified_role_claim_ids(evidence)),
    })
    return {**updated, "signals": rows, "outcome": outcome, "outcome_reason": reason, "evaluation_state": "evaluated"}

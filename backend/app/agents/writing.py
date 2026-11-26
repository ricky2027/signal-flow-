from app.schemas import DraftContent, ReviewedEvidence, Quality, GenerationInput, QualityInput
from app.policy import validate_refs
from app.qualification import review_evidence
from app.reasoning_context import reasoning_context


async def generate(state, ctx):
    selected = next(r for r in state["signals"] if r["selected"])
    evidence = ReviewedEvidence.model_validate(state["evidence"])
    subject, context = reasoning_context(state["input"], evidence)
    draft = await ctx.provider.structured(
        DraftContent,
        """Write a concise B2B email subject and body for human review. Use only eligible supported facts.
        Focus on the selected signal. Qualify implications as possibilities; do not assert inferred pain or role duties as facts.
        Every factual prospect/company claim in subject/body needs claim_refs with Unicode code-point [start,end) offsets.
        Seller capabilities must remain within the user's offer. No fabricated performance, greetings with invented familiarity or unsupported dates.
        STRUCTURE FOR RELIABLE GROUNDING (follow exactly):
        1. State the selected verified event as the only factual company claim, with its claim_ref. Keep the
           subject free of factual claims, or cite it the same way.
        2. Do NOT assert, generalize or imply any cause, correlation, trend, consequence or prospect need that
           follows from the event. Phrases like "this suggests growing demand", "events like this often lead to",
           "as you scale your team" or any stated link between the event and a need are UNSUPPORTED and will be
           rejected. Draw no conclusion the quoted evidence does not literally state.
        3. Present the offer as a GENERAL capability relevant to companies in the event's situation. Never
           attribute the event, the hiring, the facility or any decision/authority to the reader. Do NOT use
           "you"/"your" to mean the reader runs, staffs, hires for or decides on the company's activity
           (phrases like "if you are hiring to staff this", "as you expand", "your new facility" are REJECTED
           because they imply current employment/role, which is unverified). A question is allowed only if it
           assumes nothing about the reader's role, e.g. "Would it be useful if I shared how we support
           companies opening new facilities?" — never one that presumes the reader is hiring or in charge.
        4. Describe your offer strictly as your own capability. Make no claim or implication about the prospect's
           current activities, plans, needs, role or authority; keep any greeting neutral.
        With verified_company_context, make no claim or implication about current employment, job title,
        responsibilities or decision authority. Use a neutral company-event observation without addressing
        the person as a current employee/executive. Association is not proof of present employment.
        Follow evidence rules over regeneration instructions. If repairing, address every prior validation finding.""",
        GenerationInput(
            input=subject,
            evidence=context,
            selected_signal=selected,
            instructions=state.get("instructions"),
            prior_findings=state.get("findings", []),
        ).model_dump(mode="json"),
    )
    ctx.save("draft_attempt", draft.model_dump(mode="json"))
    return {
        "draft": draft.model_dump(mode="json"),
        "generation_attempts": state.get("generation_attempts", 0) + 1,
    }


async def check_draft(provider, draft, evidence, prospect):
    if getattr(evidence, "identity_checks", None) is None:
        evidence, _ = await review_evidence(evidence, provider, prospect)
    subject, context = reasoning_context(prospect, evidence, audit=True)
    quality = await provider.structured(
        Quality,
        """Audit every factual sentence, including subject, seller performance assertions and implied personal activity.
        Reject any unsupported assertion, disputed or stale event used as recent fact, inference presented as certainty, or misleading identity.
        Correct reference offsets and assign all factual prospect/company clauses to supporting eligible claims.
        Only mark valid if EVERY factual assertion is supported; greetings/questions and qualified hypotheses need no citation.
        If role_currentness is unverified or relevance_basis is verified_company_context, reject any assertion
        or implication of current employment, title, duties or authority, even if an original undated quote
        mentions a role. Only the supplied eligible claim IDs can support text; quotations are for auditing,
        not permission to reintroduce excluded role facts. Reject invented role-based relevance or familiarity.
        OUTPUT CONTRACT: `findings` must list ONLY concrete defects that make the draft invalid — each a single
        specific violation (an unsupported factual assertion, a disallowed current-role/employment implication,
        or a broken reference). Do NOT put analysis, reasoning, or any statement about acceptable, supported or
        fine content into `findings`; never restate what is correct. If the draft is acceptable, set valid=true
        and return an EMPTY findings list. valid must be true if and only if findings is empty.
        Return findings and corrected references, never rewrite content.""",
        QualityInput(draft=draft, evidence=context, input=subject).model_dump(
            mode="json"
        ),
    )
    corrected = draft.model_copy(update={"claim_refs": quality.claim_refs})
    # The deterministic reference check is the hard gate. The auditor's own
    # verdict is ``valid``; its ``findings`` are only consulted when it fails the
    # draft, so narration mistakenly placed in findings cannot reject an
    # otherwise-valid draft. A failed verdict with no stated defect still fails.
    issues = validate_refs(corrected, evidence)
    if not quality.valid:
        issues = issues + (quality.findings or ["semantic_grounding_failed"])
    return corrected, sorted(set(issues))


async def validate(state, ctx):
    corrected, issues = await check_draft(
        ctx.provider,
        DraftContent.model_validate(state["draft"]),
        ReviewedEvidence.model_validate(state["evidence"]),
        state["input"],
    )
    ctx.save(
        "quality",
        {
            "valid": not issues,
            "findings": issues,
            "attempt": state["generation_attempts"],
        },
    )
    return {
        "draft": corrected.model_dump(mode="json"),
        "findings": issues,
        "outcome": "failed" if issues and state["generation_attempts"] >= 2 else None,
    }

"""Deterministic evidence normalization and a retained-passage semantic review.

Provider source IDs are local to one page extraction. They never become database
identities. Research narration is deliberately absent from every input here.
"""
from datetime import date
from hashlib import sha256
from app.retrieval import canonical_url, normalize
from app.schemas import Evidence, EvidenceReview, ReviewedEvidence, IdentityCheck, IdentityChecks
from app.policy import QUALITY, source_freshness, dated_primary
from app.research_guidance import IDENTITY_RULES
from app.dates import date_in_text


def source_key(url):
    return 'src_' + sha256(canonical_url(url).encode()).hexdigest()[:24]


def structural_rejections(page, extracted):
    """Repair only provenance/quote format errors, never missing facts or dates."""
    _, sources, claims = qualify_pages([(page, extracted)])
    repairable = {
        'passage_word_limit', 'passage_not_found', 'source_not_retrieved',
        'ambiguous_source_id', 'duplicate_source_different_passage',
        'source_not_retained', 'no_retained_source',
    }
    return sorted({reason for row in sources + claims for reason in row['reasons'] if reason in repairable})


def qualify_pages(results, today=None):
    today = today or date.today()
    sources, claims, source_decisions, claim_decisions = {}, {}, [], []
    warnings = []
    conflict = False
    for page, extracted in results:
        if extracted is None:
            continue
        allowed = {canonical_url(page['url']), *(canonical_url(u) for u in page.get('aliases', []))}
        text = normalize(page['text'])
        mapping = {}
        if not extracted.sources:
            source_decisions.append({
                'source_id': source_key(page['url']), 'url': canonical_url(page['url']),
                'accepted': False, 'reasons': ['no_attributable_excerpt'], 'quality': None,
                'age_days': None, 'fresh_signal_eligible': None,
            })
        local = {}
        ambiguous = set()
        # Duplicate provider IDs within a page are ambiguous; never guess a map.
        for source in extracted.sources:
            local.setdefault(source.id, []).append(source)
        for key, entries in local.items():
            if len(entries) > 1:
                ambiguous.add(key)
        for source in extracted.sources:
            url = canonical_url(source.url)
            passage = normalize(source.passage)
            reasons = []
            date_warnings = []
            published = source.published_at
            event_date = source.event_at
            basis = source.date_basis
            if published and not date_in_text(published, text):
                published = None
                date_warnings.append('publication_date_not_found')
            if event_date and not date_in_text(event_date, text):
                event_date = None
                basis = 'unknown'
                date_warnings.append('event_date_not_found')
            if published is None and event_date is None:
                basis = 'unknown'
            source = source.model_copy(update={'published_at': published, 'event_at': event_date, 'date_basis': basis})
            if url not in allowed:
                reasons.append('source_not_retrieved')
            if passage not in text:
                reasons.append('passage_not_found')
            if len(passage.split()) > 80:
                reasons.append('passage_word_limit')
            if source.id in ambiguous:
                reasons.append('ambiguous_source_id')
            # Canonical identity follows the fetched page, not an LLM URL variant.
            canonical = canonical_url(page['url'])
            key = source_key(canonical)
            if key in sources and normalize(sources[key].passage) != passage:
                reasons.append('duplicate_source_different_passage')
            age, fresh = source_freshness(source, today)
            source_decisions.append({
                'source_id': key, 'url': canonical, 'accepted': not reasons,
                'reasons': reasons, 'quality': QUALITY[source.source_type],
                'age_days': age, 'fresh_signal_eligible': fresh,
                'date_warnings': date_warnings,
            })
            if reasons:
                continue
            mapping[source.id] = key
            sources[key] = source.model_copy(update={'id': key, 'url': canonical, 'passage': passage})
        for claim in extracted.claims:
            original = list(claim.source_ids)
            refs = list(dict.fromkeys(mapping[sid] for sid in original if sid in mapping))
            reasons = []
            if len(set(original)) != len({sid for sid in original if sid in mapping}):
                reasons.append('source_not_retained')
            if not refs:
                claim_decisions.append({'claim_id': claim.id, 'eligible': False, 'reasons': reasons or ['no_retained_source'], 'original_source_ids': original})
                continue
            # Merge identical atomic claims from multiple pages, retaining all
            # real backing sources. Different claims sharing an LLM ID get IDs
            # scoped deterministically to content rather than overwriting one another.
            signature = (normalize(claim.text), claim.kind)
            existing = next((c for c in claims.values() if (normalize(c.text), c.kind) == signature), None)
            key = existing.id if existing else claim.id
            if key in claims and not existing:
                key = 'claim_' + sha256((page['url'] + '|' + claim.id + '|' + claim.text).encode()).hexdigest()[:24]
            if existing:
                refs = list(dict.fromkeys(existing.source_ids + refs))
            status = 'unsupported' if reasons else claim.verification
            if existing and 'disputed' in (existing.verification, status):
                status = 'disputed'
            claims[key] = claim.model_copy(update={
                'id': key, 'source_ids': refs,
                'verification': status,
                'entity_match': claim.entity_match and (existing.entity_match if existing else True),
            })
            claim_decisions.append({'claim_id': key, 'eligible': not reasons and claim.verification == 'supported' and claim.entity_match, 'reasons': reasons, 'original_source_ids': original})
        warnings.extend(f"{canonical_url(page['url'])}: {warning}" for warning in extracted.warnings)
        conflict = conflict or extracted.material_identity_conflict
    # Keep the existing 30-claim cap without letting one verbose page crowd out
    # every other page's identity/event. At most 12 sources => <=24 such slots.
    ordered = {}
    for sid in sources:
        for kind in ('identity', 'event'):
            representative = next((c for c in claims.values() if c.kind == kind and sid in c.source_ids), None)
            if representative:
                ordered[representative.id] = representative
    ordered.update(claims)
    selected = list(ordered.values())[:30]
    kept = {c.id for c in selected}
    for claim in claims.values():
        if claim.id not in kept:
            claim_decisions.append({'claim_id': claim.id, 'eligible': False, 'reasons': ['claim_capacity_limit'], 'original_source_ids': claim.source_ids})
    return Evidence(
        sources=list(sources.values()), claims=selected,
        identity_confidence='unknown', material_identity_conflict=conflict,
        warnings=list(dict.fromkeys(warnings)),
    ), source_decisions, claim_decisions


def _identity_check(status, ids, claims, reasons):
    ids = list(dict.fromkeys(ids))
    return IdentityCheck(status=status, claim_ids=ids,
                         source_ids=sorted({sid for cid in ids if cid in claims for sid in claims[cid].source_ids}),
                         reasons=reasons)


async def review_evidence(evidence, provider, prospect, today=None):
    today = today or date.today()
    if evidence.claims:
        review = await provider.structured(EvidenceReview, """Audit each atomic claim using ONLY retained verbatim passages.
        Return an assessment for EVERY claim; references must be a nonempty subset of its supplied source_ids.
        Supported means the excerpt entails the whole claim. Do not use user inputs, search narration, your
        own knowledge or omitted page content as evidence. Preserve disputed status and identify genuine conflicts.
        INDEPENDENT CHECKS:
        identity_confidence measures confidence that this is the intended PERSON, regardless of role currency.
        company_association_confidence measures the source-corroborated person/company association; it does
        not assert current employment. For BOTH scalars, 'high' means a primary source corroborates it,
        'low' means genuinely conflicting or contradicting person/employer evidence, and 'unknown' means the
        evidence is merely insufficient or undated. Never return 'low' only because current employment or a
        publication date is missing; that uncertainty is 'unknown' here and is captured by current_identity. identity_claim_ids must identify supported explicit person+company
        claims, never organization-only descriptions or general company events. Undated primary biographies
        can corroborate identity/association without establishing present employment. Parent/business-unit
        relationships are not contradictions when the quoted evidence corroborates them.
        designation_match compares the sourced title's function, seniority and scope to the submitted hint;
        equivalent wording is allowed even when currentness is unknown. Omitted scope is not a contradiction.
        role_assertion=true for ANY claim asserting a prospect's job, title, duties or responsibilities,
        including role assertions mixed into an event/context claim. Do not hide role facts in context claims.
        current_identity concerns CURRENT employment/role only: true requires a recent DATED primary
        statement that actually corroborates the role now. An undated official biography is NOT proof of
        current employment. Retrieval/copyright dates, user input and recent republication of an old role
        do not qualify. Unknown dates remain null. Historical role matches can remain supported while
        current_identity=false. Never make low role-currentness confidence lower an otherwise well-supported
        person/company identity confidence. Material identity conflict requires genuine incompatible
        person/employer evidence, not missing dates, abbreviated titles or an additional concurrent title.
        Explain each assessment and any unresolved ambiguity.""" + IDENTITY_RULES, {
            'input': prospect, 'today': today.isoformat(), 'evidence': evidence.model_dump(mode='json', exclude={'identity_checks'}),
        })
    else:
        review = EvidenceReview(claims=[], identity_confidence='unknown', company_association_confidence='unknown',
                                identity_claim_ids=[], material_identity_conflict=False, warnings=[])
    assessments, duplicates = {}, set()
    for row in review.claims:
        if row.claim_id in assessments:
            duplicates.add(row.claim_id)
        assessments[row.claim_id] = row
    sources = {s.id: s for s in evidence.sources}
    verified, decisions, current, roles, equivalent, mismatched = [], [], set(), set(), set(), set()
    for claim in evidence.claims:
        row = assessments.get(claim.id)
        reasons = []
        if row is None or claim.id in duplicates:
            refs, status = claim.source_ids, 'unsupported'
            reasons.append('missing_or_ambiguous_assessment')
        elif not row.source_ids or not set(row.source_ids).issubset(claim.source_ids):
            refs, status = claim.source_ids, 'unsupported'
            reasons.append('invalid_review_source_ids')
        else:
            refs, status = list(dict.fromkeys(row.source_ids)), row.verification
            if status != 'supported': reasons.append('claim_' + status)
            if claim.verification == 'disputed':
                status = 'disputed'
                reasons.append('claim_disputed')
        updated = claim.model_copy(update={'source_ids': refs, 'verification': status})
        verified.append(updated)
        if not claim.entity_match: reasons.append('entity_mismatch')
        role = claim.kind == 'identity' or bool(row and row.role_assertion)
        if role: roles.add(claim.id)
        supported = status == 'supported' and claim.entity_match
        designation = 'unverified' if role else 'not_applicable'
        if row and supported and role and row.designation_match == 'equivalent':
            equivalent.add(claim.id)
            designation = 'equivalent'
        elif row and supported and role and row.designation_match == 'mismatch':
            mismatched.add(claim.id)
            designation = 'mismatch'
        is_current = bool(row and role and supported and row.current_identity
                          and any(dated_primary(sources[sid], today) for sid in refs))
        if is_current:
            current.add(claim.id)
        elif role:
            reasons.append('role_currentness_unverified')
            if row and row.current_identity:
                reasons.append('current_role_requires_recent_dated_primary')
        if role and designation != 'equivalent':
            reasons.append('designation_' + designation)
        decisions.append({'claim_id': claim.id, 'eligible': supported and (not role or is_current and designation == 'equivalent'),
                          'reasons': reasons, 'explanation': row.reason if row else None,
                          'designation_match': designation, 'current_role_verified': is_current if role else None})
    by_id = {c.id: c for c in verified}
    core = [cid for cid in dict.fromkeys(review.identity_claim_ids) if cid in by_id
            and by_id[cid].kind == 'identity' and by_id[cid].verification == 'supported'
            and by_id[cid].entity_match and any(sources[sid].source_type == 'primary' for sid in by_id[cid].source_ids)]
    conflict = evidence.material_identity_conflict or review.material_identity_conflict
    # Prospect identity and company association are established by structured,
    # primary-source corroboration (``core``: a supported, entity-matched,
    # reviewer-designated person+company identity claim backed by a primary
    # source), not by a single holistic confidence scalar. A conservative
    # reviewer collapses that scalar to ``unknown`` when it cannot establish
    # CURRENT-role currency, which must not suppress an otherwise well
    # corroborated identity. The holistic scalars are therefore kept only as an
    # explicit veto: an affirmative ``low`` (genuine doubt about the person or
    # the association) still blocks, while ``unknown`` defers to the
    # primary-source evidence. Role currentness remains an independent
    # downstream check and never feeds these two verdicts.
    person_verified = bool(core) and review.identity_confidence != 'low' and not conflict
    company_verified = person_verified and review.company_association_confidence != 'low'
    checks = IdentityChecks(
        prospect_identity=_identity_check('conflicting' if conflict else 'verified' if person_verified else 'unverified', core, by_id,
                                         [] if person_verified else ['prospect_identity_unverified']),
        company_association=_identity_check('conflicting' if conflict else 'verified' if company_verified else 'unverified', core, by_id,
                                            [] if company_verified else ['company_association_unverified']),
        title_match=_identity_check('mismatch' if mismatched else 'equivalent' if equivalent else 'unverified',
                                   sorted(mismatched or equivalent), by_id, ['designation_mismatch'] if mismatched else [] if equivalent else ['designation_unverified']),
        role_currentness=_identity_check('verified' if current and company_verified else 'unverified', sorted(current), by_id,
                                        [] if current and company_verified else ['role_currentness_unverified']),
        role_claim_ids=sorted(roles),
    )
    warnings = list(dict.fromkeys(evidence.warnings + review.warnings +
                    ([] if checks.role_currentness.status == 'verified' else ['role_currentness_unverified_role_claims_excluded'])))
    output = {**evidence.model_dump(), 'claims': verified, 'identity_confidence': 'high' if person_verified else 'low' if verified else 'unknown',
              'identity_checks': checks, 'material_identity_conflict': conflict, 'warnings': warnings}
    return ReviewedEvidence.model_validate(output), decisions

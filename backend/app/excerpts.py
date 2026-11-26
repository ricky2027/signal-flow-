"""Short, literal repair candidates. No generated quotations or factual inference."""
import re
from app.retrieval import normalize, canonical_url
from app.schemas import Evidence
from app.qualification import source_key


def passage_candidates(text, prospect, limit=16):
    words = normalize(text).split()
    hints = [str(prospect.get(k) or '').casefold().split() for k in ('prospect_name', 'company_name')]
    rows = []
    for start in range(0, len(words), 30):
        quote = ' '.join(words[start:start + 60])
        if not quote or len(quote) > 1500:
            continue
        tokens = set(re.findall(r'\w+', quote.casefold()))
        score = sum((8 if i == 0 else 2) * sum(token in tokens for token in hint) for i, hint in enumerate(hints))
        rows.append((score, start, {'id': f'p{start}', 'text': quote}))
        if start + 60 >= len(words):
            break
    # Names rank passages for inspection only; they never verify an identity.
    rows.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in rows[:limit]]


def selected_evidence(page, original, selection, candidates):
    if selection.passage_id is None:
        if selection.claims:
            raise ValueError('claims_without_excerpt')
        return Evidence(sources=[], claims=[], identity_confidence='unknown',
                        material_identity_conflict=original.material_identity_conflict,
                        warnings=['no_attributable_excerpt'])
    by_id = {row['id']: row['text'] for row in candidates}
    if selection.passage_id not in by_id:
        raise ValueError('unknown_excerpt_id')
    allowed = {canonical_url(page['url']), *(canonical_url(u) for u in page.get('aliases', []))}
    matching = [s for s in original.sources if canonical_url(s.url) in allowed]
    if len(matching) != 1:
        raise ValueError('ambiguous_excerpt_source')
    # Preserve the original classification/date uncertainty. A format repair
    # cannot upgrade credibility, invent dates or silently create a new source.
    source = matching[0].model_copy(update={
        'id': source_key(page['url']), 'url': canonical_url(page['url']),
        'passage': by_id[selection.passage_id],
    })
    if any(set(c.source_ids) != {source.id} for c in selection.claims):
        raise ValueError('invalid_selected_source_reference')
    return Evidence(sources=[source], claims=selection.claims,
                    identity_confidence='unknown',
                    material_identity_conflict=original.material_identity_conflict,
                    warnings=original.warnings)

"""Search suggestions and identity rules, never evidence or fabricated URLs."""
from urllib.parse import urlsplit
from datetime import date, timedelta


IDENTITY_RULES = """The user-entered designation is an unverified search/comparison hint, not a fact.
Do not require a literal title-string match: abbreviations and expanded titles can describe the same
function, seniority, employer and scope (for example CEO and Chief Executive Officer).
Preserve the source's actual designation in claim text; never rewrite it to agree with the user.
entity_match concerns the person and employer, not literal designation wording. current_identity concerns
the source-confirmed current role; designation_match separately compares it with the user's hint.
Different functions, seniorities, subsidiaries, geographic scopes, former/acting roles or chair versus
executive roles are not automatically equivalent. A corroborated incompatible current role is a mismatch;
missing role evidence is unverified, not a mismatch. Name aliases also require corroboration.
An additional potentially concurrent title does not prove the requested role is false; absence alone
is unverified. Do not infer that a source's role list is exhaustive.
Neither title similarity nor a user assertion can establish person/employer identity without source evidence."""


def research_plan(prospect):
    # Quotes limit accidental query broadening; these are suggestions passed
    # as untrusted data, not claims that the search tool executed these strings.
    def quoted(value):
        return '"' + str(value or '').replace('"', ' ').strip() + '"'

    person = quoted(prospect.get('prospect_name'))
    company = quoted(prospect.get('company_name'))
    base = f'{person} {company}'
    site = urlsplit(prospect.get('company_website') or '').hostname
    cutoff = (date.today() - timedelta(days=180)).isoformat()
    # Recent, dated business events are the basis for a signal. Bias these toward
    # the company's own newsroom/press releases (primary, dated) within the
    # freshness window; these are company-scoped and never name an assumed role.
    event_terms = ('(expansion OR hiring OR "new office" OR facility OR acquisition OR merger OR '
                   'funding OR investment OR partnership OR launch OR "quarterly results" OR '
                   'earnings OR restructuring OR layoffs OR appointed OR opening)')

    def event_queries():
        qs = [
            {'purpose': 'events', 'query': f'{company} {event_terms} after:{cutoff}'},
            {'purpose': 'events', 'query': f'{company} ("press release" OR newsroom OR announced OR news) after:{cutoff}'},
        ]
        if site:
            qs.insert(0, {'purpose': 'events', 'query': f'site:{site} (news OR newsroom OR "press release" OR announcement) after:{cutoff}'})
        return qs

    focus = prospect.get('research_focus')
    if focus == 'employment_currentness':
        dated = f'{base} (appointed OR joined OR "press release" OR quoted) after:{cutoff}'
        queries = [{'purpose': 'current_employment', 'query': dated}]
        if site:
            queries.insert(0, {'purpose': 'current_employment', 'query': f'site:{site} {dated}'})
        return {'focus': 'employment_currentness', 'suggested_queries': queries}
    if focus == 'recent_events':
        # Dedicated follow-up: identity already corroborated, now find a recent
        # dated company event to score against the offer.
        return {'focus': 'recent_events', 'suggested_queries': event_queries()}
    queries = [
        {'purpose': 'identity', 'query': f'{base} (leadership OR team OR biography)'},
        {'purpose': 'identity', 'query': f'{base} (profile OR executive)'},
    ]
    if site:
        queries.insert(0, {'purpose': 'identity', 'query': f'site:{site} {person}'})
    if prospect.get('followup_focus'):
        return {'focus': 'identity_recovery', 'suggested_queries': queries}
    queries.append({'purpose': 'current_employment', 'query': f'{base} (appointed OR joined OR "press release") after:{cutoff}'})
    queries.extend(event_queries())
    return {'focus': 'identity_then_events', 'suggested_queries': queries}

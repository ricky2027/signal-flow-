"""SYNTHETIC TEST DATA ONLY. Never imported by production code."""

from datetime import date
from app.schemas import Evidence, Candidates, DraftContent, Quality, EvidenceReview, ExcerptSelection

INPUT = {
    "prospect_name": "Test Person",
    "company_name": "Example Corp",
    "designation": "CFO",
    "company_website": None,
    "product_service": "Cost analytics",
    "value_proposition": "Understand spending",
}
PASSAGE = f"Test Person is CFO of Example Corp. On {date.today().isoformat()}, Example Corp announced a new region."


def evidence():
    return Evidence.model_validate(
        {
            "sources": [
                {
                    "id": "s1",
                    "url": "https://example.com/news",
                    "title": "Test source",
                    "publisher": "Example",
                    "origin_group": "example.com",
                    "source_type": "primary",
                    "passage": PASSAGE,
                    "published_at": date.today().isoformat(),
                    "event_at": date.today().isoformat(),
                    "date_basis": "event",
                    "planned": False,
                }
            ],
            "claims": [
                {
                    "id": "identity",
                    "text": "Test Person is CFO of Example Corp",
                    "source_ids": ["s1"],
                    "entity_match": True,
                    "verification": "supported",
                    "kind": "identity",
                    "conflict_group": None,
                },
                {
                    "id": "event",
                    "text": "Example Corp announced a new region",
                    "source_ids": ["s1"],
                    "entity_match": True,
                    "verification": "supported",
                    "kind": "event",
                    "conflict_group": None,
                },
            ],
            "identity_confidence": "high",
            "material_identity_conflict": False,
            "warnings": [],
        }
    )


def candidates():
    return Candidates.model_validate(
        {
            "signals": [
                {
                    "id": "candidate",
                    "claim_ids": ["event"],
                    "fact_summary": "New region",
                    "implication": "Costs may grow",
                    "role_reason": "Budget ownership",
                    "offer_reason": "Spend visibility",
                    "role_relevance": 3,
                    "offer_fit": 3,
                }
            ]
        }
    )


def draft():
    text = "Example Corp announced a new region."
    return DraftContent(
        subject="Regional spending",
        body=text + " Could cost visibility help?",
        claim_refs=[
            {"field": "body", "start": 0, "end": len(text), "claim_ids": ["event"]}
        ],
    )


class FixtureProvider:
    def __init__(self, case="happy"):
        self.case = case
        self.quality_calls = 0

    async def close(self):
        pass

    async def search(self, prospect):
        return {
            "summary": "Test-only fixture",
            "urls": {"https://example.com/news": "Test"},
            "provider_call_id": "test-only",
        }

    async def structured(self, schema, task, data):
        if schema is ExcerptSelection:
            if self.case == "invented_passage":
                return ExcerptSelection(passage_id="not-a-supplied-id", claims=[])
            candidate = next((c for c in data["candidates"] if PASSAGE in c["text"]), None)
            if not candidate:
                return ExcerptSelection(passage_id=None, claims=[])
            claims = [c.model_copy(update={"source_ids": [data["source_id"]]}) for c in evidence().claims]
            return ExcerptSelection(passage_id=candidate["id"], claims=claims)
        if schema is EvidenceReview:
            return EvidenceReview(
                claims=[{"claim_id": c["id"], "source_ids": c["source_ids"],
                         "verification": c["verification"], "current_identity": c["kind"] == "identity", "role_assertion": c["kind"] == "identity",
                         "designation_match": "equivalent" if c["kind"] == "identity" else "not_applicable", "reason": "Synthetic fixture review only"} for c in data["evidence"]["claims"]],
                identity_confidence="high", company_association_confidence="high", identity_claim_ids=[c["id"] for c in data["evidence"]["claims"] if c["kind"] == "identity"], material_identity_conflict=False, warnings=[],
            )
        if schema is Evidence:
            e = evidence()
            if self.case == "missing":
                e.identity_confidence = "unknown"
                e.claims = []
                e.sources = []
            if self.case == "conflict":
                e.material_identity_conflict = True
            if self.case == "stale":
                e.sources[0].event_at = date(2020, 1, 1)
            if self.case == "invented_passage":
                e.sources[0].passage = "This was never on the page"
            return e
        if schema is Candidates:
            c = candidates()
            if data['evidence'].get('relevance_basis') == 'verified_company_context':
                c.signals[0].role_reason = 'Verified company-event context; current role not assumed'
            if self.case == "irrelevant":
                c.signals[0].offer_fit = 0
            return c
        if schema is DraftContent:
            return draft()
        if schema is Quality:
            self.quality_calls += 1
            invalid = self.case == "bad_quality"
            return Quality(
                valid=not invalid,
                findings=["unsupported fact"] if invalid else [],
                claim_refs=draft().claim_refs,
            )
        raise AssertionError(schema)

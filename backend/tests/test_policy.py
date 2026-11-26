from datetime import date, timedelta
import pytest
from app.policy import rank, validate_refs
from app.schemas import RunInput
from tests.fixtures import evidence, candidates, draft, INPUT


def test_happy():
    rows, outcome = rank(evidence(), candidates().signals)
    assert outcome is None and rows[0]["selected"] and rows[0]["score"] == 100


@pytest.mark.parametrize(
    "change,expected",
    [
        ("missing", "insufficient_information"),
        ("conflict", "conflicting_evidence"),
        ("stale", "no_relevant_signal"),
        ("irrelevant", "no_relevant_signal"),
        ("unknown_date", "no_relevant_signal"),
        ("weak", "no_relevant_signal"),
        ("disputed", "conflicting_evidence"),
    ],
)
def test_edges(change, expected):
    e = evidence()
    c = candidates()
    if change == "missing":
        e.identity_confidence = "unknown"
    if change == "conflict":
        e.material_identity_conflict = True
    if change == "stale":
        e.sources[0].event_at = date.today() - timedelta(days=181)
    if change == "irrelevant":
        c.signals[0].role_relevance = 1
    if change == "unknown_date":
        e.sources[0].event_at = None
        e.sources[0].published_at = None
    if change == "weak":
        weak = e.sources[0].model_copy(update={"id": "weak", "url": "https://example.com/weak", "source_type": "aggregator"})
        e.sources.append(weak)
        e.claims[1].source_ids = ["weak"]
    if change == "disputed":
        e.claims[1].verification = "disputed"
    assert rank(e, c.signals)[1] == expected


def test_claim_refs_and_input():
    d = draft()
    assert not validate_refs(d, evidence())
    d.claim_refs[0].end = 99999
    assert "invalid_reference_offsets" in validate_refs(d, evidence())
    for url in [
        "http://localhost",
        "http://127.0.0.1",
        "file:///etc/passwd",
        "http://192.168.1.1",
        "https://user:pass@example.com",
    ]:
        with pytest.raises(ValueError):
            RunInput(**{**INPUT, "company_website": url})
    with pytest.raises(ValueError):
        RunInput(**{**INPUT, "prospect_name": "  "})

import asyncio
from types import SimpleNamespace

from app.agents.research import research
from app.config import settings
from app.models import Run
from app.retrieval import RetrievalError
from app.schemas import Evidence, Candidates
from app.store import detail
from app.worker import claim, execute
from tests.fixtures import FixtureProvider, PASSAGE, evidence
from tests.test_workflow import enqueue


def test_followup_uses_new_pages_at_capacity_and_produces_persisted_draft(factory, monkeypatch):
    class FollowupProvider(FixtureProvider):
        searches = 0
        extractions = 0
        scoring_calls = 0

        async def search(self, prospect):
            self.searches += 1
            return {"summary": "Synthetic regression only", "urls": {f"https://example.com/news-{self.searches}": "Test"}, "provider_call_id": "fixture"}

        async def structured(self, schema, task, data):
            if schema is Evidence:
                self.extractions += 1
                e = evidence()
                if self.extractions == 1:
                    e.sources, e.claims, e.identity_confidence = [], [], "unknown"
                else:
                    assert len(data["pages"]) == 1
                    assert data["pages"][0]["url"] == "https://example.com/news-2"
                    e.sources[0].url = "https://example.com/news-2"
                return e
            if schema is Candidates:
                self.scoring_calls += 1
            return await super().structured(schema, task, data)

    async def fetch(url):
        return PASSAGE

    monkeypatch.setattr("app.retrieval.fetch", fetch)
    monkeypatch.setattr(settings(), "max_sources", 1)
    run_id = enqueue(factory)
    provider = FollowupProvider()
    asyncio.run(execute(claim(factory), factory, provider))
    with factory() as db:
        output = detail(db, db.get(Run, run_id))
        assert output["status"] == "awaiting_review"
        assert output["sources"][0]["url"].endswith("news-2")
        assert output["drafts"] and output["signals"][0]["selected"]
        assert output["research_diagnostics"]["retrieval_attempts"][1]["selected_urls"] == ["https://example.com/news-2"]
    assert provider.searches == 2 and provider.scoring_calls == 1


def test_failed_refetch_preserves_successful_page(monkeypatch):
    async def fail(url):
        raise RetrievalError("http_403")

    monkeypatch.setattr("app.retrieval.fetch", fail)
    artifacts = {}
    ctx = SimpleNamespace(provider=FixtureProvider(), config=SimpleNamespace(max_sources=1), save=lambda kind, data: artifacts.update({kind: data}))
    result = asyncio.run(research({"input": {}, "evidence": {}, "pages": [{"url": "https://example.com/news", "title": "Test", "text": PASSAGE}]}, ctx))
    assert result["pages"][0]["text"] == PASSAGE
    assert artifacts["retrieval_summary"]["sources"][0]["error"] == "http_403"


def test_unavailable_sources_abstain_without_calling_extraction_or_generation(factory, monkeypatch):
    class SearchOnly(FixtureProvider):
        searches = 0

        async def search(self, prospect):
            self.searches += 1
            return await super().search(prospect)

        async def structured(self, *args):
            raise AssertionError("No LLM extraction/scoring/writing on unavailable pages")

    async def unavailable(url):
        raise RetrievalError("http_403")

    monkeypatch.setattr("app.retrieval.fetch", unavailable)
    provider = SearchOnly()
    run_id = enqueue(factory)
    asyncio.run(execute(claim(factory), factory, provider))
    with factory() as db:
        output = detail(db, db.get(Run, run_id))
        assert output["status"] == "insufficient_information"
        assert not output["sources"] and not output["signals"] and not output["drafts"]
        assert output["signal_evaluation"]["state"] == "blocked"
        assert "no_eligible_claims" in output["signal_evaluation"]["gate_reasons"]
        assert len(output["research_diagnostics"]["retrieval_attempts"]) == 2
        assert all(source["error"] == "http_403" for attempt in output["research_diagnostics"]["retrieval_attempts"] for source in attempt["sources"])
        assert not any("designation_mismatch" in claim["reasons"] for attempt in output["research_diagnostics"]["verification_attempts"] for claim in attempt["claims"])
    assert provider.searches == 2


def test_page_extraction_cache_is_run_scoped_and_invalidated_by_changed_body():
    from app.agents.research import extract
    from tests.fixtures import INPUT

    class Counting(FixtureProvider):
        extractions = 0
        reviews = 0

        async def structured(self, schema, task, data):
            from app.schemas import EvidenceReview
            if schema is Evidence:
                self.extractions += 1
            if schema is EvidenceReview:
                self.reviews += 1
            return await super().structured(schema, task, data)

    provider = Counting()
    ctx = SimpleNamespace(provider=provider, save=lambda *args: None)
    state = {'input': INPUT, 'pages': [{'url': 'https://example.com/news', 'text': PASSAGE}]}
    first = asyncio.run(extract(state, ctx))
    second = asyncio.run(extract({**state, **first}, ctx))
    assert provider.extractions == 1 and provider.reviews == 2
    changed = {**state, **second, 'pages': [{'url': 'https://example.com/news', 'text': PASSAGE + ' Additional text.'}]}
    asyncio.run(extract(changed, ctx))
    assert provider.extractions == 2 and provider.reviews == 3

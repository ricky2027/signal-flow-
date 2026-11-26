import asyncio
import httpx
import pytest
from app.provider import OpenAIProvider
from app.config import Settings


def config():
    return Settings(openai_api_key="test-only", _env_file=None)


def test_real_adapter_parsing_with_test_transport():
    calls = []
    provider = OpenAIProvider(calls.append, config())

    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "test-response",
                "status": "completed",
                "output": [
                    {
                        "type": "web_search_call",
                        "action": {
                            "type": "search",
                            "sources": [
                                {"url": "https://example.com", "title": "Example"}
                            ],
                        },
                    },
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Test narration",
                                "annotations": [],
                            }
                        ],
                    },
                ],
            },
        )

    async def run():
        await provider.client.aclose()
        provider.client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.openai.com/v1/",
        )
        result = await provider.search({"name": "fixture"})
        await provider.close()
        return result

    result = asyncio.run(run())
    assert list(result["urls"]) == ["https://example.com"] and len(calls) == 2


def test_auth_failure_not_retried():
    calls = []
    provider = OpenAIProvider(calls.append, config())

    async def run():
        await provider.client.aclose()
        provider.client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(401, json={"error": "test"})
            ),
            base_url="https://api.openai.com/v1/",
        )
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await provider.search({})
        finally:
            await provider.close()

    asyncio.run(run())
    assert len(calls) == 1


def test_network_retries_bounded(monkeypatch):
    async def no_wait(t):
        pass

    monkeypatch.setattr("app.provider.asyncio.sleep", no_wait)
    calls = []
    provider = OpenAIProvider(calls.append, config())

    def handler(request):
        raise httpx.ConnectError("test failure")

    async def run():
        await provider.client.aclose()
        provider.client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.openai.com/v1/",
        )
        try:
            with pytest.raises(httpx.ConnectError):
                await provider.search({})
        finally:
            await provider.close()

    asyncio.run(run())
    assert len(calls) == 3 and provider.search_attempts == 3

"""Explicit paid live smoke: python -m app.smoke. Never uses fixtures."""

import asyncio
import json
from app.provider import OpenAIProvider


async def main():
    calls = []
    provider = OpenAIProvider(calls.append)
    try:
        result = await provider.search(
            {
                "prospect_name": "Satya Nadella",
                "company_name": "Microsoft",
                "designation": "CEO",
                "product_service": "Cloud cost analytics",
                "value_proposition": "Identify cloud spending inefficiencies",
            }
        )
        print(
            json.dumps(
                {
                    "provider_call_id": result["provider_call_id"],
                    "source_urls": list(result["urls"]),
                    "call_count": len(calls),
                },
                indent=2,
            )
        )
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())

from typing import Any

from .config import settings
from .http_client import async_client


async def search_web(query: str) -> list[dict[str, Any]]:
    params = {
        "q": query,
        "format": "json",
        "language": "auto",
        "safesearch": 0,
    }

    async with async_client(settings.searxng_timeout_seconds) as client:
        resp = await client.get(settings.searxng_url, params=params)
        if resp.status_code == 403:
            raise RuntimeError(
                "SearXNG returned 403. Enable JSON in searxng/settings.yml: "
                "search.formats: [html, json]."
            )
        resp.raise_for_status()
        data = resp.json()

    items: list[dict[str, Any]] = []
    for r in data.get("results", []):
        url = r.get("url")
        if not url:
            continue
        items.append(
            {
                "title": r.get("title") or "",
                "url": url,
                "snippet": r.get("content") or "",
                "engine": r.get("engine") or "",
                "score": float(r.get("score") or 0),
            }
        )

    return items[: settings.max_search_results]

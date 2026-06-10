from typing import Any

from .config import settings
from .http_client import async_client
from .text import chunk_text, stable_id


class BGEVectorDBClient:
    """HTTP adapter for your self-hosted BGE vector database / retrieval service.

    Expected API:

    POST /upsert
    {
      "collection": "web_search",
      "documents": [
        {
          "id": "...",
          "text": "...",
          "metadata": {"title": "...", "url": "...", "source": "web"}
        }
      ]
    }

    POST /search
    {
      "collection": "web_search",
      "query": "user question",
      "top_k": 8,
      "filters": {}
    }

    Expected search response, either shape is accepted:
    {
      "results": [
        {
          "id": "...",
          "text": "...",
          "score": 0.87,
          "metadata": {"title": "...", "url": "..."}
        }
      ]
    }

    or directly:
    [
      {"id": "...", "text": "...", "score": 0.87, "metadata": {...}}
    ]
    """

    def __init__(self) -> None:
        self.base_url = settings.bge_db_base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return settings.bge_db_enabled

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.bge_db_api_key:
            headers["Authorization"] = f"Bearer {settings.bge_db_api_key}"
        return headers

    async def upsert_pages(self, pages: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "reason": "bge_db_disabled"}

        documents: list[dict[str, Any]] = []
        for page in pages:
            url = page.get("url") or ""
            title = page.get("title") or ""
            content = page.get("content") or page.get("snippet") or ""
            if not url or not content.strip():
                continue

            for idx, chunk in enumerate(chunk_text(content), start=1):
                documents.append(
                    {
                        "id": stable_id(f"{url}#{idx}"),
                        "text": chunk,
                        "metadata": {
                            "title": title,
                            "url": url,
                            "chunk_index": idx,
                            "source": "web",
                        },
                    }
                )

        if not documents:
            return {"ok": False, "reason": "no_documents"}

        payload = {
            "collection": settings.bge_db_collection,
            "documents": documents,
        }
        url = f"{self.base_url}{settings.bge_db_upsert_path}"

        async with async_client(settings.bge_db_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return {"ok": True, "status_code": resp.status_code}

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        payload = {
            "collection": settings.bge_db_collection,
            "query": query,
            "top_k": top_k or settings.bge_db_top_k,
            "filters": filters or {},
        }
        url = f"{self.base_url}{settings.bge_db_search_path}"

        async with async_client(settings.bge_db_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        raw_results = data.get("results", data) if isinstance(data, dict) else data
        normalized: list[dict[str, Any]] = []
        for item in raw_results or []:
            metadata = item.get("metadata") or {}
            normalized.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title") or metadata.get("title") or "",
                    "url": item.get("url") or metadata.get("url") or "",
                    "text": item.get("text") or item.get("content") or "",
                    "score": item.get("score", 0),
                    "metadata": metadata,
                }
            )
        return normalized


bge_db = BGEVectorDBClient()

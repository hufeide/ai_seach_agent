import os
from typing import Any

from .config import settings
from .http_client import async_client
from .text import chunk_text


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings from BGE API."""
    if not texts:
        return []

    url = f"{settings.bge_url.rstrip('/')}/v1/embeddings"
    payload = {
        "model": settings.bge_model,
        "input": texts,
    }

    async with async_client(30, trust_env=False) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    return [item["embedding"] for item in data.get("data", [])]


class MilvusLiteClient:
    """Milvus Lite client - stores vectors in local file."""

    def __init__(self) -> None:
        self.db_path = settings.bge_db_path or "./data/milvus_lite.db"
        self.collection_name = settings.bge_db_collection or "web_search"
        self._client = None
        self._initialized = False

    def _init(self) -> None:
        """Initialize Milvus Lite and create collection if needed."""
        if self._initialized:
            return

        try:
            from pymilvus import MilvusClient, CollectionSchema, FieldSchema, DataType
        except ImportError:
            raise ImportError("milvus-lite not installed: pip install milvus-lite")

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        # Create Milvus Client (local file)
        self._client = MilvusClient(self.db_path)

        # Check if collection exists, if not create it with full schema
        if not self._client.has_collection(self.collection_name):
            # BGE-m3 is 1024 dimensions
            dim = 1024
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            ]
            schema = CollectionSchema(fields, description=f"{self.collection_name} collection")
            self._client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                metric_type="IP",
            )
        else:
            # Collection exists - check if we need to drop and recreate due to schema mismatch
            # Try to get collection info and verify schema
            try:
                coll_info = self._client.describe_collection(self.collection_name)
                fields_dict = {f["name"]: f for f in coll_info.get("fields", [])}

                # Check if id field exists and has auto_id enabled
                if "id" in fields_dict:
                    id_field = fields_dict["id"]
                    if not id_field.get("auto_id", False):
                        # Schema mismatch - id field requires manual value
                        # Drop and recreate with correct schema
                        print(f"Warning: Dropping collection '{self.collection_name}' due to schema mismatch (auto_id=False)")
                        self._client.drop_collection(self.collection_name)

                        dim = 1024
                        fields = [
                            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),
                            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
                        ]
                        schema = CollectionSchema(fields, description=f"{self.collection_name} collection")
                        self._client.create_collection(
                            collection_name=self.collection_name,
                            schema=schema,
                            metric_type="IP",
                        )
            except Exception as e:
                print(f"Warning: Could not verify collection schema: {e}")

        # Create index if not exists
        try:
            self._client.create_index(
                collection_name=self.collection_name,
                field_name="vector",
                index_type="IVF_FLAT",
                metric_type="IP",
                params={"nlist": 128},
            )
        except Exception:
            pass  # Index might already exist

        self._initialized = True

    async def upsert_pages(self, pages: list[dict[str, Any]]) -> dict[str, Any]:
        """Index pages into Milvus Lite."""
        if not settings.bge_db_enabled:
            return {"ok": False, "reason": "bge_db_disabled"}

        if not pages:
            return {"ok": False, "reason": "no_pages"}

        self._init()

        try:
            from pymilvus import MilvusClient
        except ImportError:
            return {"ok": False, "error": "milvus-lite not installed"}

        documents = []
        for page in pages:
            url = page.get("url") or ""
            title = page.get("title") or ""
            content = page.get("content") or page.get("snippet") or ""
            if not url or not content.strip():
                continue

            for idx, chunk in enumerate(chunk_text(content), start=1):
                documents.append(
                    {
                        "text": chunk,
                        "metadata": f"{title}|{url}",
                    }
                )

        if not documents:
            return {"ok": False, "reason": "no_documents"}

        # Get embeddings from BGE API
        all_texts = [d["text"] for d in documents]
        embeddings = await get_embeddings(all_texts)

        if not embeddings:
            return {"ok": False, "error": "failed to get embeddings"}

        # Insert in batches using MilvusClient
        client = self._client
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            emb_batch = embeddings[i : i + batch_size]

            # Build list of row dictionaries (each row is a dict with single values)
            rows = []
            for doc, vec in zip(batch, emb_batch):
                rows.append({
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "vector": [float(x) for x in vec],
                })

            client.insert(
                collection_name=self.collection_name,
                data=rows,
            )

        # Flush to ensure data is searchable
        client.flush(self.collection_name)

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search Milvus Lite."""
        if not settings.bge_db_enabled:
            return []

        self._init()

        try:
            from pymilvus import MilvusClient
        except ImportError:
            return []

        client = self._client

        # Ensure collection is loaded for search (with error handling)
        try:
            client.load_collection(self.collection_name)
        except Exception:
            pass  # Collection may already be loaded or not have data

        top_k = top_k or settings.bge_db_top_k

        # Get query embedding
        embeddings = await get_embeddings([query])
        if not embeddings:
            return []

        query_vector = [list(embeddings[0])]

        results = client.search(
            collection_name=self.collection_name,
            data=query_vector,
            anns_field="vector",
            limit=top_k,
            output_fields=["text", "metadata"],
        )

        if not results or not results[0]:
            return []

        normalized = []
        for hits in results:
            for hit in hits:
                # 兼容新版本 pymilvus API
                entity = getattr(hit, 'entity', None)
                if entity:
                    metadata = entity.get("metadata", "") or ""
                    text = entity.get("text", "") or ""
                else:
                    # 旧版本 API 兼容
                    data = getattr(hit, '_data', {})
                    metadata = data.get("metadata", "") if isinstance(data, dict) else ""
                    text = data.get("text", "") if isinstance(data, dict) else ""
                
                parts = metadata.split("|", 1) if "|" in metadata else ["", ""]
                title, url = parts[0], parts[1] if len(parts) > 1 else ""
                normalized.append(
                    {
                        "title": title,
                        "url": url,
                        "text": text,
                        "score": hit.score,
                    }
                )

        return normalized


bge_db = MilvusLiteClient()
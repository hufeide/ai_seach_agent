from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Proxy
    http_proxy: str = "socks5://192.168.1.159:10808"
    https_proxy: str = "socks5://192.168.1.159:10808"
    no_proxy: str = "localhost,127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8"

    # vLLM OpenAI-compatible API
    vllm_base_url: str = "http://127.0.0.1:8000/v1"
    vllm_api_key: str = "EMPTY"
    vllm_model: str = "qwen2.5-7b-instruct"
    vllm_timeout_seconds: float = 120

    # SearXNG
    searxng_url: str = "http://127.0.0.1:8080/search"
    searxng_timeout_seconds: float = 30

    # Crawl4AI
    crawl_timeout_seconds: float = 45
    crawl_max_chars_per_page: int = 12000
    crawl_user_agent: str = (
        "Mozilla/5.0 (compatible; AISearchAgent/0.1; +https://example.local/bot)"
    )

    # BGE vector DB / retrieval service
    bge_db_base_url: str = "http://127.0.0.1:9000"
    bge_db_api_key: str = ""
    bge_db_upsert_path: str = "/upsert"
    bge_db_search_path: str = "/search"
    bge_db_timeout_seconds: float = 60
    bge_db_enabled: bool = True
    bge_db_collection: str = "web_search"
    bge_db_top_k: int = 8

    # Agent behavior
    max_search_results: int = 10
    max_crawl_pages: int = 6
    max_iterations: int = 2
    query_count: int = Field(default=4, ge=1, le=8)
    evidence_top_k: int = 6


settings = Settings()

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from .config import settings
from .crawler import crawl_pages
from .graph import run_search_agent
from .http_client import apply_proxy_env
from .searxng import search_web
from fastapi import Response
apply_proxy_env()

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="AI Search Agent - vLLM + SearXNG + Crawl4AI + BGE DB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/static/{path:path}")
async def static_files(request: Request, path: str):
    file_path = WEB_DIR / path
    if file_path.exists() and file_path.is_file():
        response = FileResponse(str(file_path))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"detail": "File not found"})


class SearchRequest(BaseModel):
    question: str = Field(..., min_length=1)
    mode: Literal["fast", "deep"] = "fast"


class SearchResponse(BaseModel):
    question: str
    mode: str
    answer: str | None
    queries: list[str]
    sources: list[dict]
    search_results: list[dict]
    crawled_pages: list[dict]
    bge_upsert_result: dict
    errors: list[str]


class SourceSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


class PageFetchRequest(BaseModel):
    url: HttpUrl
    title: str = ""
    snippet: str = ""



@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/")
async def index():
    return FileResponse(str(WEB_DIR / "index.html"))


@app.get("/health")
async def health():
    return {
        "ok": True,
        "vllm_base_url": settings.vllm_base_url,
        "vllm_model": settings.vllm_model,
        "searxng_url": settings.searxng_url,
        "bge_db_enabled": settings.bge_db_enabled,
        "bge_db_base_url": settings.bge_db_base_url,
        "proxy": {
            "http_proxy": settings.http_proxy,
            "https_proxy": settings.https_proxy,
            "no_proxy": settings.no_proxy,
        },
    }


@app.post("/search-agent", response_model=SearchResponse)
async def search_agent(req: SearchRequest):
    result = await run_search_agent(req.question, mode=req.mode)
    evidence = result.get("evidence", [])
    search_results = result.get("search_results", [])
    crawled_pages = result.get("pages", [])

    return SearchResponse(
        question=req.question,
        mode=req.mode,
        answer=result.get("answer"),
        queries=result.get("queries", []),
        sources=[
            {
                "source_id": e.get("source_id"),
                "title": e.get("title"),
                "url": e.get("url"),
                "supports": e.get("supports"),
                "quote_or_summary": e.get("quote_or_summary"),
            }
            for e in evidence
        ],
        search_results=[
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "engine": item.get("engine", ""),
                "query": item.get("query", ""),
                "score": item.get("score", 0),
            }
            for item in search_results
        ],
        crawled_pages=[
            {
                "title": page.get("title", ""),
                "url": page.get("url", ""),
                "snippet": page.get("snippet", ""),
                "content_preview": (page.get("content") or "")[:500],
                "error": page.get("error", ""),
            }
            for page in crawled_pages
        ],
        bge_upsert_result=result.get("bge_upsert_result", {}),
        errors=result.get("errors", []),
    )


@app.post("/search-sources")
async def search_sources(req: SourceSearchRequest):
    """Only search SearXNG and return candidate data sources, without LLM answering."""
    results = await search_web(req.query)
    return {
        "query": req.query,
        "results": [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "engine": item.get("engine", ""),
                "score": item.get("score", 0),
            }
            for item in results
        ],
    }


@app.post("/fetch-page")
async def fetch_page(req: PageFetchRequest):
    """Crawl one URL with Crawl4AI and return readable webpage content."""
    pages = await crawl_pages(
        [
            {
                "title": req.title,
                "url": str(req.url),
                "snippet": req.snippet,
            }
        ]
    )
    if not pages:
        return {
            "ok": False,
            "url": str(req.url),
            "title": req.title,
            "content": "",
            "error": "no_page_returned",
        }

    page = pages[0]
    return {
        "ok": bool((page.get("content") or "").strip()),
        "title": page.get("title") or req.title,
        "url": page.get("url") or str(req.url),
        "snippet": page.get("snippet") or req.snippet,
        "content": page.get("content") or "",
        "error": page.get("error") or "",
    }

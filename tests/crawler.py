import asyncio
from typing import Any

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from .config import settings
from .http_client import apply_proxy_env
from .text import normalize_text


def _extract_markdown(result: Any) -> str:
    markdown = getattr(result, "markdown", None)
    if isinstance(markdown, str):
        return markdown
    if markdown is not None and hasattr(markdown, "raw_markdown"):
        return markdown.raw_markdown or ""
    if hasattr(result, "cleaned_html"):
        return result.cleaned_html or ""
    if hasattr(result, "html"):
        return result.html or ""
    return ""


async def _crawl_single_page(
    crawler: AsyncWebCrawler,
    item: dict[str, Any],
    run_config: CrawlerRunConfig,
) -> dict[str, Any]:
    """爬取单个页面"""
    url = item["url"]
    try:
        result = await crawler.arun(url=url, config=run_config)
        if not getattr(result, "success", False):
            return {**item, "content": "", "error": "crawl_failed"}

        text = normalize_text(_extract_markdown(result))
        return {
            "title": item.get("title", ""),
            "url": url,
            "snippet": item.get("snippet", ""),
            "content": text[: settings.crawl_max_chars_per_page],
        }
    except Exception as exc:
        return {**item, "content": "", "error": str(exc)}


async def crawl_pages(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Crawl search results and return normalized page text.

    Crawl4AI/Playwright inherits HTTP_PROXY/HTTPS_PROXY from the environment; run_api.sh
    and apply_proxy_env() set the proxy to socks5://192.168.1.159:10808 by default.
    """
    apply_proxy_env()

    browser_config = BrowserConfig(
        headless=True,
        user_agent=settings.crawl_user_agent,
    )
    run_config = CrawlerRunConfig()

    # 限制并行爬取数量，避免资源耗尽
    max_concurrent = min(settings.max_crawl_pages, 4)
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # 创建爬取任务列表
        items_to_crawl = results[: settings.max_crawl_pages]
        
        # 分批并行爬取
        pages: list[dict[str, Any]] = []
        for i in range(0, len(items_to_crawl), max_concurrent):
            batch = items_to_crawl[i : i + max_concurrent]
            tasks = [
                _crawl_single_page(crawler, item, run_config)
                for item in batch
            ]
            batch_results = await asyncio.gather(*tasks)
            pages.extend(batch_results)

    return pages

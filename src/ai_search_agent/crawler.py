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


async def crawl_pages(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Crawl search results and return normalized page text.

    Crawl4AI/Playwright inherits HTTP_PROXY/HTTPS_PROXY from the environment; run_api.sh
    and apply_proxy_env() set the proxy to socks5://192.168.1.159:10808 by default.
    """
    apply_proxy_env()
    pages: list[dict[str, Any]] = []

    browser_config = BrowserConfig(
        headless=True,
        user_agent=settings.crawl_user_agent,
    )
    run_config = CrawlerRunConfig()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for item in results[: settings.max_crawl_pages]:
            url = item["url"]
            try:
                result = await crawler.arun(url=url, config=run_config)
                if not getattr(result, "success", False):
                    pages.append({**item, "content": "", "error": "crawl_failed"})
                    continue

                text = normalize_text(_extract_markdown(result))
                pages.append(
                    {
                        "title": item.get("title", ""),
                        "url": url,
                        "snippet": item.get("snippet", ""),
                        "content": text[: settings.crawl_max_chars_per_page],
                    }
                )
            except Exception as exc:
                pages.append({**item, "content": "", "error": str(exc)})

    return pages

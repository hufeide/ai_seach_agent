import asyncio
import re
from typing import Any
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from .config import settings
from .http_client import apply_proxy_env
from .text import normalize_text


MIN_FAST_CONTENT_LENGTH = 500
MIN_DEEP_CONTENT_LENGTH = 100
PER_PAGE_TIMEOUT_SECONDS = 35


FAST_CONFIG = CrawlerRunConfig(
    page_timeout=15000,
    wait_until="domcontentloaded",
)


DEFAULT_DEEP_CONFIG = CrawlerRunConfig(
    page_timeout=30000,
    wait_until="domcontentloaded",
    js_code_before_wait="""
() => {
    window.scrollTo(0, document.body.scrollHeight / 2);
    setTimeout(() => window.scrollTo(0, document.body.scrollHeight), 300);
    setTimeout(() => window.scrollTo(0, 0), 800);
}
""",
    wait_for="""
js:() => {
    const text = document.body?.innerText || "";
    const tableRows = document.querySelectorAll("table tr, tbody tr").length;
    const articleLike = document.querySelectorAll(
        "article, main, .article, .content, .post, .entry, #content"
    ).length;

    return text.length >= 1000 || tableRows >= 10 || articleLike > 0;
}
""",
    delay_before_return_html=2.0,
    process_iframes=True,
    scan_full_page=True,
    magic=True,
)


MARKDOWN_IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\((?:\\.|[^)\\])*\)",
    flags=re.MULTILINE,
)

MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]\n]{1,300})\]\((?:\\.|[^)\\])*\)",
    flags=re.MULTILINE,
)

BARE_JS_RE = re.compile(
    r"javascript\s*:\s*(?:void\s*\(\s*0\s*\)|;)",
    flags=re.IGNORECASE,
)

MULTIPLE_BLANK_LINES_RE = re.compile(r"\n{3,}")


BOILERPLATE_CUTOFF_MARKERS = (
    "\n频道资讯",
    "\n投资热点",
    "\n数据精华",
    "\n提示",
    "\n投资者关系",
    "\n不良信息举报电话",
    "\nCopyright",
    "\nICP证",
)


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


def _remove_markdown_urls(text: str) -> str:
    """删除 Markdown 图片，把 Markdown 链接转换成纯文本。"""

    # ![logo](https://example.com/logo.png) -> ""
    text = MARKDOWN_IMAGE_RE.sub("", text)

    # [现价](javascript:void\(0\)) -> 现价
    # [新威凌](http://stockpage.10jqka.com.cn/920634/) -> 新威凌
    text = MARKDOWN_LINK_RE.sub(r"\1", text)

    # 删除裸露的 javascript:void(0)
    text = BARE_JS_RE.sub("", text)

    return text


def _remove_boilerplate_sections(text: str) -> str:
    """删除常见页脚、站点导航、推荐链接区域。"""

    cutoff_indexes = [
        text.find(marker)
        for marker in BOILERPLATE_CUTOFF_MARKERS
        if text.find(marker) != -1
    ]

    if not cutoff_indexes:
        return text

    return text[: min(cutoff_indexes)]


def _clean_crawled_text(raw_text: str) -> str:
    """面向搜索 Agent 的网页正文清洗。"""

    text = _remove_markdown_urls(raw_text)
    text = _remove_boilerplate_sections(text)
    text = normalize_text(text)
    text = MULTIPLE_BLANK_LINES_RE.sub("\n\n", text)

    return text.strip()


def _get_deep_config_for_url(url: str) -> CrawlerRunConfig:
    """针对部分强动态网站返回特化配置。"""

    host = urlparse(url).netloc.lower()

    if "10jqka.com.cn" in host:
        return CrawlerRunConfig(
            page_timeout=30000,
            wait_until="domcontentloaded",
            js_code_before_wait="""
() => {
    // 模拟真实用户滚动，触发懒加载和表格渲染
    window.scrollTo(0, 300);
    setTimeout(() => window.scrollTo(0, 900), 300);
    setTimeout(() => window.scrollTo(0, 0), 800);
}
""",
            wait_for="""
js:() => {
    const text = document.body?.innerText || "";

    const rows = document.querySelectorAll(
        "table tr, tbody tr, .m-table tr, .table-list tr"
    ).length;

    const hasStockCode = /\\b(60|68|30|00|92)\\d{4}\\b/.test(text);

    return (
        rows >= 10 ||
        hasStockCode ||
        text.includes("个股行情") ||
        text.includes("A股市场")
    );
}
""",
            delay_before_return_html=2.0,
            process_iframes=True,
            scan_full_page=True,
            magic=True,
        )

    return DEFAULT_DEEP_CONFIG


async def _run_crawl(
    crawler: AsyncWebCrawler,
    url: str,
    config: CrawlerRunConfig,
) -> tuple[bool, str]:
    result = await crawler.arun(
        url=url,
        config=config,
    )

    if not getattr(result, "success", False):
        return False, ""

    text = _clean_crawled_text(_extract_markdown(result))
    return True, text


async def crawl_with_fallback(
    crawler: AsyncWebCrawler,
    url: str,
) -> tuple[str, str | None]:
    """先快速抓取；内容不足时再用动态渲染模式重试。"""

    fast_success, fast_text = await _run_crawl(
        crawler=crawler,
        url=url,
        config=FAST_CONFIG,
    )

    if fast_success and len(fast_text) >= MIN_FAST_CONTENT_LENGTH:
        return fast_text, None

    deep_success, deep_text = await _run_crawl(
        crawler=crawler,
        url=url,
        config=_get_deep_config_for_url(url),
    )

    if deep_success and len(deep_text) >= MIN_DEEP_CONTENT_LENGTH:
        return deep_text, None

    if fast_success or deep_success:
        return "", "insufficient_content"

    return "", "crawl_failed"


async def _crawl_single_page_impl(
    crawler: AsyncWebCrawler,
    item: dict[str, Any],
) -> dict[str, Any]:
    """爬取单个页面。"""

    url = item["url"]

    text, error = await crawl_with_fallback(
        crawler=crawler,
        url=url,
    )

    page: dict[str, Any] = {
        "title": item.get("title", ""),
        "url": url,
        "snippet": item.get("snippet", ""),
        "content": text[: settings.crawl_max_chars_per_page],
    }

    if error:
        page["error"] = error

    return page


async def _crawl_single_page(
    crawler: AsyncWebCrawler,
    item: dict[str, Any],
) -> dict[str, Any]:
    """带全局超时保护的单页爬取。"""

    try:
        return await asyncio.wait_for(
            _crawl_single_page_impl(
                crawler=crawler,
                item=item,
            ),
            timeout=PER_PAGE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return {
            **item,
            "content": "",
            "error": "timeout",
        }
    except Exception as exc:
        return {
            **item,
            "content": "",
            "error": str(exc),
        }


async def crawl_pages(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Crawl search results and return normalized page text.

    Crawl4AI / Playwright inherits HTTP_PROXY / HTTPS_PROXY from the environment.
    run_api.sh and apply_proxy_env() set the proxy to socks5://192.168.1.159:10808
    by default.
    """

    apply_proxy_env()

    browser_config = BrowserConfig(
        headless=True,
        user_agent=settings.crawl_user_agent,
        viewport_width=1920,
        viewport_height=1080,
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )

    items_to_crawl = results[: settings.max_crawl_pages]

    if not items_to_crawl:
        return []

    max_concurrent = max(
        1,
        min(
            len(items_to_crawl),
            8,
        ),
    )

    pages: list[dict[str, Any]] = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i in range(0, len(items_to_crawl), max_concurrent):
            batch = items_to_crawl[i : i + max_concurrent]

            tasks = [
                _crawl_single_page(
                    crawler=crawler,
                    item=item,
                )
                for item in batch
            ]

            batch_results = await asyncio.gather(*tasks)
            pages.extend(batch_results)

    return pages
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from .config import settings


def apply_proxy_env() -> None:
    """Apply proxy env vars so httpx, Crawl4AI/Playwright, and other libs can inherit them."""
    os.environ["http_proxy"] = settings.http_proxy
    os.environ["https_proxy"] = settings.https_proxy
    os.environ["HTTP_PROXY"] = settings.http_proxy
    os.environ["HTTPS_PROXY"] = settings.https_proxy
    os.environ["NO_PROXY"] = settings.no_proxy
    os.environ["no_proxy"] = settings.no_proxy


@asynccontextmanager
async def async_client(
    timeout: float,
    trust_env: bool = True,
) -> AsyncIterator[httpx.AsyncClient]:
    """Create an httpx client.

    trust_env=True  时读取环境变量代理。
    trust_env=False 时忽略 http_proxy/https_proxy/all_proxy，适合访问本地 vLLM。
    """
    if trust_env:
        apply_proxy_env()

    async with httpx.AsyncClient(
        timeout=timeout,
        trust_env=trust_env,
        follow_redirects=True,
    ) as client:
        yield client
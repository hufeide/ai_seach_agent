#!/usr/bin/env python3
"""
Debug 脚本 - 用于调试各个模块
Usage: python scripts/debug.py [module]
"""

import asyncio
import os
import sys

# 添加 src 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# 加载 .env
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from ai_search_agent import (
    searxng,
    crawler,
    bge_db,
    llm,
    graph,
)


async def debug_searxng():
    """调试搜索功能"""
    print("\n=== Debug SearXNG ===")
    query = "罗马天气"
    results = await searxng.search_web(query)
    print(f"Query: {query}")
    print(f"Results count: {len(results)}")
    for i, r in enumerate(results[:3]):
        print(f"  [{i}] {r.get('title')} - {r.get('url')}")
    return results


async def debug_crawl(search_results):
    """调试爬虫功能"""
    print("\n=== Debug Crawler ===")
    pages = await crawler.crawl_pages(search_results[:3])
    print(f"Crawled pages: {len(pages)}")
    for p in pages:
        title = p.get("title", "")[:50]
        content_len = len(p.get("content") or "")
        error = p.get("error") or "OK"
        print(f"  - {title}... (content: {content_len} chars, error: {error})")
    return pages


async def debug_bge(pages):
    """调试 BGE 向量库"""
    print("\n=== Debug BGE ===")

    # 测试 upsert
    print("Testing upsert...")
    result = await bge_db.upsert_pages(pages[:2])
    print(f"Upsert result: {result}")

    # 测试 search
    print("Testing search...")
    results = await bge_db.search("罗马天气怎么样", top_k=3)
    print(f"Search results: {len(results)}")
    for r in results:
        print(f"  - {r.get('title')} (score: {r.get('score', 0):.3f})")
    return results


async def debug_llm():
    """调试 LLM"""
    print("\n=== Debug LLM ===")

    messages = [
        {"role": "user", "content": "你好，请用一句话介绍北京。"}
    ]
    response = await llm.llm.chat(messages, temperature=0.5, max_tokens=200)
    print(f"LLM Response: {response[:200]}...")
    return response


async def debug_llm_json():
    """调试 LLM JSON 模式"""
    print("\n=== Debug LLM JSON ===")

    messages = [
        {"role": "system", "content": "你是一个助手。请输出 JSON。"},
        {"role": "user", "content": "给我一个包含 name 和 age 的 JSON 对象。"}
    ]
    response = await llm.llm.json_chat(messages, temperature=0)
    print(f"LLM JSON Response: {response}")
    return response


async def debug_graph():
    """调试完整 Graph"""
    print("\n=== Debug Graph ===")
    result = await graph.run_search_agent("罗马天气", mode="fast")
    print(f"Answer: {result.get('answer', '')[:300]}...")
    print(f"Errors: {result.get('errors', [])}")
    return result


async def main():
    module = sys.argv[1] if len(sys.argv) > 1 else "all"

    print(f"Running debug for: {module}")
    print("=" * 50)

    if module == "searxng" or module == "all":
        await debug_searxng()

    if module == "crawl" or module == "all":
        search_results = await debug_searxng()
        await debug_crawl(search_results)

    if module == "bge" or module == "all":
        search_results = await searxng.search_web("罗马天气")
        pages = await crawler.crawl_pages(search_results[:2])
        await debug_bge(pages)

    if module == "llm":
        await debug_llm()

    if module == "llm_json":
        await debug_llm_json()

    if module == "graph" or module == "all":
        await debug_graph()

    print("\n" + "=" * 50)
    print("Debug completed!")


if __name__ == "__main__":
    asyncio.run(main())
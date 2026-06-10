from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from .bge_db import bge_db
from .config import settings
from .crawler import crawl_pages
from .llm import llm
from .searxng import search_web
from .text import dedupe_by_url


class SearchAgentState(TypedDict, total=False):
    question: str
    mode: Literal["fast", "deep"]
    queries: list[str]
    search_results: list[dict[str, Any]]
    pages: list[dict[str, Any]]
    bge_upsert_result: dict[str, Any]
    bge_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    answer: str
    need_more: bool
    missing: str
    iteration: int
    errors: list[str]


def _append_error(state: SearchAgentState, message: str) -> list[str]:
    return [*state.get("errors", []), message]


async def plan_queries(state: SearchAgentState) -> dict[str, Any]:
    question = state["question"]
    iteration = state.get("iteration", 0)
    mode = state.get("mode", "fast")

    system = """
你是一个联网搜索查询规划器。请把用户问题改写成适合 SearXNG 的搜索 query。
要求：
- 输出 JSON，不要输出 Markdown。
- queries 数量控制在 2 到 5 个。
- 如果是时效性问题，query 里加入年份或 latest/recent。
- 如果上一轮信息不足，下一轮 query 应该补齐缺失信息。
""".strip()

    user = f"""
用户问题：{question}
搜索模式：{mode}
当前轮次：{iteration + 1}
上一轮缺失信息：{state.get('missing', '')}

输出格式：
{{
  "queries": ["query1", "query2"]
}}
""".strip()

    data = await llm.json_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    queries = data.get("queries") or [question]
    queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]

    return {
        "queries": queries[: settings.query_count],
        "iteration": iteration + 1,
    }


async def search_node(state: SearchAgentState) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    errors: list[str] = state.get("errors", [])

    for query in state.get("queries", []):
        try:
            results = await search_web(query)
            for item in results:
                item["query"] = query
                merged.append(item)
        except Exception as exc:
            errors.append(f"search failed for query={query!r}: {exc}")

    return {
        "search_results": dedupe_by_url(merged)[: settings.max_search_results],
        "errors": errors,
    }


async def crawl_node(state: SearchAgentState) -> dict[str, Any]:
    try:
        pages = await crawl_pages(state.get("search_results", []))
        return {"pages": pages}
    except Exception as exc:
        return {
            "pages": [],
            "errors": _append_error(state, f"crawl failed: {exc}"),
        }


async def bge_upsert_and_search_node(state: SearchAgentState) -> dict[str, Any]:
    """Index crawled pages into self-hosted BGE DB and retrieve relevant chunks."""
    question = state["question"]
    errors = state.get("errors", [])
    upsert_result: dict[str, Any] = {}
    bge_results: list[dict[str, Any]] = []

    if not settings.bge_db_enabled:
        return {
            "bge_upsert_result": {"ok": False, "reason": "bge_db_disabled"},
            "bge_results": [],
        }

    try:
        upsert_result = await bge_db.upsert_pages(state.get("pages", []))
    except Exception as exc:
        errors.append(f"BGE DB upsert failed: {exc}")
        upsert_result = {"ok": False, "error": str(exc)}

    try:
        bge_results = await bge_db.search(question, top_k=settings.bge_db_top_k)
    except Exception as exc:
        errors.append(f"BGE DB search failed: {exc}")
        bge_results = []

    return {
        "bge_upsert_result": upsert_result,
        "bge_results": bge_results,
        "errors": errors,
    }


def _pack_materials(state: SearchAgentState) -> str:
    materials: list[str] = []

    # Prefer BGE vector DB retrieval results.
    for idx, item in enumerate(state.get("bge_results", [])[: settings.evidence_top_k], start=1):
        materials.append(
            f"""
[BGE-{idx}]
title: {item.get('title', '')}
url: {item.get('url', '')}
score: {item.get('score', '')}
content:
{(item.get('text') or '')[:4000]}
""".strip()
        )

    # Fallback / supplement from crawled pages.
    offset = len(materials)
    for idx, page in enumerate(state.get("pages", [])[: settings.evidence_top_k], start=1):
        content = page.get("content") or page.get("snippet") or ""
        if not content.strip():
            continue
        materials.append(
            f"""
[PAGE-{offset + idx}]
title: {page.get('title', '')}
url: {page.get('url', '')}
content:
{content[:4000]}
""".strip()
        )

    return "\n\n".join(materials)


async def select_evidence_node(state: SearchAgentState) -> dict[str, Any]:
    question = state["question"]
    materials = _pack_materials(state)

    if not materials.strip():
        return {
            "evidence": [],
            "need_more": state.get("iteration", 0) < settings.max_iterations,
            "missing": "没有可用网页正文或 BGE 检索结果。",
        }

    system = """
你是一个严谨的搜索证据筛选器。你只能基于给定材料抽取证据，不要编造。
输出 JSON，不要输出 Markdown。
""".strip()

    user = f"""
用户问题：
{question}

候选材料：
{materials}

请输出：
{{
  "evidence": [
    {{
      "source_id": "BGE-1 或 PAGE-1",
      "title": "来源标题",
      "url": "来源 URL",
      "quote_or_summary": "证据摘要，必须来自材料",
      "supports": "这条证据支持什么结论"
    }}
  ],
  "need_more": false,
  "missing": "如果信息不足，说明还缺什么；否则为空字符串"
}}
""".strip()

    data = await llm.json_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )

    evidence = data.get("evidence") or []
    need_more = bool(data.get("need_more", False))
    missing = str(data.get("missing") or "")

    return {
        "evidence": evidence[: settings.evidence_top_k],
        "need_more": need_more,
        "missing": missing,
    }


async def answer_node(state: SearchAgentState) -> dict[str, Any]:
    question = state["question"]
    evidence = state.get("evidence", [])
    errors = state.get("errors", [])

    system = """
你是一个联网搜索智能体。请用中文回答。
必须遵守：
- 只基于 evidence 回答，不要编造。
- 关键结论后使用 [1]、[2] 这样的引用编号。
- 如果 evidence 不足，直接说明不足。
- 最后输出 Sources，包含编号、标题、URL。
""".strip()

    user = f"""
用户问题：
{question}

证据列表：
{evidence}

检索/抓取错误，仅用于判断可靠性，不要逐条展开：
{errors}
""".strip()

    answer = await llm.chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=3072,
    )

    return {"answer": answer}


def should_continue(state: SearchAgentState) -> Literal["plan_queries", "answer"]:
    need_more = state.get("need_more", False)
    iteration = state.get("iteration", 0)
    mode = state.get("mode", "fast")
    max_iterations = settings.max_iterations if mode == "deep" else 1

    if need_more and iteration < max_iterations:
        return "plan_queries"
    return "answer"


def build_graph():
    graph = StateGraph(SearchAgentState)

    graph.add_node("plan_queries", plan_queries)
    graph.add_node("search", search_node)
    graph.add_node("crawl", crawl_node)
    graph.add_node("bge_upsert_and_search", bge_upsert_and_search_node)
    graph.add_node("select_evidence", select_evidence_node)
    graph.add_node("answer", answer_node)

    graph.add_edge(START, "plan_queries")
    graph.add_edge("plan_queries", "search")
    graph.add_edge("search", "crawl")
    graph.add_edge("crawl", "bge_upsert_and_search")
    graph.add_edge("bge_upsert_and_search", "select_evidence")
    graph.add_conditional_edges(
        "select_evidence",
        should_continue,
        {
            "plan_queries": "plan_queries",
            "answer": "answer",
        },
    )
    graph.add_edge("answer", END)

    return graph.compile()


search_agent_graph = build_graph()


async def run_search_agent(question: str, mode: Literal["fast", "deep"] = "fast") -> dict[str, Any]:
    return await search_agent_graph.ainvoke(
        {
            "question": question,
            "mode": mode,
            "iteration": 0,
            "need_more": False,
            "errors": [],
        }
    )

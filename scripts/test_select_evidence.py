#!/usr/bin/env python3
"""测试 select_evidence 函数"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ai_search_agent import graph, llm

async def test_select_evidence_empty():
    """测试空材料情况"""
    print("=== 测试空材料 ===")
    state = {
        "question": "测试问题",
        "bge_results": [],
        "pages": [],
        "iteration": 0,
    }
    result = await graph.select_evidence_node(state)
    print(f"结果: {result}")
    assert "evidence" in result
    assert result["evidence"] == []
    print("✓ 空材料测试通过")

async def test_select_evidence_with_bge_results():
    """测试有 BGE 结果的情况"""
    print("\n=== 测试有 BGE 结果 ===")
    state = {
        "question": "罗马天气",
        "bge_results": [
            {"title": "罗马天气预报", "url": "http://example.com", "text": "罗马今天晴天", "score": 0.9},
            {"title": "罗马气候", "url": "http://example.org", "text": "罗马夏季炎热", "score": 0.8},
        ],
        "pages": [],
        "iteration": 0,
    }
    try:
        result = await graph.select_evidence_node(state)
        print(f"结果: {result}")
        print("✓ BGE 结果测试通过")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_select_evidence_with_pages():
    """测试有网页结果的情况"""
    print("\n=== 测试有网页结果 ===")
    state = {
        "question": "北京旅游",
        "bge_results": [],
        "pages": [
            {"title": "北京景点", "url": "http://example.com", "content": "故宫是北京著名景点"},
            {"title": "北京美食", "url": "http://example.org", "content": "北京烤鸭很有名"},
        ],
        "iteration": 0,
    }
    try:
        result = await graph.select_evidence_node(state)
        print(f"结果: {result}")
        print("✓ 网页结果测试通过")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_select_evidence_with_none_items():
    """测试包含 None 的列表"""
    print("\n=== 测试包含 None 的列表 ===")
    state = {
        "question": "测试问题",
        "bge_results": [
            None,  # 测试 None 项
            {"title": "有效结果", "url": "http://example.com", "text": "有效内容", "score": 0.9},
            None,
        ],
        "pages": [
            None,
            {"title": "有效页面", "url": "http://example.org", "content": "有效内容"},
        ],
        "iteration": 0,
    }
    try:
        result = await graph.select_evidence_node(state)
        print(f"结果: {result}")
        print("✓ None 项测试通过")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await test_select_evidence_empty()
    await test_select_evidence_with_none_items()
    # 下面两个测试需要 LLM，可能会失败
    # await test_select_evidence_with_bge_results()
    # await test_select_evidence_with_pages()
    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""测试 _pack_materials 函数"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ai_search_agent import graph

def test_pack_materials_empty():
    """测试空状态"""
    print("=== 测试空状态 ===")
    state = {"bge_results": [], "pages": []}
    result = graph._pack_materials(state)
    print(f"结果长度: {len(result)}")
    print("✓ 通过")

def test_pack_materials_with_none():
    """测试包含 None 的列表"""
    print("\n=== 测试包含 None 的列表 ===")
    state = {
        "bge_results": [
            None,
            {"title": "Test", "url": "http://example.com", "text": "content", "score": 0.9},
            None,
        ],
        "pages": [None, {"title": "Page", "url": "http://page.com", "content": "page content"}]
    }
    try:
        result = graph._pack_materials(state)
        print(f"结果长度: {len(result)}")
        print(f"结果内容:\n{result}")
        print("✓ 通过")
    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()

def test_pack_materials_normal():
    """测试正常数据"""
    print("\n=== 测试正常数据 ===")
    state = {
        "bge_results": [
            {"title": "BGE Result", "url": "http://bge.com", "text": "BGE content", "score": 0.9},
        ],
        "pages": [
            {"title": "Page Result", "url": "http://page.com", "content": "Page content"},
        ]
    }
    try:
        result = graph._pack_materials(state)
        print(f"结果长度: {len(result)}")
        print("✓ 通过")
    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pack_materials_empty()
    test_pack_materials_with_none()
    test_pack_materials_normal()
    print("\n所有测试完成!")

#!/usr/bin/env python3
"""测试 BGE DB 搜索功能"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ai_search_agent import bge_db, config

async def test_bge_embeddings():
    """测试 BGE 向量化服务"""
    print("=== 测试 BGE 向量化服务 ===")
    try:
        embeddings = await bge_db.get_embeddings(["测试文本"])
        print(f"Embeddings 长度: {len(embeddings)}")
        if embeddings:
            print(f"向量维度: {len(embeddings[0])}")
            return True
        else:
            print("ERROR: 获取到空的 embeddings")
            return False
    except Exception as e:
        print(f"ERROR: 获取 embeddings 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_milvus_init():
    """测试 Milvus Lite 初始化"""
    print("\n=== 测试 Milvus Lite 初始化 ===")
    try:
        bge_db.bge_db._init()
        print("Milvus 初始化成功")
        print(f"DB 路径: {bge_db.bge_db.db_path}")
        print(f"Collection: {bge_db.bge_db.collection_name}")
        return True
    except Exception as e:
        print(f"ERROR: Milvus 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_milvus_search():
    """测试 Milvus 搜索"""
    print("\n=== 测试 Milvus 搜索 ===")
    try:
        # 先确保初始化
        bge_db.bge_db._init()
        
        # 尝试搜索
        results = await bge_db.bge_db.search("测试查询")
        print(f"搜索结果数量: {len(results)}")
        if results:
            for r in results:
                print(f"  - {r.get('title')} (score: {r.get('score', 0):.3f})")
        else:
            print("警告: 没有搜索结果（可能数据库为空）")
        return True
    except Exception as e:
        print(f"ERROR: Milvus 搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_full_search():
    """测试完整的 BGE DB 搜索流程"""
    print("\n=== 测试完整 BGE DB 搜索流程 ===")
    try:
        results = await bge_db.bge_db.search("罗马天气")
        print(f"搜索结果: {len(results)}")
        return True
    except Exception as e:
        print(f"ERROR: BGE DB search failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("当前配置:")
    print(f"  BGE URL: {config.settings.bge_url}")
    print(f"  BGE Model: {config.settings.bge_model}")
    print(f"  BGE DB Enabled: {config.settings.bge_db_enabled}")
    print(f"  BGE DB Path: {config.settings.bge_db_path}")
    print(f"  BGE DB Collection: {config.settings.bge_db_collection}")
    print()

    # 运行所有测试
    tests = [
        test_bge_embeddings,
        test_milvus_init,
        test_milvus_search,
        test_full_search
    ]

    for test in tests:
        await test()
        print()

if __name__ == "__main__":
    asyncio.run(main())

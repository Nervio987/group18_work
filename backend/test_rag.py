"""RAG 全流程测试脚本"""

import os
import sys
import time

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(__file__))

from document_parser import parse_document
from text_splitter import split_text
from opensearch_store import add_documents, search, ensure_index, clear_index
from web_search import web_search
from rag_chain import rag_query
from conversation_store import init_db, get_history, clear_session


def test_text_splitter():
    print("=" * 60)
    print("测试 1: 文本切片")
    print("=" * 60)
    text = """
人工智能（Artificial Intelligence，简称AI）是计算机科学的一个分支，
它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。

人工智能研究的领域包括机器人、语言识别、图像识别、自然语言处理和专家系统等。
人工智能从诞生以来，理论和技术日益成熟，应用领域也不断扩大。

深度学习是机器学习的分支，是一种以人工神经网络为架构，对数据进行表征学习的算法。
深度学习在语音识别、计算机视觉、自然语言处理等领域取得了突破性进展。

大语言模型（LLM）是深度学习在自然语言处理领域的重要应用。
通过海量文本数据训练，大语言模型能够理解和生成人类语言，
在问答、翻译、摘要、代码生成等任务中表现出色。

检索增强生成（RAG, Retrieval-Augmented Generation）是一种结合信息检索和文本生成的技术。
RAG 通过先从知识库中检索相关信息，再将检索结果作为上下文提供给大语言模型，
从而让模型生成更准确、更有依据的回答。

向量数据库是 RAG 系统的核心组件之一。它将文本转换为高维向量，
通过向量相似度搜索快速找到与查询最相关的文档片段。
常见的向量数据库有 OpenSearch、Milvus、Chroma 等。
""" * 3

    chunks = split_text(text, chunk_size=300, chunk_overlap=50)
    print(f"  原文长度: {len(text)}")
    print(f"  切片数量: {len(chunks)}")
    for i, c in enumerate(chunks[:3]):
        print(f"  切片{i+1} (len={len(c)}): {c[:80]}...")
    print("  [PASS] 文本切片测试通过\n")


def test_embedder():
    print("=" * 60)
    print("测试 2: 向量嵌入 (nomic-embed-text)")
    print("=" * 60)
    from embedder import embed_text
    vec = embed_text("人工智能是什么？")
    print(f"  向量维度: {len(vec)}")
    print(f"  前5个值: {vec[:5]}")
    assert len(vec) == 768, f"维度不对: {len(vec)}"
    print("  [PASS] 向量嵌入测试通过\n")


def test_opensearch():
    print("=" * 60)
    print("测试 3: OpenSearch 存储与检索")
    print("=" * 60)

    # 清空旧索引
    clear_index()
    time.sleep(1)
    ensure_index()

    # 写入测试文档
    docs = [
        "人工智能（AI）是计算机科学的一个分支，研究如何使机器具备智能行为。",
        "深度学习是机器学习的子领域，使用多层神经网络进行特征学习。",
        "大语言模型（LLM）通过海量文本训练，能够理解和生成自然语言。",
        "RAG（检索增强生成）结合检索和生成，提高回答的准确性。",
        "向量数据库将文本编码为向量，通过相似度搜索实现高效检索。",
        "OpenSearch 是一个开源的搜索和分析引擎，支持向量检索功能。",
        "SearXNG 是一个开源的元搜索引擎，可以聚合多个搜索引擎的结果。",
        "MinerU 是一个文档解析工具，可以将 PDF 转换为 Markdown 格式。",
    ]

    count = add_documents(docs, source="test")
    print(f"  写入文档数: {count}")
    time.sleep(2)  # 等待索引刷新

    # 检索测试
    results = search("什么是RAG？", top_k=3)
    print(f"  检索结果数: {len(results)}")
    for i, r in enumerate(results):
        print(f"  [{i+1}] score={r['score']:.4f}: {r['content'][:60]}...")
    print("  [PASS] OpenSearch 存储与检索测试通过\n")


def test_web_search():
    print("=" * 60)
    print("测试 4: SearXNG 联网搜索")
    print("=" * 60)
    results = web_search("RAG 检索增强生成", count=3)
    print(f"  搜索结果数: {len(results)}")
    for i, r in enumerate(results):
        print(f"  [{i+1}] {r['title'][:50]}")
        print(f"      {r['url'][:80]}")
    print("  [PASS] 联网搜索测试通过\n")


def test_rag_chain():
    print("=" * 60)
    print("测试 5: RAG 完整链路")
    print("=" * 60)

    session_id = "test_session"
    clear_session(session_id)

    # 先确保索引中有数据
    ensure_index()

    answer = rag_query("RAG是什么技术？", session_id=session_id, use_web=False)
    print(f"  回答:\n  {answer[:300]}...")

    # 检查历史
    history = get_history(session_id)
    print(f"  对话历史轮数: {len(history) // 2}")
    print("  [PASS] RAG 完整链路测试通过\n")


def test_document_pipeline():
    print("=" * 60)
    print("测试 6: 文档上传→解析→切片→索引→检索 全流程")
    print("=" * 60)

    # 创建一个测试 MD 文件
    test_md = os.path.join(os.path.dirname(__file__), "test_doc.md")
    with open(test_md, "w", encoding="utf-8") as f:
        f.write("""# RAG 技术详解

## 什么是 RAG

检索增强生成（Retrieval-Augmented Generation，RAG）是一种将信息检索与大语言模型相结合的技术范式。

## RAG 的工作原理

RAG 系统通常包含以下核心组件：

1. **文档解析**：将 PDF、Word 等格式的文档转换为纯文本或 Markdown
2. **文本切片**：将长文档切分为适当大小的片段
3. **向量嵌入**：使用嵌入模型将文本片段转换为高维向量
4. **向量存储**：将向量存入向量数据库（如 OpenSearch、Milvus）
5. **检索**：根据用户查询的向量，在数据库中检索最相似的片段
6. **生成**：将检索结果作为上下文，由 LLM 生成最终回答

## RAG 的优势

- 减少幻觉：基于真实文档回答，降低模型编造信息的风险
- 知识更新：无需重新训练模型，更新文档库即可
- 可追溯性：可以追溯回答的信息来源
- 成本控制：相比微调，RAG 的部署成本更低

## 常用工具

- MinerU：文档解析（PDF → Markdown）
- nomic-embed-text：文本向量嵌入
- OpenSearch：向量存储与检索
- SearXNG：联网搜索补充
- Ollama：本地 LLM 推理
""")

    # 解析
    text = parse_document(test_md)
    print(f"  文档解析成功，长度: {len(text)}")

    # 切片
    chunks = split_text(text)
    print(f"  切片数量: {len(chunks)}")

    # 入库
    count = add_documents(chunks, source="test_doc.md")
    print(f"  入库文档数: {count}")
    time.sleep(2)

    # 检索
    results = search("RAG的优势有哪些", top_k=3)
    print(f"  检索结果: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"  [{i+1}] {r['content'][:80]}...")

    # 清理测试文件
    os.remove(test_md)
    print("  [PASS] 文档全流程测试通过\n")


def main():
    print("\n" + "=" * 60)
    print("  RAG 全流程测试开始")
    print("=" * 60 + "\n")

    # 初始化数据库
    init_db()

    tests = [
        ("文本切片", test_text_splitter),
        ("向量嵌入", test_embedder),
        ("OpenSearch", test_opensearch),
        ("联网搜索", test_web_search),
        ("RAG链路", test_rag_chain),
        ("文档全流程", test_document_pipeline),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name} 测试失败: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"测试完成: {passed} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    main()

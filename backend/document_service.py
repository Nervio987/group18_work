"""文档处理服务：解析 → 切片 → 向量化 → 存储 一站式管线"""

from document_parser import parse_document
from text_splitter import split_text
from embedder import embed_batch
from opensearch_store import add_documents


def process_document(file_path: str, kb_id: int, source: str) -> dict:
    """
    完整的文档处理管线：
    1. 解析文档为 Markdown/纯文本（MinerU API 或本地）
    2. 智能语义切片
    3. 批量向量化
    4. 存入 OpenSearch

    Args:
        file_path: 文档文件路径
        kb_id: 知识库 ID
        source: 来源标识（通常是文件名）

    Returns:
        {"success": bool, "chunk_count": int, "error": str|None, "content": str|None}
    """
    try:
        # 1. 解析文档
        print(f"[DocumentService] 开始解析: {source}")
        md_content = parse_document(file_path)
        if not md_content or not md_content.strip():
            return {"success": False, "error": "文档解析结果为空", "chunk_count": 0}

        print(f"[DocumentService] 解析完成，长度: {len(md_content)} 字符")

        # 2. 文本切片
        chunks = split_text(md_content)
        if not chunks:
            return {"success": False, "error": "文本切片结果为空", "chunk_count": 0}

        print(f"[DocumentService] 切片完成，共 {len(chunks)} 个片段")

        # 3. 批量向量化
        vectors = embed_batch(chunks)
        print(f"[DocumentService] 向量化完成，共 {len(vectors)} 个向量")

        # 4. 存入 OpenSearch
        count = add_documents(chunks, source=source, knowledge_base_id=kb_id)
        print(f"[DocumentService] OpenSearch 写入完成，{count} 条")

        return {
            "success": True,
            "chunk_count": len(chunks),
            "content": md_content,
            "error": None,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "chunk_count": 0,
            "error": str(e),
            "content": None,
        }


def regenerate_for_document(file_path: str, source: str, knowledge_base_id: int = None) -> dict:
    """仅重新生成向量（文档已存在，重新切片+向量化+存储）"""
    try:
        md_content = parse_document(file_path)
        chunks = split_text(md_content)
        if not chunks:
            return {"success": False, "error": "切片结果为空", "chunk_count": 0}

        embed_batch(chunks)
        count = add_documents(chunks, source=source, knowledge_base_id=knowledge_base_id)

        return {"success": True, "chunk_count": len(chunks), "error": None}
    except Exception as e:
        return {"success": False, "chunk_count": 0, "error": str(e)}

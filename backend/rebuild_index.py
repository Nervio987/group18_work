"""
重建 OpenSearch 索引并重新导入所有文档
删除旧索引 → 创建新索引（含 knowledge_base_id 字段）→ 重新处理所有文档

用法:
  cd backend
  python rebuild_index.py
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from opensearch_store import _client, OPENSEARCH_INDEX, INDEX_SETTINGS, ensure_index, add_documents
from app.database import SessionLocal
from app import models
from document_parser import parse_document
from text_splitter import split_text
from embedder import embed_batch


def rebuild():
    # 1. 删除旧索引
    if _client.indices.exists(index=OPENSEARCH_INDEX):
        print(f"[Rebuild] 删除旧索引: {OPENSEARCH_INDEX}")
        _client.indices.delete(index=OPENSEARCH_INDEX)

    # 2. 创建新索引
    _client.indices.create(index=OPENSEARCH_INDEX, body=INDEX_SETTINGS)
    print(f"[Rebuild] 创建新索引: {OPENSEARCH_INDEX} (含 knowledge_base_id 字段)")

    # 3. 查询所有已完成的文档
    db = SessionLocal()
    try:
        docs = db.query(models.Document).filter(
            models.Document.status == "completed"
        ).all()
        print(f"[Rebuild] 找到 {len(docs)} 个已完成的文档需要重新导入")

        success_count = 0
        fail_count = 0

        for doc in docs:
            if not os.path.exists(doc.file_path):
                print(f"  [跳过] {doc.filename} (文件不存在)")
                fail_count += 1
                continue

            print(f"  [处理] {doc.filename} (kb_id={doc.knowledge_base_id}) ...", end=" ", flush=True)

            try:
                content = parse_document(doc.file_path)
                chunks = split_text(content)
                if not chunks:
                    print("跳过 (无内容)")
                    fail_count += 1
                    continue

                embed_batch(chunks)
                count = add_documents(chunks, source=doc.filename, knowledge_base_id=doc.knowledge_base_id)

                doc.chunk_count = count
                print(f"完成 ({count} 个片段)")
                success_count += 1
            except Exception as e:
                doc.status = "failed"
                print(f"失败: {e}")
                fail_count += 1

            db.commit()

        print(f"\n[Rebuild] 完成! 成功: {success_count}, 失败: {fail_count}")

    finally:
        db.close()


if __name__ == "__main__":
    rebuild()

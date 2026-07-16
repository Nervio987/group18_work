"""OpenSearch 向量存储与检索模块"""

import uuid
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
from urllib3.exceptions import InsecureRequestWarning
import warnings

from config import (
    OPENSEARCH_HOST, OPENSEARCH_USER, OPENSEARCH_PASSWORD,
    OPENSEARCH_INDEX, TOP_K, EMBED_MODEL, OPENSEARCH_USE_SSL,
    EMBED_DIMENSION,
)
from embedder import embed_text

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

http_auth = (OPENSEARCH_USER, OPENSEARCH_PASSWORD) if OPENSEARCH_USE_SSL else None
_client = OpenSearch(
    hosts=[OPENSEARCH_HOST],
    http_auth=http_auth,
    use_ssl=OPENSEARCH_USE_SSL,
    verify_certs=False,
    connection_class=RequestsHttpConnection,
)

INDEX_SETTINGS = {
    "settings": {
        "index": {
            "knn": True,
        }
    },
    "mappings": {
        "properties": {
            "content": {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": EMBED_DIMENSION,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                },
            },
            "source": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
        }
    },
}


def ensure_index():
    """确保索引存在，且 embedding 维度与当前模型匹配"""
    if not _client.indices.exists(index=OPENSEARCH_INDEX):
        _client.indices.create(index=OPENSEARCH_INDEX, body=INDEX_SETTINGS)
        print(f"[OpenSearch] 创建索引: {OPENSEARCH_INDEX} (dimension={EMBED_DIMENSION})")
        return

    try:
        mapping = _client.indices.get_mapping(index=OPENSEARCH_INDEX)
        current_dim = (
            mapping[OPENSEARCH_INDEX]["mappings"]["properties"]
            .get("embedding", {}).get("dimension")
        )
        if current_dim and current_dim != EMBED_DIMENSION:
            print(
                f"[OpenSearch] 警告: 索引维度不匹配 (现有={current_dim}, 当前模型={EMBED_DIMENSION})，"
                f"自动删除并重建索引 {OPENSEARCH_INDEX}"
            )
            _client.indices.delete(index=OPENSEARCH_INDEX)
            _client.indices.create(index=OPENSEARCH_INDEX, body=INDEX_SETTINGS)
            print(f"[OpenSearch] 重建索引完成 (dimension={EMBED_DIMENSION})")
    except Exception as e:
        print(f"[OpenSearch] 检查索引维度时出错: {e}")


def add_documents(chunks: list[str], source: str = "unknown"):
    """将文本切片存入 OpenSearch"""
    ensure_index()
    docs = []
    for i, chunk in enumerate(chunks):
        vec = embed_text(chunk)
        docs.append({
            "_index": OPENSEARCH_INDEX,
            "_id": str(uuid.uuid4()),
            "_source": {
                "content": chunk,
                "embedding": vec,
                "source": source,
                "chunk_index": i,
            },
        })

    success, errors = bulk(_client, docs)
    print(f"[OpenSearch] 写入 {success} 条文档, 错误 {len(errors)}")
    return success


def search(query: str, top_k: int = TOP_K) -> list[dict]:
    """混合检索：向量相似度 + BM25 关键词匹配，取并集后重排"""
    ensure_index()
    vec = embed_text(query)

    # 1. 向量检索（多取一些候选）
    vector_k = max(top_k * 3, 10)
    vector_body = {
        "size": vector_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": vec,
                    "k": vector_k,
                }
            }
        },
    }
    vector_resp = _client.search(index=OPENSEARCH_INDEX, body=vector_body)
    vector_hits = {h["_id"]: h for h in vector_resp["hits"]["hits"]}

    # 2. BM25 关键词检索（中文分词后用 multi_match）
    bm25_body = {
        "size": vector_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["content"],
                "type": "best_fields",
                "minimum_should_match": "30%",
            }
        },
    }
    try:
        bm25_resp = _client.search(index=OPENSEARCH_INDEX, body=bm25_body)
        bm25_hits = {h["_id"]: h for h in bm25_resp["hits"]["hits"]}
    except Exception:
        bm25_hits = {}

    # 3. 合并结果（RRF 倒数排名融合）
    all_ids = set(vector_hits.keys()) | set(bm25_hits.keys())
    scored = []
    for doc_id in all_ids:
        v_rank = (list(vector_hits.keys()).index(doc_id) + 1) if doc_id in vector_hits else 9999
        b_rank = (list(bm25_hits.keys()).index(doc_id) + 1) if doc_id in bm25_hits else 9999
        rrf_score = 1.0 / (60 + v_rank) + 1.0 / (60 + b_rank)
        hit = vector_hits.get(doc_id) or bm25_hits[doc_id]
        scored.append((rrf_score, hit))

    # 4. 按 RRF 分数排序，取 top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for rrf_score, hit in scored[:top_k]:
        results.append({
            "content": hit["_source"]["content"],
            "source": hit["_source"].get("source", ""),
            "score": rrf_score,
        })
    return results


def clear_index():
    """清空索引"""
    if _client.indices.exists(index=OPENSEARCH_INDEX):
        _client.indices.delete(index=OPENSEARCH_INDEX)
        print(f"[OpenSearch] 已删除索引: {OPENSEARCH_INDEX}")

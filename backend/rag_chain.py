"""RAG 链：查询重述 → 检索 → Rerank 精排 → LLM 流式生成"""

import json
import sys
from config import TOP_K
from opensearch_store import search as vector_search
from web_search import web_search
from conversation_store import save_message, get_history
from query_rewriter import rewrite_query
from reranker import rerank_chunks
from llm_client import chat_completion
from redis_cache import get_search_cache, set_search_cache


def _safe_print(*args, **kwargs):
    """安全打印，忽略 Windows GBK 编码错误"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            print(*(str(a).encode('ascii', errors='replace').decode('ascii') for a in args), **kwargs)
        except Exception:
            pass

SYSTEM_PROMPT = """你是一个智能助手，基于检索到的信息回答问题。
请优先使用本地知识库的参考资料回答，如果本地资料不足以回答，可以结合联网搜索结果补充。
回答时请引用来源。如果参考资料中没有相关信息，请明确说明。"""

_MAX_CONTEXT_LENGTH = 8000


def _truncate_text(text: str, max_len: int) -> str:
    """截断文本并添加省略标记"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def rag_query(query: str, session_id: str = "default", use_web: bool = False,
              use_rerank: bool = True, use_rewrite: bool = True,
              stream_callback=None, provider: str = "api") -> str:
    """
    RAG 完整链路：
    1. 查询重述（多轮对话中补全省略/指代）
    2. 向量检索本地知识库（带缓存）
    3. Rerank 精排（LLM 对检索结果重新打分）
    4. 可选联网搜索
    5. 构建上下文 + 对话历史（带长度限制）
    6. LLM 流式生成
    7. 保存对话历史

    Args:
        provider: "api" = DeepSeek API, "local" = Ollama 本地模型
    """
    # 1. 查询重述
    search_query = query
    if use_rewrite:
        search_query = rewrite_query(query, session_id)

    # 2. 向量检索（带缓存）
    cached_results = get_search_cache(search_query)
    if cached_results:
        local_results = cached_results
        _safe_print(f"[RAG] 命中搜索缓存，返回 {len(local_results)} 条结果")
    else:
        local_results = vector_search(search_query, top_k=TOP_K)
        set_search_cache(search_query, local_results)
        _safe_print(f"[RAG] 向量检索返回 {len(local_results)} 条结果")

    # 3. Rerank 精排
    if use_rerank and len(local_results) > 1:
        local_results = rerank_chunks(search_query, local_results, top_k=3)
        _safe_print(f"[RAG] Rerank 精排后保留 {len(local_results)} 条结果")

    # 4. 构建上下文（截断过长内容）
    context_parts = []
    for i, r in enumerate(local_results, 1):
        content = _truncate_text(r.get("content", ""), 2000)
        context_parts.append(f"[{i}] (来源: {r.get('source', '')}) {content}")

    # 5. 可选联网搜索
    if use_web:
        web_results = web_search(query)
        for i, r in enumerate(web_results, len(context_parts) + 1):
            content = _truncate_text(r.get("content", ""), 500)
            context_parts.append(f"[{i}] (来源: {r.get('url', '')}) {r.get('title', '')}: {content}")

    if context_parts:
        context = "\n\n".join(context_parts)
        context = _truncate_text(context, _MAX_CONTEXT_LENGTH)
    else:
        context = "暂无相关参考资料。"

    # 6. 获取对话历史（限制长度）
    history = get_history(session_id)

    # 7. 构建消息列表（计算 token 消耗，避免超过限制）
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    history_text = ""
    for msg in history:
        msg_text = f"{msg['role']}: {msg['content']}\n"
        if len(history_text) + len(msg_text) < 3000:
            history_text += msg_text
            messages.append(msg)

    user_msg = f"参考资料：\n{context}\n\n问题：{query}"
    messages.append({"role": "user", "content": user_msg})

    # 8. 调用 LLM（API 或本地模型）
    model_label = "Ollama 本地" if provider == "local" else LLM_MODEL if 'LLM_MODEL' in dir() else "DeepSeek"
    _safe_print(f"\n[RAG] 调用 {model_label} 生成回答...\n", flush=True)

    answer = chat_completion(
        messages=messages,
        provider=provider,
        stream=True,
        stream_callback=stream_callback or (lambda ctype, t: _safe_print(t, end="", flush=True)),
        timeout=120 if provider == "local" else 60,
    )

    _safe_print()
    _safe_print(f"\n[RAG] 生成完毕，共 {len(answer)} 字符", flush=True)

    # 9. 保存对话历史
    save_message(session_id, "user", query)
    save_message(session_id, "assistant", answer)

    return answer

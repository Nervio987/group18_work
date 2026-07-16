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

# 模块描述映射（用于 prompt 和模块隔离）
MODULE_DESCRIPTIONS = {
    "policy": "规章制度",
    "tech": "产品技术",
    "admin": "行政服务",
    "general": "自由问答",
}

# 各模块的 System Prompt（非自由问答模块限定回答范围）
MODULE_SYSTEM_PROMPTS = {
    "policy": """你是一个企业规章制度助手，专注于回答与企业规章制度、流程规范、管理制度相关的问题。
你的职责范围：报销流程、请假制度、考勤规定、差旅标准、加班申请、合同管理、奖惩条例、晋升通道、培训制度等。
如果用户的问题不属于规章制度范畴（如天气、闲聊、技术问题等），请礼貌地说明这超出了你的职责范围，并建议用户切换到"自由问答"模块。
请优先使用本地知识库的参考资料回答，回答时请引用来源。""",
    "tech": """你是一个产品技术助手，专注于回答与技术文档、产品手册、API说明、开发规范相关的问题。
你的职责范围：系统架构、API接口、数据库设计、部署运维、安全规范、性能优化、故障排查、CI/CD、微服务等。
如果用户的问题不属于技术范畴（如天气、闲聊、行政制度等），请礼貌地说明这超出了你的职责范围，并建议用户切换到对应模块。
请优先使用本地知识库的参考资料回答，回答时请引用来源。""",
    "admin": """你是一个行政服务助手，专注于回答与办公场地、IT支持、福利政策、行政事务相关的问题。
你的职责范围：办公场地申请、IT设备报修、员工福利、会议室预定、办公用品领取、考勤管理、差旅报销、员工入离职等。
如果用户的问题不属于行政服务范畴（如天气、闲聊、技术架构等），请礼貌地说明这超出了你的职责范围，并建议用户切换到对应模块。
请优先使用本地知识库的参考资料回答，回答时请引用来源。""",
    "general": """你是一个智能助手，基于检索到的信息回答问题。
请优先使用本地知识库的参考资料回答，如果本地资料不足以回答，可以结合联网搜索结果补充。
回答时请引用来源。如果参考资料中没有相关信息，请明确说明。""",
}

_MAX_CONTEXT_LENGTH = 8000


def _truncate_text(text: str, max_len: int) -> str:
    """截断文本并添加省略标记"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def rag_query(query: str, session_id: str = "default", use_web: bool = False,
              use_rerank: bool = True, use_rewrite: bool = True,
              stream_callback=None, provider: str = "api",
              module: str = "general", knowledge_base_ids: list = None) -> str:
    """
    RAG 完整链路：
    1. 查询重述（多轮对话中补全省略/指代）
    2. 向量检索本地知识库（带缓存，支持模块隔离）
    3. Rerank 精排（LLM 对检索结果重新打分）
    4. 可选联网搜索
    5. 构建上下文 + 对话历史（带长度限制）
    6. LLM 流式生成
    7. 保存对话历史

    Args:
        provider: "api" = DeepSeek API, "local" = Ollama 本地模型
        module: 当前模块 (policy/tech/admin/general)
        knowledge_base_ids: 限定的知识库 ID 列表，None 表示按模块自动选择
    """
    # 获取系统 prompt
    system_prompt = MODULE_SYSTEM_PROMPTS.get(module, MODULE_SYSTEM_PROMPTS["general"])

    # 1. 查询重述
    search_query = query
    if use_rewrite:
        search_query = rewrite_query(query, session_id)

    # 2. 向量检索（带缓存，支持知识库过滤）
    cache_key = f"{search_query}|{','.join(map(str, knowledge_base_ids))}" if knowledge_base_ids else search_query
    cached_results = get_search_cache(cache_key)
    if cached_results:
        local_results = cached_results
        _safe_print(f"[RAG] 命中搜索缓存，返回 {len(local_results)} 条结果")
    else:
        local_results = vector_search(search_query, top_k=TOP_K, knowledge_base_ids=knowledge_base_ids)
        set_search_cache(cache_key, local_results)
        _safe_print(f"[RAG] 向量检索返回 {len(local_results)} 条结果 (kb_ids={knowledge_base_ids})")

    # 3. Rerank 精排
    if use_rerank and len(local_results) > 1:
        local_results = rerank_chunks(search_query, local_results, top_k=3)
        _safe_print(f"[RAG] Rerank 精排后保留 {len(local_results)} 条结果")

    # 4. 构建上下文（截断过长内容）
    context_parts = []
    for i, r in enumerate(local_results, 1):
        content = _truncate_text(r.get("content", ""), 2000)
        context_parts.append(f"[{i}] (来源: {r.get('source', '')}) {content}")

    # 5. 可选联网搜索（自由问答模块默认允许，其他模块仅在知识库无结果时）
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
    messages = [{"role": "system", "content": system_prompt}]
    
    history_text = ""
    for msg in history:
        msg_text = f"{msg['role']}: {msg['content']}\n"
        if len(history_text) + len(msg_text) < 3000:
            history_text += msg_text
            messages.append(msg)

    user_msg = f"参考资料：\n{context}\n\n问题：{query}"
    messages.append({"role": "user", "content": user_msg})

    # 8. 调用 LLM（API 或本地模型）
    from config import LLM_MODEL
    model_label = "Ollama 本地" if provider == "local" else LLM_MODEL
    _safe_print(f"\n[RAG] 调用 {model_label} 生成回答 (模块: {module})...\n", flush=True)

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

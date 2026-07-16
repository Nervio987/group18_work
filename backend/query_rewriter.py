"""查询重述模块：用 LLM 将用户的口语化/省略查询重写为完整检索查询"""

import json
import requests
from config import DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, LLM_MODEL
from conversation_store import get_history

_headers = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json",
}

REWRITE_PROMPT = """你是一个查询重写助手。用户在多轮对话中可能会使用省略、指代或口语化的表达。
请根据对话历史，将用户的最新查询重写为一个完整的、适合检索的独立查询。

规则：
- 补全省略的主语、宾语等
- 将代词（他、它、这个、那个）替换为具体指代的内容
- 保持原意不变，不要添加额外信息
- 只输出重写后的查询，不要解释

对话历史：
{history}

用户最新查询：{query}

重写后的查询："""


def rewrite_query(query: str, session_id: str = "default") -> str:
    """
    将用户查询重写为适合检索的完整查询。

    Args:
        query: 用户原始查询
        session_id: 会话 ID，用于获取对话历史

    Returns:
        重写后的查询（如果重写失败则返回原始查询）
    """
    # 获取对话历史
    history = get_history(session_id, turns=5)

    # 如果没有历史，不需要重写
    if not history:
        return query

    # 构建历史文本
    history_text = "\n".join([
        f"{'用户' if msg['role'] == 'user' else '助手'}: {msg['content']}"
        for msg in history
    ])

    prompt = REWRITE_PROMPT.format(history=history_text, query=query)

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers=_headers,
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        rewritten = result["choices"][0]["message"]["content"].strip()

        # 如果重写结果为空或太短，使用原始查询
        if rewritten and len(rewritten) > 2:
            print(f"[QueryRewrite] \"{query}\" → \"{rewritten}\"")
            return rewritten

    except Exception as e:
        print(f"[QueryRewrite] 重写失败，使用原始查询: {e}")

    return query

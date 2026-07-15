"""Rerank 精排模块：用 LLM 对检索结果重新打分排序"""

import json
import requests
from config import DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, LLM_MODEL

_headers = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json",
}

RERANK_PROMPT = """请根据用户查询，对以下文档片段的相关性进行打分（0-10分）。
返回 JSON 格式，按分数从高到低排序。

用户查询：{query}

文档片段：
{chunks}

请返回如下 JSON 格式（只返回 JSON，不要其他内容）：
[{{"index": 原始序号, "score": 分数, "reason": "简短理由"}}]
"""


def rerank_chunks(query: str, chunks: list[dict], top_k: int = 3) -> list[dict]:
    """
    用 LLM 对检索结果重新打分排序。

    Args:
        query: 用户查询
        chunks: 检索结果列表，每项包含 content, source, score 等
        top_k: 返回前 k 个

    Returns:
        重新排序后的 chunks 列表
    """
    if not chunks:
        return []

    # 构建文档片段文本
    chunks_text = "\n".join([
        f"[{i}] (来源: {c.get('source', 'unknown')}) {c['content']}"
        for i, c in enumerate(chunks)
    ])

    prompt = RERANK_PROMPT.format(query=query, chunks=chunks_text)

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers=_headers,
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        # 解析 JSON
        # 提取 JSON 部分（可能被 markdown 代码块包裹）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        scores = json.loads(content.strip())

        # 按分数排序
        scores.sort(key=lambda x: x.get("score", 0), reverse=True)

        # 映射回原始 chunks
        reranked = []
        for s in scores:
            idx = s.get("index", 0)
            if 0 <= idx < len(chunks):
                chunk = chunks[idx].copy()
                chunk["rerank_score"] = s.get("score", 0)
                chunk["rerank_reason"] = s.get("reason", "")
                reranked.append(chunk)

        return reranked[:top_k]

    except Exception as e:
        print(f"[Rerank] 精排失败，使用原始排序: {e}")
        return chunks[:top_k]

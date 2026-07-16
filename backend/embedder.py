"""向量嵌入模块：使用 Ollama embedding 模型"""

import time
import requests
from config import OLLAMA_HOST, EMBED_MODEL

_MAX_RETRIES = 3
_RETRY_DELAY = 2


def _safe_request(url: str, payload: dict, timeout: int) -> requests.Response:
    """带重试的安全请求"""
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 404:
                raise requests.HTTPError(f"模型 {EMBED_MODEL} 未找到，请先运行 `ollama pull {EMBED_MODEL}`")
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (attempt + 1))
    raise last_error


def embed_text(text: str) -> list[float]:
    """将文本转换为向量（调用 /api/embed 接口）"""
    if not text or not text.strip():
        return [0.0] * 1024
    
    resp = _safe_request(
        f"{OLLAMA_HOST}/api/embed",
        {"model": EMBED_MODEL, "input": text.strip()[:4000]},
        timeout=60,
    )
    data = resp.json()
    return data["embeddings"][0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """批量嵌入"""
    valid_texts = [t.strip()[:4000] for t in texts if t and t.strip()]
    
    if not valid_texts:
        return [[0.0] * 1024 for _ in texts]
    
    resp = _safe_request(
        f"{OLLAMA_HOST}/api/embed",
        {"model": EMBED_MODEL, "input": valid_texts},
        timeout=120,
    )
    embeddings = resp.json()["embeddings"]
    
    result = []
    idx = 0
    for t in texts:
        if t and t.strip():
            result.append(embeddings[idx])
            idx += 1
        else:
            result.append([0.0] * 1024)
    return result

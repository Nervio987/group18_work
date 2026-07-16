"""LLM 调用模块：支持 DeepSeek API 和 Ollama 本地模型"""

import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import SSLError, ConnectionError, Timeout
from config import (
    DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, LLM_MODEL,
    OLLAMA_HOST, OLLAMA_CHAT_MODEL,
)


def _build_session() -> requests.Session:
    """构造带重试机制的 Session（针对 SSL/连接错误）"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_SESSION = _build_session()


def _safe_request(method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
    """带 SSL 重试的安全请求，自动切换到本地 Ollama 兜底"""
    global _SESSION
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = _SESSION.request(method, url, **kwargs)
            return resp
        except (SSLError, ConnectionError, Timeout) as e:
            last_err = e
            wait = 2 ** (attempt - 1)
            print(f"[LLM] 网络异常 (第{attempt}/{max_retries}次): {type(e).__name__}: {e}，{wait}s 后重试")
            if attempt < max_retries:
                time.sleep(wait)
            # SSL EOF 错误时刷新 session 强制重建连接池
            if isinstance(e, SSLError):
                _SESSION = _build_session()
    raise last_err


def _ollama_chat(messages: list[dict], stream: bool = False,
                 stream_callback=None, timeout: int = 120) -> str:
    """通过 Ollama 本地模型生成回答"""
    # 将 messages 转换为 Ollama prompt 格式
    system_prompt = ""
    user_prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        elif msg["role"] == "user":
            user_prompt = msg["content"]

    payload = {
        "model": OLLAMA_CHAT_MODEL,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": stream,
        "options": {
            "temperature": 0.7,
            "num_predict": 2048,
        }
    }

    if stream and stream_callback:
        resp = _safe_request(
            "POST",
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            stream=True,
            timeout=timeout,
        )
        resp.raise_for_status()
        answer = ""
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line.decode("utf-8"))
                token = chunk.get("response", "")
                if token:
                    answer += token
                    stream_callback("content", token)
                if chunk.get("done"):
                    break
            except json.JSONDecodeError:
                continue
        return answer
    else:
        payload["stream"] = False
        resp = _safe_request(
            "POST",
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def _deepseek_chat(messages: list[dict], stream: bool = False,
                   stream_callback=None, tools: list = None,
                   tool_choice: str = None, timeout: int = 60) -> str:
    """通过 DeepSeek API 生成回答"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice

    resp = _safe_request(
        "POST",
        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
        max_retries=3,
        headers=headers,
        json=payload,
        stream=stream,
        timeout=timeout,
    )
    resp.raise_for_status()

    if stream:
        answer = ""
        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8") if isinstance(line, bytes) else line
            if line_str.startswith("data: "):
                line_str = line_str[6:]
            if line_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(line_str)
                delta = chunk.get("choices", [{}])[0].get("delta", {})

                # 推理模型（deepseek-reasoner / deepseek-v4-flash 等）：
                # 思考阶段返回 reasoning_content，思考结束后返回 content
                # 两阶段分别推送，类型标记为 reasoning / content
                reasoning_token = delta.get("reasoning_content", "")
                content_token = delta.get("content", "")

                if reasoning_token and stream_callback:
                    stream_callback("reasoning", reasoning_token)
                if content_token:
                    answer += content_token
                    if stream_callback:
                        stream_callback("content", content_token)
            except json.JSONDecodeError:
                continue
        return answer
    else:
        result = resp.json()
        return result["choices"][0]["message"]["content"]


def deepseek_chat_with_tools(messages: list[dict], tools: list,
                              tool_choice: str = "auto", timeout: int = 60) -> dict:
    """DeepSeek API 带工具调用的非流式请求，返回完整响应对象"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": tool_choice,
    }
    resp = _safe_request(
        "POST",
        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
        max_retries=3,
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def chat_completion(messages: list[dict], provider: str = "api",
                    stream: bool = False, stream_callback=None,
                    tools: list = None, tool_choice: str = None,
                    timeout: int = 120) -> str | dict:
    """
    统一的聊天补全接口

    Args:
        messages: 消息列表 [{"role": "user"/"system"/"assistant", "content": "..."}]
        provider: "api" (DeepSeek) 或 "local" (Ollama)
        stream: 是否流式输出
        stream_callback: 流式回调函数
        tools: 工具列表（仅 api 模式支持 Function Calling）
        tool_choice: 工具选择策略（仅 api 模式）
        timeout: 超时时间

    Returns:
        非流式返回字符串，带 tools 时返回 dict（仅 api 模式）
    """
    if provider == "local":
        return _ollama_chat(messages, stream=stream,
                           stream_callback=stream_callback, timeout=timeout)
    else:
        # DeepSeek API，带 SSL 错误自动 fallback 到本地 Ollama
        try:
            if tools:
                return deepseek_chat_with_tools(messages, tools, tool_choice, timeout)
            return _deepseek_chat(messages, stream=stream,
                                 stream_callback=stream_callback,
                                 tools=tools, tool_choice=tool_choice, timeout=timeout)
        except (SSLError, ConnectionError, Timeout) as e:
            print(f"[LLM] DeepSeek API 不可用 ({type(e).__name__})，自动降级到本地 Ollama: {e}")
            if tools:
                # 工具调用不支持 fallback（Ollama 不支持 Function Calling）
                raise RuntimeError(
                    "DeepSeek API 当前不可用，且本地 Ollama 不支持 Function Calling。"
                    "请稍后重试或切换到 RAG/LangGraph 模式。"
                ) from e
            return _ollama_chat(messages, stream=stream,
                               stream_callback=stream_callback, timeout=timeout)

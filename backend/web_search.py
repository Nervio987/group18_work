"""SearXNG 联网搜索模块"""

import requests
from config import SEARXNG_HOST, SEARXNG_SECRET, WEB_SEARCH_COUNT


def web_search(query: str, count: int = WEB_SEARCH_COUNT) -> list[dict]:
    """通过 SearXNG 搜索（POST + secret），返回标题+摘要+链接"""
    url = f"{SEARXNG_HOST}/search"
    data = {
        "q": query,
        "format": "json",
        "secret": SEARXNG_SECRET,
    }
    try:
        resp = requests.post(url, data=data, timeout=15)
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        print(f"[SearXNG] 搜索失败: {e}")
        return []

    results = []
    for item in result.get("results", [])[:count]:
        results.append({
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "url": item.get("url", ""),
        })
    return results

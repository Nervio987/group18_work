"""Redis 缓存增强模块：热门问题、统计缓存、搜索缓存、速率限制"""

import json
import hashlib
from datetime import datetime, timedelta
import time
import redis
from config import REDIS_HOST, REDIS_PORT


def _get_redis():
    """获取 Redis 连接，失败返回 None（降级模式）"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=1, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception as e:
        print(f"[RedisCache] Redis 连接失败: {e}，降级为内存模式")
        return None


_r = _get_redis()

# 内存降级存储
_mem_hot: dict[str, float] = {}
_mem_search: dict[str, tuple[str, float]] = {}
_mem_stats: tuple[dict, float] | None = None
_mem_rate: dict[str, list[float]] = {}


def _fallback():
    return _r is None


# ========== 热门问题排行（Sorted Set）==========

_HOT_QUESTIONS_KEY = "stats:hot_questions"
_SEARCH_CACHE_PREFIX = "cache:search:"
_STATS_CACHE_KEY = "cache:dashboard_stats"
_RATE_LIMIT_PREFIX = "rate_limit:"
_CACHE_TTL = 300  # 5 分钟
_SEARCH_CACHE_TTL = 600  # 10 分钟


def track_question(query: str):
    """记录用户提问，更新热门问题排行"""
    if not query or len(query) < 2:
        return
    normalized = query.strip()[:100]

    if _fallback():
        _mem_hot[normalized] = _mem_hot.get(normalized, 0) + 1
        return

    try:
        _r.zincrby(_HOT_QUESTIONS_KEY, 1, normalized)
    except Exception as e:
        print(f"[RedisCache] track_question 失败: {e}")


def get_hot_questions(limit: int = 10) -> list[dict]:
    """获取热门问题 Top-N"""
    if _fallback():
        sorted_items = sorted(_mem_hot.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"question": q, "count": int(score)} for q, score in sorted_items]

    try:
        items = _r.zrevrange(_HOT_QUESTIONS_KEY, 0, limit - 1, withscores=True)
        return [{"question": q, "count": int(score)} for q, score in items]
    except Exception as e:
        print(f"[RedisCache] get_hot_questions 失败: {e}")
        return []


# ========== 搜索/检索结果缓存 ==========

def _cache_key(query: str) -> str:
    return f"{_SEARCH_CACHE_PREFIX}{hashlib.md5(query.encode()).hexdigest()}"


def get_search_cache(query: str) -> list[dict] | None:
    """尝试从缓存获取搜索结果"""
    if _fallback():
        key = query
        if key in _mem_search:
            data, expire_at = _mem_search[key]
            if time.time() < expire_at:
                return json.loads(data)
            else:
                del _mem_search[key]
        return None

    try:
        key = _cache_key(query)
        data = _r.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"[RedisCache] get_search_cache 失败: {e}")
        return None


def set_search_cache(query: str, results: list[dict], ttl: int = _SEARCH_CACHE_TTL):
    """缓存搜索结果"""
    if _fallback():
        key = query
        _mem_search[key] = (json.dumps(results, ensure_ascii=False), time.time() + ttl)
        if len(_mem_search) > 100:
            oldest_key = min(_mem_search.keys(), key=lambda k: _mem_search[k][1])
            del _mem_search[oldest_key]
        return

    try:
        key = _cache_key(query)
        _r.setex(key, ttl, json.dumps(results, ensure_ascii=False))
    except Exception as e:
        print(f"[RedisCache] set_search_cache 失败: {e}")


# ========== Dashboard 统计缓存 ==========

def get_dashboard_stats() -> dict | None:
    """获取缓存的仪表盘统计数据"""
    if _fallback():
        global _mem_stats
        if _mem_stats:
            data, expire_at = _mem_stats
            if time.time() < expire_at:
                return data
            else:
                _mem_stats = None
        return None

    try:
        data = _r.get(_STATS_CACHE_KEY)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"[RedisCache] get_dashboard_stats 失败: {e}")
        return None


def set_dashboard_stats(stats: dict, ttl: int = _CACHE_TTL):
    """缓存仪表盘统计数据"""
    if _fallback():
        global _mem_stats
        _mem_stats = (stats, time.time() + ttl)
        return

    try:
        _r.setex(_STATS_CACHE_KEY, ttl, json.dumps(stats))
    except Exception as e:
        print(f"[RedisCache] set_dashboard_stats 失败: {e}")


def invalidate_stats():
    """使统计缓存失效"""
    if _fallback():
        global _mem_stats
        _mem_stats = None
        return

    try:
        _r.delete(_STATS_CACHE_KEY)
    except Exception as e:
        print(f"[RedisCache] invalidate_stats 失败: {e}")


# ========== 速率限制 ==========

def check_rate_limit(user_id: int, endpoint: str = "chat",
                     max_requests: int = 30, window_seconds: int = 60) -> tuple[bool, int]:
    """检查用户速率限制，返回 (是否允许, 剩余次数)"""
    if _fallback():
        key = f"{endpoint}:{user_id}"
        now = time.time()
        if key not in _mem_rate:
            _mem_rate[key] = []
        _mem_rate[key] = [t for t in _mem_rate[key] if now - t < window_seconds]
        count = len(_mem_rate[key])
        remaining = max_requests - count
        if remaining <= 0:
            return False, 0
        _mem_rate[key].append(now)
        return True, remaining - 1

    try:
        key = f"{_RATE_LIMIT_PREFIX}{endpoint}:{user_id}"
        now = datetime.now().timestamp()

        _r.zremrangebyscore(key, 0, now - window_seconds)
        count = _r.zcard(key)
        remaining = max_requests - count

        if remaining <= 0:
            return False, 0

        _r.zadd(key, {str(now): now})
        _r.expire(key, window_seconds * 2)

        return True, remaining - 1
    except Exception as e:
        print(f"[RedisCache] check_rate_limit 失败: {e}，放行请求")
        return True, max_requests

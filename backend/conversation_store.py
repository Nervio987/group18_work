"""对话历史存储模块：Redis"""

import json
from datetime import datetime
import redis
from config import HISTORY_TURNS, REDIS_HOST, REDIS_PORT


def _get_redis():
    """获取 Redis 连接，失败返回 None（降级模式）"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception as e:
        print(f"[ConvStore] Redis 连接失败: {e}，降级为内存模式")
        return None


_r = _get_redis()
_memory_store: dict[str, list[str]] = {}
_memory_sessions: set[str] = set()


def _fallback():
    """检查是否使用内存降级模式"""
    return _r is None


# Redis key 前缀
_KEY_PREFIX = "rag:session:"
# 会话列表 key（记录所有 session_id）
_SESSION_LIST_KEY = "rag:sessions"
# 每条消息的 TTL（30 天自动过期）
_TTL = 30 * 24 * 3600


def init_db():
    """Redis 不需要建表，此函数保持兼容"""
    pass


def save_message(session_id: str, role: str, content: str):
    """保存一条对话消息到 Redis List"""
    msg = json.dumps({
        "role": role,
        "content": content,
        "created_at": datetime.now().isoformat(),
    }, ensure_ascii=False)

    if _fallback():
        key = session_id
        if key not in _memory_store:
            _memory_store[key] = []
        _memory_store[key].append(msg)
        if len(_memory_store[key]) > HISTORY_TURNS * 4:
            _memory_store[key] = _memory_store[key][-HISTORY_TURNS * 2:]
        _memory_sessions.add(key)
        return

    try:
        key = f"{_KEY_PREFIX}{session_id}"
        _r.rpush(key, msg)
        _r.expire(key, _TTL)
        _r.sadd(_SESSION_LIST_KEY, session_id)
        _r.expire(_SESSION_LIST_KEY, _TTL)
    except Exception as e:
        print(f"[ConvStore] 保存消息失败: {e}")


def get_history(session_id: str, turns: int = HISTORY_TURNS) -> list[dict]:
    """获取最近 N 轮对话历史（每轮 = user + assistant = 2 条消息）"""
    if _fallback():
        msgs = _memory_store.get(session_id, [])
        return [json.loads(m) for m in msgs[-turns * 2:]]

    try:
        key = f"{_KEY_PREFIX}{session_id}"
        messages = _r.lrange(key, -turns * 2, -1)
        return [json.loads(m) for m in messages]
    except Exception as e:
        print(f"[ConvStore] 获取历史失败: {e}")
        return []


def clear_session(session_id: str):
    """清除指定会话"""
    if _fallback():
        _memory_store.pop(session_id, None)
        _memory_sessions.discard(session_id)
        return

    try:
        key = f"{_KEY_PREFIX}{session_id}"
        _r.delete(key)
        _r.srem(_SESSION_LIST_KEY, session_id)
    except Exception as e:
        print(f"[ConvStore] 清除会话失败: {e}")


def list_sessions(limit: int = 10) -> list[dict]:
    """列出最近的会话及其最后一条消息时间"""
    if _fallback():
        results = []
        for sid in _memory_sessions:
            msgs = _memory_store.get(sid, [])
            last_time = ""
            if msgs:
                try:
                    last_time = json.loads(msgs[-1]).get("created_at", "")[:19]
                except json.JSONDecodeError:
                    pass
            results.append({"session_id": sid, "last_message_at": last_time})
        results.sort(key=lambda x: x["last_message_at"], reverse=True)
        return results[:limit]

    try:
        session_ids = _r.smembers(_SESSION_LIST_KEY)
        results = []
        for sid in session_ids:
            key = f"{_KEY_PREFIX}{sid}"
            last_msg = _r.lindex(key, -1)
            last_time = ""
            if last_msg:
                try:
                    last_time = json.loads(last_msg).get("created_at", "")[:19]
                except json.JSONDecodeError:
                    pass
            results.append({"session_id": sid, "last_message_at": last_time})
        results.sort(key=lambda x: x["last_message_at"], reverse=True)
        return results[:limit]
    except Exception as e:
        print(f"[ConvStore] 列出会话失败: {e}")
        return []

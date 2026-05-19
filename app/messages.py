"""会话聊天消息的服务端持久化（Redis list + AOF）。

替代「前端每次请求回传 history」：刷新/重进后由服务端恢复多轮上下文。
键：web55:msg:{session_id}，每元素 JSON {role, content, ts}；裁剪到 MAX_MESSAGES。
durability 由 redis AOF（compose 已开 --appendonly yes）保证。

任何 Redis 异常都向上抛 → 调用方降级到「用前端回传 history」，不阻断主流程。
"""
import json
import time

from .redis_client import get_redis

MAX_MESSAGES = 200
_KEY = "web55:msg:{}"
# 与会话 TTL 对齐（秒）；每次写入续期，避免与 sessions/ 清理脱节。
_TTL = 60 * 60 * 24 * 30


def _key(session_id: str) -> str:
    return _KEY.format(session_id)


async def append_message(session_id: str, role: str, content: str) -> None:
    r = await get_redis()
    entry = json.dumps(
        {"role": role, "content": content, "ts": int(time.time() * 1000)},
        ensure_ascii=False,
    )
    k = _key(session_id)
    pipe = r.pipeline()
    pipe.rpush(k, entry)
    pipe.ltrim(k, -MAX_MESSAGES, -1)
    pipe.expire(k, _TTL)
    await pipe.execute()


async def get_messages(session_id: str) -> list[dict]:
    r = await get_redis()
    raw = await r.lrange(_key(session_id), 0, -1)
    out: list[dict] = []
    for item in raw:
        try:
            out.append(json.loads(item))
        except (ValueError, TypeError):
            continue
    return out


async def clear_messages(session_id: str) -> None:
    r = await get_redis()
    await r.delete(_key(session_id))


def to_llm_history(messages: list[dict]) -> list[dict]:
    """会话消息 → parse_command 期望的 [{role:'user'|'assistant', content}]。

    存储用 'bot' 表示助手；LLM 侧用 'assistant'。错误气泡不进上下文。
    """
    hist: list[dict] = []
    for m in messages:
        if m.get("error"):
            continue
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            hist.append({"role": "user", "content": content})
        elif role in ("bot", "assistant"):
            hist.append({"role": "assistant", "content": content})
    return hist

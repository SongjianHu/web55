"""Redis 连接与 arq 队列设置（主应用侧）。

职责边界：Redis 存「工作态/快」——会话消息、任务队列、进度 pub/sub；
durable 元数据（users/sessions/library）由 SQLite 负责（Phase 4）。

未配置/不可达时，调用方应捕获异常做降级（消息持久化退回前端回传 history、
队列退回同步处理）——保证本地无 Redis 也能开发主流程。
"""
import os
from functools import lru_cache

import redis.asyncio as aioredis
from arq.connections import RedisSettings

REDIS_URL = os.getenv("REDIS_URL", "").strip()

# 队列名：web-batch 与 render 分开，避免某 worker 取到自己不认识的 job。
QUEUE_WEB = "web55:web"
QUEUE_RENDER = "web55:render"


def redis_configured() -> bool:
    return bool(REDIS_URL)


@lru_cache(maxsize=1)
def _settings() -> RedisSettings:
    return RedisSettings.from_dsn(REDIS_URL)


def arq_redis_settings() -> RedisSettings:
    if not REDIS_URL:
        raise RuntimeError("未配置 REDIS_URL")
    return _settings()


_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """通用异步 Redis 连接（会话消息 / 进度 pub/sub 用）。单例。"""
    global _pool
    if not REDIS_URL:
        raise RuntimeError("未配置 REDIS_URL")
    if _pool is None:
        _pool = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None

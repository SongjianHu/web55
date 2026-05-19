"""会话 TTL 清理（进程内 APScheduler，无需 Celery/独立进程）。

定期删除 last_active_at 超过 SESSION_TTL_DAYS 的：
  sessions/{id}/ 目录  +  SQLite 会话记录  +  Redis 会话消息键
解决「会话目录无限增长」。仅在 web 主进程启动一次（worker 不启）。
"""
import os
import shutil
import time
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import db

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = BASE_DIR / "sessions"
SESSION_TTL_DAYS = float(os.getenv("SESSION_TTL_DAYS", "14"))

_scheduler: AsyncIOScheduler | None = None


async def purge_expired() -> int:
    cutoff = int((time.time() - SESSION_TTL_DAYS * 86400) * 1000)
    import asyncio

    try:
        ids = await asyncio.to_thread(db.expired_session_ids, cutoff)
    except Exception:
        return 0

    removed = 0
    for sid in ids:
        # 1) 会话目录
        d = WORK_DIR / sid
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        # 2) Redis 会话消息
        try:
            from .messages import clear_messages
            await clear_messages(sid)
        except Exception:
            pass
        # 3) DB 记录
        try:
            await asyncio.to_thread(db.delete_session, sid)
        except Exception:
            pass
        removed += 1
    return removed


def start_scheduler() -> None:
    """web 启动时调用一次；每 6 小时清理一次，并启动后延迟跑一次。"""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(purge_expired, "interval", hours=6, id="purge_expired")
    _scheduler.add_job(
        purge_expired, "date",
        run_date=time.strftime("%Y-%m-%d %H:%M:%S",
                                time.localtime(time.time() + 60)),
        id="purge_expired_initial",
    )
    _scheduler.start()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

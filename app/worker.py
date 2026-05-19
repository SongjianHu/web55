"""web 镜像的 arq worker：处理批量排版 job（需 app 代码，不能放 render 容器）。

启动：  arq app.worker.WorkerSettings
本地原生开发：另开终端运行同一命令即可（Redis 由 docker-compose.dev 提供）。
"""
import asyncio
import os
from pathlib import Path

from arq.connections import RedisSettings

from .batch_core import applied_default_names, run_batch
from .queue import publish_progress
from .redis_client import QUEUE_WEB

BASE_DIR = Path(__file__).resolve().parent.parent
BATCH_DIR = BASE_DIR / "sessions" / "_batch"


async def batch_job(ctx, saved, feature_ids, message, batch_id):
    redis = ctx["redis"]
    job_id = ctx["job_id"]
    loop = asyncio.get_running_loop()
    batch_dir = BATCH_DIR / batch_id

    def progress(done: int, total: int, fn: str):
        payload = {
            "done": done, "total": total, "current": fn,
            "pct": int(done * 100 / total) if total else 100,
        }
        # 同步回调 → 异步发布：跨线程安全地调度到 worker 事件循环
        fut = asyncio.run_coroutine_threadsafe(
            publish_progress(redis, job_id, payload), loop
        )
        try:
            fut.result(timeout=5)
        except Exception:
            pass

    # run_batch 为阻塞（python-docx/LLM）→ 丢线程池，事件循环不被卡
    result = await asyncio.to_thread(
        run_batch, saved, feature_ids, message, batch_dir, progress
    )
    result["batch_id"] = batch_id
    result["applied"] = applied_default_names(feature_ids)
    result["download_url"] = (
        f"/batch/{batch_id}/download" if result["success_count"] > 0 else None
    )
    return result


_REDIS_URL = os.getenv("REDIS_URL", "").strip()


class WorkerSettings:
    functions = [batch_job]
    queue_name = QUEUE_WEB
    # import 期不崩：未配置时退回默认（worker 实际运行时 compose 必注入 REDIS_URL）
    redis_settings = (
        RedisSettings.from_dsn(_REDIS_URL) if _REDIS_URL else RedisSettings()
    )
    keep_result = 3600          # 结果留存 1h，够前端轮询取回
    max_jobs = 4
    job_timeout = 1800          # 大批量留足时间

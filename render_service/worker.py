"""render 镜像的 arq worker：消费异步渲染 job（docx 字节 → pdf 字节）。

同步 HTTP 路径（render_service/main.py）仍是本地调试与 /render/{id}/pdf 的主路径；
本 worker 供批量/大文档/带进度的异步渲染场景（与 web 队列分离，互不串）。

启动：  arq render_service.worker.WorkerSettings
"""
import os

from arq.connections import RedisSettings

from .renderer import render_pdf

REDIS_URL = os.getenv("REDIS_URL", "").strip()
QUEUE_RENDER = "web55:render"


async def render_job(ctx, docx_bytes: bytes) -> bytes:
    return await render_pdf(docx_bytes)


class WorkerSettings:
    functions = [render_job]
    queue_name = QUEUE_RENDER
    redis_settings = (
        RedisSettings.from_dsn(REDIS_URL) if REDIS_URL else RedisSettings()
    )
    keep_result = 1800
    max_jobs = int(os.getenv("RENDER_MAX_CONCURRENCY", "2"))
    job_timeout = int(os.getenv("RENDER_TIMEOUT", "120")) + 30

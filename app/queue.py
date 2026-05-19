"""arq 任务队列封装：入队、查询状态、进度读写。

进度：worker 既 PUBLISH 到频道 web55:progress:{job_id}（SSE 实时透传），
也 SET 到键 web55:progress:{job_id}（轮询/迟到订阅兜底，带 TTL）。

注意：arq 的队列(sorted set)按 queue_name 命名，查 queued/not_found 需带对应
queue_name；批量走 QUEUE_WEB，异步渲染走 QUEUE_RENDER。
"""
import json

from arq import create_pool
from arq.jobs import Job, JobStatus

from .redis_client import QUEUE_RENDER, QUEUE_WEB, arq_redis_settings, get_redis

_PROGRESS_KEY = "web55:progress:{}"
_PROGRESS_TTL = 3600

_pool = None


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(arq_redis_settings())
    return _pool


async def enqueue_batch(saved: list[tuple[str, bytes]], feature_ids: list,
                        message: str, batch_id: str) -> str:
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "batch_job", saved, feature_ids, message, batch_id,
        _queue_name=QUEUE_WEB,
    )
    return job.job_id


async def enqueue_render(docx_bytes: bytes) -> str:
    """异步渲染（供批量/大文档/进度场景；/render/{id}/pdf 仍走同步路径）。"""
    pool = await _get_pool()
    job = await pool.enqueue_job("render_job", docx_bytes, _queue_name=QUEUE_RENDER)
    return job.job_id


_STATUS_MAP = {
    JobStatus.queued: "queued",
    JobStatus.deferred: "queued",
    JobStatus.in_progress: "in_progress",
    JobStatus.complete: "complete",
    JobStatus.not_found: "not_found",
}


async def job_status(job_id: str, queue_name: str = QUEUE_WEB) -> dict:
    pool = await _get_pool()
    job = Job(job_id, pool, _queue_name=queue_name)
    status = await job.status()
    out: dict = {"job_id": job_id, "status": _STATUS_MAP.get(status, str(status))}

    try:
        r = await get_redis()
        p = await r.get(_PROGRESS_KEY.format(job_id))
        if p:
            out["progress"] = json.loads(p)
    except Exception:
        pass

    if status == JobStatus.complete:
        info = await job.result_info()
        if info is not None:
            if info.success:
                out["result"] = info.result
            else:
                out["status"] = "failed"
                out["error"] = str(info.result)
    return out


async def publish_progress(redis, job_id: str, payload: dict) -> None:
    """worker 侧调用：写最新进度 + 发布到频道。redis 为 arq ctx['redis']。"""
    data = json.dumps(payload, ensure_ascii=False)
    try:
        await redis.set(_PROGRESS_KEY.format(job_id), data, ex=_PROGRESS_TTL)
        await redis.publish(f"web55:progress:{job_id}", data)
    except Exception:
        pass

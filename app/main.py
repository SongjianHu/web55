"""
FastAPI 后端：上传、聊天修改、撤销、下载接口 + 静态首页。

版本控制：每次 chat 操作前将 current.docx 快照存入 sessions/{id}/history/，
最多保留 MAX_HISTORY 步，/undo 接口弹出最新快照恢复。
"""
import asyncio
import io
import re as _re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import List

import os as _os

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import json as _json

from . import auth as _auth
from . import db as _db

from .llm_parser import parse_command
from .docx_formatter import (
    apply_operations,
    get_used_paragraph_styles,
    get_document_structure,
    get_document_title,
    get_thesis_label,
    get_thesis_structure,
)
from .schemas import ParsedCommand
from .defaults import get_defaults_metadata, collect_ops, DEFAULTS
from .extract import extract_any
from .knowledge_base import list_knowledge_sources, get_knowledge_source, refresh_knowledge
from .qa import answer_question
from .checker import run_checks
from .openalex_search import search_works as openalex_search_works, default_year_range
from .zotero_save import save_items as zotero_save_items


app = FastAPI(title="Docx Chat Editor")

# 签名 Cookie 会话（最小认证用）。SECRET_KEY 生产务必在 .env 改成随机串。
app.add_middleware(
    SessionMiddleware,
    secret_key=_os.getenv("SECRET_KEY", "dev-only-change-me"),
    same_site="lax",
    https_only=False,   # 由 Caddy 终止 TLS；容器内为 http
)
app.include_router(_auth.router)


@app.on_event("startup")
async def _on_startup():
    # 建库（幂等）+ 启动会话 TTL 清理调度（仅 web 主进程）
    import asyncio

    from .cleanup import start_scheduler
    await asyncio.to_thread(_db.init_db)
    start_scheduler()


@app.on_event("shutdown")
async def _on_shutdown():
    from .cleanup import shutdown_scheduler
    shutdown_scheduler()

# 仓库根目录（app/ 的上一级）。数据/资源目录均以此为基准，与启动时的工作目录无关。
BASE_DIR   = Path(__file__).resolve().parent.parent
WORK_DIR   = BASE_DIR / "sessions"
BATCH_DIR  = WORK_DIR / "_batch"
STATIC_DIR = BASE_DIR / "static"
MAX_HISTORY = 20

WORK_DIR.mkdir(exist_ok=True)
BATCH_DIR.mkdir(exist_ok=True)

# Vite 构建产物（index.html + assets/）输出到 static/；
# index.html 以 /static/assets/* 引用 hash 资源，由此挂载解析。
# 挂载在 /static，不影响 GET /（仍返回 static/index.html 文本）。
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── 版本历史工具 ──

def _hist_dir(session_dir: Path) -> Path:
    d = session_dir / "history"
    d.mkdir(exist_ok=True)
    return d


def _history_count(session_dir: Path) -> int:
    d = session_dir / "history"
    return len(list(d.glob("*.docx"))) if d.exists() else 0


def _save_snapshot(session_dir: Path):
    """将 current.docx 存入历史；超出上限时丢弃最旧的快照。"""
    hd = _hist_dir(session_dir)
    files = sorted(hd.glob("*.docx"))
    while len(files) >= MAX_HISTORY:
        files[0].unlink()
        files = files[1:]
    next_idx = (int(files[-1].stem) + 1) if files else 0
    shutil.copy2(session_dir / "current.docx", hd / f"{next_idx:06d}.docx")


def _restore_snapshot(session_dir: Path) -> bool:
    """弹出最新快照恢复为 current.docx，返回是否成功。"""
    hd = session_dir / "history"
    if not hd.exists():
        return False
    files = sorted(hd.glob("*.docx"))
    if not files:
        return False
    shutil.copy2(files[-1], session_dir / "current.docx")
    files[-1].unlink()
    return True


# ── 路由 ──

@app.get("/health")
async def health():
    """容器存活/就绪探针（compose / 反代用）。liveness 恒 ok，附依赖就绪。"""
    from . import __version__
    out = {"status": "ok", "version": __version__}

    from .redis_client import redis_configured
    if redis_configured():
        try:
            from .redis_client import get_redis
            r = await get_redis()
            await r.ping()
            out["redis"] = "ok"
        except Exception:
            out["redis"] = "down"
    else:
        out["redis"] = "disabled"

    from .render_client import render_configured
    out["render"] = "configured" if render_configured() else "disabled"
    out["auth"] = "enabled" if _auth.auth_enabled() else "disabled"
    return out


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/upload")
async def upload_doc(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "只支持 .docx 文件")

    session_id = uuid.uuid4().hex
    session_dir = WORK_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    with open(session_dir / "current.docx", "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 记录会话归属（启用鉴权时据此校验；未登录则 owner=None，匿名兼容）
    user = _auth.current_user(request)
    try:
        await asyncio.to_thread(
            _db.upsert_session, session_id,
            user["id"] if user else None, file.filename,
        )
    except Exception:
        pass

    return {"session_id": session_id, "filename": file.filename}


async def _persist_msg(session_id: str, role: str, content: str) -> None:
    """会话消息落 Redis；未配置/不可达则静默跳过（降级，不阻断主流程）。"""
    if not content:
        return
    try:
        from .messages import append_message
        await append_message(session_id, role, content)
    except Exception:
        pass


@app.post("/chat")
async def chat(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(...),
    history: str = Form("[]"),
):
    session_dir = WORK_DIR / session_id
    doc_path = session_dir / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失，请先上传 docx")
    await _auth.require_owner(session_id, request)
    await asyncio.to_thread(_db.touch_session, session_id)

    # 多轮历史：优先服务端 Redis 会话消息（刷新/换设备可恢复上下文），
    # Redis 未配置/为空时回退前端回传的 history（向后兼容，离线开发可用）。
    hist = []
    try:
        from .messages import get_messages, to_llm_history
        srv = await get_messages(session_id)
        if srv:
            hist = to_llm_history(srv)
    except Exception:
        hist = []
    if not hist:
        try:
            hist = _json.loads(history) if history else []
            if not isinstance(hist, list):
                hist = []
        except (ValueError, _json.JSONDecodeError):
            hist = []

    # 本轮用户消息入库（早写：澄清分支也能留存）
    await _persist_msg(session_id, "user", message)

    # 1. 提取文档样式 + 大纲 + 推断的论文题目，作为 LLM 上下文
    try:
        available_styles = get_used_paragraph_styles(str(doc_path))
        doc_structure    = get_document_structure(str(doc_path))
        doc_title        = get_document_title(str(doc_path))
    except Exception:
        available_styles = None
        doc_structure    = None
        doc_title        = ""

    # 2. LLM 解析
    try:
        parsed = parse_command(message,
                               available_styles=available_styles,
                               doc_structure=doc_structure,
                               doc_title=doc_title,
                               history=hist)
    except Exception as e:
        raise HTTPException(500, f"指令解析失败：{e}")

    # 2.5 LLM 信息不足时只返回澄清问题（operations 为空）→ 不动文档、不建快照
    if not parsed.operations:
        clarify = parsed.explanation or "需要更多信息才能继续，请补充说明。"
        await _persist_msg(session_id, "bot", clarify)
        return {
            "explanation":   clarify,
            "operations":    [],
            "history_count": _history_count(session_dir),
            "needs_input":   True,
        }

    # 3. 操作前保存快照
    _save_snapshot(session_dir)

    # 4. 应用修改；失败时自动回滚快照
    try:
        apply_operations(str(doc_path), str(doc_path), parsed.operations)
    except Exception as e:
        _restore_snapshot(session_dir)
        raise HTTPException(500, f"文档修改失败：{e}")

    await _persist_msg(session_id, "bot", parsed.explanation or "")
    return {
        "explanation":   parsed.explanation,
        "operations":    [op.model_dump(exclude_none=True) for op in parsed.operations],
        "history_count": _history_count(session_dir),
        "distilled":     parsed.distilled,    # 长文本蒸馏结果（短输入时为空）
    }


@app.post("/chat/stream")
async def chat_stream(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(...),
    history: str = Form("[]"),
):
    """与 /chat 等价，但以 SSE 流出阶段事件改善感知延迟。

    设计说明：parse_command 返回的是整块 JSON 指令（operations + explanation 字段），
    不是可逐 token 显示的对话流；且 operations 必须完整才能套用到文档。强行做
    token 级流式需重写核心解析逻辑，违背「稳定」目标。因此这里流式的是**阶段进度**
    （理解指令 →[长文本: 提炼要求]→ 应用排版 → 完成），复用 SSE，零风险提升体验。

    事件：data: {"stage":"parsing|applying|done|error", ...}
    done 的 payload 与 /chat 返回体一致（前端可直接复用渲染逻辑）。
    """
    session_dir = WORK_DIR / session_id
    doc_path = session_dir / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失，请先上传 docx")
    await _auth.require_owner(session_id, request)
    await asyncio.to_thread(_db.touch_session, session_id)

    from fastapi.responses import StreamingResponse

    from .llm_parser import LONG_TEXT_THRESHOLD

    def sse(obj: dict) -> str:
        return f"data: {_json.dumps(obj, ensure_ascii=False)}\n\n"

    async def gen():
        # 多轮历史：Redis 会话消息优先，回退前端回传
        hist = []
        try:
            from .messages import get_messages, to_llm_history
            srv = await get_messages(session_id)
            if srv:
                hist = to_llm_history(srv)
        except Exception:
            hist = []
        if not hist:
            try:
                hist = _json.loads(history) if history else []
                if not isinstance(hist, list):
                    hist = []
            except (ValueError, _json.JSONDecodeError):
                hist = []

        await _persist_msg(session_id, "user", message)

        long_text = len(message) >= LONG_TEXT_THRESHOLD
        yield sse({
            "stage": "parsing",
            "text": "正在提炼并规划排版要求…" if long_text else "正在理解指令…",
        })

        try:
            try:
                available_styles = get_used_paragraph_styles(str(doc_path))
                doc_structure = get_document_structure(str(doc_path))
                doc_title = get_document_title(str(doc_path))
            except Exception:
                available_styles = doc_structure = None
                doc_title = ""

            parsed = await asyncio.to_thread(
                parse_command, message,
                available_styles, doc_structure, doc_title, hist,
            )
        except Exception as e:
            yield sse({"stage": "error", "error": f"指令解析失败：{e}"})
            return

        if not parsed.operations:
            clarify = parsed.explanation or "需要更多信息才能继续，请补充说明。"
            await _persist_msg(session_id, "bot", clarify)
            yield sse({
                "stage": "done", "explanation": clarify, "operations": [],
                "history_count": _history_count(session_dir), "needs_input": True,
            })
            return

        yield sse({"stage": "applying", "text": "正在应用排版…"})
        await asyncio.to_thread(_save_snapshot, session_dir)
        try:
            await asyncio.to_thread(
                apply_operations, str(doc_path), str(doc_path), parsed.operations
            )
        except Exception as e:
            await asyncio.to_thread(_restore_snapshot, session_dir)
            yield sse({"stage": "error", "error": f"文档修改失败：{e}"})
            return

        await _persist_msg(session_id, "bot", parsed.explanation or "")
        yield sse({
            "stage": "done",
            "explanation": parsed.explanation,
            "operations": [op.model_dump(exclude_none=True) for op in parsed.operations],
            "history_count": _history_count(session_dir),
            "distilled": parsed.distilled,
        })

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/undo/{session_id}")
async def undo(session_id: str, request: Request):
    session_dir = WORK_DIR / session_id
    if not (session_dir / "current.docx").exists():
        raise HTTPException(404, "会话不存在")
    await _auth.require_owner(session_id, request)
    if not _restore_snapshot(session_dir):
        raise HTTPException(400, "没有可撤销的操作")
    return {"history_count": _history_count(session_dir)}


@app.get("/session/{session_id}")
async def session_restore(session_id: str, request: Request):
    """刷新/重进后恢复会话：文档是否在、历史步数、服务端聊天消息。

    Redis 未配置时 messages 为空（前端退回本地态），不报错。
    """
    session_dir = WORK_DIR / session_id
    exists = (session_dir / "current.docx").exists()
    if exists:
        await _auth.require_owner(session_id, request)
    msgs = []
    if exists:
        try:
            from .messages import get_messages
            msgs = await get_messages(session_id)
        except Exception:
            msgs = []
    return {
        "exists": exists,
        "history_count": _history_count(session_dir) if exists else 0,
        "messages": msgs,
    }


@app.get("/download/{session_id}")
async def download(session_id: str, request: Request):
    doc_path = WORK_DIR / session_id / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "文档不存在")
    await _auth.require_owner(session_id, request)
    return FileResponse(
        doc_path,
        filename="modified.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/render/{session_id}/pdf")
async def render_session_pdf(session_id: str, request: Request):
    """高保真 PDF：经独立渲染服务用 LibreOffice 计算域后导出。

    与 /download（原始 .docx，域未计算）互补——本接口页码/题注/交叉引用为正确值。
    渲染服务未启用/不可达 → 503 友好提示，不影响其余功能。
    """
    doc_path = WORK_DIR / session_id / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失")
    await _auth.require_owner(session_id, request)
    from .render_client import RenderUnavailable, render_pdf
    try:
        pdf = await render_pdf(str(doc_path))
    except RenderUnavailable as e:
        raise HTTPException(503, str(e))
    import io as _io
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        _io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="preview.pdf"'},
    )


@app.get("/render/{session_id}/preview")
async def render_session_preview(session_id: str, request: Request, dpi: int = 120):
    """分页 PNG（zip）：前端可做与 docx-preview 并存的高保真预览开关。"""
    doc_path = WORK_DIR / session_id / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失")
    await _auth.require_owner(session_id, request)
    from .render_client import RenderUnavailable, render_preview_zip
    try:
        zip_bytes = await render_preview_zip(str(doc_path), dpi=max(60, min(dpi, 300)))
    except RenderUnavailable as e:
        raise HTTPException(503, str(e))
    from fastapi.responses import Response
    return Response(zip_bytes, media_type="application/zip")


@app.get("/structure/{session_id}")
async def get_structure(session_id: str, request: Request):
    doc_path = WORK_DIR / session_id / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失")
    await _auth.require_owner(session_id, request)
    try:
        sections = get_thesis_structure(str(doc_path))
    except Exception as e:
        raise HTTPException(500, f"结构识别失败：{e}")
    from collections import Counter
    # 扁平列表供统计（不含被过滤的内联类型，但需从原始调用处获取）
    flat = [item for sec in sections.values() for item in sec]
    counts = Counter(item["type"] for item in flat)
    # 图/表/公式统计需从全文扫描（get_thesis_structure 已过滤，通过 get_document_structure 无法得到，
    # 这里退化到用 flat；如需精确统计可调用独立扫描）
    return {
        "sections": sections,
        "items": flat,          # 向后兼容：前端可继续用 data.items
        "stats": {
            "headings":  sum(v for k, v in counts.items() if k.startswith("heading_")),
            "figures":   counts.get("figure_caption", 0),
            "tables":    counts.get("table_caption",  0),
            "equations": counts.get("equation",       0),
        },
    }


# ── 批量排版（多文档同规则处理）──

def _safe_filename(name: str) -> str:
    """文件名清洗：剔除目录穿越和 Windows 非法字符，保持扩展名。"""
    name = Path(name or "doc.docx").name  # 去掉路径
    # Windows 禁用字符 + 控制字符
    name = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(". ")
    return name or "doc.docx"


@app.post("/batch")
async def batch_format(
    files: List[UploadFile] = File(...),
    feature_ids: str = Form("[]"),
    message: str = Form(""),
):
    """多文档同规则排版。

    Redis 已配置：入队交给 web-worker 异步处理，返回 {batch_id, job_id, queued:true}，
                  前端轮询 GET /jobs/{job_id}（或订阅 SSE）取进度与结果。
    Redis 未配置：同步降级处理，直接返回完整结果（向后兼容，离线开发可用）。
    """
    if not files:
        raise HTTPException(400, "至少上传一份 .docx 文件")
    docx_files = [f for f in files if (f.filename or "").lower().endswith(".docx")]
    if not docx_files:
        raise HTTPException(400, "所有上传文件均不是 .docx")

    try:
        feature_id_list = _json.loads(feature_ids)
        if not isinstance(feature_id_list, list):
            raise ValueError("feature_ids 必须是数组")
    except (ValueError, _json.JSONDecodeError) as e:
        raise HTTPException(400, f"feature_ids 格式错误：{e}")

    from .batch_core import applied_default_names, dedupe_names, run_batch

    raw = [(f.filename or "doc.docx", await f.read()) for f in docx_files]
    saved = dedupe_names(raw)   # [(safe_name, bytes)]
    batch_id = uuid.uuid4().hex

    from .redis_client import redis_configured
    if redis_configured():
        try:
            from .queue import enqueue_batch
            job_id = await enqueue_batch(saved, feature_id_list, message, batch_id)
            return {"batch_id": batch_id, "job_id": job_id, "queued": True}
        except Exception as e:
            # 入队失败（如 Redis 临时不可达）→ 不让用户卡住，回退同步
            _ = e

    result = await asyncio.to_thread(
        run_batch, saved, feature_id_list, message, BATCH_DIR / batch_id, None
    )
    result["batch_id"] = batch_id
    result["applied"] = applied_default_names(feature_id_list)
    result["download_url"] = (
        f"/batch/{batch_id}/download" if result["success_count"] > 0 else None
    )
    result["queued"] = False
    return result


@app.get("/jobs/{job_id}")
async def job_get(job_id: str):
    """查询异步 job 状态/进度/结果（批量、异步渲染共用）。"""
    from .redis_client import redis_configured
    if not redis_configured():
        raise HTTPException(409, "未配置 Redis，无异步任务")
    from .queue import job_status
    try:
        return await job_status(job_id)
    except Exception as e:
        raise HTTPException(500, f"查询任务失败：{e}")


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    """SSE 实时进度：订阅 web55:progress:{job_id}；完成/失败后补发终态并关闭。"""
    from .redis_client import redis_configured
    if not redis_configured():
        raise HTTPException(409, "未配置 Redis，无异步任务")

    from fastapi.responses import StreamingResponse

    from .queue import job_status
    from .redis_client import get_redis

    async def gen():
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(f"web55:progress:{job_id}")
        try:
            # 先补发一次当前状态（可能订阅前已有进度）
            st = await job_status(job_id)
            yield f"data: {_json.dumps(st, ensure_ascii=False)}\n\n"
            if st.get("status") in ("complete", "failed", "not_found"):
                return
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=15.0
                )
                if msg and msg.get("data"):
                    yield f"data: {msg['data']}\n\n"
                # 周期性回查终态（pub/sub 可能错过最后一条）
                st = await job_status(job_id)
                if st.get("status") in ("complete", "failed", "not_found"):
                    yield f"data: {_json.dumps(st, ensure_ascii=False)}\n\n"
                    return
                if not msg:
                    yield ": keep-alive\n\n"
                    await asyncio.sleep(0)
        finally:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:
                pass

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/batch/{batch_id}/download")
async def batch_download(batch_id: str):
    # 防止目录穿越：只接受十六进制 uuid
    if not _re.fullmatch(r"[0-9a-f]{32}", batch_id):
        raise HTTPException(400, "非法 batch_id")
    zip_path = BATCH_DIR / batch_id / "results.zip"
    if not zip_path.exists():
        raise HTTPException(404, "批次不存在或已过期")
    return FileResponse(
        zip_path,
        filename=f"batch_{batch_id[:8]}.zip",
        media_type="application/zip",
    )


# ── 默认排版功能 ──

@app.get("/defaults")
async def list_defaults():
    """返回前端默认排版面板可勾选的全部条目（不含 ops 详情）。"""
    return {"defaults": get_defaults_metadata()}


@app.post("/apply_defaults")
async def apply_defaults(
    request: Request,
    session_id: str = Form(...),
    feature_ids: str = Form(...),
):
    """批量应用所选默认排版条目。

    feature_ids: JSON 编码的字符串数组，如 ["page_a4_standard","body_song_xiaosi"]
    """
    session_dir = WORK_DIR / session_id
    doc_path = session_dir / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失，请先上传 docx")
    await _auth.require_owner(session_id, request)

    try:
        ids = _json.loads(feature_ids)
        if not isinstance(ids, list):
            raise ValueError("feature_ids 必须是数组")
    except (ValueError, _json.JSONDecodeError) as e:
        raise HTTPException(400, f"feature_ids 格式错误：{e}")

    if not ids:
        raise HTTPException(400, "至少勾选一项排版功能")

    # 推断论文题目 / 学校学位论文名，用于 {THESIS_TITLE} / {THESIS_LABEL} 占位符替换
    try:
        thesis_title = get_document_title(str(doc_path))
    except Exception:
        thesis_title = ""
    try:
        thesis_label = get_thesis_label(str(doc_path))
    except Exception:
        thesis_label = ""

    raw_ops = collect_ops(ids, thesis_title=thesis_title, thesis_label=thesis_label)
    if not raw_ops:
        raise HTTPException(400, "所选条目无可执行操作（可能因占位符无法解析全部跳过）")

    # 复用 ParsedCommand 校验：raw_ops 必须能通过 AnyOperation discriminated union
    try:
        parsed = ParsedCommand.model_validate({"operations": raw_ops, "explanation": ""})
    except Exception as e:
        raise HTTPException(500, f"默认 ops 校验失败：{e}")

    _save_snapshot(session_dir)
    try:
        apply_operations(str(doc_path), str(doc_path), parsed.operations)
    except Exception as e:
        _restore_snapshot(session_dir)
        raise HTTPException(500, f"应用默认排版失败：{e}")

    # 报告：勾选了哪些条目 / 实际生成多少 op / 是否使用了论文题目
    applied_names = [
        d["name"] for d in get_defaults_metadata() if d["id"] in ids
    ]
    selected_defaults_json = _json.dumps(
        [d for d in DEFAULTS if d["id"] in ids],
        ensure_ascii=False,
    )
    note_parts = []
    if thesis_title and "{THESIS_TITLE}" in selected_defaults_json:
        note_parts.append(f"论文题目：{thesis_title}")
    if thesis_label and "{THESIS_LABEL}" in selected_defaults_json:
        note_parts.append(f"偶数页页眉：{thesis_label}")
    note = f"（页眉已自动填入识别出的 {'；'.join(note_parts)}）" if note_parts else ""

    # thesis_4_sections（一键 4 分节）无 LLM 可交互询问：检测不到学校/题目时
    # 不污染页眉（已留空），但要明确告知用户如何补全。
    if "thesis_4_sections" in ids:
        miss = []
        if not thesis_title:
            miss.append("论文题目（奇数页页眉）")
        if not thesis_label:
            miss.append("学校学位论文名（偶数页页眉）")
        if miss:
            note += (
                f"⚠️ 未能从文档可靠识别 {('、'.join(miss))}，对应页眉已留空（未填入猜测内容）。"
                "可在对话框告诉我贵校全称与学历层次（本科/硕士/博士），我据此重设页眉；"
                "或直接在 Word 中补填。"
            )

    return {
        "explanation": (
            f"已应用 {len(applied_names)} 项默认排版，共生成 {len(parsed.operations)} "
            f"个 op 按规范顺序执行。{note}"
        ),
        "applied":      applied_names,
        "operations":   [op.model_dump(exclude_none=True) for op in parsed.operations],
        "history_count": _history_count(session_dir),
    }


# ── 需求文档解析（PDF / DOCX / TXT → 纯文本）──

@app.post("/extract_text")
async def extract_text(file: UploadFile = File(...)):
    """从上传的 PDF / DOCX / TXT 中提取纯文本，供前端注入到指令输入框。

    PDF：先尝试文字图层，无文字（扫描件）自动走 OCR。
    """
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")

    try:
        text, ocr_used = extract_any(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"文件解析失败：{e}")

    if not text:
        raise HTTPException(400, "未从文件中提取到任何文字")

    return {
        "text": text,
        "filename": file.filename,
        "chars": len(text),
        "ocr_used": ocr_used,
    }


# ── 问答模式：论文格式知识库 ──

@app.get("/knowledge")
async def knowledge_list():
    """返回知识库来源清单（内置国标要点 + knowledge/ 目录 PDF）。"""
    return {"sources": list_knowledge_sources()}


@app.post("/knowledge/refresh")
async def knowledge_refresh():
    """重新扫描 knowledge/ 目录（投放新 PDF 后调用）。"""
    n = refresh_knowledge()
    return {"pdf_count": n, "sources": list_knowledge_sources()}


@app.get("/knowledge/{source_id}/view")
async def knowledge_view(source_id: str):
    """查看原件：内置来源以 HTML 文本呈现；PDF 内联返回。"""
    src = get_knowledge_source(source_id)
    if src is None:
        raise HTTPException(404, "知识库来源不存在")
    if src["kind"] == "pdf":
        return FileResponse(src["path"], media_type="application/pdf",
                            filename=src["filename"])
    body = escape_html_min(src["text"])
    html = (
        f"<!doctype html><meta charset='utf-8'>"
        f"<title>{escape_html_min(src['title'])}</title>"
        f"<body style='font:15px/1.7 -apple-system,Segoe UI,sans-serif;"
        f"max-width:820px;margin:32px auto;padding:0 20px;color:#1a1a1a'>"
        f"<pre style='white-space:pre-wrap;font-family:inherit'>{body}</pre></body>"
    )
    return HTMLResponse(html)


def escape_html_min(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))


@app.post("/qa")
async def qa(question: str = Form(...), history: str = Form("[]"),
             references: str = Form("[]")):
    """论文格式答疑。

    history:    JSON 数组 [{role,content}, ...]，可选多轮上下文。
    references: JSON 字符串数组，用户从 OpenAlex 检索勾选带入的 GB/T 7714 著录串。
    """
    try:
        hist = _json.loads(history) if history else []
        if not isinstance(hist, list):
            hist = []
    except (ValueError, _json.JSONDecodeError):
        hist = []
    try:
        refs = _json.loads(references) if references else []
        if not isinstance(refs, list):
            refs = []
    except (ValueError, _json.JSONDecodeError):
        refs = []
    try:
        answer = answer_question(question, history=hist, references=refs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"问答失败：{e}")
    return {"answer": answer}


# ── 文献检索（OpenAlex）+ 存入 Zotero（问答模式辅助）──

@app.get("/openalex/defaults")
async def openalex_defaults():
    """返回默认年份范围（近三年），供前端初始化年份输入框。"""
    f, t = default_year_range()
    return {"from_year": f, "to_year": t}


@app.post("/openalex/search")
async def openalex_search(
    query: str = Form(...),
    from_year: int = Form(None),
    to_year: int = Form(None),
    limit: int = Form(20),
    api_key: str = Form(""),
):
    """按关键词（含内置英文同义词扩展）检索 OpenAlex，附 GB/T 7714 著录串。

    api_key：OpenAlex 免费 Key（前端传入；缺省回退环境变量 OPENALEX_API_KEY）。
    """
    try:
        result = openalex_search_works(query, from_year=from_year,
                                       to_year=to_year, limit=limit,
                                       api_key=api_key)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        raise HTTPException(500, f"OpenAlex 检索失败：{e}")
    return result


@app.post("/zotero/save")
async def zotero_save(
    api_key: str = Form(...),
    user_id: str = Form(...),
    items: str = Form(...),
):
    """把勾选的文献写入用户 Zotero 库。items: JSON 数组（归一化条目）。"""
    try:
        item_list = _json.loads(items) if items else []
        if not isinstance(item_list, list):
            raise ValueError("items 必须是数组")
    except (ValueError, _json.JSONDecodeError) as e:
        raise HTTPException(400, f"items 格式错误：{e}")
    try:
        result = zotero_save_items(api_key, user_id, item_list)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        raise HTTPException(500, f"Zotero 写入失败：{e}")
    return result


# ── 检查模式：论文合规性检查 ──

@app.post("/check")
async def check_thesis(
    request: Request,
    session_id: str = Form(...),
    categories: str = Form("[]"),
    review: UploadFile = File(None),
):
    """对会话中的当前论文执行合规检查。

    categories: JSON 数组，可选 ["citation","reference_format","structure","compliance"]；
                空数组 = 全部检查。
    review:     可选的文献综述文件（docx/pdf/txt），用于引用对应性交叉核对。
    """
    session_dir = WORK_DIR / session_id
    doc_path = session_dir / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失，请先上传论文 docx")
    await _auth.require_owner(session_id, request)

    try:
        cats = _json.loads(categories) if categories else []
        if not isinstance(cats, list):
            cats = []
    except (ValueError, _json.JSONDecodeError):
        cats = []

    review_path = None
    if review is not None and review.filename:
        rdata = await review.read()
        if rdata:
            review_path = session_dir / ("review" + Path(_safe_filename(review.filename)).suffix)
            with open(review_path, "wb") as f:
                f.write(rdata)

    try:
        report = run_checks(str(doc_path),
                            review_path=str(review_path) if review_path else None,
                            categories=cats)
    except Exception as e:
        raise HTTPException(500, f"检查失败：{e}")
    return report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

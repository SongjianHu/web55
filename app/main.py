"""
FastAPI 后端：上传、聊天修改、撤销、下载接口 + 静态首页。

版本控制：每次 chat 操作前将 current.docx 快照存入 sessions/{id}/history/，
最多保留 MAX_HISTORY 步，/undo 接口弹出最新快照恢复。
"""
import io
import re as _re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import json as _json

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

@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/upload")
async def upload_doc(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "只支持 .docx 文件")

    session_id = uuid.uuid4().hex
    session_dir = WORK_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    with open(session_dir / "current.docx", "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"session_id": session_id, "filename": file.filename}


@app.post("/chat")
async def chat(
    session_id: str = Form(...),
    message: str = Form(...),
    history: str = Form("[]"),
):
    session_dir = WORK_DIR / session_id
    doc_path = session_dir / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失，请先上传 docx")

    # 多轮历史（澄清式追问依赖它：先问学校/学历，用户补充后才能生成 thesis_sections）
    try:
        hist = _json.loads(history) if history else []
        if not isinstance(hist, list):
            hist = []
    except (ValueError, _json.JSONDecodeError):
        hist = []

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
        return {
            "explanation":   parsed.explanation or "需要更多信息才能继续，请补充说明。",
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

    return {
        "explanation":   parsed.explanation,
        "operations":    [op.model_dump(exclude_none=True) for op in parsed.operations],
        "history_count": _history_count(session_dir),
        "distilled":     parsed.distilled,    # 长文本蒸馏结果（短输入时为空）
    }


@app.post("/undo/{session_id}")
async def undo(session_id: str):
    session_dir = WORK_DIR / session_id
    if not (session_dir / "current.docx").exists():
        raise HTTPException(404, "会话不存在")
    if not _restore_snapshot(session_dir):
        raise HTTPException(400, "没有可撤销的操作")
    return {"history_count": _history_count(session_dir)}


@app.get("/download/{session_id}")
async def download(session_id: str):
    doc_path = WORK_DIR / session_id / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "文档不存在")
    return FileResponse(
        doc_path,
        filename="modified.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/structure/{session_id}")
async def get_structure(session_id: str):
    doc_path = WORK_DIR / session_id / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失")
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
    """对多份 docx 应用同一套排版（默认功能勾选 + 可选自定义指令）。

    feature_ids: JSON 数组字符串，对应 /apply_defaults 的格式
    message:     可选自定义指令；若提供则用首份文档的上下文解析一次，复用到全部文件
    返回：批次 id、每份文件的处理状态；可通过 GET /batch/{id}/download 下载 zip。
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

    batch_id = uuid.uuid4().hex
    batch_dir = BATCH_DIR / batch_id
    in_dir    = batch_dir / "in"
    out_dir   = batch_dir / "out"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 落盘所有文件（避免 UploadFile 流式状态污染）+ 处理重名
    saved = []   # [(safe_name, in_path)]
    seen  = set()
    for f in docx_files:
        safe = _safe_filename(f.filename or "doc.docx")
        base, ext = (safe[:-5], ".docx") if safe.endswith(".docx") else (safe, ".docx")
        candidate = safe
        i = 1
        while candidate in seen:
            candidate = f"{base}({i}){ext}"
            i += 1
        seen.add(candidate)
        in_path = in_dir / candidate
        with open(in_path, "wb") as fp:
            shutil.copyfileobj(f.file, fp)
        saved.append((candidate, in_path))

    # 2) 自定义指令：仅解析一次（用首份文档的上下文，section: 类目标按首份文档对齐）
    custom_ops_raw = []
    custom_parse_error = None
    if message and message.strip():
        try:
            first_path = saved[0][1]
            try:
                ctx_styles = get_used_paragraph_styles(str(first_path))
                ctx_struct = get_document_structure(str(first_path))
                ctx_title  = get_document_title(str(first_path))
            except Exception:
                ctx_styles = ctx_struct = None
                ctx_title  = ""
            parsed = parse_command(
                message,
                available_styles=ctx_styles,
                doc_structure=ctx_struct,
                doc_title=ctx_title,
            )
            custom_ops_raw = [op.model_dump(exclude_none=True) for op in parsed.operations]
        except Exception as e:
            custom_parse_error = str(e)

    # 3) 逐份处理
    results = []
    for name, in_path in saved:
        if custom_parse_error is not None:
            # 自定义指令解析失败 → 整批失败（用户应当意识到指令问题）
            results.append({"filename": name, "status": "error",
                            "error": f"自定义指令解析失败：{custom_parse_error}"})
            continue

        try:
            # 每份文档单独解析 {THESIS_TITLE} / {THESIS_LABEL} 等占位符
            try:
                thesis_title = get_document_title(str(in_path))
            except Exception:
                thesis_title = ""
            try:
                thesis_label = get_thesis_label(str(in_path))
            except Exception:
                thesis_label = ""
            default_ops_raw = collect_ops(
                feature_id_list, thesis_title=thesis_title, thesis_label=thesis_label
            )
            all_ops_raw = default_ops_raw + custom_ops_raw
            if not all_ops_raw:
                results.append({"filename": name, "status": "error",
                                "error": "未勾选默认功能且无自定义指令"})
                continue

            # 走与 /chat 同样的 Pydantic 校验
            pc = ParsedCommand.model_validate({"operations": all_ops_raw, "explanation": ""})

            out_path = out_dir / name
            apply_operations(str(in_path), str(out_path), pc.operations)
            results.append({
                "filename": name,
                "status": "ok",
                "ops_count": len(pc.operations),
                "title_used": thesis_title,
            })
        except Exception as e:
            results.append({"filename": name, "status": "error", "error": str(e)})

    # 4) 打包成功项为 zip
    ok_count = sum(1 for r in results if r["status"] == "ok")
    zip_path = batch_dir / "results.zip"
    if ok_count > 0:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in results:
                if r["status"] == "ok":
                    src = out_dir / r["filename"]
                    if src.exists():
                        zf.write(src, arcname=r["filename"])

    return {
        "batch_id":      batch_id,
        "total":         len(results),
        "success_count": ok_count,
        "fail_count":    len(results) - ok_count,
        "results":       results,
        "download_url":  f"/batch/{batch_id}/download" if ok_count > 0 else None,
    }


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

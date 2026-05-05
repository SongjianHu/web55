"""
FastAPI 后端：提供上传、聊天修改、下载三个接口 + 一个静态首页。

会话管理：每次上传创建一个 session_id，文档存到 sessions/{id}/current.docx，
后续 chat 接口在该文件上做增量修改 —— 实现"持续对话编辑"。
"""
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from llm_parser import parse_command
from docx_formatter import apply_operations, get_used_paragraph_styles


app = FastAPI(title="Docx Chat Editor")

WORK_DIR = Path("./sessions")
WORK_DIR.mkdir(exist_ok=True)
STATIC_DIR = Path(__file__).parent / "static"


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

    doc_path = session_dir / "current.docx"
    with open(doc_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"session_id": session_id, "filename": file.filename}


@app.post("/chat")
async def chat(session_id: str = Form(...), message: str = Form(...)):
    session_dir = WORK_DIR / session_id
    doc_path = session_dir / "current.docx"
    if not doc_path.exists():
        raise HTTPException(404, "会话不存在或文档已丢失，请先上传 docx")

    # 1. 提取文档样式列表，作为 LLM 上下文
    try:
        available_styles = get_used_paragraph_styles(str(doc_path))
    except Exception:
        available_styles = None

    # 2. LLM 解析
    try:
        parsed = parse_command(message, available_styles=available_styles)
    except Exception as e:
        raise HTTPException(500, f"指令解析失败：{e}")

    # 2. 应用修改（直接覆写 current.docx，下次 chat 基于新结果）
    try:
        apply_operations(str(doc_path), str(doc_path), parsed.operations)
    except Exception as e:
        raise HTTPException(500, f"文档修改失败：{e}")

    return {
        "explanation": parsed.explanation,
        "operations": [op.model_dump(exclude_none=True) for op in parsed.operations],
    }


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

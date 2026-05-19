"""渲染服务 HTTP 入口（同步路径，本地调试最简形态，不经 Redis）。

  GET  /health           存活探针
  POST /render/pdf        multipart docx → application/pdf（域已计算）
  POST /render/preview    multipart docx[,dpi] → application/zip（page-0001.png ...）

异步队列消费在 render_service/worker.py（Phase 3），与本 HTTP 同镜像不同进程。
"""
import io
import zipfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from .renderer import RenderError, render_pdf, render_preview_pngs, soffice_available

app = FastAPI(title="web55 render service")

_PDF_MEDIA = "application/pdf"


@app.get("/health")
async def health():
    return {"status": "ok", "soffice": soffice_available()}


async def _read_docx(file: UploadFile) -> bytes:
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(400, "只接受 .docx")
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")
    return data


@app.post("/render/pdf")
async def render_pdf_endpoint(file: UploadFile = File(...)):
    data = await _read_docx(file)
    try:
        pdf = await render_pdf(data)
    except RenderError as e:
        raise HTTPException(503, str(e))
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type=_PDF_MEDIA,
        headers={"Content-Disposition": 'inline; filename="render.pdf"'},
    )


@app.post("/render/preview")
async def render_preview_endpoint(
    file: UploadFile = File(...),
    dpi: int = Form(120),
):
    data = await _read_docx(file)
    dpi = max(60, min(dpi, 300))
    try:
        pngs = await render_preview_pngs(data, dpi=dpi)
    except RenderError as e:
        raise HTTPException(503, str(e))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, png in enumerate(pngs, 1):
            zf.writestr(f"page-{i:04d}.png", png)
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"X-Page-Count": str(len(pngs))},
    )

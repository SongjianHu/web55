"""LibreOffice headless 渲染核心：docx → PDF（域已计算）/ PDF → 分页 PNG。

为什么用 LibreOffice：主应用插入的 Word 域（PAGE/NUMPAGES、交叉引用书签、
图表题注 SEQ 编号）在 .docx 里是占位的，不会自动算值；LibreOffice 在
排版生成 PDF 时会计算这些域，因此 PDF 中页码/编号/交叉引用为正确值。

并发安全：每次转换用独立 UserInstallation 配置目录，避免 soffice 实例互锁；
信号量限制并发，asyncio.to_thread 跑阻塞子进程不卡事件循环。
"""
import asyncio
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

SOFFICE_BIN = os.getenv("SOFFICE_BIN", "soffice")
RENDER_TIMEOUT = int(os.getenv("RENDER_TIMEOUT", "120"))
_MAX_CONCURRENCY = int(os.getenv("RENDER_MAX_CONCURRENCY", "2"))
_SEM = asyncio.Semaphore(_MAX_CONCURRENCY)


class RenderError(RuntimeError):
    """渲染失败（soffice 不存在 / 超时 / 未产出文件）。"""


def soffice_available() -> bool:
    return shutil.which(SOFFICE_BIN) is not None


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError as e:
        raise RenderError(f"未找到可执行程序：{cmd[0]}（{e}）") from e
    except subprocess.TimeoutExpired as e:
        raise RenderError(f"渲染超时（>{timeout}s）") from e


def _convert_to_pdf_sync(docx_bytes: bytes) -> bytes:
    work = Path(tempfile.mkdtemp(prefix="lo_"))
    try:
        inp = work / "in.docx"
        inp.write_bytes(docx_bytes)
        # 每次独立 profile 目录 → 支持并发、避免 ~/.config 互锁
        profile = work / f"profile_{uuid.uuid4().hex}"
        cmd = [
            SOFFICE_BIN, "--headless", "--nologo", "--nodefault",
            "--norestore", "--nolockcheck",
            f"-env:UserInstallation=file://{profile.as_posix()}",
            "--convert-to", "pdf:writer_pdf_Export",
            "--outdir", str(work), str(inp),
        ]
        proc = _run(cmd, RENDER_TIMEOUT)
        out = work / "in.pdf"
        # soffice 即使部分失败也常返回 0 → 以产物是否存在为准
        if not out.exists() or out.stat().st_size == 0:
            stderr = proc.stderr.decode("utf-8", "ignore")[:800]
            raise RenderError(f"soffice 未产出 PDF（rc={proc.returncode}）：{stderr}")
        return out.read_bytes()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _pdf_to_pngs_sync(pdf_bytes: bytes, dpi: int) -> list[bytes]:
    work = Path(tempfile.mkdtemp(prefix="pp_"))
    try:
        pdf = work / "in.pdf"
        pdf.write_bytes(pdf_bytes)
        # poppler-utils pdftoppm：轻量、无需 python pdf 库
        proc = _run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(work / "page")],
            RENDER_TIMEOUT,
        )
        pages = sorted(work.glob("page-*.png"))
        if not pages:
            stderr = proc.stderr.decode("utf-8", "ignore")[:800]
            raise RenderError(f"pdftoppm 未产出图片：{stderr}")
        return [p.read_bytes() for p in pages]
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def render_pdf(docx_bytes: bytes) -> bytes:
    """docx → PDF（域已计算）。"""
    if not soffice_available():
        raise RenderError(
            f"渲染服务未安装 LibreOffice（{SOFFICE_BIN} 不可用）"
        )
    async with _SEM:
        return await asyncio.to_thread(_convert_to_pdf_sync, docx_bytes)


async def render_preview_pngs(docx_bytes: bytes, dpi: int = 120) -> list[bytes]:
    """docx → 分页 PNG（高保真预览）。"""
    pdf = await render_pdf(docx_bytes)
    async with _SEM:
        return await asyncio.to_thread(_pdf_to_pngs_sync, pdf, dpi)

"""主应用 → 独立渲染服务的客户端（同步 HTTP 路径）。

设计要点：未配置 RENDER_SERVICE_URL 或服务不可达时抛 RenderUnavailable，
上层转 503 友好提示——这样 Windows 本地不启渲染容器也能正常开发其余功能。
"""
import os
from pathlib import Path

import httpx

RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "").strip().rstrip("/")
RENDER_HTTP_TIMEOUT = float(os.getenv("RENDER_HTTP_TIMEOUT", "180"))

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class RenderUnavailable(RuntimeError):
    """渲染未配置 / 服务不可达 / 渲染失败（统一降级信号）。"""


def render_configured() -> bool:
    return bool(RENDER_SERVICE_URL)


async def _post(path: str, docx_path: str, data: dict | None = None) -> httpx.Response:
    if not RENDER_SERVICE_URL:
        raise RenderUnavailable(
            "未配置渲染服务（RENDER_SERVICE_URL 为空）。"
            "本地开发可 `docker compose -f docker-compose.dev.yml up -d` 启动渲染容器。"
        )
    content = Path(docx_path).read_bytes()
    try:
        async with httpx.AsyncClient(timeout=RENDER_HTTP_TIMEOUT) as client:
            return await client.post(
                f"{RENDER_SERVICE_URL}{path}",
                files={"file": ("current.docx", content, _DOCX_MIME)},
                data=data or {},
            )
    except httpx.HTTPError as e:
        raise RenderUnavailable(f"渲染服务不可达：{e}") from e


async def render_pdf(docx_path: str) -> bytes:
    """docx → PDF 字节（域已计算：页码/题注/交叉引用为正确值）。"""
    resp = await _post("/render/pdf", docx_path)
    if resp.status_code != 200:
        raise RenderUnavailable(f"渲染失败（{resp.status_code}）：{resp.text[:300]}")
    return resp.content


async def render_preview_zip(docx_path: str, dpi: int = 120) -> bytes:
    """docx → 分页 PNG 的 zip 字节（高保真预览）。"""
    resp = await _post("/render/preview", docx_path, data={"dpi": str(dpi)})
    if resp.status_code != 200:
        raise RenderUnavailable(f"预览渲染失败（{resp.status_code}）：{resp.text[:300]}")
    return resp.content

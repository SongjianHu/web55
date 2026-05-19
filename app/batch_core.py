"""批量排版核心（与 FastAPI 解耦），供三处复用：

  1) /batch 路由在无 Redis 时的同步降级
  2) arq web-worker 的 batch_job（带进度回调）

注意：批量需要 LLM 解析 + python-docx + defaults，属「主应用域」，
因此其 worker 必须用 web 镜像（app/worker.py），不能放 render 容器。
"""
import re as _re
import zipfile
from collections.abc import Callable
from pathlib import Path

from .defaults import collect_ops, get_defaults_metadata
from .docx_formatter import (
    apply_operations,
    get_document_structure,
    get_document_title,
    get_thesis_label,
    get_used_paragraph_styles,
)
from .llm_parser import parse_command
from .schemas import ParsedCommand

ProgressCb = Callable[[int, int, str], None]


def safe_filename(name: str) -> str:
    """文件名清洗：剔除目录穿越和 Windows 非法字符，保持扩展名。"""
    name = Path(name or "doc.docx").name
    name = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(". ")
    return name or "doc.docx"


def run_batch(
    saved: list[tuple[str, bytes]],
    feature_ids: list,
    message: str,
    batch_dir: Path,
    progress: ProgressCb | None = None,
) -> dict:
    """对多份 docx 应用同一套排版，落盘并打包。

    saved: [(已去重的安全文件名, docx 字节)]；batch_dir 下建 in/out/results.zip。
    返回结构与原 /batch 响应一致（不含 batch_id/download_url，由调用方补）。
    """
    in_dir = batch_dir / "in"
    out_dir = batch_dir / "out"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 落盘输入
    paths: list[tuple[str, Path]] = []
    for name, data in saved:
        p = in_dir / name
        p.write_bytes(data)
        paths.append((name, p))

    # 2) 自定义指令仅解析一次（用首份文档上下文，section: 类目标对齐首份）
    custom_ops_raw: list = []
    custom_parse_error: str | None = None
    if message and message.strip():
        try:
            first = paths[0][1]
            try:
                ctx_styles = get_used_paragraph_styles(str(first))
                ctx_struct = get_document_structure(str(first))
                ctx_title = get_document_title(str(first))
            except Exception:
                ctx_styles = ctx_struct = None
                ctx_title = ""
            parsed = parse_command(
                message,
                available_styles=ctx_styles,
                doc_structure=ctx_struct,
                doc_title=ctx_title,
            )
            custom_ops_raw = [op.model_dump(exclude_none=True) for op in parsed.operations]
        except Exception as e:
            custom_parse_error = str(e)

    # 3) 逐份处理（带进度回调）
    total = len(paths)
    results = []
    for idx, (name, in_path) in enumerate(paths, 1):
        if progress:
            try:
                progress(idx - 1, total, name)
            except Exception:
                pass
        if custom_parse_error is not None:
            results.append({"filename": name, "status": "error",
                            "error": f"自定义指令解析失败：{custom_parse_error}"})
            continue
        try:
            try:
                thesis_title = get_document_title(str(in_path))
            except Exception:
                thesis_title = ""
            try:
                thesis_label = get_thesis_label(str(in_path))
            except Exception:
                thesis_label = ""
            default_ops_raw = collect_ops(
                feature_ids, thesis_title=thesis_title, thesis_label=thesis_label
            )
            all_ops_raw = default_ops_raw + custom_ops_raw
            if not all_ops_raw:
                results.append({"filename": name, "status": "error",
                                "error": "未勾选默认功能且无自定义指令"})
                continue
            pc = ParsedCommand.model_validate(
                {"operations": all_ops_raw, "explanation": ""}
            )
            out_path = out_dir / name
            apply_operations(str(in_path), str(out_path), pc.operations)
            results.append({
                "filename": name, "status": "ok",
                "ops_count": len(pc.operations), "title_used": thesis_title,
            })
        except Exception as e:
            results.append({"filename": name, "status": "error", "error": str(e)})

    if progress:
        try:
            progress(total, total, "")
        except Exception:
            pass

    # 4) 打包成功项
    ok_count = sum(1 for r in results if r["status"] == "ok")
    if ok_count > 0:
        with zipfile.ZipFile(batch_dir / "results.zip", "w", zipfile.ZIP_DEFLATED) as zf:
            for r in results:
                if r["status"] == "ok":
                    src = out_dir / r["filename"]
                    if src.exists():
                        zf.write(src, arcname=r["filename"])

    return {
        "total": len(results),
        "success_count": ok_count,
        "fail_count": len(results) - ok_count,
        "results": results,
    }


def dedupe_names(raw: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """对 (原始名, 字节) 列表做安全名清洗 + 重名加 (n) 后缀。"""
    seen: set[str] = set()
    out: list[tuple[str, bytes]] = []
    for orig, data in raw:
        safe = safe_filename(orig or "doc.docx")
        base, ext = (safe[:-5], ".docx") if safe.endswith(".docx") else (safe, ".docx")
        cand = safe
        i = 1
        while cand in seen:
            cand = f"{base}({i}){ext}"
            i += 1
        seen.add(cand)
        out.append((cand, data))
    return out


def applied_default_names(feature_ids: list) -> list[str]:
    return [d["name"] for d in get_defaults_metadata() if d["id"] in feature_ids]

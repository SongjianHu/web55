"""Docx Chat Editor —— 聊天式 Word 文档自动排版工具。

业务模块包：FastAPI 服务（main）、LLM 指令解析（llm_parser）、
python-docx 执行层（docx_formatter）、数据模型（schemas）等。
入口见仓库根目录的 run.py。
"""

__version__ = "0.1.0"

# 在任何子模块读取环境变量前，从仓库根目录的 .env 加载（若存在）。
# 缺少 python-dotenv 或 .env 时静默跳过，仍可用 export/set 注入变量。
try:
    from pathlib import Path as _Path

    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(_Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

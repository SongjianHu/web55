"""
问答模式：基于论文格式知识库回答用户的排版/规范问题。

检索策略：上下文直塞 + 提示缓存（Anthropic prompt caching）。
知识库全文作为可缓存的 system 块，多轮提问命中缓存、显著降本提速。
"""
from anthropic import Anthropic

from knowledge_base import get_knowledge_text

QA_MODEL = "claude-sonnet-4-5"

_QA_INSTRUCTION = """你是论文格式规范答疑助手。下方<知识库>包含国标要点与排版规范资料。

回答规则：
1. 仅依据<知识库>内容作答；知识库未覆盖的，明确说明“资料中未明确规定，以下为通用做法”，再给经验性建议。
2. 回答用中文，简洁分点，必要时给出具体格式示例（如参考文献著录样例）。
3. 引用来源时标注资料名（如“依据 GB/T 7714—2015”）。
4. 涉及“本校模板可能不同”的，提醒用户以学校模板为准。
5. 不要编造国标条款号或不存在的规定。
6. 如果用户问的不是论文格式/排版/参考文献相关问题，礼貌说明本助手只负责论文格式答疑。"""

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def answer_question(question: str, history: list = None) -> str:
    """回答一个问题。history: [{role, content}, ...] 可选的多轮上下文。

    知识库放在 system 第二块并标记 cache_control，实现跨请求提示缓存。
    """
    question = (question or "").strip()
    if not question:
        raise ValueError("问题不能为空")

    kb = get_knowledge_text()
    system = [
        {"type": "text", "text": _QA_INSTRUCTION},
        {
            "type": "text",
            "text": "<知识库>\n" + kb + "\n</知识库>",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    messages = []
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})

    client = _get_client()
    resp = client.messages.create(
        model=QA_MODEL,
        max_tokens=1500,
        system=system,
        messages=messages,
    )
    text_block = next((b for b in resp.content if hasattr(b, "text")), None)
    if text_block is None:
        raise ValueError("LLM 返回内容中未找到文本块")
    return text_block.text.strip()

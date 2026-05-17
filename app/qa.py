"""
问答模式：基于论文格式知识库回答用户的排版/规范问题。

检索策略：上下文直塞 + 提示缓存（Anthropic prompt caching）。
知识库全文作为可缓存的 system 块，多轮提问命中缓存、显著降本提速。
"""
from anthropic import Anthropic

from .knowledge_base import get_knowledge_text

QA_MODEL = "claude-sonnet-4-5"

_QA_INSTRUCTION = """你是面向学位论文写作的助手，擅长格式规范（GB/T 7714、GB/T 7713 等）与参考文献著录。
下方<知识库>是可供参考的国标要点与排版规范资料。

回答规则：
1. 先判断用户意图，再决定怎么答——不要把所有问题都套用知识库长篇罗列规则：
   - 用户要你「执行任务」（如把下列文献转成 GB/T 7714 格式、生成/排序/去重参考文献表、
     修订某条著录错误、给出某类型著录模板填好的结果）时，直接按要求产出结果本身，
     依据 GB/T 7714—2015 规则著录即可，不要答非所问，也不要只复述规则不给结果。
   - 用户「问规范/格式问题」时，依据<知识库>作答并标注依据（如“依据 GB/T 7714—2015”）；
     知识库未覆盖时说明“资料中未明确规定，以下为通用做法”，再给经验性建议。
2. 若用户随消息附带<检索文献>，那是其经 OpenAlex 检索勾选的文献；按用户要求处理它们
   （未明确说明时，默认转成 GB/T 7714—2015 顺序编码制著录并用 [1][2]… 依次编号输出）；
   不要臆造缺失信息，字段缺失时标注“[缺:字段名]”并提示补全。
3. 回答用中文，简洁；涉及“本校模板可能不同”的提醒以学校模板为准；不编造国标条款号或不存在的规定。
4. 仅当问题与论文写作/格式/参考文献完全无关（如闲聊、与学术写作无关的请求）时，
   才礼貌说明本助手专注论文写作与格式；除此之外都应尽力帮忙，不要轻易拒答或转移话题。"""

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def answer_question(question: str, history: list = None,
                    references: list = None) -> str:
    """回答一个问题。history: [{role, content}, ...] 可选的多轮上下文。

    references: 可选的 GB/T 7714 著录串列表（用户从 Zotero 库勾选带入），
    作为<Zotero文献>块拼到本轮问题前，供 LLM 校对/生成参考文献。

    知识库放在 system 第二块并标记 cache_control，实现跨请求提示缓存。
    """
    question = (question or "").strip()
    refs = [r.strip() for r in (references or [])
            if isinstance(r, str) and r.strip()]
    if not question and not refs:
        raise ValueError("问题不能为空")

    if refs:
        ref_lines = "\n".join(f"[{i + 1}] {r}" for i, r in enumerate(refs))
        prefix = (
            "我经 OpenAlex 检索并勾选了以下文献，"
            "请在回答时优先据此作答（如需参考文献表，按 GB/T 7714—2015 "
            "顺序编码制著录；字段缺失请指出需补充项）：\n"
            f"<检索文献>\n{ref_lines}\n</检索文献>\n\n"
        )
        question = prefix + (question or "请按 GB/T 7714—2015 规范以上文献的著录格式。")

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

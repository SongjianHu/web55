#!/usr/bin/env python3
"""
auto_caption.py - 自动为 Word 文档中的公式、图片、表格添加题注

用法:
    python auto_caption.py input.docx output.docx [选项]

选项:
    --fig-prefix    图注前缀，默认 "图"
    --tbl-prefix    表注前缀，默认 "表"
    --eq-prefix     公式编号格式，默认 "({n})"
    --font-size     题注字号（pt），默认 10.5
    --chapter N     启用章节编号（如 图 2-1），传入章节号
    --skip-existing 跳过已有题注的图/表（检测紧邻段落）

规则:
    - 公式编号 (n) 追加在同行右侧制表位
    - 图注在图下方居中
    - 表注在表上方（左对齐）
    - 若文档中已有 Caption 样式则复用，否则自动创建

依赖:
    pip install python-docx
"""

import sys
import argparse
from docx import Document
from docx.oxml.ns import qn, nsmap
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Twips
from lxml import etree

# ─────────────────────────── 元素检测 ───────────────────────────

def has_drawing(elem):
    """段落中含有图片（内联图或浮动图）"""
    return (
        elem.find(".//" + qn("w:drawing")) is not None
        or elem.find(".//" + qn("w:pict")) is not None
    )


def has_equation(elem):
    """段落中含有 OMML 公式（Word 原生公式）"""
    return (
        elem.find(".//" + qn("m:oMath")) is not None
        or elem.find(".//" + qn("m:oMathPara")) is not None
    )


def is_caption_paragraph(elem):
    """检测段落是否已应用 Caption 样式"""
    pPr = elem.find(qn("w:pPr"))
    if pPr is None:
        return False
    pStyle = pPr.find(qn("w:pStyle"))
    if pStyle is None:
        return False
    val = pStyle.get(qn("w:val"), "")
    return val.lower() in ("caption", "图注", "表注", "figcaption", "tablecaption")


def get_paragraph_text(elem):
    """提取段落纯文本"""
    texts = []
    for t in elem.iter(qn("w:t")):
        if t.text:
            texts.append(t.text)
    return "".join(texts)


# ─────────────────────────── 页面尺寸 ───────────────────────────

def get_text_width_twips(doc):
    """
    计算正文区宽度（twips，1 twip = 1/1440 英寸），
    用于设置公式编号制表位的位置。
    """
    try:
        sec = doc.sections[0]
        width_emu = sec.page_width - sec.left_margin - sec.right_margin
        # python-docx 以 EMU 存储，1 inch = 914400 EMU，1 inch = 1440 twips
        return int(width_emu / 914400 * 1440)
    except Exception:
        return 8640  # 默认约 6 英寸


# ─────────────────────────── 题注段落构建 ────────────────────────

def _make_rpr(font_size_pt: float, italic=False, color=None) -> OxmlElement:
    """构建 <w:rPr> 运行属性"""
    rPr = OxmlElement("w:rPr")
    half_pt = str(int(font_size_pt * 2))
    for tag in ("w:sz", "w:szCs"):
        e = OxmlElement(tag)
        e.set(qn("w:val"), half_pt)
        rPr.append(e)
    if italic:
        rPr.append(OxmlElement("w:i"))
    if color:
        c = OxmlElement("w:color")
        c.set(qn("w:val"), color)
        rPr.append(c)
    return rPr


def create_caption_para(
    text: str,
    align: str = "center",
    font_size_pt: float = 10.5,
    italic: bool = False,
    use_caption_style: bool = True,
) -> OxmlElement:
    """
    创建一个题注 <w:p> 元素。
    align: 'center' | 'left' | 'right' | 'both'
    """
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")

    if use_caption_style:
        pStyle = OxmlElement("w:pStyle")
        pStyle.set(qn("w:val"), "Caption")
        pPr.append(pStyle)

    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), align)
    pPr.append(jc)

    # 段前段后间距：题注通常 0 磅
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "60")
    pPr.append(spacing)

    p.append(pPr)

    r = OxmlElement("w:r")
    r.append(_make_rpr(font_size_pt, italic=italic))

    t = OxmlElement("w:t")
    t.text = text
    if text and (text[0] == " " or text[-1] == " "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    p.append(r)

    return p


# ─────────────────────────── 公式编号 ────────────────────────────

def inject_equation_number(para_elem, number: int, label: str, right_pos: int):
    """
    在公式段落末尾追加 [Tab][编号] 并设置右对齐制表位。

    right_pos: 右制表位位置（twips）
    """
    # ── 段落属性：添加右制表位 ──
    pPr = para_elem.find(qn("w:pPr"))
    if pPr is None:
        pPr = OxmlElement("w:pPr")
        para_elem.insert(0, pPr)

    tabs = pPr.find(qn("w:tabs"))
    if tabs is None:
        tabs = OxmlElement("w:tabs")
        pPr.append(tabs)

    # 避免重复添加
    existing_positions = {
        t.get(qn("w:pos")) for t in tabs.findall(qn("w:tab"))
    }
    right_pos_str = str(right_pos)
    if right_pos_str not in existing_positions:
        tab_stop = OxmlElement("w:tab")
        tab_stop.set(qn("w:val"), "right")
        tab_stop.set(qn("w:pos"), right_pos_str)
        tabs.append(tab_stop)

    # ── 追加制表符 run ──
    tab_run = OxmlElement("w:r")
    tab_char = OxmlElement("w:tab")
    tab_run.append(tab_char)
    para_elem.append(tab_run)

    # ── 追加编号 run ──
    num_run = OxmlElement("w:r")
    num_rPr = _make_rpr(10.5)
    num_run.append(num_rPr)

    num_t = OxmlElement("w:t")
    num_t.text = label.format(n=number)
    num_run.append(num_t)
    para_elem.append(num_run)


# ─────────────────────────── Caption 样式注册 ────────────────────

def ensure_caption_style(doc):
    """
    若文档中没有 Caption 样式，则创建一个简单的版本。
    """
    styles_elem = doc.element.find(qn("w:styles"))
    if styles_elem is None:
        return

    for style in styles_elem.findall(qn("w:style")):
        sid = style.find(qn("w:styleId"))
        if sid is not None and sid.get(qn("w:val")) == "Caption":
            return  # 已存在

    # 创建 Caption 样式
    style = OxmlElement("w:style")
    style.set(qn("w:type"), "paragraph")
    style.set(qn("w:styleId"), "Caption")

    name_e = OxmlElement("w:name")
    name_e.set(qn("w:val"), "caption")
    style.append(name_e)

    basedOn = OxmlElement("w:basedOn")
    basedOn.set(qn("w:val"), "Normal")
    style.append(basedOn)

    pPr = OxmlElement("w:pPr")
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    pPr.append(jc)
    style.append(pPr)

    rPr = OxmlElement("w:rPr")
    i_e = OxmlElement("w:i")
    rPr.append(i_e)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "21")   # 10.5pt
    rPr.append(sz)
    style.append(rPr)

    styles_elem.append(style)


# ─────────────────────────── 主处理逻辑 ──────────────────────────

def process_document(
    input_path: str,
    output_path: str,
    fig_prefix: str = "图",
    tbl_prefix: str = "表",
    eq_label: str = "({n})",
    font_size: float = 10.5,
    chapter: int = None,
    skip_existing: bool = True,
):
    doc = Document(input_path)
    ensure_caption_style(doc)

    body = doc.element.body
    right_pos = get_text_width_twips(doc)

    fig_count = 0
    tbl_count = 0
    eq_count = 0

    children = list(body)

    # 收集所有需要插入的操作，再统一执行（防止修改时索引漂移）
    # operations: list of dict
    #   type: 'insert_before' | 'insert_after' | 'modify_eq'
    #   index: int  (index in children[])
    #   payload: OxmlElement | (int, str, int)
    operations = []

    def make_number(count):
        if chapter is not None:
            return f"{chapter}-{count}"
        return str(count)

    for i, child in enumerate(children):
        tag = child.tag

        # ── 图片 ──────────────────────────────────────────────────
        if tag == qn("w:p") and has_drawing(child):
            # 检测下一个兄弟是否已有题注
            if skip_existing and i + 1 < len(children):
                nxt = children[i + 1]
                if nxt.tag == qn("w:p") and is_caption_paragraph(nxt):
                    continue

            fig_count += 1
            num_str = make_number(fig_count)
            caption_text = f"{fig_prefix} {num_str}."
            cap_elem = create_caption_para(
                caption_text, align="center", font_size_pt=font_size
            )
            operations.append({"type": "insert_after", "index": i, "payload": cap_elem})

        # ── 公式 ──────────────────────────────────────────────────
        elif tag == qn("w:p") and has_equation(child):
            eq_count += 1
            operations.append({
                "type": "modify_eq",
                "index": i,
                "payload": (eq_count, eq_label, right_pos),
            })

        # ── 表格 ──────────────────────────────────────────────────
        elif tag == qn("w:tbl"):
            # 检测上一个兄弟是否已有题注
            if skip_existing and i > 0:
                prev = children[i - 1]
                if prev.tag == qn("w:p") and is_caption_paragraph(prev):
                    continue

            tbl_count += 1
            num_str = make_number(tbl_count)
            caption_text = f"{tbl_prefix} {num_str}."
            cap_elem = create_caption_para(
                caption_text, align="left", font_size_pt=font_size
            )
            operations.append({"type": "insert_before", "index": i, "payload": cap_elem})

    # ── 执行操作（逆序，防止索引偏移）──────────────────────────
    # 先执行 modify_eq（不影响结构）
    for op in operations:
        if op["type"] == "modify_eq":
            idx = op["index"]
            num, label, rp = op["payload"]
            inject_equation_number(children[idx], num, label, rp)

    # 再执行插入（逆序）
    insert_ops = [op for op in operations if op["type"] in ("insert_before", "insert_after")]
    for op in reversed(insert_ops):
        idx = op["index"]
        elem = op["payload"]
        ref = children[idx]
        if op["type"] == "insert_after":
            ref.addnext(elem)
        else:
            ref.addprevious(elem)

    doc.save(output_path)

    print("─" * 40)
    print(f"✅ 题注添加完成")
    print(f"   公式: {eq_count} 个")
    print(f"   图片: {fig_count} 个")
    print(f"   表格: {tbl_count} 个")
    print(f"   输出: {output_path}")
    print("─" * 40)


# ─────────────────────────── CLI ─────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="自动为 Word 文档中的公式、图片、表格添加题注"
    )
    parser.add_argument("input", help="输入 .docx 文件路径")
    parser.add_argument("output", help="输出 .docx 文件路径")
    parser.add_argument("--fig-prefix", default="图", help="图注前缀（默认：图）")
    parser.add_argument("--tbl-prefix", default="表", help="表注前缀（默认：表）")
    parser.add_argument(
        "--eq-label",
        default="({n})",
        help="公式编号格式，{n} 为序号占位符（默认：({n})）",
    )
    parser.add_argument("--font-size", type=float, default=10.5, help="题注字号 pt（默认：10.5）")
    parser.add_argument(
        "--chapter",
        type=int,
        default=None,
        help="启用章节编号，传入章节号（如 --chapter 2 → 图 2-1）",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="跳过已有 Caption 样式题注的图/表（默认启用）",
    )
    args = parser.parse_args()

    process_document(
        input_path=args.input,
        output_path=args.output,
        fig_prefix=args.fig_prefix,
        tbl_prefix=args.tbl_prefix,
        eq_label=args.eq_label,
        font_size=args.font_size,
        chapter=args.chapter,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
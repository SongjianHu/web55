"""
docx 格式化执行层。所有 python-docx 的"魔法"都封在这里。

设计原则：
1. 同时修改 style 和已有段落，避免直接格式覆盖样式导致的"看起来没生效"问题。
2. 中文字体通过 XML 直接设置 w:eastAsia，否则中文会回退到默认字体。
3. 首行缩进优先用字符数 (w:firstLineChars)，符合中文排版习惯。
"""
import re
from typing import List
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH

from schemas import (
    FormatOperation, FormatProperties,
    PageSetupOperation, PageSetupProperties,
    HeaderFooterOperation, HeaderFooterProperties,
)

_ALIGN_MAP = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

# 纸张尺寸（纵向，单位 cm）
_PAGE_SIZE_MAP = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "B5": (17.6, 25.0),
    "Letter": (21.59, 27.94),
}


# ============= 通用工具 =============

def _set_font_xml(rPr_element, font_name: str = None, font_name_ascii: str = None):
    """设置字体 XML。
    - font_name: 中文/东亚字体 (w:eastAsia, w:cs)
    - font_name_ascii: 西文字体 (w:ascii, w:hAnsi)
    - 只传 font_name 时四种属性统一设为同一字体（向后兼容）。
    """
    if not font_name and not font_name_ascii:
        return
    rFonts = rPr_element.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr_element.insert(0, rFonts)
    if font_name and font_name_ascii:
        # 中西文分开设置
        rFonts.set(qn("w:eastAsia"), font_name)
        rFonts.set(qn("w:cs"), font_name)
        rFonts.set(qn("w:ascii"), font_name_ascii)
        rFonts.set(qn("w:hAnsi"), font_name_ascii)
    elif font_name:
        # 只指定中文字体 → 中英文统一（向后兼容）
        rFonts.set(qn("w:eastAsia"), font_name)
        rFonts.set(qn("w:ascii"), font_name)
        rFonts.set(qn("w:hAnsi"), font_name)
        rFonts.set(qn("w:cs"), font_name)
    else:
        # 只指定西文字体
        rFonts.set(qn("w:ascii"), font_name_ascii)
        rFonts.set(qn("w:hAnsi"), font_name_ascii)


def _set_first_line_indent_chars(pPr_element, chars: float):
    """以"字符数"设置首行缩进（中文排版标准做法）。"""
    ind = pPr_element.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr_element.append(ind)
    ind.set(qn("w:firstLineChars"), str(int(chars * 100)))
    if ind.get(qn("w:firstLine")) is not None:
        del ind.attrib[qn("w:firstLine")]


def _parse_color(hex_str: str) -> RGBColor:
    """解析 'FF0000' 或 '#FF0000' → RGBColor。"""
    hex_str = hex_str.lstrip("#")
    return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


# ============= Style 级别修改 =============

def _apply_to_style(style, props: FormatProperties):
    """修改样式定义本身，后续基于该样式的段落会继承。"""
    if props.font_name or props.font_name_ascii:
        if props.font_name:
            style.font.name = props.font_name
        rPr = style.element.get_or_add_rPr()
        _set_font_xml(rPr, props.font_name, props.font_name_ascii)
    if props.font_size is not None:
        style.font.size = Pt(props.font_size)
    if props.bold is not None:
        style.font.bold = props.bold
    if props.italic is not None:
        style.font.italic = props.italic
    if props.underline is not None:
        style.font.underline = props.underline
    if props.color:
        style.font.color.rgb = _parse_color(props.color)

    pf = style.paragraph_format
    if props.alignment:
        pf.alignment = _ALIGN_MAP.get(props.alignment)
    if props.line_spacing is not None:
        pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        pf.line_spacing = props.line_spacing
    if props.space_before is not None:
        pf.space_before = Pt(props.space_before)
    if props.space_after is not None:
        pf.space_after = Pt(props.space_after)
    if props.first_line_indent_chars is not None:
        pPr = style.element.get_or_add_pPr()
        _set_first_line_indent_chars(pPr, props.first_line_indent_chars)


# ============= 段落级别修改（覆盖直接格式）=============

def _apply_to_paragraph(paragraph, props: FormatProperties):
    """直接作用到段落和它的 run 上，覆盖掉文档里已有的直接格式。"""
    pf = paragraph.paragraph_format
    if props.alignment:
        pf.alignment = _ALIGN_MAP.get(props.alignment)
    if props.line_spacing is not None:
        pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        pf.line_spacing = props.line_spacing
    if props.space_before is not None:
        pf.space_before = Pt(props.space_before)
    if props.space_after is not None:
        pf.space_after = Pt(props.space_after)
    if props.first_line_indent_chars is not None:
        pPr = paragraph._p.get_or_add_pPr()
        _set_first_line_indent_chars(pPr, props.first_line_indent_chars)

    for run in paragraph.runs:
        if props.font_name or props.font_name_ascii:
            if props.font_name:
                run.font.name = props.font_name
            rPr = run._element.get_or_add_rPr()
            _set_font_xml(rPr, props.font_name, props.font_name_ascii)
        if props.font_size is not None:
            run.font.size = Pt(props.font_size)
        if props.bold is not None:
            run.font.bold = props.bold
        if props.italic is not None:
            run.font.italic = props.italic
        if props.underline is not None:
            run.font.underline = props.underline
        if props.color:
            run.font.color.rgb = _parse_color(props.color)


# ============= 目标解析 =============

def _resolve_targets(target: str) -> List[str]:
    if target == "all_headings":
        return [f"Heading {i}" for i in range(1, 7)]
    if target == "all":
        return ["Normal"] + [f"Heading {i}" for i in range(1, 7)]
    return [target]


def _paragraph_style_name(paragraph) -> str:
    try:
        return paragraph.style.name
    except Exception:
        return ""


def _is_heading_style(style_name: str) -> bool:
    """判断样式是否属于标题类，用于确定 section: 节的边界。"""
    return (
        style_name.startswith("Heading")
        or "标题" in style_name
        or "heading" in style_name.lower()
    )


def _resolve_section_paragraphs(doc, heading_text: str) -> List:
    """
    找到文本等于 heading_text 的段落，收集其后所有非标题段落，
    遇到下一个标题类样式的段落时停止。
    用于定位摘要、关键词、前言等没有专属样式的章节正文。
    """
    heading_text = heading_text.strip()
    in_section = False
    result = []
    for para in doc.paragraphs:
        style_name = _paragraph_style_name(para)
        if not in_section:
            if para.text.strip() == heading_text:
                in_section = True
        else:
            if _is_heading_style(style_name):
                break
            result.append(para)
    return result


# ============= 文本格式操作 =============

def _apply_format_op(doc, op: FormatOperation):
    target = op.target

    # ---- section: 语法：按节标题文字定位正文段落 ----
    if target.startswith("section:"):
        heading_text = target[len("section:"):]
        for para in _resolve_section_paragraphs(doc, heading_text):
            _apply_to_paragraph(para, op.properties)
        return

    # ---- 普通样式名 / 内置别名 ----
    target_styles = _resolve_targets(target)

    for style_name in target_styles:
        try:
            style = doc.styles[style_name]
        except KeyError:
            continue
        _apply_to_style(style, op.properties)

    target_set = set(target_styles)
    for para in doc.paragraphs:
        if _paragraph_style_name(para) in target_set:
            _apply_to_paragraph(para, op.properties)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if _paragraph_style_name(para) in target_set:
                        _apply_to_paragraph(para, op.properties)


# ============= 页面设置 =============

def _apply_page_setup(doc, props: PageSetupProperties):
    for section in doc.sections:
        if props.page_size:
            w_cm, h_cm = _PAGE_SIZE_MAP[props.page_size]  # 始终为纵向尺寸
            # 如果当前文档是横向，先把新尺寸也横过来
            if section.page_width > section.page_height:
                w_cm, h_cm = h_cm, w_cm
            section.page_width = Cm(w_cm)
            section.page_height = Cm(h_cm)

        if props.orientation:
            is_landscape = section.page_width > section.page_height
            if props.orientation == "landscape" and not is_landscape:
                section.page_width, section.page_height = section.page_height, section.page_width
            elif props.orientation == "portrait" and is_landscape:
                section.page_width, section.page_height = section.page_height, section.page_width

        if props.margin_top is not None:
            section.top_margin = Cm(props.margin_top)
        if props.margin_bottom is not None:
            section.bottom_margin = Cm(props.margin_bottom)
        if props.margin_left is not None:
            section.left_margin = Cm(props.margin_left)
        if props.margin_right is not None:
            section.right_margin = Cm(props.margin_right)


# ============= 页眉页脚 =============

def _clear_paragraph_content(para):
    """清除段落中所有 run 级别内容，保留段落属性 pPr（对齐等设置）。"""
    p = para._p
    pPr = p.find(qn("w:pPr"))
    for child in list(p):
        if child is not pPr:
            p.remove(child)


def _add_text_run(para, text: str, props: HeaderFooterProperties):
    run = para.add_run(text)
    if props.font_name or props.font_name_ascii:
        if props.font_name:
            run.font.name = props.font_name
        _set_font_xml(run._element.get_or_add_rPr(), props.font_name, props.font_name_ascii)
    if props.font_size is not None:
        run.font.size = Pt(props.font_size)
    if props.bold is not None:
        run.font.bold = props.bold


def _add_field_code_runs(para, field_name: str):
    """向段落追加一个 Word 域代码（PAGE 或 NUMPAGES），标准三段式结构。"""
    r1 = para.add_run()._element
    fc_begin = OxmlElement("w:fldChar")
    fc_begin.set(qn("w:fldCharType"), "begin")
    r1.append(fc_begin)

    r2 = para.add_run()._element
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {field_name} "
    r2.append(instr)

    r3 = para.add_run()._element
    fc_end = OxmlElement("w:fldChar")
    fc_end.set(qn("w:fldCharType"), "end")
    r3.append(fc_end)


def _fill_hf_container(container, props: HeaderFooterProperties):
    """向页眉/页脚容器写入内容（清除旧内容 → 设对齐 → 写文字和域代码）。"""
    if props.clear:
        for para in container.paragraphs:
            _clear_paragraph_content(para)
        return

    para = container.paragraphs[0] if container.paragraphs else container.add_paragraph()
    _clear_paragraph_content(para)

    if props.alignment:
        para.alignment = _ALIGN_MAP.get(props.alignment)

    if props.text:
        tokens = re.split(r"(\{page\}|\{total\})", props.text)
        for token in tokens:
            if token == "{page}":
                _add_field_code_runs(para, "PAGE")
            elif token == "{total}":
                _add_field_code_runs(para, "NUMPAGES")
            elif token:
                _add_text_run(para, token, props)


def _apply_header_footer(doc, props: HeaderFooterProperties):
    page_type = props.page_type or "all"
    is_header = props.location == "header"

    # 文档级：启用奇偶页不同页眉/页脚
    if page_type in ("odd", "even"):
        doc.settings.odd_and_even_pages_header_footer = True

    for section in doc.sections:
        # section 级：启用首页不同页眉/页脚
        if page_type == "first":
            section.different_first_page_header_footer = True

        # 根据 page_type 选取对应容器
        if page_type in ("all", "odd"):
            container = section.header if is_header else section.footer
        elif page_type == "even":
            container = section.even_page_header if is_header else section.even_page_footer
        elif page_type == "first":
            container = section.first_page_header if is_header else section.first_page_footer
        else:
            container = section.header if is_header else section.footer

        _fill_hf_container(container, props)


# ============= 样式查询 =============

def get_used_paragraph_styles(path: str) -> list:
    """返回文档中实际出现过的段落样式名列表（正文区 + 表格单元格），供 LLM 参考。"""
    doc = Document(path)
    used: set = set()
    for para in doc.paragraphs:
        try:
            used.add(para.style.name)
        except Exception:
            pass
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    try:
                        used.add(para.style.name)
                    except Exception:
                        pass
    return sorted(used)


# ============= 主入口 =============

def apply_operations(input_path: str, output_path: str, operations):
    """
    打开文档 → 依次应用所有操作 → 保存。
    支持三类操作：format（文本格式）、page_setup（页面设置）、header_footer（页眉页脚）。
    """
    doc = Document(input_path)

    for op in operations:
        if isinstance(op, PageSetupOperation):
            _apply_page_setup(doc, op.properties)
        elif isinstance(op, HeaderFooterOperation):
            _apply_header_footer(doc, op.properties)
        elif isinstance(op, FormatOperation):
            _apply_format_op(doc, op)

    doc.save(output_path)

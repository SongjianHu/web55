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
from docx.enum.style import WD_STYLE_TYPE

from schemas import (
    FormatOperation, FormatProperties,
    PageSetupOperation, PageSetupProperties,
    HeaderFooterOperation, HeaderFooterProperties,
    KeywordLabelOperation,
    ThreeLineTableOperation, TableContinuationOperation,
    RenumberOperation, CaptionOperation, CrossRefOperation,
    SmartThesisFormatOperation, SmartOutlineOperation, AutoCaptionOperation, TocOperation,
)
from numbering import renumber_all, insert_caption, insert_cross_ref

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


_THESIS_HEADING_LEVEL = {"一级标题": 1, "二级标题": 2, "三级标题": 3}


def _get_heading_level(style_name: str):
    """返回 Heading 样式的层级数 (1-6)，非标题样式返回 None。
    同时识别论文命名样式：一级标题→1, 二级标题→2, 三级标题→3。
    """
    m = re.match(r"^Heading (\d)$", style_name)
    if m:
        return int(m.group(1))
    m = re.match(r"^标题 (\d)$", style_name)
    if m:
        return int(m.group(1))
    return _THESIS_HEADING_LEVEL.get(style_name)


def _is_heading_style(style_name: str) -> bool:
    """判断样式是否属于标题类（内置 Heading / 含"标题"字样的自定义样式）。"""
    return (
        _get_heading_level(style_name) is not None
        or "标题" in style_name
        or "heading" in style_name.lower()
    )


def _resolve_section_paragraphs(doc, heading_text: str) -> List:
    """
    按大纲层级感知的节范围定位：
    - 找到文本 == heading_text 的段落作为节起点
    - 若该段落是 Heading N 样式：收集直到遇到同级（≤N）的标题为止
    - 若是普通段落样式：收集直到遇到任何标题样式为止
    适用于摘要、前言、结论、参考文献、附录等论文节。
    """
    heading_text = heading_text.strip()
    in_section = False
    section_level = None   # 节标题的 Heading 层级，None 表示非 Heading 样式
    result = []

    for para in doc.paragraphs:
        style_name = _paragraph_style_name(para)
        level = _get_heading_level(style_name)

        if not in_section:
            if para.text.strip() == heading_text:
                in_section = True
                section_level = level   # 记录节标题层级
        else:
            # 停止条件：遇到同级或更高层级的标题
            if level is not None:
                if section_level is None or level <= section_level:
                    break
            elif _is_heading_style(style_name):
                # 自定义标题类样式（含"标题"但非 Heading N）
                break
            result.append(para)

    return result


def _resolve_heading_paragraph(doc, heading_text: str):
    """找到文本等于 heading_text 的第一个段落（标题段落本身）。"""
    heading_text = heading_text.strip()
    for para in doc.paragraphs:
        if para.text.strip() == heading_text:
            return para
    return None


def _get_or_create_paragraph_style(doc, style_name: str, base_style: str = "Normal"):
    """获取或新建一个段落样式。新建时继承 base_style（默认 Normal）。"""
    try:
        return doc.styles[style_name]
    except KeyError:
        try:
            base = doc.styles[base_style]
        except KeyError:
            base = doc.styles["Normal"]
        style = doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = base
        return style


# 不随 section:X + create_style 批量切换的专用样式
_SPECIAL_PARA_STYLES = {"图题", "表题", "公式编号"}

_KW_LABEL_DEFAULTS = ["关键词", "关键字", "Keywords", "Key words"]


# ============= 文本格式操作 =============

def _apply_format_op(doc, op: FormatOperation):
    target = op.target
    create_style_name = getattr(op, "create_style", None)

    # ---- heading: 语法：定位特定标题段落本身 ----
    if target.startswith("heading:"):
        heading_text = target[len("heading:"):]
        para = _resolve_heading_paragraph(doc, heading_text)
        if para:
            if create_style_name:
                # 继承原标题样式（保留大纲级别 / 编号等属性）
                style = _get_or_create_paragraph_style(
                    doc, create_style_name, base_style=para.style.name
                )
                _apply_to_style(style, op.properties)
                para.style = style
            else:
                _apply_to_paragraph(para, op.properties)
        return

    # ---- section: 语法：层级感知节范围，定位节内正文段落 ----
    if target.startswith("section:"):
        heading_text = target[len("section:"):]
        paras = _resolve_section_paragraphs(doc, heading_text)
        if create_style_name:
            style = _get_or_create_paragraph_style(doc, create_style_name)
            _apply_to_style(style, op.properties)
            for para in paras:
                # 跳过图题/表题/公式编号等专用样式，避免破坏题注格式
                if para.style.name not in _SPECIAL_PARA_STYLES:
                    para.style = style
        else:
            for para in paras:
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

def _set_gutter_at_top(doc, at_top: bool):
    """文档级开关：装订线在顶部 vs 左侧。位于 settings.xml 的 <w:gutterAtTop/>。"""
    try:
        settings_elem = doc.settings.element
    except Exception:
        return
    el = settings_elem.find(qn("w:gutterAtTop"))
    if at_top:
        if el is None:
            settings_elem.append(OxmlElement("w:gutterAtTop"))
    else:
        if el is not None:
            settings_elem.remove(el)


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

        if props.gutter is not None:
            section.gutter = Cm(props.gutter)

    # 装订线位置（左/顶）— 文档级设置
    if props.gutter_position is not None:
        _set_gutter_at_top(doc, props.gutter_position == "top")


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


def _find_top_level_para_containing(body, marker_text: str):
    """在 body 顶层段落中查找第一个文本包含 marker_text 的 w:p。"""
    for child in body:
        if child.tag != qn("w:p"):
            continue
        text = "".join(t.text or "" for t in child.iter(qn("w:t")))
        if marker_text in text:
            return child
    return None


def _has_section_break_immediately_before(p_elem) -> bool:
    """目标段落正前方是否已有分节符（即上一段 pPr 中含 sectPr）。"""
    prev = p_elem.getprevious()
    while prev is not None and prev.tag not in (qn("w:p"), qn("w:tbl")):
        prev = prev.getprevious()
    if prev is None:
        # 文档开头 = 第一节起点，视为已存在分节
        return True
    if prev.tag != qn("w:p"):
        return False
    pPr = prev.find(qn("w:pPr"))
    return pPr is not None and pPr.find(qn("w:sectPr")) is not None


def _insert_section_break_before(doc, target_p):
    """在 target_p 紧邻前方插入一个 nextPage 分节符。复用 body 末尾 sectPr 的页面设置。"""
    import copy as _copy
    body = doc.element.body

    # 复制 body 末尾的 sectPr 作为新前一节的属性（保持纸张/边距一致）
    body_sectPr = body.find(qn("w:sectPr"))
    if body_sectPr is not None:
        new_sectPr = _copy.deepcopy(body_sectPr)
    else:
        new_sectPr = OxmlElement("w:sectPr")

    # 类型设为 nextPage（新章从下一页起）
    type_el = new_sectPr.find(qn("w:type"))
    if type_el is None:
        type_el = OxmlElement("w:type")
        new_sectPr.insert(0, type_el)
    type_el.set(qn("w:val"), "nextPage")

    # 清除继承下来的 pgNumType/header/footerReference —— 前置节独立配置页码与引用
    for tag in ("w:pgNumType", "w:headerReference", "w:footerReference"):
        for el in list(new_sectPr.findall(qn(tag))):
            new_sectPr.remove(el)

    # 找到/创建宿主段落（分节符必须放在 w:p/pPr 里）
    prev = target_p.getprevious()
    while prev is not None and prev.tag not in (qn("w:p"),):
        prev = prev.getprevious()
    if prev is None:
        host_p = OxmlElement("w:p")
        target_p.addprevious(host_p)
    else:
        host_p = prev

    pPr = host_p.find(qn("w:pPr"))
    if pPr is None:
        pPr = OxmlElement("w:pPr")
        host_p.insert(0, pPr)
    # 清除已有 sectPr，避免重复
    for old in pPr.findall(qn("w:sectPr")):
        pPr.remove(old)
    pPr.append(new_sectPr)


def _section_index_of(doc, target_p) -> int:
    """返回 target_p 所在节的序号（0-indexed）。"""
    body = doc.element.body
    idx = 0
    for child in body:
        if child is target_p:
            return idx
        if child.tag == qn("w:p"):
            pPr = child.find(qn("w:pPr"))
            if pPr is not None and pPr.find(qn("w:sectPr")) is not None:
                idx += 1
    return idx  # 兜底


def _ensure_section_break_at_marker(doc, marker_text: str):
    """确保 marker_text 段落正前方存在分节符；幂等。返回 (body_section_index, marker_para_elem)。

    若文档中没有此 marker，返回 (None, None)。
    """
    body = doc.element.body
    target = _find_top_level_para_containing(body, marker_text)
    if target is None:
        return None, None
    if not _has_section_break_immediately_before(target):
        _insert_section_break_before(doc, target)
    return _section_index_of(doc, target), target


def _set_pgnum_restart(section, start: int = 1):
    """在该节 sectPr 内设置 <w:pgNumType w:start="1"/>，让页码从指定值重新开始。"""
    sectPr = section._sectPr
    pgNumType = sectPr.find(qn("w:pgNumType"))
    if pgNumType is None:
        pgNumType = OxmlElement("w:pgNumType")
        sectPr.append(pgNumType)
    pgNumType.set(qn("w:start"), str(start))


def _clear_hf_container_fully(container):
    """完全清空页眉/页脚容器（用于前置节"无页眉/页脚"场景）。"""
    para = container.paragraphs[0] if container.paragraphs else None
    if para is not None:
        _clear_paragraph_content(para)


def _apply_header_footer(doc, props: HeaderFooterProperties):
    """写入页眉/页脚。

    支持作用范围：
      - apply_to="all"（默认）→ 全文档每一节
      - apply_to="body"        → 仅 body_marker 之后的节；自动插入分节符 + 默认重置页码
      - apply_to="front_matter"→ 仅 body_marker 之前的节

    奇偶页 bug 修复：
      page_type="all" 时若文档已启用奇偶页不同，"all" 必须**同步写入偶数页容器**，
      否则偶数页对应的页眉/页脚保持空白。
    """
    page_type = props.page_type or "all"
    apply_to  = props.apply_to or "all"
    is_header = props.location == "header"

    # 1. 处理作用范围 → 解析出 target_sections
    target_sections = list(doc.sections)
    front_matter_sections = []
    if apply_to in ("body", "front_matter"):
        if not props.body_marker:
            raise ValueError("apply_to=body/front_matter 必须同时提供 body_marker（如'第一章'）")
        body_idx, _marker_p = _ensure_section_break_at_marker(doc, props.body_marker)
        if body_idx is None:
            raise ValueError(f"未在文档中找到包含 '{props.body_marker}' 的段落")
        sections = list(doc.sections)
        if apply_to == "body":
            target_sections      = sections[body_idx:]
            front_matter_sections = sections[:body_idx]
        else:  # front_matter
            target_sections      = sections[:body_idx]

    # 2. 奇偶页处理
    if page_type in ("odd", "even"):
        doc.settings.odd_and_even_pages_header_footer = True
    odd_even_active = bool(doc.settings.odd_and_even_pages_header_footer)

    # 3. 对每个 target section 写入
    for section in target_sections:
        # apply_to != "all" 时把对应容器与前一节解绑，避免继承
        if apply_to != "all":
            try:
                if is_header:
                    section.header.is_linked_to_previous = False
                else:
                    section.footer.is_linked_to_previous = False
            except Exception:
                pass

        if page_type == "first":
            section.different_first_page_header_footer = True
            container = section.first_page_header if is_header else section.first_page_footer
            _fill_hf_container(container, props)
        elif page_type == "odd":
            container = section.header if is_header else section.footer
            _fill_hf_container(container, props)
        elif page_type == "even":
            container = section.even_page_header if is_header else section.even_page_footer
            _fill_hf_container(container, props)
        else:  # page_type == "all"
            primary = section.header if is_header else section.footer
            _fill_hf_container(primary, props)
            if odd_even_active:
                even = section.even_page_header if is_header else section.even_page_footer
                _fill_hf_container(even, props)

    # 4. apply_to=body 时：默认清空前置节同位置容器，且重新开始页码
    if apply_to == "body":
        # 默认重置页码（用户可显式设 False 关闭）
        if props.restart_page_numbering is not False and target_sections:
            _set_pgnum_restart(target_sections[0], start=1)
        # 清空前置节同名容器，避免前置部分意外出现页眉/页脚
        for fs in front_matter_sections:
            try:
                if is_header:
                    fs.header.is_linked_to_previous = False
                    _clear_hf_container_fully(fs.header)
                else:
                    fs.footer.is_linked_to_previous = False
                    _clear_hf_container_fully(fs.footer)
            except Exception:
                pass


# ============= 三线表 =============

def _set_cell_border(cell, **kwargs):
    """设置单元格的上下左右边框，支持 val/sz/color 属性。"""
    tcPr = cell._element.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge in ("top", "bottom", "left", "right"):
        if edge not in kwargs:
            continue
        tag = f"w:{edge}"
        el = tcBorders.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            tcBorders.append(el)
        for attr, val in kwargs[edge].items():
            el.set(qn(f"w:{attr}"), str(val))


def _make_three_line_table(table):
    """将一张表格转换为三线表样式。"""
    rows = table.rows
    nil = {"val": "nil"}

    # 1. 清除所有单元格边框
    for row in rows:
        for cell in row.cells:
            _set_cell_border(cell, top=nil, bottom=nil, left=nil, right=nil)

    # 2. 首行上边框（粗线 1.5pt ≈ sz 12）
    for cell in rows[0].cells:
        _set_cell_border(cell, top={"sz": 12, "val": "single", "color": "000000"})

    # 3. 首行下边框（细线 0.75pt ≈ sz 6）
    for cell in rows[0].cells:
        _set_cell_border(cell, bottom={"sz": 6, "val": "single", "color": "000000"})

    # 4. 末行下边框（粗线）
    for cell in rows[-1].cells:
        _set_cell_border(cell, bottom={"sz": 12, "val": "single", "color": "000000"})


def _apply_three_line_table(doc, op: ThreeLineTableOperation):
    tables = doc.tables
    if not tables:
        return
    if op.table_index is None:
        for table in tables:
            _make_three_line_table(table)
    else:
        idx = op.table_index
        if 0 <= idx < len(tables):
            _make_three_line_table(tables[idx])


# ============= 表格跨页续表 =============

def _make_row_repeat_header(row):
    """在行的 trPr 上加 <w:tblHeader/>，实现跨页时该行自动重复。"""
    tr = row._tr
    trPr = tr.find(qn("w:trPr"))
    if trPr is None:
        trPr = OxmlElement("w:trPr")
        # trPr 必须排在 tc 之前，故插在最前
        tr.insert(0, trPr)
    if trPr.find(qn("w:tblHeader")) is None:
        trPr.append(OxmlElement("w:tblHeader"))


def _make_row_no_split(row):
    """禁止行内分页（<w:cantSplit/>），避免单元格被切成两半。"""
    tr = row._tr
    trPr = tr.find(qn("w:trPr"))
    if trPr is None:
        trPr = OxmlElement("w:trPr")
        tr.insert(0, trPr)
    if trPr.find(qn("w:cantSplit")) is None:
        trPr.append(OxmlElement("w:cantSplit"))


def _make_table_continuation(table, header_rows: int = 1):
    """让表格在跨页时自动重复表头并防止行内截断。

    Word 的 <w:tblHeader/> 是真正的"标题行重复"机制：标记了的行会在每个新页面顶部
    自动出现。多数论文模板用此实现"续表"——续页上虽然没有显式的"续"字，但表头会
    重新出现，保留可读性。
    """
    rows = table.rows
    if not rows:
        return
    n = min(max(1, header_rows), len(rows))
    for row in rows[:n]:
        _make_row_repeat_header(row)
        _make_row_no_split(row)


def _apply_table_continuation(doc, op: TableContinuationOperation):
    tables = doc.tables
    if not tables:
        return
    if op.table_index is None:
        for table in tables:
            _make_table_continuation(table, op.header_rows)
    else:
        idx = op.table_index
        if 0 <= idx < len(tables):
            _make_table_continuation(tables[idx], op.header_rows)


# ============= 文档结构查询 =============

# ── 论文结构识别 ──

_THESIS_RE = {
    "abstract_ch":    re.compile(r'^摘\s*要'),
    "keywords_ch":    re.compile(r'^关键[词字]'),
    "abstract_en":    re.compile(r'^abstract\s*[：:.]?\s*$', re.IGNORECASE),
    "keywords_en":    re.compile(r'^key\s*words?\s*[：:.]', re.IGNORECASE),
    "toc":            re.compile(r'^目\s*录\s*$'),
    "figure_cap":     re.compile(r'^图\s*\d+(?:[—\-–]\d+)?(?:[ \t　]|$)'),
    "table_cap":      re.compile(r'^表\s*\d+(?:[—\-–]\d+)?(?:[ \t　]|$)'),
    "references":     re.compile(r'^参\s*考\s*文\s*献'),
    "acknowledgment": re.compile(r'^(?:致\s*谢|谢\s*辞)'),
    "appendix":       re.compile(r'^附\s*录'),
    "intro":          re.compile(r'^(?:引\s*言|绪\s*论|序\s*言)\s*$'),
    "conclusion":     re.compile(r'^(?:结\s*论|总\s*结|结\s*语)\s*$'),
}

_THESIS_LABEL_MAP = {
    "abstract_ch":    ("abstract_h",    "摘要标题"),
    "keywords_ch":    ("keywords_h",    "关键词标题"),
    "abstract_en":    ("en_abstract_h", "英文摘要标题"),
    "keywords_en":    ("en_keywords_h", "英文关键词"),
    "toc":            ("toc_h",         "目录标题"),
    "figure_cap":     ("figure_caption","图编号"),
    "table_cap":      ("table_caption", "表编号"),
    "references":     ("references",    "参考文献"),
    "acknowledgment": ("acknowledgment","致谢"),
    "appendix":       ("appendix",      "附录标题"),
    "intro":          ("intro_h1",      "引言/绪论"),
    "conclusion":     ("conclusion_h1", "结论"),
}

_COVER_BOILERPLATE_RE = re.compile(
    r'学\s*[校院]|指\s*导|导\s*师|专\s*业|学\s*号|班\s*级|年\s*级'
    r'|学\s*位|申请.*学位|\d{4}\s*年|\d+\s*月\s*\d+\s*日'
)


def _classify_thesis_para(text: str, style_name: str, para_elem) -> tuple | None:
    if not text:
        return None
    level = _get_heading_level(style_name)
    if level is not None:
        return (f"heading_{level}", f"标题{level}级")
    for key, pat in _THESIS_RE.items():
        if pat.match(text):
            return _THESIS_LABEL_MAP[key]
    if _para_has_equation(para_elem):
        return ("equation", "公式")
    return None


def _looks_like_en_title(text: str) -> bool:
    if not text or len(text) < 5 or len(text) > 150:
        return False
    low = text.lower().lstrip()
    if any(low.startswith(p) for p in ("abstract", "key", "keywords", "chapter", "section", "http")):
        return False
    ascii_ratio = sum(1 for c in text if c.isascii()) / len(text)
    return ascii_ratio >= 0.65


def get_thesis_structure(path: str) -> list:
    """智能识别论文各类结构元素，返回带类型标注的列表。

    识别范围：论文题目/摘要/关键词/英文摘要/英文关键词/目录/
    正文多级标题（含引言/绪论/结论）/图编号/表编号/公式编号/
    致谢/参考文献/附录标题；封面样板文字自动跳过。

    返回格式: [{"type": str, "label": str, "text": str, "index": int}, ...]
    """
    doc = Document(path)
    items, abstract_pos, en_abstract_pos, toc_pos = _classify_thesis_paragraphs_in_doc(doc)

    landmarks = [p for p in [abstract_pos, en_abstract_pos, toc_pos] if p is not None]
    first_h1 = next(
        (i for i, x in enumerate(items) if x["cls"] and x["cls"][0] == "heading_1" and i > 3),
        None,
    )
    if first_h1 is not None:
        landmarks.append(first_h1)
    first_landmark = min(landmarks) if landmarks else None

    keep_in_cover = {"thesis_title", "toc_h", "abstract_h", "en_abstract_h"}
    result = []
    for i, info in enumerate(items):
        if not info["cls"] or not info["text"]:
            continue
        type_key = info["cls"][0]
        if first_landmark is not None and i < first_landmark and type_key not in keep_in_cover:
            continue
        result.append({
            "type":  type_key,
            "label": info["cls"][1],
            "text":  info["text"],
            "index": info["idx"],
        })
    return result


def get_document_structure(path: str) -> list:
    """返回文档大纲：所有标题段落的层级与文字，供 LLM 精确填写 section:/heading: 目标。"""
    doc = Document(path)
    result = []
    for para in doc.paragraphs:
        level = _get_heading_level(para.style.name)
        if level is not None and para.text.strip():
            result.append({"level": level, "text": para.text.strip()})
    return result


def get_document_title(path: str) -> str:
    """猜测文档的"论文题目"，供 LLM 在用户说"页眉=论文题目"等场景下取实际文字。

    猜测策略（按优先级）：
    1. 样式为 "Title" / "Subtitle" / "题目" / "论文题目" 的段落
    2. 第一个 Heading 1 段落的文字
    3. 文档前 5 段中：长度合理（4–60 字）、不以"摘要/目录/前言/Abstract"等开头的最大字号段落
    4. 找不到 → 返回空串
    """
    doc = Document(path)

    TITLE_STYLE_HINTS = {"Title", "Subtitle", "题目", "论文题目", "标题", "封面标题"}
    SKIP_PREFIXES     = ("摘要", "目录", "前言", "引言", "abstract", "contents",
                         "keywords", "关键词", "致谢", "声明", "封面")

    def _looks_like_title(text: str) -> bool:
        if not text or len(text) < 4 or len(text) > 80:
            return False
        low = text.strip().lower()
        return not any(low.startswith(p) for p in SKIP_PREFIXES)

    # 策略 1：精确样式名
    for para in doc.paragraphs[:30]:
        try:
            sname = para.style.name or ""
        except Exception:
            sname = ""
        if sname in TITLE_STYLE_HINTS and _looks_like_title(para.text):
            return para.text.strip()

    # 策略 2：第一个 Heading 1 段落
    for para in doc.paragraphs[:50]:
        if _get_heading_level(_paragraph_style_name(para)) == 1 and _looks_like_title(para.text):
            return para.text.strip()

    # 策略 3：前 5 段中字号最大且文字像标题
    candidates = []
    for para in doc.paragraphs[:5]:
        text = para.text.strip()
        if not _looks_like_title(text):
            continue
        # 取第一个 run 的字号；没有则取段落样式定义的字号
        size = 0
        for run in para.runs:
            if run.font.size:
                size = max(size, run.font.size.pt)
        candidates.append((size, text))
    if candidates:
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    return ""


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


# ============= 关键词标签加粗 =============

def _kw_split_pos(text: str, sorted_labels: list) -> int:
    """返回标签+冒号之后的字符位置（即关键词内容起始），未匹配返回 -1。"""
    stripped = text.lstrip()
    lead = len(text) - len(stripped)
    lower = stripped.lower()

    for label in sorted_labels:
        if not lower.startswith(label.lower()):
            continue
        after = stripped[len(label):]
        i = 0
        while i < len(after) and after[i] in (' ', '\t', '　'):
            i += 1
        if i < len(after) and after[i] in ('：', ':'):
            return lead + len(label) + i + 1  # 冒号之后的位置
    return -1


def _apply_keyword_label(doc, labels):
    """将"关键词："/"Keywords:"等标签加粗，冒号后内容不加粗。

    同时搜索正文段落和表格单元格段落，兼容将摘要/关键词放在表格布局中的论文模板。
    """
    if not labels:
        labels = _KW_LABEL_DEFAULTS

    sorted_labels = sorted(labels, key=len, reverse=True)

    # 收集所有段落：正文 + 表格单元格
    all_paras = list(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                all_paras.extend(cell.paragraphs)

    for para in all_paras:
        text = para.text
        if not text:
            continue

        pos = _kw_split_pos(text, sorted_labels)
        if pos < 0:
            continue

        label_text   = text[:pos]
        content_text = text[pos:]

        # 清除段落所有内容元素，保留 pPr（对齐/缩进等段落格式）
        p_elem = para._p
        pPr = p_elem.find(qn("w:pPr"))
        for child in list(p_elem):
            if child is not pPr:
                p_elem.remove(child)

        r_label = para.add_run(label_text)
        r_label.bold = True

        if content_text:
            r_content = para.add_run(content_text)
            r_content.bold = False


# ============= 智能大纲识别 =============

# 默认的"封面级标题"标记词：不带 outlineLvl，**不出现在 TOC**
# 中文常见变体：声明书 / 致谢辞 / 致谢词 等 CJK 后缀通过下方匹配器规则自动识别，无需穷举。
_DEFAULT_TITLE_ONLY_MARKERS = [
    "论文题目", "本文标题", "题目",
    "摘要", "中文摘要", "英文摘要", "摘 要", "中文摘 要",
    "Abstract", "ABSTRACT",
    "致谢", "致 谢", "谢辞",
    "Acknowledgments", "Acknowledgements", "Acknowledgement",
    "声明", "诚信声明", "原创性声明", "学位论文原创性声明", "独创性声明",
    "学位论文版权使用授权书", "原创性承诺书", "保密承诺书",
]

# 默认的"前后置但出现在 TOC"标记词：Heading 1，但不计入正文章节编号
_DEFAULT_BODY_OUTSIDE_MARKERS = [
    "关键词", "关键字", "Keywords", "Key Words", "Key words",
    "目录", "目 录", "Contents", "Table of Contents",
    "前言", "引言", "Preface", "Foreword", "Introduction",
    "参考文献", "参 考 文 献", "References", "REFERENCES", "Bibliography",
    "附录", "附 录", "Appendix", "APPENDIX", "Appendices",
]


def _is_cjk_char(c: str) -> bool:
    """是否中日韩统一汉字（U+4E00–U+9FFF + 扩展 A）。"""
    if not c:
        return False
    code = ord(c)
    return (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF)

# 正文章节："第X章" / "Chapter N:" 等
_CHAPTER_RE = re.compile(
    r"^(?:第\s*[一二三四五六七八九十百千0-9]+\s*章\b|Chapter\s+\d+[:\.\s])",
    re.IGNORECASE,
)
# 子节："1.1 X" / "1.1.1 X" / "1.1.1.1 X"，最深匹配 5 级
_SUB_RE = re.compile(r"^(\d+)((?:\.\d+){1,4})\s+\S")


def _ensure_title_only_style(doc, name: str = "封面标题"):
    """创建无 outlineLvl 的封面标题样式（确保不出现在 TOC）。"""
    try:
        style = doc.styles[name]
    except KeyError:
        style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        try:
            style.base_style = doc.styles["Normal"]
        except KeyError:
            pass
        pf = style.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(18)
        pf.space_after  = Pt(12)
    # 移除任何可能继承来的 outlineLvl（这是 TOC 不收录的关键）
    sty_pPr = style.element.find(qn("w:pPr"))
    if sty_pPr is not None:
        ol = sty_pPr.find(qn("w:outlineLvl"))
        if ol is not None:
            sty_pPr.remove(ol)
    return style


def _smart_outline_set_default_styles(doc):
    """为 Normal / Heading 1–3 / 封面标题 设定标准论文样式。

    - 正文：小四号宋体，首行缩进 2 字符，黑色
    - 标题一：三号黑体（16pt），加粗，居中，**首行不缩进**，黑色（不蓝）
    - 标题二：四号黑体（14pt），加粗，左对齐，**首行不缩进**，黑色
    - 标题三：小四号黑体（12pt），加粗，左对齐，**首行不缩进**，黑色
    - 封面标题：二号黑体（22pt），加粗，居中，黑色
    Word 默认的 Heading N 是蓝色，这里强制覆盖为 #000000。
    """
    # 正文（Normal）
    normal_props = FormatProperties(
        font_name="宋体",
        font_name_ascii="Times New Roman",
        font_size=12,                    # 小四
        color="000000",
        first_line_indent_chars=2,
    )
    try:
        _apply_to_style(doc.styles["Normal"], normal_props)
    except KeyError:
        pass

    # 三级标题统一规则
    heading_specs = [
        ("Heading 1", 16, "center"),     # 三号
        ("Heading 2", 14, "left"),       # 四号
        ("Heading 3", 12, "left"),       # 小四
    ]
    for style_name, size, align in heading_specs:
        try:
            style = doc.styles[style_name]
        except KeyError:
            continue
        props = FormatProperties(
            font_name="黑体",
            font_name_ascii="Times New Roman",
            font_size=size,
            bold=True,
            color="000000",
            first_line_indent_chars=0,    # 强制无首行缩进
            alignment=align,
        )
        _apply_to_style(style, props)

    # 封面标题
    try:
        title_style = doc.styles["封面标题"]
    except KeyError:
        title_style = _ensure_title_only_style(doc, "封面标题")
    _apply_to_style(title_style, FormatProperties(
        font_name="黑体",
        font_name_ascii="Times New Roman",
        font_size=22,                    # 二号
        bold=True,
        color="000000",
        alignment="center",
        first_line_indent_chars=0,
    ))


# 规则 5：附录/Appendix 等 + 单字母/数字标号（可带":描述"）
#   匹配如 " A" / " 1" / " II" / " A: 数据集" / " 1) 模型结构"
_LABEL_SUFFIX_RE = re.compile(
    r"^\s+(?:[A-Za-z]{1,3}|\d{1,3})"
    r"(?:\s*[:：\.\)\]\、\,]\s*\S.{0,30})?\s*$"
)


def _matches_marker_prefix(text: str, markers) -> bool:
    """text 是否是一个 marker 标题段落（而非含 marker 词的正文句子）。

    五档匹配规则（从严到宽）：
      1. 文本（清理后）完全等于 marker
      2. 以 marker 起始，后接**单个 CJK** 字符 → 如"声明书"/"致谢辞"/"致谢词"
         （只取 1 个字符避免"参考文献综述"这类正文片段误判）
      3. 以 marker 起始，后接**仅非字母数字**（≤ 10 个）→ 如"Abstract:"/"摘要（一）"
      4. 以 marker 起始，后接**空格 + 短 CJK 翻译**（≤ 6 个 CJK）→ 如"Abstract 摘要"
      5. 以 marker 起始，后接**空格 + 短标号**（A/B/1/II/...，可选 ":描述"）
         → 如"附录 A"/"附录 1"/"Appendix A"/"附录 A: 数据集"
    """
    if not text:
        return False
    cleaned = text.strip().strip("：:").strip().lower()
    for m in markers:
        ml = m.lower()
        if cleaned == ml:
            return True
        if not cleaned.startswith(ml):
            continue
        rest = cleaned[len(ml):]
        if not rest:
            return True
        # 规则 2：恰好 1 个 CJK 后缀字符
        if len(rest) == 1 and _is_cjk_char(rest):
            return True
        # 规则 3：仅非字母数字，长度 ≤ 10
        if all(not c.isalnum() for c in rest) and len(rest) <= 10:
            return True
        # 规则 4：双语标题（marker = 英文 + 翻译 = 中文）
        # 限定 marker 为纯 ASCII，避免"参考文献综述"/"参考文献的整理方法"
        # 之类中文 marker + 中文后缀的正文片段被误匹配
        if all(ord(c) < 128 for c in ml):
            rest_stripped = rest.strip()
            if rest_stripped and len(rest_stripped) <= 6:
                if all(_is_cjk_char(c) or not c.isalnum() for c in rest_stripped):
                    return True
        # 规则 5：附录式短标号后缀
        if _LABEL_SUFFIX_RE.match(rest):
            return True
    return False


def _set_p_style_id(p_elem, style_id: str):
    """直接覆盖段落的 pStyle/@w:val。"""
    pPr = p_elem.find(qn("w:pPr"))
    if pPr is None:
        pPr = OxmlElement("w:pPr")
        p_elem.insert(0, pPr)
    pStyle = pPr.find(qn("w:pStyle"))
    if pStyle is None:
        pStyle = OxmlElement("w:pStyle")
        pPr.insert(0, pStyle)
    pStyle.set(qn("w:val"), style_id)


def _style_id(doc, name: str) -> str:
    try:
        return doc.styles[name].style_id
    except (KeyError, AttributeError):
        return name


def _is_abstract_marker(text: str, kind: str) -> bool:
    """专门检测"摘要"/"Abstract" 标题段落（严格相等，去掉冒号空白后）。"""
    cleaned = text.strip().strip("：:").strip().lower()
    if kind == "zh":
        return cleaned in ("摘要", "中文摘要")
    if kind == "en":
        return cleaned == "abstract"
    return False


def _apply_smart_outline(doc, op: SmartOutlineOperation):
    """根据段落内容判断标题层级并覆盖样式。

    流程：
      1. 设定 Normal/Heading 1-3/封面标题 标准样式（论文规格 + 强制黑色）
      2. 第一遍：按 marker/正则分类每个顶层段落
      3. 第二遍：检测"摘要/Abstract 上方那段"作为论文题目 → 封面标题
      4. 应用分类
    """
    front = list(op.front_matter) if op.front_matter else list(_DEFAULT_TITLE_ONLY_MARKERS)
    back  = list(op.back_matter)  if op.back_matter  else list(_DEFAULT_BODY_OUTSIDE_MARKERS)

    # Step 1: 覆盖 Normal/Heading/封面标题 默认样式
    _ensure_title_only_style(doc, "封面标题")
    _smart_outline_set_default_styles(doc)

    body = doc.element.body
    id_title  = _style_id(doc, "封面标题")
    id_h1     = _style_id(doc, "Heading 1")
    id_h_lvl  = {n: _style_id(doc, f"Heading {n}") for n in range(2, 7)}

    paragraphs = [c for c in body if c.tag == qn("w:p")]
    # 段落分类：id(p_elem) → target_style_id
    plan = {}

    def text_of(p):
        return "".join(t.text or "" for t in p.iter(qn("w:t"))).strip()

    # Step 2: 主分类
    for p_elem in paragraphs:
        text = text_of(p_elem)
        if not text or len(text) > 120:
            continue

        if _matches_marker_prefix(text, front):
            plan[id(p_elem)] = id_title
            continue
        if _matches_marker_prefix(text, back):
            plan[id(p_elem)] = id_h1
            continue
        if _CHAPTER_RE.match(text):
            plan[id(p_elem)] = id_h1
            continue
        m = _SUB_RE.match(text)
        if m:
            depth = 1 + m.group(2).count(".")
            depth = max(2, min(depth, 6))
            plan[id(p_elem)] = id_h_lvl.get(depth, id_h_lvl[2])

    # Step 3: 论文题目的位置识别（摘要/Abstract 之上）
    # 跳过日期、作者、学号、导师、文档类型 等封面页元数据行
    # 注意 metadata 正则用 search（不带 ^），因为 "学生姓名" 的"姓名:" 不在串首
    _METADATA_RE = re.compile(
        r"(?:"
        r"\d{4}\s*年|"                                       # 2024 年
        r"(?:20|19)\d{2}[\-./]\d{1,2}|"                       # 2024-05 / 2024.5
        # 中文标签 + 冒号
        r"(?:学号|学位|导师|教师|姓名|作者|班级|专业|学院|院系|学校|大学|"
        r"指导教师|研究方向|提交日期|完成日期|答辩日期)\s*[:：]|"
        # 英文标签 + 冒号
        r"(?:author|advisor|supervisor|professor|department|school|"
        r"university|college|major|student\s+id|submitted)\s*:|"
        # F. M. Lastname
        r"(?:[A-Z]\.[\s]?){2,}\b|"
        # 文档类型标签（本科 / 硕士 / 博士 / 学位 毕业论文）
        r"^[一-鿿]{0,4}(?:毕业论文|学位论文|课程论文|学年论文)\s*$"
        r")",
        re.IGNORECASE,
    )

    def _looks_like_title(text: str) -> bool:
        text = text.strip()
        if not text:
            return False
        if len(text) < 6 or len(text) > 120:
            return False
        # 含日期/作者/学号/院校等元数据 → 不是标题
        if _METADATA_RE.search(text):
            return False
        # 含中文分隔（如多个作者用顿号分隔）→ 大概率不是标题
        if re.search(r"[、，,;；][^\s]{0,3}[、，,;；]", text):
            return False
        return True

    def _mark_prev_as_title(i: int, max_back: int = 10):
        """向上扫描 ≤ max_back 段，收集所有"形似标题"的候选，取**最长**的作为论文题目。

        理由：封面页常见结构是 "学校→学位类型→[题目]→作者→导师→日期"。
        题目通常是这一区段里最长的非元数据段；按"长度=信息量"启发式择优。
        """
        candidates = []
        for j in range(i - 1, max(-1, i - 1 - max_back), -1):
            prev = paragraphs[j]
            prev_text = text_of(prev)
            if not prev_text:
                continue
            if id(prev) in plan:
                break  # 已分类，停止上溯
            if _looks_like_title(prev_text):
                candidates.append((j, prev_text))
        if not candidates:
            return
        # 选最长
        candidates.sort(key=lambda c: -len(c[1]))
        j, _ = candidates[0]
        plan[id(paragraphs[j])] = id_title

    for i, p_elem in enumerate(paragraphs):
        text = text_of(p_elem)
        if not text:
            continue
        if _is_abstract_marker(text, "zh") or _is_abstract_marker(text, "en"):
            _mark_prev_as_title(i)

    # Step 4: 应用分类
    for p_elem in paragraphs:
        target_id = plan.get(id(p_elem))
        if target_id:
            _set_p_style_id(p_elem, target_id)


# ============= 自动题注（图/表/公式）=============

def _is_existing_caption(p_elem, cap_type: str) -> bool:
    """判断段落是否已是某类型题注。两种判据：
    1. 段落样式名为 图题/表题/公式编号
    2. 文本以 "图 N" / "表 N" / "(N)" 起始
    """
    pPr = p_elem.find(qn("w:pPr"))
    if pPr is not None:
        pStyle = pPr.find(qn("w:pStyle"))
        if pStyle is not None:
            sid = pStyle.get(qn("w:val")) or ""
            target_styles = {"图": ("图题",), "表": ("表题",), "公式": ("公式编号",)}.get(cap_type, ())
            if sid in target_styles:
                return True
    text = "".join(t.text or "" for t in p_elem.iter(qn("w:t"))).strip()
    if cap_type == "图":
        return bool(re.match(r"^图\s*(?:\d|X)", text))
    if cap_type == "表":
        return bool(re.match(r"^表\s*(?:\d|X)", text))
    if cap_type == "公式":
        return bool(re.match(r"^\s*\(\s*(?:\d|X)", text))
    return False


def _make_placeholder_caption_para(doc, cap_type: str):
    """生成一个占位题注段落 <w:p>，文本为"图 X-Y "/"表 X-Y "/"(X-Y)"，绑定对应样式。"""
    from numbering import CAPTION_STYLE_MAP
    style_name = CAPTION_STYLE_MAP[cap_type]
    placeholder = f"{cap_type} X-Y " if cap_type != "公式" else "(X-Y)"

    new_p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")
    pSty = OxmlElement("w:pStyle")
    pSty.set(qn("w:val"), _style_id(doc, style_name))
    pPr.append(pSty)
    new_p.append(pPr)

    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = placeholder
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    new_p.append(r)
    return new_p


def _para_has_drawing(p_elem) -> bool:
    return next(p_elem.iter(qn("w:drawing")), None) is not None


def _para_has_equation(p_elem) -> bool:
    for tag in ("m:oMath", "m:oMathPara"):
        if next(p_elem.iter(qn(tag)), None) is not None:
            return True
    return False


def _apply_auto_caption(doc, op: AutoCaptionOperation):
    """扫描全文为图/表/公式自动插入题注，最后调用 renumber_all 填实际编号。"""
    from numbering import _ensure_caption_styles
    _ensure_caption_styles(doc)
    body = doc.element.body

    # 用快照避免遍历过程中修改 body 子节点导致迭代异常
    children = list(body)
    for child in children:
        tag = child.tag

        # 图：在图片段落"下方"插题注
        if tag == qn("w:p") and op.fig and _para_has_drawing(child):
            nxt = child.getnext()
            if nxt is not None and nxt.tag == qn("w:p") and _is_existing_caption(nxt, "图"):
                if not op.override_existing:
                    continue
                body.remove(nxt)
            cap = _make_placeholder_caption_para(doc, "图")
            child.addnext(cap)
            continue

        # 公式：在公式段落"右侧"加编号（公式段落自身就是题注的载体）
        if tag == qn("w:p") and op.eq and _para_has_equation(child):
            # 已有公式编号的判定：段落末尾已含 "(X-Y)" 或 "(N-M)"
            text = "".join(t.text or "" for t in child.iter(qn("w:t"))).strip()
            if re.search(r"\(\s*[\dXxYy\-−–]+\)\s*$", text):
                if not op.override_existing:
                    continue
                # 简单覆盖策略：在该公式段落下面新建一个独立公式编号段落
            cap = _make_placeholder_caption_para(doc, "公式")
            child.addnext(cap)
            continue

        # 表：在表格"上方"插题注
        if tag == qn("w:tbl") and op.tbl:
            prev = child.getprevious()
            if prev is not None and prev.tag == qn("w:p") and _is_existing_caption(prev, "表"):
                if not op.override_existing:
                    continue
                body.remove(prev)
            cap = _make_placeholder_caption_para(doc, "表")
            child.addprevious(cap)
            continue

    # 占位符 X-Y 由 renumber_all 替换为真正的"章节-序号"
    renumber_all(doc)


# ============= TOC 域（目录）=============

def _build_toc_field_paragraph(levels: int):
    """构造一个含 TOC 域的段落 <w:p>。用户在 Word 中按 F9 更新即可填充。"""
    p = OxmlElement("w:p")

    def _add_run(*children):
        r = OxmlElement("w:r")
        for c in children:
            r.append(c)
        p.append(r)

    fc_begin = OxmlElement("w:fldChar"); fc_begin.set(qn("w:fldCharType"), "begin")
    _add_run(fc_begin)

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    # \o "1-N" 含 H1..HN；\h 超链接；\z 隐藏制表前导符前的页码（在 Web 视图）；\u 用大纲级别
    instr.text = f' TOC \\o "1-{levels}" \\h \\z \\u '
    _add_run(instr)

    fc_sep = OxmlElement("w:fldChar"); fc_sep.set(qn("w:fldCharType"), "separate")
    _add_run(fc_sep)

    t = OxmlElement("w:t")
    t.text = "在 Word 中按 F9 或右键 → 更新域以生成目录"
    _add_run(t)

    fc_end = OxmlElement("w:fldChar"); fc_end.set(qn("w:fldCharType"), "end")
    _add_run(fc_end)
    return p


def _remove_existing_toc_fields(doc) -> int:
    """删除文档中所有 TOC 域（含被 Word 展开后的多段目录条目）。

    识别策略：
      - 遍历 body 顶层段落，跟踪 fldChar begin/end 配对（栈式，支持嵌套字段如
        TOC 内含 PAGEREF）
      - 若任一 begin 块内出现以 "TOC" 开头的 instrText，则该 begin 对应的整个
        段落范围（从 begin 段到 end 段）整体删除
    返回删除的段落数。
    """
    body = doc.element.body
    children = list(body)

    field_stack = []      # list of [start_idx, is_toc]
    toc_ranges = []       # list of (start_idx, end_idx)

    for i, child in enumerate(children):
        if child.tag != qn("w:p"):
            continue
        for el in child.iter():
            tag = el.tag
            if tag == qn("w:fldChar"):
                fct = el.get(qn("w:fldCharType"))
                if fct == "begin":
                    field_stack.append([i, False])
                elif fct == "end" and field_stack:
                    start_idx, is_toc = field_stack.pop()
                    if is_toc:
                        toc_ranges.append((start_idx, i))
            elif tag == qn("w:instrText"):
                text = (el.text or "").lstrip().upper()
                if text.startswith("TOC") and field_stack:
                    field_stack[-1][1] = True

    indices = set()
    for start, end in toc_ranges:
        for i in range(start, end + 1):
            indices.add(i)

    for i in sorted(indices, reverse=True):
        body.remove(children[i])
    return len(indices)


def _apply_toc(doc, op: TocOperation):
    """删除文档中已存在的 TOC 域，然后在 after_marker 段落后插入新 TOC。"""
    # 先清空所有旧 TOC（防止 marker 后面有过期目录块）
    _remove_existing_toc_fields(doc)

    body = doc.element.body
    target = None
    for child in body:
        if child.tag != qn("w:p"):
            continue
        text = "".join(t.text or "" for t in child.iter(qn("w:t"))).strip()
        if op.after_marker in text:
            target = child
            break
    if target is None:
        # 没找到 marker：在文档开头补一段标记段落作为锚点
        marker_p = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        pSty = OxmlElement("w:pStyle")
        pSty.set(qn("w:val"), _style_id(doc, "Heading 1"))
        pPr.append(pSty)
        marker_p.append(pPr)
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = op.after_marker
        r.append(t)
        marker_p.append(r)
        first_p = next((c for c in body if c.tag == qn("w:p")), None)
        if first_p is not None:
            first_p.addprevious(marker_p)
        else:
            body.insert(0, marker_p)
        target = marker_p

    target.addnext(_build_toc_field_paragraph(op.levels))


# ============= 智能论文样式 =============

# 字号：三号=16pt  四号=14pt  小四=12pt  五号=10.5pt
# outline: 0=大纲一级, 1=大纲二级, None=不设大纲等级
_THESIS_NAMED_STYLES: dict[str, dict] = {
    "论文题目":      dict(fc="黑体",  fa=None,              sz=16,   bold=True,  align="center",  ls=1.5, sb=18, sa=18, ol=None, ind=0),
    "摘要标题":      dict(fc="黑体",  fa=None,              sz=12,   bold=True,  align=None,      ls=1.5, sb=12, sa=6,  ol=None, ind=0),
    "关键词标题":    dict(fc="黑体",  fa=None,              sz=12,   bold=True,  align=None,      ls=1.5, sb=12, sa=6,  ol=None, ind=0),
    "英文论文题目":  dict(fc=None,    fa="Times New Roman", sz=16,   bold=True,  align="center",  ls=1.5, sb=18, sa=18, ol=None, ind=0),
    "英文摘要标题":  dict(fc=None,    fa="Times New Roman", sz=12,   bold=True,  align=None,      ls=1.5, sb=None,sa=None,ol=None,ind=0),
    "英文关键词标题":dict(fc=None,    fa="Times New Roman", sz=12,   bold=True,  align=None,      ls=1.5, sb=None,sa=None,ol=None,ind=0),
    "目录标题":      dict(fc="黑体",  fa=None,              sz=16,   bold=True,  align="center",  ls=1.5, sb=18, sa=18, ol=None, ind=0),
    "图题":          dict(fc="宋体",  fa=None,              sz=10.5, bold=False, align="center",  ls=None,sb=3,  sa=6,  ol=None, ind=0),
    "表题":          dict(fc="黑体",  fa=None,              sz=10.5, bold=False, align="center",  ls=None,sb=6,  sa=3,  ol=None, ind=0),
    "公式编号":      dict(fc="宋体",  fa=None,              sz=12,   bold=False, align="right",   ls=None,sb=None,sa=None,ol=None,ind=0),
    "一级标题":      dict(fc="黑体",  fa=None,              sz=16,   bold=True,  align="center",  ls=1.5, sb=18, sa=18, ol=0,    ind=0),
    "二级标题":      dict(fc="黑体",  fa=None,              sz=14,   bold=True,  align="left",    ls=1.5, sb=12, sa=6,  ol=1,    ind=0),
    "三级标题":      dict(fc="黑体",  fa=None,              sz=12,   bold=True,  align="left",    ls=1.5, sb=6,  sa=3,  ol=None, ind=0),
    "正文":          dict(fc="宋体",  fa="Times New Roman", sz=12,   bold=False, align="justify", ls=1.5, sb=None,sa=None,ol=None,ind=2),
    "致谢标题":      dict(fc="黑体",  fa=None,              sz=16,   bold=True,  align=None,      ls=1.5, sb=18, sa=18, ol=0,    ind=0),
    "参考文献标题":  dict(fc="黑体",  fa=None,              sz=16,   bold=True,  align=None,      ls=1.5, sb=18, sa=18, ol=0,    ind=0),
    "附录标题":      dict(fc="黑体",  fa=None,              sz=16,   bold=True,  align=None,      ls=1.5, sb=18, sa=18, ol=0,    ind=0),
}

# 结构类型 → 命名样式
_THESIS_TYPE_TO_STYLE: dict[str, str] = {
    "thesis_title":    "论文题目",
    "abstract_h":      "摘要标题",
    "keywords_h":      "关键词标题",
    "en_title":        "英文论文题目",
    "en_abstract_h":   "英文摘要标题",
    "en_keywords_h":   "英文关键词标题",
    "toc_h":           "目录标题",
    "figure_caption":  "图题",
    "table_caption":   "表题",
    "equation":        "公式编号",
    "heading_1":       "一级标题",
    "heading_2":       "二级标题",
    "heading_3":       "三级标题",
    "heading_4":       "三级标题",
    "intro_h1":        "一级标题",
    "conclusion_h1":   "一级标题",
    "acknowledgment":  "致谢标题",
    "references":      "参考文献标题",
    "appendix":        "附录标题",
}


def _style_set_outline_level(style, level):
    """在样式的 pPr 中设置 w:outlineLvl。level=0 → 大纲一级, None → 移除。"""
    pPr = style.element.find(qn("w:pPr"))
    if pPr is None:
        pPr = OxmlElement("w:pPr")
        rPr = style.element.find(qn("w:rPr"))
        if rPr is not None:
            rPr.addprevious(pPr)
        else:
            style.element.append(pPr)
    ol = pPr.find(qn("w:outlineLvl"))
    if level is None:
        if ol is not None:
            pPr.remove(ol)
    else:
        if ol is None:
            ol = OxmlElement("w:outlineLvl")
            pPr.append(ol)
        ol.set(qn("w:val"), str(int(level)))


def _create_thesis_named_style(doc, name: str, spec: dict):
    """在文档中创建或更新一个论文命名样式。"""
    try:
        style = doc.styles[name]
    except KeyError:
        style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        try:
            style.base_style = doc.styles["Normal"]
        except KeyError:
            pass

    props = FormatProperties(
        font_name=spec.get("fc"),
        font_name_ascii=spec.get("fa"),
        font_size=spec.get("sz"),
        bold=spec.get("bold"),
        color="000000",
        alignment=spec.get("align"),
        line_spacing=spec.get("ls"),
        space_before=spec.get("sb"),
        space_after=spec.get("sa"),
        first_line_indent_chars=spec["ind"] if spec.get("ind", 0) > 0 else None,
    )
    _apply_to_style(style, props)

    # 明确清除首行缩进（避免继承 Normal 的 2字符缩进）
    if spec.get("ind", 0) == 0:
        pPr_e = style.element.get_or_add_pPr()
        ind_e = pPr_e.find(qn("w:ind"))
        if ind_e is not None:
            for attr in (qn("w:firstLine"), qn("w:firstLineChars")):
                if attr in ind_e.attrib:
                    del ind_e.attrib[attr]

    _style_set_outline_level(style, spec.get("ol"))
    return style


def _classify_thesis_paragraphs_in_doc(doc) -> list:
    """对文档内所有段落执行论文结构分类，返回带上下文感知修正后的列表。

    每项: {"idx": int, "para": Paragraph, "text": str, "cls": tuple|None}
    """
    paras = list(doc.paragraphs)
    items = []
    for idx, para in enumerate(paras):
        text = para.text.strip()
        style_name = ""
        try:
            style_name = para.style.name or ""
        except Exception:
            pass
        cls = _classify_thesis_para(text, style_name, para._element)
        items.append({"idx": idx, "para": para, "text": text, "cls": cls})

    def _find_first(type_key):
        return next((i for i, x in enumerate(items) if x["cls"] and x["cls"][0] == type_key), None)

    abstract_pos    = _find_first("abstract_h")
    en_abstract_pos = _find_first("en_abstract_h")
    toc_pos         = _find_first("toc_h")

    # 中文论文题目
    if abstract_pos is not None:
        for info in reversed(items[:abstract_pos]):
            if not info["text"]:
                continue
            if info["cls"] is not None:
                break
            t = info["text"]
            if 4 <= len(t) <= 80 and not _COVER_BOILERPLATE_RE.search(t) and not t.isdigit():
                info["cls"] = ("thesis_title", "论文题目")
                break

    # 英文论文题目
    if en_abstract_pos is not None:
        kw_pos = _find_first("keywords_h")
        search_start = (kw_pos + 1) if kw_pos is not None else 0
        for info in reversed(items[search_start:en_abstract_pos]):
            if not info["text"]:
                continue
            if info["cls"] is not None:
                break
            if _looks_like_en_title(info["text"]):
                info["cls"] = ("en_title", "英文论文题目")
                break

    return items, abstract_pos, en_abstract_pos, toc_pos


def _detect_and_apply_headings(doc):
    """通过文本内容检测未标记的标题段落，直接赋予论文命名样式（须在创建命名样式之后调用）。

    检测规则（只处理当前无标题样式的段落，避免覆盖已有正确样式）：
    • 引言/绪论/序言/结论/总结/结语 → 一级标题
    • 第N章 X / Chapter N: X       → 一级标题
    • 1.1 X（两级编号）              → 二级标题
    • 1.1.1 X（三级及以上编号）       → 三级标题
    """
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text or len(text) > 120:
            continue
        style_name = ""
        try:
            style_name = para.style.name or ""
        except Exception:
            pass
        # 已有标题样式（含内置 Heading N 和论文命名样式）→ 跳过
        if _get_heading_level(style_name) is not None:
            continue

        target = None
        if _THESIS_RE["intro"].match(text) or _THESIS_RE["conclusion"].match(text):
            target = "一级标题"
        elif _CHAPTER_RE.match(text):
            target = "一级标题"
        else:
            m = _SUB_RE.match(text)
            if m:
                depth = 1 + m.group(2).count(".")
                if depth == 2:
                    target = "二级标题"
                elif depth >= 3:
                    target = "三级标题"

        if target:
            try:
                para.style = doc.styles[target]
            except KeyError:
                pass


def _apply_kw_para_thesis_format(para, type_key: str, doc):
    """关键词段落 run 级格式：'关键词：' 部分用标题字体加粗，其后内容用正文字体。

    段落样式切换为正文，覆盖首行缩进为 0，保留关键词段间距（段前12pt 段后6pt）。
    """
    text = para.text
    pos = _kw_split_pos(text, sorted(_KW_LABEL_DEFAULTS, key=len, reverse=True))

    # 段落样式 → 正文（字号/行距基准）
    try:
        para.style = doc.styles["正文"]
    except KeyError:
        pass

    # 清除继承来的首行缩进
    pPr = para._p.get_or_add_pPr()
    ind = pPr.find(qn("w:ind"))
    if ind is not None:
        for attr in (qn("w:firstLine"), qn("w:firstLineChars")):
            if attr in ind.attrib:
                del ind.attrib[attr]

    # 段间距（与关键词标题样式规格一致）
    pf = para.paragraph_format
    pf.space_before = Pt(12)
    pf.space_after  = Pt(6)

    # 清除现有 run 内容，保留 pPr
    p_elem = para._p
    pPr_el = p_elem.find(qn("w:pPr"))
    for child in list(p_elem):
        if child is not pPr_el:
            p_elem.remove(child)

    label_text   = text[:pos] if pos >= 0 else text
    content_text = text[pos:] if pos >= 0 else ""
    is_ch = (type_key == "keywords_h")

    # 标签 run：黑体（中文）或 Times New Roman（英文），加粗
    r_lbl = para.add_run(label_text)
    r_lbl.font.size = Pt(12)
    r_lbl.bold = True
    _set_font_xml(r_lbl._element.get_or_add_rPr(),
                  "黑体" if is_ch else None,
                  None  if is_ch else "Times New Roman")

    # 内容 run：宋体 + Times New Roman（中文）或 Times New Roman（英文），不加粗
    if content_text:
        r_cnt = para.add_run(content_text)
        r_cnt.font.size = Pt(12)
        r_cnt.bold = False
        _set_font_xml(r_cnt._element.get_or_add_rPr(),
                      "宋体" if is_ch else None,
                      "Times New Roman")


def _apply_smart_thesis_format(doc, op: SmartThesisFormatOperation):
    """创建论文命名样式，并（可选）将识别到的段落切换到对应样式。"""
    # 1. 创建/更新所有命名样式
    for name, spec in _THESIS_NAMED_STYLES.items():
        _create_thesis_named_style(doc, name, spec)

    if not op.apply_to_paragraphs:
        return

    # 2. 内容感知标题检测：为 第N章/1.1/引言/结论 等未标记段落赋予一/二/三级标题样式
    _detect_and_apply_headings(doc)

    # 3. 分类段落（已在上一步更新过标题样式，分类结果更完整）
    items, abstract_pos, en_abstract_pos, toc_pos = _classify_thesis_paragraphs_in_doc(doc)

    # 封面边界
    landmarks = [p for p in [abstract_pos, en_abstract_pos, toc_pos] if p is not None]
    first_h1 = next(
        (i for i, x in enumerate(items) if x["cls"] and x["cls"][0] == "heading_1" and i > 3),
        None,
    )
    if first_h1 is not None:
        landmarks.append(first_h1)
    first_landmark = min(landmarks) if landmarks else None
    keep_in_cover = {"thesis_title", "toc_h", "abstract_h", "en_abstract_h"}

    # 3. 应用样式
    for i, info in enumerate(items):
        cls = info["cls"]
        if cls is None:
            continue
        type_key = cls[0]
        if first_landmark is not None and i < first_landmark and type_key not in keep_in_cover:
            continue

        # 关键词段落：run 级分割——标签用黑体/TNR加粗，内容用正文字体
        if type_key in ("keywords_h", "en_keywords_h"):
            _apply_kw_para_thesis_format(info["para"], type_key, doc)
            continue

        target_style = _THESIS_TYPE_TO_STYLE.get(type_key)
        if target_style is None:
            continue
        try:
            info["para"].style = doc.styles[target_style]
        except (KeyError, Exception):
            pass


# ============= 主入口 =============

def apply_operations(input_path: str, output_path: str, operations):
    """
    打开文档 → 依次应用所有操作 → 保存。
    支持七类操作：format / page_setup / header_footer / keyword_label / three_line_table / renumber / caption / cross_ref。
    """
    doc = Document(input_path)
    needs_renumber = False

    for op in operations:
        if isinstance(op, PageSetupOperation):
            _apply_page_setup(doc, op.properties)
        elif isinstance(op, HeaderFooterOperation):
            _apply_header_footer(doc, op.properties)
        elif isinstance(op, FormatOperation):
            _apply_format_op(doc, op)
        elif isinstance(op, KeywordLabelOperation):
            _apply_keyword_label(doc, op.labels)
        elif isinstance(op, ThreeLineTableOperation):
            _apply_three_line_table(doc, op)
        elif isinstance(op, TableContinuationOperation):
            _apply_table_continuation(doc, op)
        elif isinstance(op, RenumberOperation):
            renumber_all(doc)
        elif isinstance(op, CaptionOperation):
            p = op.properties
            insert_caption(doc, p.caption_type, p.after_text, p.description)
            needs_renumber = True
        elif isinstance(op, CrossRefOperation):
            p = op.properties
            insert_cross_ref(doc, p.bookmark_name, p.display_text, p.in_paragraph_containing)
        elif isinstance(op, SmartThesisFormatOperation):
            _apply_smart_thesis_format(doc, op)
        elif isinstance(op, SmartOutlineOperation):
            _apply_smart_outline(doc, op)
        elif isinstance(op, AutoCaptionOperation):
            _apply_auto_caption(doc, op)
            # auto_caption 已自带 renumber_all，不再额外触发
        elif isinstance(op, TocOperation):
            _apply_toc(doc, op)

    # 插入题注后统一重新编号一次
    if needs_renumber:
        renumber_all(doc)

    doc.save(output_path)

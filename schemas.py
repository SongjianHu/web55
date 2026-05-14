"""
数据结构定义。LLM 输出严格遵循这里的 schema，便于后续校验和扩展。
"""
from typing import Optional, List, Literal, Union, Annotated
from pydantic import BaseModel, Field, model_validator

# ===== 文本/段落格式 =====

# TargetType 接受任意字符串：
#   内置别名   : "all_headings"（所有标题）、"all"（正文+所有标题）
#   Word 内置  : "Normal"、"Heading 1"–"Heading 6"、"Title"、"Subtitle" …
#   自定义样式 : 文档模板中定义的任意中文样式名，如 "摘要"、"关键词"、"参考文献" 等
#   节定位语法 : "section:摘要" —— 找到文中文本为"摘要"的段落，对其后所有正文段落（到下一标题止）应用格式
#               适用于文档中没有对应专属样式、但有明确节标题文字的情况
TargetType = str

AlignmentType = Literal["left", "center", "right", "justify"]


class FormatProperties(BaseModel):
    """单次修改可设置的格式属性，全部可选——LLM 只填用户提到的字段。"""
    font_name: Optional[str] = Field(None, description="中文字体名（东亚字符），如 宋体/黑体/仿宋/楷体；若未指定 font_name_ascii 则中英文统一用此字体")
    font_name_ascii: Optional[str] = Field(None, description="西文字体名（英文字母/数字），如 Times New Roman/Arial/Calibri；常与 font_name 同时用，分别控制中英文")
    font_size: Optional[float] = Field(None, description="字号 pt，小四=12, 四号=14, 小三=15, 三号=16")
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    color: Optional[str] = Field(None, description="16进制颜色，如 FF0000 红色，000000 黑色")
    alignment: Optional[AlignmentType] = Field(None, description="对齐方式")
    line_spacing: Optional[float] = Field(None, description="行距倍数，1.5 = 1.5 倍行距")
    space_before: Optional[float] = Field(None, description="段前距 pt")
    space_after: Optional[float] = Field(None, description="段后距 pt")
    first_line_indent_chars: Optional[float] = Field(None, description="首行缩进字符数，论文常用 2")


class FormatOperation(BaseModel):
    type: Literal["format"] = "format"
    target: TargetType = Field(
        ...,
        description=(
            "目标段落范围。可填：\n"
            "  内置别名: all / all_headings\n"
            "  Word 内置样式: Normal / Heading 1-6\n"
            "  自定义样式名: 文档中存在的任意样式\n"
            "  section:X  — 文中标题文字为 X 的节的正文（层级感知）\n"
            "  heading:X  — 文中标题文字为 X 的标题段落本身"
        )
    )
    properties: FormatProperties
    create_style: Optional[str] = Field(
        None,
        description=(
            "若指定，则创建/更新此名称的段落样式，并将目标段落切换为该样式。"
            "适合为论文各节（摘要/前言/结论等）自动建立专属样式，方便后续统一修改。"
        )
    )


# ===== 页面设置 =====

class PageSetupProperties(BaseModel):
    """页面设置属性。"""
    page_size: Optional[Literal["A4", "A3", "B5", "Letter"]] = Field(None, description="纸张大小")
    orientation: Optional[Literal["portrait", "landscape"]] = Field(
        None, description="页面方向：portrait 纵向，landscape 横向"
    )
    margin_top: Optional[float] = Field(None, description="上边距 cm，论文常用 2.54 或 3")
    margin_bottom: Optional[float] = Field(None, description="下边距 cm")
    margin_left: Optional[float] = Field(None, description="左边距 cm，论文常用 2.54 或 3.17")
    margin_right: Optional[float] = Field(None, description="右边距 cm")
    gutter: Optional[float] = Field(
        None,
        description="装订线宽度 cm，论文常用 0.5–1.0；与边距并存（实际边距 = margin + gutter）"
    )
    gutter_position: Optional[Literal["left", "top"]] = Field(
        None,
        description="装订线位置：left 左侧（默认）/ top 顶部；横向装订时用 top"
    )


class PageSetupOperation(BaseModel):
    type: Literal["page_setup"] = "page_setup"
    properties: PageSetupProperties


# ===== 页眉页脚 =====

class HeaderFooterProperties(BaseModel):
    """页眉或页脚属性。text 支持 {page} 页码和 {total} 总页数占位符。"""
    location: Literal["header", "footer"] = Field(..., description="header=页眉, footer=页脚")
    page_type: Optional[Literal["all", "odd", "even", "first"]] = Field(
        "all",
        description="页面类型：all=全部页（默认），odd=奇数页，even=偶数页，first=首页；"
                    "设置 odd/even 会自动启用奇偶页不同功能，设置 first 会自动启用首页不同功能"
    )
    text: Optional[str] = Field(
        None,
        description="内容文本，支持占位符：{page} 当前页码，{total} 总页数。如 '第{page}页共{total}页'"
    )
    alignment: Optional[AlignmentType] = Field(None, description="对齐方式")
    font_name: Optional[str] = Field(None, description="中文字体名")
    font_name_ascii: Optional[str] = Field(None, description="西文字体名（英文/数字）")
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    clear: Optional[bool] = Field(None, description="true 则清除页眉/页脚所有内容")

    apply_to: Optional[Literal["all", "body", "front_matter"]] = Field(
        "all",
        description=(
            "作用范围：all=全部页（默认）；body=仅正文（body_marker 之后的章节）；"
            "front_matter=仅前置部分（封面/摘要/目录，body_marker 之前）。"
            "选择 body/front_matter 时，会自动在 body_marker 段前插入分节符（已存在则复用），"
            "并把对应章节的页眉/页脚与前一节断开链接（is_linked_to_previous=False）。"
        )
    )
    body_marker: Optional[str] = Field(
        None,
        description=(
            "正文起始段落的标识文字（仅在 apply_to=body/front_matter 时使用）。"
            "常用值：'第一章'/'绪论'/'引言'/'第1章'。"
            "系统会从文档中找第一个含此文字的顶层段落作为正文起点，并在其前插入分节符。"
        )
    )
    restart_page_numbering: Optional[bool] = Field(
        None,
        description=(
            "apply_to=body 时是否让正文页码从 1 重新开始。默认 True；"
            "若希望保留前置部分的页码序列连续，可设为 False。"
        )
    )


class HeaderFooterOperation(BaseModel):
    type: Literal["header_footer"] = "header_footer"
    properties: HeaderFooterProperties


# ===== 关键词标签加粗 =====

class KeywordLabelOperation(BaseModel):
    """将"关键词："/"Keywords:"等标签加粗，冒号后的关键词内容保持不加粗。"""
    type: Literal["keyword_label"] = "keyword_label"
    labels: Optional[List[str]] = Field(
        None,
        description="要匹配的标签词列表（大小写不敏感），默认匹配：关键词、关键字、Keywords、Key words"
    )


# ===== 三线表 =====

class ThreeLineTableOperation(BaseModel):
    """将指定表格设置为三线表样式（上粗线、表头下细线、底粗线，其余边框清除）。"""
    type: Literal["three_line_table"] = "three_line_table"
    table_index: Optional[int] = Field(
        None,
        description="目标表格序号（从 0 起），None 表示对文档中全部表格生效"
    )


class TableContinuationOperation(BaseModel):
    """跨页表格续表设置：标题行在每页重复，并禁止行内分页（避免行被切成两半）。"""
    type: Literal["table_continuation"] = "table_continuation"
    table_index: Optional[int] = Field(
        None,
        description="目标表格序号（从 0 起），None 表示对文档中全部表格生效"
    )
    header_rows: int = Field(
        1,
        ge=1,
        le=5,
        description="作为标题行重复显示的前 N 行行数，常用 1（仅列名）或 2（含表题）"
    )


# ===== 自动编号 =====

class RenumberOperation(BaseModel):
    """重新扫描并编号全文中所有图题/表题/公式编号段落。"""
    type: Literal["renumber"] = "renumber"


class CaptionProperties(BaseModel):
    caption_type: Literal["图", "表", "公式"] = Field(..., description="题注类型")
    after_text: Optional[str] = Field(None, description="在含此文字的段落之后插入；None=追加到末尾")
    description: Optional[str] = Field(None, description="题注说明文字；None=用占位符")


class CaptionOperation(BaseModel):
    """插入图题/表题/公式编号段落，插入后自动触发重新编号。"""
    type: Literal["caption"] = "caption"
    properties: CaptionProperties


class CrossRefProperties(BaseModel):
    bookmark_name: str = Field(..., description="书签名，格式 fig_X_Y / tab_X_Y / eq_X_Y")
    display_text: str = Field(..., description="显示文字，如 图1-1 / 表2-3 / 公式1-2")
    in_paragraph_containing: Optional[str] = Field(
        None, description="定位段落：含此文字的第一个段落末尾追加引用"
    )


class CrossRefOperation(BaseModel):
    """在指定段落末尾插入 Word REF 域交叉引用。"""
    type: Literal["cross_ref"] = "cross_ref"
    properties: CrossRefProperties


# ===== 智能论文样式 =====

class SmartThesisFormatOperation(BaseModel):
    """一键创建论文规范命名样式并应用到识别出的结构元素。

    创建的样式（如不存在则新建）：
      论文题目 / 英文论文题目 / 摘要标题 / 关键词标题 /
      英文摘要标题 / 英文关键词标题 / 目录标题 /
      一级标题 / 二级标题 / 三级标题 / 正文 /
      图题 / 表题 / 公式编号 /
      致谢标题 / 参考文献标题 / 附录标题

    同时识别引言/绪论/结论等无编号一级标题并应用"一级标题"样式。
    """
    type: Literal["smart_thesis_format"] = "smart_thesis_format"
    apply_to_paragraphs: bool = Field(
        True,
        description="True=将识别到的段落切换到对应命名样式；False=仅创建样式定义，不修改段落"
    )


# ===== 智能大纲识别 =====

class SmartOutlineOperation(BaseModel):
    """通过内容识别自动指派多级标题样式（覆盖已有样式）。

    分类规则：
      封面标题（论文题目/摘要/Abstract/致谢/声明）→ "封面标题" 样式（无大纲级别，不进入 TOC）
      前后置（关键词/目录/前言/引言/参考文献/附录）→ Heading 1（进入 TOC，但不计入正文章节序号）
      正文章节（"第N章 X" / "Chapter N: X"）→ Heading 1（计入正文章节）
      子节（N.N / N.N.N / N.N.N.N）→ Heading 2 / Heading 3 / Heading 4
    """
    type: Literal["smart_outline"] = "smart_outline"
    front_matter: Optional[List[str]] = Field(
        None,
        description="封面级（不进入 TOC）标记词列表，默认：论文题目/摘要/Abstract/致谢/声明 等"
    )
    back_matter: Optional[List[str]] = Field(
        None,
        description="后置但出现在 TOC 的标记词列表，默认：参考文献/附录/致谢 等"
    )


# ===== 自动题注 =====

class AutoCaptionOperation(BaseModel):
    """扫描全文为图/表/公式自动插入题注（按章节编号 X-Y）。

    位置：
      图题：图片段落**下方**
      表题：表格**上方**
      公式编号：公式段落**右端**（使用右制表位）
    现有题注存在时根据 override_existing 决定保留或覆盖。
    """
    type: Literal["auto_caption"] = "auto_caption"
    fig: bool = Field(True, description="是否处理图")
    tbl: bool = Field(True, description="是否处理表")
    eq:  bool = Field(True, description="是否处理公式")
    override_existing: bool = Field(
        True,
        description="True 则先移除已有的相邻题注再重新插入；False 则跳过已有题注的对象"
    )


# ===== 目录生成 =====

class TocOperation(BaseModel):
    """在标记段落后插入 Word TOC 域（基于现有标题样式自动生成目录）。

    用户需要在 Word 中按 F9 或右键 → 更新域来填充目录内容。
    """
    type: Literal["toc"] = "toc"
    after_marker: str = Field(
        "目录",
        description="在含此文字的段落之后插入 TOC 域；通常是文档中已有的「目录」段落"
    )
    levels: int = Field(
        3, ge=1, le=9,
        description="包含的标题层级（1-N）。论文常用 3，含 H1/H2/H3"
    )


# ===== 联合类型 =====

AnyOperation = Annotated[
    Union[
        FormatOperation, PageSetupOperation, HeaderFooterOperation,
        KeywordLabelOperation, ThreeLineTableOperation, TableContinuationOperation,
        RenumberOperation, CaptionOperation, CrossRefOperation,
        SmartThesisFormatOperation, SmartOutlineOperation, AutoCaptionOperation, TocOperation,
    ],
    Field(discriminator="type")
]


class ParsedCommand(BaseModel):
    """LLM 解析用户消息后的结构化结果。"""
    operations: List[AnyOperation]
    explanation: str = ""
    # 长文本输入时由两阶段管线填入：第一阶段提取出的"已剔除无关信息的排版要求清单"
    distilled: str = ""

    @model_validator(mode="before")
    @classmethod
    def _inject_default_type(cls, data):
        """为没有 type 字段的 operation 补充默认值 'format'，保持向后兼容。"""
        for op in data.get("operations", []):
            if isinstance(op, dict) and "type" not in op:
                op["type"] = "format"
        return data

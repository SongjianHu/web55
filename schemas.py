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
        description="样式名：内置别名(all/all_headings)、Word 内置样式(Normal/Heading 1…)、或文档中任意自定义样式名"
    )
    properties: FormatProperties


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


class HeaderFooterOperation(BaseModel):
    type: Literal["header_footer"] = "header_footer"
    properties: HeaderFooterProperties


# ===== 联合类型 =====

AnyOperation = Annotated[
    Union[FormatOperation, PageSetupOperation, HeaderFooterOperation],
    Field(discriminator="type")
]


class ParsedCommand(BaseModel):
    """LLM 解析用户消息后的结构化结果。"""
    operations: List[AnyOperation]
    explanation: str = ""

    @model_validator(mode="before")
    @classmethod
    def _inject_default_type(cls, data):
        """为没有 type 字段的 operation 补充默认值 'format'，保持向后兼容。"""
        for op in data.get("operations", []):
            if isinstance(op, dict) and "type" not in op:
                op["type"] = "format"
        return data

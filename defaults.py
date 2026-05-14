"""
论文排版默认功能库。

每个条目代表一项常见学术排版规则，关联若干可执行的 operations。
前端勾选后，POST /apply_defaults 会按 ORDER 顺序执行所选条目对应的 ops。
"""

# 类目展示顺序（前端折叠面板分组用）
CATEGORY_ORDER = ["智能", "页面", "字体", "标题", "节专属", "题注", "表格", "页眉页脚", "编号"]


# 每条 default 结构：
#   id          唯一标识（前端 → 后端传递）
#   name        中文短名（勾选行展示）
#   category    分组名（与 CATEGORY_ORDER 对应）
#   description 鼠标悬浮详细说明
#   ops         对应的 operations（按 SYSTEM_PROMPT 中规定的全局顺序执行）
DEFAULTS = [
    # ===== 页面 =====
    {
        "id": "page_a4_standard",
        "name": "A4 + 标准页边距",
        "category": "页面",
        "description": "纸张 A4，上下边距 2.54cm，左右边距 3.17cm（学位论文常用）",
        "ops": [{
            "type": "page_setup",
            "properties": {
                "page_size": "A4",
                "margin_top": 2.54, "margin_bottom": 2.54,
                "margin_left": 3.17, "margin_right": 3.17,
            },
        }],
    },
    {
        "id": "binding_gutter_left_1cm",
        "name": "装订线：左侧 1cm",
        "category": "页面",
        "description": (
            "在左侧加 1cm 装订线（不与左边距合并）。打印装订时该宽度不会落到正文区，"
            "保证装订后左侧文字不被遮挡。横向装订改用「装订线：顶部」。"
        ),
        "ops": [{
            "type": "page_setup",
            "properties": {"gutter": 1.0, "gutter_position": "left"},
        }],
    },

    # ===== 字体（全局正文 / 各级标题）=====
    {
        "id": "body_song_xiaosi",
        "name": "正文：宋体小四 / Times New Roman",
        "category": "字体",
        "description": (
            "中文宋体、西文 Times New Roman，字号小四（12pt），"
            "1.5 倍行距，首行缩进 2 字符。论文正文通用规格。"
        ),
        "ops": [{
            "type": "format",
            "target": "Normal",
            "properties": {
                "font_name": "宋体",
                "font_name_ascii": "Times New Roman",
                "font_size": 12,
                "line_spacing": 1.5,
                "first_line_indent_chars": 2,
            },
        }],
    },
    {
        "id": "heading_h1_san_hei",
        "name": "一级标题：黑体三号居中",
        "category": "标题",
        "description": "Heading 1 → 黑体 + Times New Roman，三号 (16pt) 加粗居中，段前段后各 12pt",
        "ops": [{
            "type": "format",
            "target": "Heading 1",
            "properties": {
                "font_name": "黑体",
                "font_name_ascii": "Times New Roman",
                "font_size": 16,
                "bold": True,
                "alignment": "center",
                "space_before": 12, "space_after": 12,
            },
        }],
    },
    {
        "id": "heading_h2_song_xiaosan",
        "name": "二级标题：宋体小三加粗",
        "category": "标题",
        "description": "Heading 2 → 宋体加粗，小三 (15pt)，左对齐，段前 6pt 段后 6pt",
        "ops": [{
            "type": "format",
            "target": "Heading 2",
            "properties": {
                "font_name": "宋体",
                "font_name_ascii": "Times New Roman",
                "font_size": 15,
                "bold": True,
                "alignment": "left",
                "space_before": 6, "space_after": 6,
            },
        }],
    },
    {
        "id": "heading_h3_song_sihao",
        "name": "三级标题：宋体四号加粗",
        "category": "标题",
        "description": "Heading 3 → 宋体加粗，四号 (14pt)，左对齐",
        "ops": [{
            "type": "format",
            "target": "Heading 3",
            "properties": {
                "font_name": "宋体",
                "font_name_ascii": "Times New Roman",
                "font_size": 14,
                "bold": True,
                "alignment": "left",
            },
        }],
    },
    {
        "id": "heading_h4_song_xiaosi",
        "name": "四级标题：宋体小四加粗",
        "category": "标题",
        "description": "Heading 4 → 宋体加粗，小四 (12pt)，左对齐，缩进 2 字符",
        "ops": [{
            "type": "format",
            "target": "Heading 4",
            "properties": {
                "font_name": "宋体",
                "font_name_ascii": "Times New Roman",
                "font_size": 12,
                "bold": True,
                "alignment": "left",
                "first_line_indent_chars": 2,
            },
        }],
    },

    # ===== 节专属样式 =====
    {
        "id": "abstract_song_wuhao",
        "name": "中文摘要：宋体五号",
        "category": "节专属",
        "description": (
            "把「摘要」节正文设为宋体五号 (10.5pt)，1.5 倍行距，"
            "并新建「摘要正文」样式以便后续统一调整。"
        ),
        "ops": [{
            "type": "format",
            "target": "section:摘要",
            "create_style": "摘要正文",
            "properties": {
                "font_name": "宋体",
                "font_name_ascii": "Times New Roman",
                "font_size": 10.5,
                "line_spacing": 1.5,
            },
        }],
    },
    {
        "id": "references_song_wuhao",
        "name": "参考文献：宋体五号",
        "category": "节专属",
        "description": (
            "把「参考文献」节正文设为宋体五号 (10.5pt)，单倍行距，"
            "新建「参考文献条目」样式。GB/T 7714 顺序编码制配套规格。"
        ),
        "ops": [{
            "type": "format",
            "target": "section:参考文献",
            "create_style": "参考文献条目",
            "properties": {
                "font_name": "宋体",
                "font_name_ascii": "Times New Roman",
                "font_size": 10.5,
                "line_spacing": 1.0,
            },
        }],
    },

    # ===== 题注 =====
    {
        "id": "caption_centered_wuhao",
        "name": "图题/表题：宋体五号居中",
        "category": "题注",
        "description": "图题、表题、公式编号统一为宋体五号 (10.5pt) 居中，段前段后 6pt",
        "ops": [
            {"type": "format", "target": "图题",
             "properties": {"font_name": "宋体", "font_name_ascii": "Times New Roman",
                            "font_size": 10.5, "alignment": "center",
                            "space_before": 6, "space_after": 6}},
            {"type": "format", "target": "表题",
             "properties": {"font_name": "宋体", "font_name_ascii": "Times New Roman",
                            "font_size": 10.5, "alignment": "center",
                            "space_before": 6, "space_after": 6}},
            {"type": "format", "target": "公式编号",
             "properties": {"font_name": "宋体", "font_name_ascii": "Times New Roman",
                            "font_size": 10.5, "alignment": "center"}},
        ],
    },
    {
        "id": "keyword_label_bold",
        "name": "关键词标签加粗",
        "category": "节专属",
        "description": (
            "查找以「关键词：」/「Keywords:」等开头的段落，"
            "把标签部分（含冒号）加粗，冒号后的关键词内容保持不加粗。"
        ),
        "ops": [{"type": "keyword_label"}],
    },

    # ===== 表格 =====
    {
        "id": "all_tables_three_line",
        "name": "全部表格转三线表",
        "category": "表格",
        "description": (
            "无竖线、无斜线、无色块——仅保留：顶线 (1.5pt 粗)、"
            "表头分隔线 (0.75pt 细)、底线 (1.5pt 粗)。学位论文/期刊通用规范。"
        ),
        "ops": [{"type": "three_line_table", "table_index": None}],
    },
    {
        "id": "all_tables_continuation",
        "name": "跨页续表（首行表头自动重复）",
        "category": "表格",
        "description": (
            "为全部表格启用跨页续表机制：首行作为标题行，跨页时自动在新页面顶部重复，"
            "并禁止行内分页（cantSplit）防止单元格被切成两半。"
            "Word 通过 <w:tblHeader/> 内建支持，比手动复制表头更可靠。"
        ),
        "ops": [{
            "type": "table_continuation",
            "table_index": None,
            "header_rows": 1,
        }],
    },

    # ===== 页眉页脚 =====
    {
        "id": "header_thesis_title",
        "name": "页眉：论文题目居中",
        "category": "页眉页脚",
        "description": (
            "把页眉设为论文题目（自动从文档内容识别实际题目，"
            "不会把「论文题目」四个字字面写入），居中宋体小五。"
        ),
        # 注意：text 用占位符 {THESIS_TITLE}，由后端在 apply_defaults 时替换为实际题目
        "ops": [{
            "type": "header_footer",
            "properties": {
                "location": "header",
                "text": "{THESIS_TITLE}",
                "alignment": "center",
                "font_name": "宋体",
                "font_size": 9,
            },
        }],
    },
    {
        "id": "footer_page_x_of_y",
        "name": "页脚：第X页共Y页",
        "category": "页眉页脚",
        "description": "页脚居中显示「第X页共Y页」格式，自动使用 Word 域更新",
        "ops": [{
            "type": "header_footer",
            "properties": {
                "location": "footer",
                "text": "第{page}页共{total}页",
                "alignment": "center",
                "font_name": "宋体",
                "font_size": 9,
            },
        }],
    },
    {
        "id": "footer_body_only_page",
        "name": "页脚：仅正文显示页码（从第一章起重新编号）",
        "category": "页眉页脚",
        "description": (
            "在「第一章」前自动插入分节符；前置部分（封面/摘要/目录）页脚清空，"
            "正文页脚居中显示阿拉伯页码并从第 1 页重新开始。"
            "学位论文常用规范。如果文档无「第一章」，会回退到「绪论」/「引言」。"
        ),
        "ops": [{
            "type": "header_footer",
            "properties": {
                "location": "footer",
                "text": "{page}",
                "alignment": "center",
                "font_name": "Times New Roman",
                "font_size": 10.5,
                "apply_to": "body",
                "body_marker": "第一章",
                "restart_page_numbering": True,
            },
        }],
    },
    {
        "id": "footer_page_only",
        "name": "页脚：仅页码",
        "category": "页眉页脚",
        "description": "页脚居中显示当前页码数字（适合简洁排版）",
        "ops": [{
            "type": "header_footer",
            "properties": {
                "location": "footer",
                "text": "{page}",
                "alignment": "center",
                "font_name": "Times New Roman",
                "font_size": 10.5,
            },
        }],
    },

    # ===== 编号 =====
    {
        "id": "renumber_all",
        "name": "图/表/公式按章节重新编号",
        "category": "编号",
        "description": (
            "扫描全文图题/表题/公式编号，按章节重新编号 (X-Y 格式) "
            "并写入 Word 书签，便于交叉引用。永远在最后执行。"
        ),
        "ops": [{"type": "renumber"}],
    },

    # ===== 智能论文样式 =====
    {
        "id": "smart_thesis_format_all",
        "name": "智能论文样式（一键建立全套命名样式）",
        "category": "智能",
        "description": (
            "根据论文结构自动识别各类元素（含引言/绪论/结论），\n"
            "在文档中新建以下命名样式并应用到对应段落：\n"
            "• 论文题目 / 英文论文题目 / 摘要标题 / 关键词标题\n"
            "• 英文摘要标题 / 英文关键词标题 / 目录标题\n"
            "• 一级标题 / 二级标题 / 三级标题 / 正文\n"
            "• 图题 / 表题 / 公式编号\n"
            "• 致谢标题 / 参考文献标题 / 附录标题\n"
            "样式格式完全符合常见学位论文规范（字号/字体/行距/段间距/大纲等级）。"
        ),
        "ops": [{"type": "smart_thesis_format", "apply_to_paragraphs": True}],
    },

    # ===== 智能大纲 =====
    {
        "id": "smart_outline_auto",
        "name": "智能标题识别（多级）",
        "category": "智能",
        "description": (
            "根据正文内容识别标题层级并覆盖样式：\n"
            "• 论文题目/摘要/Abstract/致谢/声明 → 「封面标题」（不进入 TOC）\n"
            "• 关键词/目录/前言/引言/参考文献/附录 → Heading 1（进入 TOC，不计入正文编号）\n"
            "• 第N章 X / Chapter N: X → Heading 1（正文章节）\n"
            "• 1.1 X / 1.1.1 X / 1.1.1.1 X → Heading 2 / 3 / 4"
        ),
        "ops": [{"type": "smart_outline"}],
    },

    # ===== 自动题注 =====
    {
        "id": "auto_caption_all",
        "name": "全文自动加图表公式题注",
        "category": "智能",
        "description": (
            "扫描全文图、表、公式并自动插入题注（按章节编号 X-Y）：\n"
            "图题：图下方  ·  表题：表上方  ·  公式编号：公式右侧\n"
            "已有题注会被覆盖。完成后自动调用「重新编号」填实际章节号。"
        ),
        "ops": [{
            "type": "auto_caption",
            "fig": True, "tbl": True, "eq": True,
            "override_existing": True,
        }],
    },

    # ===== TOC =====
    {
        "id": "toc_after_marker",
        "name": "在「目录」段落后插入 TOC 域",
        "category": "智能",
        "description": (
            "在含「目录」文字的段落后插入 Word TOC 域；目录内容基于现有标题样式自动生成。\n"
            "用户在 Word 中按 F9 或右键 → 更新域可填充实际目录。\n"
            "提示：「封面标题」样式不会出现在 TOC（论文题目/摘要/致谢/声明 等被自动排除）。"
        ),
        "ops": [{"type": "toc", "after_marker": "目录", "levels": 3}],
    },
]


# 默认勾选的项（首次打开面板时预选）
DEFAULT_PRESELECTED = {
    "smart_outline_auto",
    "page_a4_standard",
    "body_song_xiaosi",
    "heading_h1_san_hei",
    "heading_h2_song_xiaosan",
    "heading_h3_song_sihao",
    "all_tables_three_line",
    "all_tables_continuation",
    "keyword_label_bold",
    "footer_page_x_of_y",
    "auto_caption_all",
    "toc_after_marker",
    "renumber_all",
}


def get_defaults_metadata():
    """返回前端展示用的精简元数据（不含 ops，避免暴露内部结构）。"""
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "category": d["category"],
            "description": d["description"],
            "preselected": d["id"] in DEFAULT_PRESELECTED,
        }
        for d in DEFAULTS
    ]


# operations 全局执行顺序：与 SYSTEM_PROMPT 中"## operations 排列顺序"一致
_TYPE_ORDER = {
    "page_setup":          1,
    "header_footer":       2,
    "smart_outline":       3,   # 先识别大纲层级
    "smart_thesis_format": 4,   # 论文命名样式在 smart_outline 之后，确保能覆盖冲突样式
    "format":              5,   # 内部还要按 target 细分（见 _format_subkey）
    "keyword_label":       6,
    "three_line_table":    7,
    "table_continuation":  8,   # 在三线表之后，避免边框被覆盖
    "auto_caption":        9,   # 题注插入需在样式与表格设置之后
    "caption":            10,
    "cross_ref":          11,
    "toc":                12,   # 目录依赖最终的标题样式
    "renumber":           13,
}

def _format_subkey(op):
    """format 内部排序：Normal → Heading 1..6 → 自定义 → section:/heading:。"""
    if op.get("type") != "format":
        return 0
    target = op.get("target", "")
    if target == "Normal":
        return 0
    if target.startswith("Heading "):
        try:
            return 1 + int(target.split()[1]) * 0.1   # Heading 1 → 1.1, ...
        except (ValueError, IndexError):
            return 1.99
    if target.startswith("section:") or target.startswith("heading:"):
        return 3
    if target in ("all_headings", "all"):
        return 1
    return 2  # 自定义命名样式


def collect_ops(feature_ids, thesis_title=""):
    """收集所选 default 的 ops，按全局执行顺序排序，并解析占位符。

    占位符替换：
      {THESIS_TITLE} → 实际论文题目；找不到题目时该 op 被丢弃
    """
    ops = []
    id_set = set(feature_ids or [])
    for d in DEFAULTS:
        if d["id"] not in id_set:
            continue
        for op in d["ops"]:
            resolved = _resolve_placeholders(op, thesis_title)
            if resolved is not None:
                ops.append(resolved)

    ops.sort(key=lambda op: (_TYPE_ORDER.get(op.get("type"), 99), _format_subkey(op)))
    return ops


def _resolve_placeholders(op, thesis_title):
    """递归替换 op 中的 {THESIS_TITLE} 占位符。返回 None 表示该 op 应跳过。"""
    import copy
    op = copy.deepcopy(op)

    def walk(node):
        if isinstance(node, dict):
            for k in list(node.keys()):
                v = node[k]
                if isinstance(v, str) and "{THESIS_TITLE}" in v:
                    if not thesis_title:
                        return False  # 没有题目可填 → 整个 op 跳过
                    node[k] = v.replace("{THESIS_TITLE}", thesis_title)
                else:
                    if walk(v) is False:
                        return False
        elif isinstance(node, list):
            for item in node:
                if walk(item) is False:
                    return False
        return True

    return op if walk(op) is not False else None

"""
论文格式知识库：供「问答模式」做上下文检索。

两层来源：
  1) 内置国标要点（BUILTIN_SOURCES）—— 开箱即用，无需外部文件
  2) knowledge/ 目录下的 PDF —— 用户自行投放（GB/T 7714、GB/T 7713 等原件），
     启动时提取文本并缓存为 .extracted.txt 旁车文件，避免每次重复 OCR

对外接口：
  get_knowledge_text()      → 拼接后的全文（喂给 LLM 的上下文，启用提示缓存）
  list_knowledge_sources()  → [{id,title,filename,kind,chars}]（前端"查看原件"列表）
  get_knowledge_source(id)  → dict: 内置返回文本，PDF 返回文件路径
  refresh_knowledge()       → 重新扫描 knowledge/ 目录
"""
from pathlib import Path

from extract import extract_pdf

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


# ============================================================
# 内置国标要点（核心条款摘录，开箱即用）
# ============================================================

_GB7714 = """\
# GB/T 7714—2015《信息与文献 参考文献著录规则》核心要点

## 1. 标注体系
本标准规定两种标注体系：顺序编码制、著者-出版年制。学位论文最常用**顺序编码制**。

### 顺序编码制
- 正文中按引用先后用阿拉伯数字连续编号，序号置于方括号中并作上标，如：研究表明……[1]。
- 同一处引用多篇文献时，各序号用逗号隔开；连续序号用短横线，如：[1-3]、[2,5,7]。
- 文后参考文献表按正文中出现的先后顺序排列。

## 2. 文献类型与载体类型标识代码
专著[M] 论文集[C] 报纸文章[N] 期刊文章[J] 学位论文[D] 报告[R]
标准[S] 专利[P] 数据库[DB] 计算机程序[CP] 电子公告[EB]
电子资源载体：磁带[MT] 磁盘[DK] 光盘[CD] 联机网络[OL]
组合示例：联机网络数据库[DB/OL]、光盘图书[M/CD]、网络电子公告[EB/OL]。

## 3. 各类型著录格式（顺序编码制）

### 专著（图书）
[序号] 主要责任者. 题名:其他题名信息[文献类型标识]. 其他责任者. 版本项. 出版地:出版者,出版年:引文页码.
示例：[1] 刘国钧,陈绍业. 图书馆目录[M]. 北京:高等教育出版社,1957:15-18.

### 期刊文章
[序号] 主要责任者. 题名[J]. 刊名,年,卷(期):起止页码.
示例：[2] 李四. 数字图书馆研究[J]. 中国图书馆学报,2010,36(5):12-18.

### 学位论文
[序号] 主要责任者. 题名[D]. 保存地:保存单位,年份.
示例：[3] 张三. 基于深度学习的图像识别研究[D]. 北京:清华大学,2018.

### 论文集中析出文献
[序号] 析出文献主要责任者. 析出文献题名[C]//论文集主要责任者. 论文集题名. 出版地:出版者,出版年:析出文献起止页码.

### 电子资源
[序号] 主要责任者. 题名[文献类型标识/载体类型标识]. 出版地:出版者,出版年(更新或修改日期)[引用日期]. 获取和访问路径.
示例：[4] 王五. 中国科技论文在线[EB/OL]. (2018-06-01)[2019-03-15]. http://www.example.com.

### 标准
[序号] 标准编号,标准名称[S]. 出版地:出版者,出版年.

### 专利
[序号] 专利申请者或所有者. 专利题名:专利国别,专利号[P]. 公告日期或公开日期.

## 4. 著录细则
- 3 名以内责任者全部著录；超过 3 名时著录前 3 名，其后加“,等”或“, et al.”。
- 各著录项目之间用规定的标识符（. , : ; // 等）分隔，标识符前后一般不空格（题名后空一格除外按本标准）。
- 题名后紧接文献类型标识，置于方括号中。
- 出版年用阿拉伯数字；页码为引文实际页码或起止页码。
- 西文著者姓在前、名在后，名可缩写；题名实词首字母是否大写依原文。
"""

_GB7713 = """\
# GB/T 7713.1—2006《学位论文编写规则》核心要点

## 1. 学位论文组成（顺序）
### 前置部分
封面 → 题名页 → 英文题名页 → 声明（原创性/版权）→ 中文摘要 → 英文摘要(Abstract)
→ 目录 → （图/表清单，可选）→ （符号、标志、缩略词等注释表，可选）

### 主体部分
引言（绪论）→ 正文（分章节）→ 结论 → 致谢 → 参考文献

### 结尾部分
附录（可选）→ 攻读学位期间的研究成果（可选）→ 索引（可选）

## 2. 摘要
- 中文摘要应说明研究目的、方法、结果和结论，是一篇独立的短文，能脱离全文阅读。
- 一般 300~600 字（不同学校规定不一）；不用图表、公式、非公知符号。
- 英文摘要内容应与中文摘要相对应。
- 关键词 3~8 个，从论文题名、摘要或正文中选取，词间用分号或逗号分隔，另起一行排在摘要下方。

## 3. 章节编号
- 采用阿拉伯数字分级编号：1 / 1.1 / 1.1.1，一般不超过 4 级（1.1.1.1）。
- 引言、结论、致谢、参考文献等通常作为不带编号的一级标题（或按学校规定）。
- 各章一般另起页。

## 4. 图、表、公式
- 图、表、公式按章编号，如 图 1-1、表 2-3、式(3-1)；编号全文唯一。
- 图题置于图下方居中；表题置于表上方居中；公式编号右对齐于公式同行。
- 三线表为推荐表格形式（仅顶线、表头线、底线）。
- 正文中应先有文字引述（如“如图 1-1 所示”）再出现图表。

## 5. 参考文献
- 文后参考文献按 GB/T 7714 著录；顺序编码制按正文引用先后排列。
- 凡正文引用的文献必须在参考文献表中列出；未引用的不列入。

## 6. 量和单位
- 应采用国家法定计量单位（GB 3100~3102），单位符号正体，量符号斜体。
"""

_TYPESET = """\
# 学位论文常见排版规范（通用参考，非强制国标，以本校模板为准）

## 页面
- 纸张 A4（210mm×297mm），单面或双面打印按学校要求。
- 页边距常用：上 2.5~3cm，下 2.5cm，左 3cm（含装订线），右 2~2.5cm。
- 装订线 0.5~1cm，位于左侧。

## 正文字体
- 中文宋体、英文及数字 Times New Roman，小四号（12pt）。
- 行距 1.5 倍或固定值 20~22pt；首行缩进 2 字符。
- 段落两端对齐。

## 标题
- 一级标题（章）：黑体三号（16pt），居中或左对齐，段前段后留白，另起页。
- 二级标题：黑体/宋体加粗小三号（15pt），左对齐。
- 三级标题：黑体/宋体加粗四号（14pt），左对齐。
- 各级标题不与上下文字过度紧贴，段前段后约 6~12pt。

## 摘要与关键词
- “摘要”二字作为标题，黑体；摘要正文宋体小四。
- 中文摘要 300~600 字；关键词 3~8 个，分号分隔。
- 英文摘要(Abstract)与关键词(Key words)与中文对应。

## 页眉页脚
- 封面无页眉页脚、无页码。
- 前置部分（摘要/目录等）页码用大写或小写罗马数字（Ⅰ、Ⅱ… 或 i、ii…）。
- 正文起从第 1 页用阿拉伯数字重新编号。
- 页眉可居中显示论文题目或章节名，宋体小五（9pt）。

## 图表公式
- 图题“图 章-序 说明”在图下方居中；表题“表 章-序 说明”在表上方居中。
- 公式编号“(章-序)”右对齐于公式同行；公式本身居中。
- 表格推荐三线表；长表跨页重复表头并标“续表”。

## 目录
- 一般列至三级标题；标题文字、页码右对齐，使用 Word 自动目录域生成。
"""

BUILTIN_SOURCES = [
    {"id": "builtin_gb7714", "title": "GB/T 7714—2015 参考文献著录规则（要点）",
     "kind": "builtin", "text": _GB7714},
    {"id": "builtin_gb7713", "title": "GB/T 7713.1—2006 学位论文编写规则（要点）",
     "kind": "builtin", "text": _GB7713},
    {"id": "builtin_typeset", "title": "学位论文常见排版规范（通用参考）",
     "kind": "builtin", "text": _TYPESET},
]


# ============================================================
# knowledge/ 目录 PDF 扫描（带文本缓存）
# ============================================================

_pdf_cache = None   # list of dicts: {id,title,filename,kind:"pdf",text,path}


def _slugify(name: str) -> str:
    keep = "".join(c if c.isalnum() else "_" for c in name)
    return keep.strip("_") or "pdf"


def _scan_pdfs():
    """扫描 knowledge/*.pdf，提取文本（缓存到同名 .extracted.txt）。"""
    out = []
    if not KNOWLEDGE_DIR.exists():
        return out
    for pdf_path in sorted(KNOWLEDGE_DIR.glob("*.pdf")):
        cache = pdf_path.with_suffix(".extracted.txt")
        text = ""
        try:
            if cache.exists() and cache.stat().st_mtime >= pdf_path.stat().st_mtime:
                text = cache.read_text(encoding="utf-8", errors="replace")
            else:
                text, _ = extract_pdf(pdf_path.read_bytes())
                try:
                    cache.write_text(text, encoding="utf-8")
                except Exception:
                    pass
        except Exception as e:
            text = f"[提取失败：{e}]"
        out.append({
            "id": "pdf_" + _slugify(pdf_path.stem),
            "title": pdf_path.stem,
            "filename": pdf_path.name,
            "kind": "pdf",
            "text": text,
            "path": str(pdf_path),
        })
    return out


def _get_pdf_sources():
    global _pdf_cache
    if _pdf_cache is None:
        _pdf_cache = _scan_pdfs()
    return _pdf_cache


def refresh_knowledge():
    """强制重新扫描 knowledge/ 目录（投放新 PDF 后调用）。"""
    global _pdf_cache
    _pdf_cache = None
    return len(_get_pdf_sources())


def _all_sources():
    return BUILTIN_SOURCES + _get_pdf_sources()


def list_knowledge_sources():
    """前端展示用：不含全文，仅元信息。"""
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "filename": s.get("filename", ""),
            "kind": s["kind"],
            "chars": len(s.get("text", "")),
        }
        for s in _all_sources()
    ]


def get_knowledge_source(source_id: str):
    """返回单个来源。内置→{kind:'builtin',text}; PDF→{kind:'pdf',path,filename}。找不到返回 None。"""
    for s in _all_sources():
        if s["id"] == source_id:
            if s["kind"] == "pdf":
                return {"kind": "pdf", "path": s["path"],
                        "filename": s["filename"], "title": s["title"]}
            return {"kind": "builtin", "text": s["text"], "title": s["title"]}
    return None


def get_knowledge_text(max_chars: int = 120_000) -> str:
    """拼接全部来源为单段上下文（喂给 LLM）。超长时按比例截断 PDF 部分。"""
    blocks = []
    for s in _all_sources():
        body = s.get("text", "").strip()
        if not body:
            continue
        header = f"\n\n===== 资料：{s['title']} =====\n"
        blocks.append(header + body)
    full = "".join(blocks).strip()
    if len(full) > max_chars:
        full = full[:max_chars] + "\n\n[知识库过长，已截断。可在问答中追问具体条款]"
    return full

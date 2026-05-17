# Docx Chat Editor 开发者文档

本开发者文档面向二次开发与维护人员，描述架构、数据流、核心模块与扩展方式。

## 1. 项目目标与核心流程

目标：将自然语言排版需求转换为结构化 operations，并通过 python-docx 执行修改，同时提供 Web UI、批量处理与撤销能力。

核心流程（单文档 /chat）：
1) 上传 .docx → 生成 session
2) 提取文档上下文（样式/标题/大纲）
3) LLM 将指令 → 结构化 operations
4) 保存历史快照
5) 执行 operations → 覆写 current.docx
6) 返回解释、操作列表与历史步数

## 2. 目录结构与职责

```
.
├── app/                 # 业务代码包
│   ├── __init__.py      # 包入口，启动时加载 .env
│   ├── main.py          # FastAPI 路由与业务编排
│   ├── llm_parser.py    # LLM 解析与长文本蒸馏
│   ├── docx_formatter.py# python-docx 执行层
│   ├── schemas.py       # Pydantic 数据结构
│   ├── defaults.py      # 默认排版规则库
│   ├── extract.py       # PDF/文档文本提取
│   ├── knowledge_base.py# 国标知识库入库与检索
│   ├── qa.py            # 问答模式
│   ├── checker.py       # 论文格式检查
│   ├── openalex_search.py # OpenAlex 文献检索
│   └── zotero_save.py   # 存入 Zotero
├── static/index.html    # 前端单页应用
├── knowledge/           # 国标 PDF 知识库
├── docs/                # 文档
├── run.py               # 开发启动入口
├── requirements.txt
├── pyproject.toml       # 项目元数据与工具配置
└── sessions/            # 运行时输出目录（自动创建，已 gitignore）
```

运行时目录结构：
```
sessions/
  {session_id}/
    current.docx
    history/
      000000.docx
      000001.docx
  _batch/
    {batch_id}/
      in/     # 原始文件
      out/    # 处理结果
      results.zip
```

## 3. 后端模块职责

- app/main.py：路由、会话管理、历史快照、批量处理、需求文档解析（PDF/DOCX/TXT）
- app/llm_parser.py：LLM 解析与长文本蒸馏（两阶段管线）
- app/docx_formatter.py：排版执行引擎（样式修改、表格、页眉页脚、题注、目录等）
- app/defaults.py：默认排版规则与全局排序，支持占位符替换
- app/schemas.py：operations 数据结构与校验
- app/extract.py：PDF/DOCX/TXT 文本提取（含 OCR 兜底）
- app/knowledge_base.py：国标 PDF 知识库入库与检索
- app/qa.py：问答模式（结合知识库）
- app/checker.py：论文格式检查与批注
- app/openalex_search.py / app/zotero_save.py：文献检索与存入 Zotero
- static/index.html：前端单页应用

## 4. LLM 解析逻辑

见 llm_parser.py。

### 4.1 输入上下文

- 文档样式列表（实际出现过）
- 文档大纲（Heading 层级 + 标题文字）
- 自动识别的文档题目

### 4.2 长文本两阶段管线

- 触发阈值：LONG_TEXT_THRESHOLD = 500
- 阶段 1：从长文本中蒸馏排版要求清单
- 阶段 2：把清单转换为 operations

### 4.3 输出校验

- LLM 输出 JSON → _extract_json() 提取 → Pydantic 校验
- ParsedCommand 会补齐缺失的 type 字段，兼容旧格式

### 4.4 默认模型

- 默认模型：claude-sonnet-4-5
- 可在 parse_command 传入 model 或改写 _get_client

## 5. 数据结构与操作类型

见 schemas.py。

### 5.1 operation 类型一览

- format：文本/段落格式
- page_setup：页面设置
- header_footer：页眉页脚
- keyword_label：关键词标签加粗
- three_line_table：三线表
- table_continuation：跨页续表
- caption：插入题注
- cross_ref：交叉引用
- renumber：重新编号
- smart_thesis_format：一键建立论文命名样式
- smart_outline：智能标题识别
- auto_caption：自动题注插入（会自动调用 renumber）
- toc：插入目录 TOC 域

### 5.2 format 的 target 语法

- Normal、Heading 1–6、all_headings、all
- section:标题文本（节正文范围）
- heading:标题文本（标题段落本身）
- 自定义样式名（文档已有样式）

create_style 用于创建样式并切换段落，便于后续统一控制。

## 6. 操作执行与顺序

apply_operations() 按传入顺序执行 operations；顺序由以下两处保证：
- llm_parser.py 中 SYSTEM_PROMPT 的排序规则
- defaults.py 中 _TYPE_ORDER + _format_subkey 的排序

默认顺序（高层级）：
1) page_setup
2) header_footer / smart_thesis_format
3) smart_outline
4) format（正文 → 标题 → 节专属 → 自定义样式）
5) keyword_label
6) three_line_table
7) table_continuation
8) auto_caption
9) caption
10) cross_ref
11) toc
12) renumber

## 7. 文档执行引擎关键点

- 中文字体：通过 XML 设置 w:eastAsia，避免中文回退默认字体
- 首行缩进：使用 w:firstLineChars（字符数）
- 样式 + 段落双通道：先改样式，再覆盖直接格式
- 页码域代码：插入 Word 字段 PAGE / NUMPAGES
- 奇偶页与首页：自动处理 odd/even/first 容器与链接
- TOC：先移除已有目录域，再插入新 TOC 域
- auto_caption：插入题注后自动触发 renumber

## 8. 结构识别与上下文提取

- get_document_title：推断论文题目（样式/Heading/字号策略）
- get_document_structure：抽取标题层级与文字
- get_thesis_structure：识别摘要/目录/图表/公式等结构元素（供 /structure 使用）

## 9. 扩展与二次开发

### 9.1 新增 operation 类型

1) schemas.py 中增加 Pydantic 模型
2) 将新类型加入 AnyOperation discriminated union
3) docx_formatter.py 中实现执行逻辑并接入 apply_operations
4) llm_parser.py 的 SYSTEM_PROMPT 补充字段与示例
5) defaults.py 中补充默认规则（如需）
6) 更新前端展示或说明

### 9.2 新增默认排版条目

- 在 defaults.py 的 DEFAULTS 追加条目
- 如新增分类，同步更新 CATEGORY_ORDER

### 9.3 更换 / 新增 LLM Provider

- 替换 llm_parser.py 的 _get_client
- 若用 OpenAI 兼容接口，保持输出严格 JSON

### 9.4 扩展文本解析类型

- app/main.py 中新增 _extract_xxx()
- /extract_text 中添加对应分支

## 10. 部署与运维注意事项

- 当前无鉴权，仅适合内网或本地环境
- 建议添加上传大小限制、会话清理策略、反向代理与 TLS
- OCR 依赖较重，生产环境建议预热或异步处理

## 11. CLI 工具：auto_caption.py

用于离线给文档插入题注（不经 LLM）：

```bash
python auto_caption.py input.docx output.docx --fig-prefix 图 --tbl-prefix 表 --eq-label "({n})"
```

# Docx Chat Editor

聊天式 Word 文档自动排版工具的 MVP。
后端用 LLM 把自然语言指令翻译成结构化操作，python-docx 执行修改。

## 项目结构

```
web55/
├── app/                   # 业务代码包
│   ├── __init__.py        # 包入口，启动时加载 .env
│   ├── main.py            # FastAPI 服务（上传/聊天/撤销/下载/检查/问答）
│   ├── llm_parser.py      # 自然语言指令 → 结构化操作（Anthropic）
│   ├── docx_formatter.py  # python-docx 执行层
│   ├── schemas.py         # Pydantic 数据模型
│   ├── defaults.py        # 排版默认值与一键排版操作集
│   ├── extract.py         # PDF/文档文本提取
│   ├── knowledge_base.py  # 国标知识库（knowledge/ 入库与检索）
│   ├── qa.py              # 问答模式
│   ├── checker.py         # 论文格式检查
│   ├── openalex_search.py # OpenAlex 文献检索
│   └── zotero_save.py     # 存入 Zotero
├── frontend/              # 前端源码：Vite + React + Tailwind（开发用）
│   ├── src/               # React 组件 / hooks / API 客户端
│   ├── package.json
│   ├── vite.config.js     # base=/static/，构建产物输出到 ../static
│   └── tailwind.config.js # 设计令牌（暖金主色 / 白底渐变 / 文字层级）
├── static/                # Vite 构建产物（index.html + assets/，由后端托管）
├── knowledge/             # 国标 PDF 知识库（随仓库分发）
├── docs/                  # API / 使用 / 技术文档
├── sessions/              # 运行时自动创建，每个会话的工作文档（已 gitignore）
├── run.py                 # 开发启动入口
├── requirements.txt
├── pyproject.toml         # 项目元数据与工具配置
├── .env.example           # 环境变量模板（复制为 .env）
└── README.md
```

## 启动

```bash
pip install -r requirements.txt
copy .env.example .env       # Linux/Mac: cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY（也可改用 set/export 注入环境变量）
python run.py
```

打开 http://127.0.0.1:8000

> 生产部署可直接 `uvicorn app.main:app --host 0.0.0.0 --port 8000`。
> `static/` 中已包含构建好的前端产物，**无需 Node 即可运行**。

## 前端开发（Vite + React + Tailwind）

前端为组件化的 React 工程，源码在 `frontend/`，构建产物输出到 `static/`
（`GET /` 返回 `static/index.html`，hash 资源由 `app.mount("/static", StaticFiles)` 托管）。

```bash
cd frontend
npm install

# 开发：Vite 热更新（:5173），API 自动代理到后端 :8000
#   需另开一个终端运行 python run.py
npm run dev

# 构建：产物写入 ../static/（提交到仓库，生产无需 Node）
npm run build
```

设计规范：白底 + 角落极淡暖米/浅紫径向渐变；卡片白底圆角 12–16px；
主色暖金 `#D4AF37`；标题 `#333`/500、正文 `#666`/400；线性描边图标。
令牌集中在 `frontend/tailwind.config.js` 与 `frontend/src/index.css`。
修改前端后需 `npm run build` 才会反映到 `uvicorn` 启动的站点。

## 使用示例

上传 docx 后，在对话框输入自然语言指令：

**文本格式**
- `把正文改成宋体小四，1.5 倍行距，首行缩进 2 字符`
- `一级标题用三号黑体加粗，段前段后各 12 磅`
- `所有标题居中，正文两端对齐`
- `正文字体颜色改成深蓝色`
- `二级标题加下划线`

**页面设置**
- `页面设置为 A4 纸，上下边距 2.54cm，左右 3.17cm`
- `页面改为横向`
- `左边距改成 3cm`

**页眉页脚**
- `页眉居中显示"北京大学本科毕业论文"，宋体小五`
- `页脚居中显示"第X页共Y页"格式的页码`
- `页脚只显示页码数字，居中`
- `清除页眉内容`

每次修改在前一次基础上叠加，对话过程中可随时点"下载当前文档"查看效果。

## 当前支持的功能

### 文本/段落格式（target: Normal / Heading 1~6 / all_headings / all）

| 字段 | 说明 | 示例 |
|------|------|------|
| font_name | 字体名 | 黑体/宋体/Times New Roman |
| font_size | 字号 pt | 12=小四, 16=三号 |
| bold | 加粗 | true/false |
| italic | 斜体 | true/false |
| underline | 下划线 | true/false |
| color | 字体颜色（16进制） | FF0000=红, 000000=黑 |
| alignment | 对齐方式 | left/center/right/justify |
| line_spacing | 行距倍数 | 1.5 |
| space_before / space_after | 段间距 pt | 12 |
| first_line_indent_chars | 首行缩进字符数 | 2 |

### 页面设置

| 字段 | 说明 | 示例 |
|------|------|------|
| page_size | 纸张大小 | A4/A3/B5/Letter |
| orientation | 页面方向 | portrait/landscape |
| margin_top/bottom/left/right | 页边距 cm | 2.54 |

### 页眉页脚

| 字段 | 说明 | 示例 |
|------|------|------|
| location | 位置 | header/footer |
| text | 内容（支持 {page}/{total} 占位符） | 第{page}页共{total}页 |
| alignment | 对齐 | left/center/right |
| font_name / font_size / bold | 字体属性 | 宋体/9/false |
| clear | 清除内容 | true |

## 操作类型（LLM 输出的 JSON 结构）

LLM 输出三种操作类型，每条指令可包含多个操作：

```json
{
  "operations": [
    { "type": "format",       "target": "Normal", "properties": {...} },
    { "type": "page_setup",                        "properties": {...} },
    { "type": "header_footer",                     "properties": {...} }
  ],
  "explanation": "..."
}
```

## 扩展方向

- 支持作用到"特定段落"（按内容匹配）
- 加入撤销/版本历史
- 用 SSE 流式返回 LLM 思考过程
- 把 LLM 换成本地模型（DeepSeek/Qwen）走 OpenAI 兼容接口
- 奇偶页不同页眉/首页不同页眉

## 设计要点（避坑）

1. **中文字体**: 必须设 XML 的 `w:eastAsia` 属性，python-docx 默认只设 ASCII 字体名，中文会回退默认字体。见 `_set_font_xml`。
2. **首行缩进**: 用 `w:firstLineChars`（字符数 × 100），比磅值更符合中文排版习惯，字号变化时缩进自动跟随。
3. **同时改 style 和段落**: 文档中常有直接格式覆盖样式定义。`apply_operations` 两步走：先改样式，再遍历段落覆盖直接格式。
4. **会话化叠加**: 每次 chat 直接覆写 `current.docx`，下次修改基于最新结果，实现"持续对话编辑"。
5. **页码域代码**: 页码需要插入 Word 域代码（`PAGE`/`NUMPAGES`），用三段式 `fldChar begin → instrText → fldChar end` XML 结构实现，不是普通文本。
6. **discriminated union**: `ParsedCommand.operations` 用 Pydantic discriminated union 按 `type` 字段自动分派到对应模型，并通过 `model_validator` 为缺少 `type` 的旧格式自动补 `"format"`。

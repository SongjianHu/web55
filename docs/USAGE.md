# Docx Chat Editor 使用说明

本说明面向最终使用者与部署人员，覆盖安装、启动与常见操作流程。

## 1. 功能概览

- 上传 .docx 后，通过自然语言指令进行排版修改
- 默认排版规则一键应用（页面、字体、标题、表格、页眉页脚等）
- 智能功能：标题识别、论文命名样式、自动题注、目录生成
- 支持撤销与下载当前文档
- 支持批量排版，多文档同规则处理并打包下载
- 支持导入 PDF/DOCX/TXT 需求文档并自动注入输入框
- 右侧实时预览（docx-preview）

## 2. 环境准备

### 2.1 基础依赖

- Python 3.9+（推荐 3.10+）
- 安装依赖：

```bash
pip install -r requirements.txt
```

### 2.2 LLM 密钥

默认使用 Anthropic Claude，需配置环境变量：

- Windows (PowerShell)

```powershell
setx ANTHROPIC_API_KEY "sk-ant-xxx"
```

- Linux / macOS

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
```

修改后需重新打开终端或重启服务进程。

### 2.3 可选依赖（需求文档解析）

- PDF 文本层提取（二选一）：pypdf / PyPDF2
- OCR（扫描件 PDF）：pymupdf + rapidocr_onnxruntime

示例：

```bash
pip install pypdf pymupdf rapidocr_onnxruntime
```

## 3. 启动服务

```bash
python run.py
```

默认地址：http://127.0.0.1:8000

开发模式：

```bash
uvicorn app.main:app --reload
```

## 4. Web UI 使用流程

### 4.1 上传文档

- 点击或拖入 .docx 文件
- 上传成功后状态变为“已加载”

### 4.2 发送自然语言指令

示例：

- 把正文改成宋体小四，1.5 倍行距，首行缩进 2 字符
- 一级标题用三号黑体加粗，居中，段前段后各 12 磅
- 页脚居中显示第 X 页共 Y 页

系统流程：解析上下文 → LLM 生成 operations → 执行并刷新预览。

### 4.3 应用默认排版

- 展开“默认排版功能”面板
- 勾选需要的条目（系统预选一组常用项）
- 点击“应用所选”

常见智能项：

- 智能标题识别（smart_outline）
- 智能论文命名样式（smart_thesis_format）
- 自动题注（auto_caption）
- 目录 TOC 生成（toc）

### 4.4 撤销与下载

- 撤销：回退到上一次修改前快照（默认最多 20 步）
- 下载：获取当前 current.docx

### 4.5 预览

- 每次修改后自动刷新右侧预览
- 若 docx-preview CDN 加载失败，可手动点击“刷新”重试

## 5. 需求文档导入（PDF / DOCX / TXT）

- 点击输入框左侧“回形针”按钮
- 选择需求文档（PDF/DOCX/TXT）
- 系统提取文本并注入到光标位置
- PDF 为扫描件时会自动尝试 OCR（需安装 OCR 依赖）

## 6. 语音输入

- 点击“麦克风”按钮开始语音输入
- 再次点击停止
- 推荐使用 Chrome / Edge

## 7. 批量排版

- 点击“批量”打开批量窗口
- 拖入多个 .docx 文件
- 选择默认排版项 + 可选附加指令
- 点击“开始批量处理”
- 完成后下载 zip

批量模式说明：

- 自定义指令只解析一次（用第一份文档上下文）
- 默认排版每份文档会按实际题目解析 {THESIS_TITLE}

## 8. CLI 工具（可选）

可用 auto_caption.py 离线插入题注：

```bash
python auto_caption.py input.docx output.docx --fig-prefix 图 --tbl-prefix 表 --eq-label "({n})"
```

## 9. 常见问题

### 9.1 指令解析失败

- 检查是否配置 ANTHROPIC_API_KEY
- 指令过于模糊时可拆分为多条

### 9.2 未从文件中提取到任何文字

- PDF 可能是扫描件，请安装 OCR 依赖

### 9.3 预览为空或加载失败

- 可能是 CDN 被拦截或网络不稳定，可刷新页面

### 9.4 撤销不可用

- 未进行过任何修改
- 历史已被清空或超过最大步数

# Docx Chat Editor API 接口文档

本文档描述后端 HTTP 接口、请求参数与返回结构。

## 1. 基本信息

- Base URL: http://127.0.0.1:8000
- 认证：无
- 传输格式：
  - 文件上传使用 multipart/form-data
  - 其余返回为 JSON 或文件流
- OpenAPI 文档（FastAPI 默认开启）：/docs 和 /redoc

## 2. 通用说明

- 错误响应：FastAPI 默认返回 {"detail": "错误信息"}
- session_id：上传后生成的 32 位十六进制字符串
- 仅支持 .docx 进行排版；/extract_text 额外支持 .pdf/.txt

## 3. 接口一览

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | / | 静态前端页面 |
| POST | /upload | 上传 docx，生成 session |
| POST | /chat | 解析指令并修改文档 |
| POST | /undo/{session_id} | 撤销一步 |
| GET | /download/{session_id} | 下载当前文档 |
| GET | /structure/{session_id} | 获取文档结构识别结果 |
| GET | /defaults | 获取默认排版条目元数据 |
| POST | /apply_defaults | 应用默认排版条目 |
| POST | /batch | 批量排版（多文档） |
| GET | /batch/{batch_id}/download | 下载批量结果 zip |
| POST | /extract_text | 解析 PDF/DOCX/TXT 为纯文本 |

## 4. 接口详情

### 4.1 GET /

返回静态前端页面（HTML）。

### 4.2 POST /upload

上传文档并创建会话。

- 请求：multipart/form-data
  - file: .docx 文件
- 返回：

```json
{
  "session_id": "b9c22596a2bb4b1da941d061ad465389",
  "filename": "thesis.docx"
}
```

- 可能错误：
  - 400 只支持 .docx 文件

### 4.3 POST /chat

解析指令并应用到当前文档。

- 请求：multipart/form-data
  - session_id: 会话 ID
  - message: 用户自然语言指令
- 返回：

```json
{
  "explanation": "已将正文设为宋体小四、1.5倍行距",
  "operations": [
    {"type": "format", "target": "Normal", "properties": {"font_name": "宋体"}}
  ],
  "history_count": 3,
  "distilled": "1. 正文：宋体小四..."
}
```

说明：当 message 很长（>= 500 字）时会触发“蒸馏”，distilled 返回提取后的清单。

- 可能错误：
  - 404 会话不存在或文档丢失
  - 500 指令解析失败 / 文档修改失败

### 4.4 POST /undo/{session_id}

撤销一步。

- 返回：

```json
{
  "history_count": 2
}
```

- 可能错误：
  - 404 会话不存在
  - 400 没有可撤销的操作

### 4.5 GET /download/{session_id}

下载当前文档（modified.docx）。

- 可能错误：
  - 404 文档不存在

### 4.6 GET /structure/{session_id}

返回论文结构识别结果（标题、摘要、图表、公式等）。

- 返回：

```json
{
  "items": [
    {"type": "heading_1", "label": "标题1级", "text": "第一章 绪论", "index": 12}
  ],
  "stats": {
    "headings": 6,
    "figures": 3,
    "tables": 2,
    "equations": 1
  }
}
```

- 可能错误：
  - 404 会话不存在或文档丢失
  - 500 结构识别失败

### 4.7 GET /defaults

获取默认排版条目（不含 ops 细节）。

- 返回：

```json
{
  "defaults": [
    {
      "id": "page_a4_standard",
      "name": "A4 + 标准页边距",
      "category": "页面",
      "description": "纸张 A4，上下边距 2.54cm...",
      "preselected": true
    }
  ]
}
```

### 4.8 POST /apply_defaults

对当前文档应用默认排版条目。

- 请求：multipart/form-data
  - session_id: 会话 ID
  - feature_ids: JSON 数组字符串，例如 ["page_a4_standard","body_song_xiaosi"]
- 返回：

```json
{
  "explanation": "已应用 2 项默认排版...",
  "applied": ["A4 + 标准页边距", "正文：宋体小四 / Times New Roman"],
  "operations": [
    {"type": "page_setup", "properties": {"page_size": "A4"}}
  ],
  "history_count": 4
}
```

- 可能错误：
  - 400 feature_ids 格式错误 / 未勾选条目
  - 500 默认 ops 校验失败 / 应用失败

### 4.9 POST /batch

批量处理多份 docx。

- 请求：multipart/form-data
  - files: 多个 .docx 文件
  - feature_ids: JSON 数组字符串
  - message: 可选自定义指令（只解析一次）
- 返回：

```json
{
  "batch_id": "0b88dae230d5481691f5245360475b9c",
  "total": 3,
  "success_count": 2,
  "fail_count": 1,
  "results": [
    {"filename": "a.docx", "status": "ok", "ops_count": 6, "title_used": "..."},
    {"filename": "b.docx", "status": "error", "error": "..."}
  ],
  "download_url": "/batch/0b88dae230d5481691f5245360475b9c/download"
}
```

- 可能错误：
  - 400 未上传文件 / 文件非 .docx / feature_ids 格式错误

### 4.10 GET /batch/{batch_id}/download

下载批量结果 zip。

- 可能错误：
  - 400 非法 batch_id
  - 404 批次不存在或已过期

### 4.11 POST /extract_text

解析 PDF/DOCX/TXT 文件为纯文本。

- 请求：multipart/form-data
  - file: .pdf/.docx/.txt
- 返回：

```json
{
  "text": "...",
  "filename": "requirements.pdf",
  "chars": 1245,
  "ocr_used": false
}
```

- 可能错误：
  - 400 文件为空 / 格式不支持 / 未提取到文字
  - 500 缺少 OCR 依赖或解析失败

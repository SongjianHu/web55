// API 客户端：逐接口镜像 app/main.py，FormData 字段名 / JSON 键逐字复制。
// 一律相对路径：开发走 Vite 代理、生产同源。

async function errText(r) {
  const t = await r.text();
  try {
    return JSON.parse(t).detail || t;
  } catch {
    return t;
  }
}

async function j(r) {
  if (!r.ok) throw new Error(await errText(r));
  return r.json();
}

export const api = {
  // POST /upload  multipart: file -> {session_id, filename}
  upload(file) {
    const f = new FormData();
    f.append('file', file);
    return fetch('/upload', { method: 'POST', body: f }).then(j);
  },

  // POST /chat  form: session_id, message, history(JSON [{role,content}])
  // -> {explanation, operations[], history_count, distilled?, needs_input?}
  chat(sessionId, message, history) {
    const f = new FormData();
    f.append('session_id', sessionId);
    f.append('message', message);
    if (history && history.length) f.append('history', JSON.stringify(history));
    return fetch('/chat', { method: 'POST', body: f }).then(j);
  },

  // POST /undo/{id} -> {history_count}
  undo(sessionId) {
    return fetch(`/undo/${sessionId}`, { method: 'POST' }).then(j);
  },

  // GET /download/{id} -> docx blob
  downloadUrl(sessionId) {
    return `/download/${sessionId}`;
  },
  fetchDocxBuffer(sessionId) {
    return fetch(`/download/${sessionId}`, { cache: 'no-store' }).then((r) => {
      if (!r.ok) throw new Error(`获取文档失败 (${r.status})`);
      return r.arrayBuffer();
    });
  },

  // GET /structure/{id} -> {sections, items[], stats}
  structure(sessionId) {
    return fetch(`/structure/${sessionId}`).then(j);
  },

  // GET /defaults -> {defaults:[{id,name,category,description,preselected}]}
  defaults() {
    return fetch('/defaults').then(j);
  },

  // POST /apply_defaults  form: session_id, feature_ids(JSON string array)
  // -> {explanation, applied[], operations[], history_count}
  applyDefaults(sessionId, ids) {
    const f = new FormData();
    f.append('session_id', sessionId);
    f.append('feature_ids', JSON.stringify(ids));
    return fetch('/apply_defaults', { method: 'POST', body: f }).then(j);
  },

  // POST /batch  multipart: files[] + feature_ids(JSON) + message
  batch(files, ids, message) {
    const f = new FormData();
    files.forEach((file) => f.append('files', file, file.name));
    f.append('feature_ids', JSON.stringify(ids));
    f.append('message', message);
    return fetch('/batch', { method: 'POST', body: f }).then(j);
  },

  // POST /extract_text  multipart: file -> {text,filename,chars,ocr_used}
  extractText(file) {
    const f = new FormData();
    f.append('file', file);
    return fetch('/extract_text', { method: 'POST', body: f }).then(j);
  },

  // POST /check  multipart: session_id, categories(JSON), review?(file)
  check(sessionId, cats, reviewFile) {
    const f = new FormData();
    f.append('session_id', sessionId);
    f.append('categories', JSON.stringify(cats));
    if (reviewFile) f.append('review', reviewFile);
    return fetch('/check', { method: 'POST', body: f }).then(j);
  },

  // POST /qa  form: question, history(JSON), references(JSON) -> {answer}
  qa(question, history, references) {
    const f = new FormData();
    f.append('question', question);
    f.append('history', JSON.stringify(history));
    if (references && references.length)
      f.append('references', JSON.stringify(references));
    return fetch('/qa', { method: 'POST', body: f }).then(j);
  },

  // GET /openalex/defaults -> {from_year,to_year}
  openalexDefaults() {
    return fetch('/openalex/defaults').then(j);
  },

  // POST /openalex/search  form: query, from_year?, to_year?, limit, api_key
  openalexSearch({ query, fromYear, toYear, limit = 20, apiKey }) {
    const f = new FormData();
    f.append('query', query);
    if (fromYear) f.append('from_year', fromYear);
    if (toYear) f.append('to_year', toYear);
    if (apiKey) f.append('api_key', apiKey);
    f.append('limit', String(limit));
    return fetch('/openalex/search', { method: 'POST', body: f }).then(j);
  },

  // POST /zotero/save  form: api_key, user_id, items(JSON array)
  zoteroSave(apiKey, userId, items) {
    const f = new FormData();
    f.append('api_key', apiKey);
    f.append('user_id', userId);
    f.append('items', JSON.stringify(items));
    return fetch('/zotero/save', { method: 'POST', body: f }).then(j);
  },
};

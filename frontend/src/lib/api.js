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

  // POST /chat/stream  SSE：onStage({stage,text}) 收阶段事件；返回 done 的 payload
  // （与 /chat 返回体同构）。流式不可用/无 body 时自动回退普通 chat。
  async chatStream(sessionId, message, history, onStage) {
    const f = new FormData();
    f.append('session_id', sessionId);
    f.append('message', message);
    if (history && history.length) f.append('history', JSON.stringify(history));
    const r = await fetch('/chat/stream', { method: 'POST', body: f });
    if (!r.ok) throw new Error(await errText(r));
    if (!r.body || !r.body.getReader) {
      return this.chat(sessionId, message, history); // 老浏览器回退
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let final = null;
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const dl = block.split('\n').find((l) => l.startsWith('data:'));
        if (!dl) continue;
        const obj = JSON.parse(dl.slice(5).trim());
        if (obj.stage === 'error') throw new Error(obj.error || '处理失败');
        if (obj.stage === 'done') final = obj;
        else if (onStage) onStage(obj);
      }
    }
    if (!final) throw new Error('未收到完成事件');
    return final;
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

  // GET /render/{id}/pdf -> 高保真 PDF blob（LibreOffice 计算域：页码/题注/交叉引用为正确值）
  // 渲染服务未启用/不可达时后端返回 503，errText 透出友好提示。
  async fetchRenderedPdf(sessionId) {
    const r = await fetch(`/render/${sessionId}/pdf`, { cache: 'no-store' });
    if (!r.ok) throw new Error(await errText(r));
    return r.blob();
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
  // Redis 在 → {batch_id, job_id, queued:true}（轮询 jobStatus）
  // Redis 不在 → 同步完整结果 {..., queued:false}
  batch(files, ids, message) {
    const f = new FormData();
    files.forEach((file) => f.append('files', file, file.name));
    f.append('feature_ids', JSON.stringify(ids));
    f.append('message', message);
    return fetch('/batch', { method: 'POST', body: f }).then(j);
  },

  // GET /jobs/{id} -> {status, progress?, result?, error?}
  jobStatus(jobId) {
    return fetch(`/jobs/${jobId}`, { cache: 'no-store' }).then(j);
  },

  // GET /session/{id} -> {exists, history_count, messages:[{role,content,ts}]}
  sessionRestore(sessionId) {
    return fetch(`/session/${sessionId}`, { cache: 'no-store' }).then(j);
  },

  // ── 最小认证（AUTH_ENABLED=true 时启用；false 时 authMe.user 恒视为放行）──
  // GET /auth/me -> {auth_enabled, user:{id,username}|null}
  authMe() {
    return fetch('/auth/me', { cache: 'no-store' }).then(j);
  },
  authLogin(username, password) {
    const f = new FormData();
    f.append('username', username);
    f.append('password', password);
    return fetch('/auth/login', { method: 'POST', body: f }).then(j);
  },
  authRegister(username, password) {
    const f = new FormData();
    f.append('username', username);
    f.append('password', password);
    return fetch('/auth/register', { method: 'POST', body: f }).then(j);
  },
  authLogout() {
    return fetch('/auth/logout', { method: 'POST' }).then(j);
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

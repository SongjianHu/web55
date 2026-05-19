import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 后端 FastAPI 默认 127.0.0.1:8000；开发期 Vite(:5173) 把所有 API 前缀代理过去。
// api.js 全部使用相对路径：开发走代理、生产同源，绝不硬编码 host。
const API_TARGET = 'http://127.0.0.1:8000';
const API_PREFIXES = [
  '/upload', '/chat', '/undo', '/download', '/structure',
  '/defaults', '/apply_defaults', '/batch', '/extract_text',
  '/check', '/qa', '/openalex', '/zotero', '/knowledge',
  '/render', '/jobs', '/health',
];

export default defineConfig({
  plugins: [react()],
  // 构建产物里的 index.html 以 /static/ 引用 hash 资源；
  // 后端通过 app.mount("/static", StaticFiles(...)) 解析。
  base: '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
    assetsDir: 'assets',
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_PREFIXES.map((p) => [p, { target: API_TARGET, changeOrigin: true }]),
    ),
  },
});

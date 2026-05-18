import { useEffect, useRef, useState } from 'react';
import { renderAsync } from 'docx-preview';
import { api } from './api.js';

// 拉取 current.docx 的 arrayBuffer 并用 docx-preview 渲染。
// busy ref 串行化防重渲染；每次渲染前清空容器。
export function useDocxPreview(sessionId, refreshSignal) {
  const containerRef = useRef(null);
  const busyRef = useRef(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    if (!sessionId) return;
    const container = containerRef.current;
    if (!container || busyRef.current) return;

    let cancelled = false;
    busyRef.current = true;
    setStatus('渲染中…');
    container.innerHTML =
      '<div class="flex flex-col items-center gap-3 py-20 text-ink-faint text-[12.5px]">' +
      '<div class="h-7 w-7 rounded-full border-[3px] border-line border-t-gold animate-spin"></div>' +
      '<span>正在渲染文档…</span></div>';

    (async () => {
      try {
        const buf = await api.fetchDocxBuffer(sessionId);
        if (cancelled) return;
        container.innerHTML = '';
        await renderAsync(buf, container, null, {
          className: 'docx',
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          breakPages: true,
          ignoreFonts: false,
          trimXmlDeclaration: true,
          useBase64URL: true,
        });
        if (cancelled) return;
        const t = new Date().toLocaleTimeString('zh-CN', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });
        setStatus(`已更新 ${t}`);
      } catch (err) {
        if (cancelled) return;
        container.innerHTML =
          `<div class="py-20 text-center text-[12.5px] text-red-600">⚠ 渲染失败：${err.message}</div>`;
        setStatus('渲染失败');
      } finally {
        busyRef.current = false;
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId, refreshSignal]);

  return { containerRef, status };
}

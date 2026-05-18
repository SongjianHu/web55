import { useEffect, useRef, useState, useCallback } from 'react';

// Web Speech API：持续监听，再按一次停止。移植旧锚点 splice 逻辑：
// 录音开始记录光标位置与已有内容，结果实时拼接 final+interim 插入到该锚点。
const SR =
  typeof window !== 'undefined' &&
  (window.SpeechRecognition || window.webkitSpeechRecognition);

export function useSpeechRecognition({
  lang = 'zh-CN',
  getEl, // () => textarea element
  setValue, // (string) => void  同步 React 受控值
  onHint, // (text, live, ms) => void
  onError, // (message) => void
}) {
  const supported = !!SR;
  const [recording, setRecording] = useState(false);
  const recRef = useRef(null);
  const anchorRef = useRef(0);
  const baseRef = useRef('');
  const finalRef = useRef('');
  const caretRef = useRef(null); // 待恢复的光标位置（Composer 在提交后应用）

  useEffect(() => {
    if (!supported) return;
    const rec = new SR();
    rec.lang = lang;
    rec.continuous = true;
    rec.interimResults = true;

    rec.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) finalRef.current += r[0].transcript;
        else interim += r[0].transcript;
      }
      const insert = finalRef.current + interim;
      const base = baseRef.current;
      const anchor = anchorRef.current;
      const next = base.slice(0, anchor) + insert + base.slice(anchor);
      caretRef.current = anchor + insert.length;
      setValue(next);
      onHint?.(
        interim ? '识别中…' : `已录入 ${finalRef.current.length} 字`,
        true,
        0,
      );
    };

    rec.onerror = (e) => {
      onError?.(`语音识别错误：${e.error || '未知错误'}`);
      doStop(true);
    };

    rec.onend = () => doStop(true);

    recRef.current = rec;
    return () => {
      try {
        rec.onresult = rec.onerror = rec.onend = null;
        rec.abort();
      } catch {
        /* ignore */
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supported, lang]);

  const doStop = useCallback(
    (silent = false) => {
      setRecording(false);
      const rec = recRef.current;
      if (rec && !silent) {
        try {
          rec.stop();
        } catch {
          /* ignore */
        }
      }
      onHint?.(
        finalRef.current ? `已录入 ${finalRef.current.length} 字` : '',
        false,
      );
    },
    [onHint],
  );

  const start = useCallback(() => {
    const rec = recRef.current;
    const el = getEl?.();
    if (!rec || !el) {
      onError?.('当前浏览器不支持语音识别（建议使用 Chrome / Edge）');
      return;
    }
    anchorRef.current = el.selectionStart ?? el.value.length;
    baseRef.current = el.value;
    finalRef.current = '';
    try {
      rec.start();
    } catch {
      return; // 已在录音中再次 start 会抛错，忽略
    }
    setRecording(true);
    onHint?.('🎙 正在录音…', true, 0);
  }, [getEl, onHint, onError]);

  const toggle = useCallback(() => {
    if (recording) doStop(false);
    else start();
  }, [recording, doStop, start]);

  return { supported, recording, toggle, caretRef };
}

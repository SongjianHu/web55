import {
  useRef,
  useState,
  useCallback,
  useLayoutEffect,
  useEffect,
} from 'react';
import { useSession } from '../../../state/SessionContext.jsx';
import { api } from '../../../lib/api.js';
import { useAutosize } from '../../../lib/useAutosize.js';
import { useSpeechRecognition } from '../../../lib/useSpeechRecognition.js';
import Icon from '../../ui/Icon.jsx';
import { cn } from '../../../lib/cn.js';
import { useRipple, RippleLayer } from '../../../lib/useRipple.jsx';

export default function Composer() {
  const sendRipple = useRipple();
  const {
    sessionId,
    hasDoc,
    addMsg,
    updateMsg,
    removeMsg,
    addError,
    setHistoryCount,
    bumpPreview,
    bumpStructure,
  } = useSession();

  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [attaching, setAttaching] = useState(false);
  const [hint, setHint] = useState({ text: '', live: false });
  const textRef = useRef(null);
  const reqFileRef = useRef(null);
  const pendingCaret = useRef(null);
  const hintTimer = useRef(null);
  // 排版对话多轮历史（澄清式追问依赖它）；换文档/重新上传时清空
  const convoRef = useRef([]);

  useEffect(() => {
    convoRef.current = [];
  }, [sessionId]);

  useAutosize(textRef, input, 320);

  // 受控值提交后恢复待定光标（语音 / 附件插入用）
  useLayoutEffect(() => {
    if (pendingCaret.current != null && textRef.current) {
      const pos = pendingCaret.current;
      pendingCaret.current = null;
      textRef.current.focus();
      textRef.current.setSelectionRange(pos, pos);
    }
  });

  const showHint = useCallback((text, live = false, ms = 2400) => {
    setHint({ text, live });
    clearTimeout(hintTimer.current);
    if (ms > 0) {
      hintTimer.current = setTimeout(
        () => setHint((h) => (h.text === text ? { text: '', live: false } : h)),
        ms,
      );
    }
  }, []);

  function insertAtCursor(text) {
    const el = textRef.current;
    const start = el?.selectionStart ?? input.length;
    const end = el?.selectionEnd ?? input.length;
    const next = input.slice(0, start) + text + input.slice(end);
    pendingCaret.current = start + text.length;
    setInput(next);
  }

  const speech = useSpeechRecognition({
    lang: 'zh-CN',
    getEl: () => textRef.current,
    setValue: (v) => {
      pendingCaret.current = speech?.caretRef?.current ?? null;
      setInput(v);
    },
    onHint: (t, live, ms) => showHint(t, live, ms),
    onError: (m) => addError(m),
  });

  async function send() {
    const message = input.trim();
    if (!message || !sessionId || sending) return;
    addMsg('user', message);
    setInput('');
    setSending(true);
    const thinkId = addMsg('bot', '思考中…');
    try {
      const data = await api.chatStream(
        sessionId,
        message,
        convoRef.current.slice(-6),
        (ev) => {
          // 阶段进度：边出边显，改善感知延迟
          if (ev.text) updateMsg(thinkId, { text: ev.text });
        },
      );
      const reply = data.explanation || '已完成修改';
      updateMsg(thinkId, {
        text: reply,
        distilled: data.distilled || undefined,
        ops: data.operations && data.operations.length ? data.operations : undefined,
      });
      // 记录本轮（含澄清问答），下一轮带上下文，模型才能"接上一轮"继续
      convoRef.current.push(
        { role: 'user', content: message },
        { role: 'assistant', content: reply },
      );
      if (data.history_count != null) setHistoryCount(data.history_count);
      bumpPreview();
      bumpStructure();
    } catch (err) {
      removeMsg(thinkId);
      addError(err.message);
    } finally {
      setSending(false);
    }
  }

  async function onPickReqFile(e) {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    const ext = file.name.toLowerCase().split('.').pop();
    if (!['pdf', 'docx', 'txt'].includes(ext)) {
      addError('需求文档只支持 .pdf / .docx / .txt');
      return;
    }
    setAttaching(true);
    const isPdf = ext === 'pdf';
    showHint(
      isPdf ? `解析 ${file.name}（扫描件将自动 OCR）…` : `解析 ${file.name} …`,
      true,
      0,
    );
    try {
      const data = await api.extractText(file);
      insertAtCursor(data.text);
      showHint(`已插入 ${data.chars} 字${data.ocr_used ? '（OCR）' : ''}`);
    } catch (err) {
      addError(`需求文档解析失败：${err.message}`);
      showHint('');
    } finally {
      setAttaching(false);
    }
  }

  const iconBtn =
    'glass flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-btn text-ink-body transition-[transform,color,background-color] duration-150 hover:text-ink-heading active:scale-90 disabled:opacity-40 disabled:pointer-events-none';

  return (
    <div className="flex flex-shrink-0 flex-col gap-2 border-t border-white/40 bg-white/30 px-3.5 py-2.5 backdrop-blur-xl">
      <div className="glass rounded-card-lg transition focus-within:border-gold focus-within:ring-2 focus-within:ring-gold/20">
        <textarea
          ref={textRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="例：把正文改成宋体小四，1.5 倍行距，首行缩进 2 字符"
          className="scroll-thin block max-h-[320px] min-h-[38px] w-full resize-none rounded-card-lg bg-transparent px-3 py-2.5 text-[13px] leading-relaxed text-ink-heading outline-none placeholder:text-ink-faint"
        />
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          className={iconBtn}
          title="上传需求文档（PDF / Word / TXT）"
          disabled={!hasDoc || attaching}
          onClick={() => reqFileRef.current?.click()}
        >
          <Icon name="paperclip" size={15} />
        </button>
        <button
          type="button"
          className={cn(
            iconBtn,
            speech.recording &&
              'animate-pulseRec border-red-500 bg-red-500 text-white hover:text-white',
          )}
          title={
            speech.supported
              ? speech.recording
                ? '停止录音'
                : '语音输入（点击开始/停止）'
              : '浏览器不支持语音识别'
          }
          disabled={!hasDoc || !speech.supported}
          onClick={speech.toggle}
        >
          <Icon name="mic" size={15} />
        </button>
        <span
          className={cn(
            'mr-1 truncate text-[11px]',
            hint.live ? 'text-gold' : 'text-ink-faint',
          )}
        >
          {hint.text}
        </span>
        <span className="flex-1" />
        <button
          type="button"
          onClick={send}
          onPointerDown={sendRipple.add}
          disabled={!hasDoc || sending || !input.trim()}
          className="relative isolate flex h-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-card bg-gold px-3.5 text-[13px] font-medium text-white shadow-gold-glow transition-[transform,background-color,box-shadow] duration-150 hover:bg-gold-deep active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <span className="relative z-10 inline-flex items-center gap-1.5">
            <Icon name="send" size={15} />
            发送
          </span>
          <RippleLayer ripples={sendRipple.ripples} color="rgba(255,255,255,0.5)" />
        </button>
      </div>
      <input
        ref={reqFileRef}
        type="file"
        accept=".pdf,.docx,.txt"
        hidden
        onChange={onPickReqFile}
      />
    </div>
  );
}

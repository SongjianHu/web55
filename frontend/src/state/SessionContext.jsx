import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useRef,
  useEffect,
} from 'react';
import { api } from '../lib/api.js';

const SessionContext = createContext(null);
const LS_KEY = 'web55.session'; // {id, name} —— 刷新后据此向服务端恢复

export function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null);
  const [filename, setFilename] = useState(null);
  const [historyCount, setHistoryCount] = useState(0);
  const [status, setStatus] = useState('未上传文档');
  const [mode, setMode] = useState('format'); // format | check | qa

  // 聊天消息（应用级：上传 / 撤销 / 默认排版 / chat 都会写入，
  // 排版模式可见）。msg: {id, role:'user'|'bot', text, ops?, distilled?, error?}
  const [messages, setMessages] = useState([]);
  const msgSeq = useRef(0);

  const addMsg = useCallback((role, text, extra = {}) => {
    const id = ++msgSeq.current;
    setMessages((m) => [...m, { id, role, text, ...extra }]);
    return id;
  }, []);
  const updateMsg = useCallback((id, patch) => {
    setMessages((m) =>
      m.map((x) =>
        x.id === id
          ? { ...x, ...(typeof patch === 'function' ? patch(x) : patch) }
          : x,
      ),
    );
  }, []);
  const removeMsg = useCallback((id) => {
    setMessages((m) => m.filter((x) => x.id !== id));
  }, []);
  const addError = useCallback(
    (text) => {
      return addMsg('bot', text, { error: true });
    },
    [addMsg],
  );

  // 信号计数器：自增即触发 PreviewPane / StructurePanel 重渲染
  const [previewSignal, setPreviewSignal] = useState(0);
  const [structureSignal, setStructureSignal] = useState(0);
  const [structureAutoOpen, setStructureAutoOpen] = useState(false);

  // 默认排版勾选 ID 上提：DefaultsPanel 与 BatchModal 共读
  const [defaultsList, setDefaultsList] = useState([]);
  const [checkedDefaultIds, setCheckedDefaultIds] = useState([]);

  const bumpPreview = useCallback(() => setPreviewSignal((n) => n + 1), []);
  const bumpStructure = useCallback(
    (autoOpen = false) => {
      setStructureAutoOpen(autoOpen);
      setStructureSignal((n) => n + 1);
    },
    [],
  );

  const setSession = useCallback((id, name) => {
    setSessionId(id);
    setFilename(name);
    setStatus(`已加载：${name}`);
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({ id, name }));
    } catch {
      /* localStorage 不可用时仅失去刷新恢复，不影响主流程 */
    }
  }, []);

  const reset = useCallback(() => {
    // 替代旧 location.reload()：清空全部会话态
    setSessionId(null);
    setFilename(null);
    setHistoryCount(0);
    setStatus('未上传文档');
    setMode('format');
    setMessages([]);
    try {
      localStorage.removeItem(LS_KEY);
    } catch {
      /* 同上 */
    }
  }, []);

  // 刷新/重进恢复：localStorage 有会话 → 向服务端核对，存在则恢复
  // 文档状态、历史步数与服务端聊天消息（Redis 持久化）。
  useEffect(() => {
    let saved;
    try {
      saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
    } catch {
      saved = null;
    }
    if (!saved?.id) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.sessionRestore(saved.id);
        if (cancelled) return;
        if (!r.exists) {
          localStorage.removeItem(LS_KEY);
          return;
        }
        setSessionId(saved.id);
        setFilename(saved.name);
        setStatus(`已恢复：${saved.name}`);
        setHistoryCount(r.history_count || 0);
        if (Array.isArray(r.messages) && r.messages.length) {
          setMessages(
            r.messages.map((m) => ({
              id: ++msgSeq.current,
              role: m.role === 'user' ? 'user' : 'bot',
              text: m.content || '',
            })),
          );
        }
      } catch {
        /* 恢复失败（如离线/无 Redis）→ 维持空白，用户重新上传即可 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({
      sessionId,
      filename,
      historyCount,
      status,
      mode,
      hasDoc: !!sessionId,
      canUndo: !!sessionId && historyCount > 0,
      previewSignal,
      structureSignal,
      structureAutoOpen,
      defaultsList,
      checkedDefaultIds,
      messages,
      addMsg,
      updateMsg,
      removeMsg,
      addError,
      setSession,
      setHistoryCount,
      setStatus,
      setMode,
      reset,
      bumpPreview,
      bumpStructure,
      setDefaultsList,
      setCheckedDefaultIds,
    }),
    [
      sessionId,
      filename,
      historyCount,
      status,
      mode,
      previewSignal,
      structureSignal,
      structureAutoOpen,
      defaultsList,
      checkedDefaultIds,
      messages,
      addMsg,
      updateMsg,
      removeMsg,
      addError,
      setSession,
      reset,
      bumpPreview,
      bumpStructure,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}

import { useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import Button from '../ui/Button.jsx';

// 最小登录闸门：AUTH_ENABLED=false 时直接放行（与改造前一致）；
// 启用且未登录时挡在登录/注册卡片前，登录后渲染应用。
export default function AuthGate({ children }) {
  const [state, setState] = useState({ loading: true });
  const [mode, setMode] = useState('login'); // login | register
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function refresh() {
    try {
      const me = await api.authMe();
      setState({ loading: false, ...me });
    } catch {
      // /auth/me 不可达：视为无需鉴权，放行（不阻断离线/老部署）
      setState({ loading: false, auth_enabled: false, user: null });
    }
  }
  useEffect(() => {
    refresh();
  }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      if (mode === 'register') {
        await api.authRegister(username.trim(), password);
      }
      await api.authLogin(username.trim(), password);
      setPassword('');
      await refresh();
    } catch (e2) {
      setErr(e2.message || '操作失败');
    } finally {
      setBusy(false);
    }
  }

  if (state.loading) return null;
  if (!state.auth_enabled || state.user) return children;

  return (
    <div className="flex h-full items-center justify-center p-6">
      <form
        onSubmit={submit}
        className="glass w-full max-w-[340px] rounded-card-lg border border-white/60 p-6"
      >
        <h1 className="mb-1 text-[15px] font-semibold text-ink-heading">
          论文排版工具 · {mode === 'login' ? '登录' : '注册'}
        </h1>
        <p className="mb-4 text-[11.5px] text-ink-faint">
          小范围使用：账号用于区分各自的文档与会话
        </p>
        <input
          className="mb-2 w-full rounded-btn border border-white/55 bg-white/45 px-3 py-2 text-[13px] outline-none focus:border-gold"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
        />
        <input
          type="password"
          className="mb-3 w-full rounded-btn border border-white/55 bg-white/45 px-3 py-2 text-[13px] outline-none focus:border-gold"
          placeholder="口令（至少 6 位）"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        />
        {err && <div className="mb-2 text-[12px] text-red-600">{err}</div>}
        <Button
          variant="primary"
          size="sm"
          type="submit"
          disabled={busy || !username.trim() || !password}
          className="w-full justify-center"
        >
          {busy ? '处理中…' : mode === 'login' ? '登录' : '注册并登录'}
        </Button>
        <button
          type="button"
          className="mt-3 w-full text-center text-[12px] text-ink-faint hover:text-gold-deep"
          onClick={() => {
            setErr('');
            setMode(mode === 'login' ? 'register' : 'login');
          }}
        >
          {mode === 'login' ? '没有账号？去注册' : '已有账号？去登录'}
        </button>
      </form>
    </div>
  );
}

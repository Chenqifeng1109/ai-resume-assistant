import React from 'react';
import { Lock, ShieldCheck } from 'lucide-react';
import AIAssistant from './components/AIAssistant';
import './index.css';

const API_BASE = window.location.origin;

const App = () => {
  const [theme, setTheme] = React.useState(() => {
    try {
      const saved = window.localStorage.getItem('offerforge_theme');
      if (saved === 'dark' || saved === 'light') return saved;
    } catch {
      // ignore storage errors
    }
    return 'light';
  });
  const [authLocked, setAuthLocked] = React.useState(false);
  const [tokenInput, setTokenInput] = React.useState('');
  const [authError, setAuthError] = React.useState('');
  const [authSubmitting, setAuthSubmitting] = React.useState(false);

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      window.localStorage.setItem('offerforge_theme', theme);
    } catch {
      // ignore storage errors
    }
  }, [theme]);

  React.useEffect(() => {
    let cancelled = false;
    const initAuth = async () => {
      try {
        const params = new URLSearchParams(window.location.search);
        const urlToken = (params.get('token') || '').trim();
        if (urlToken) {
          await fetch(`${API_BASE}/api/auth/unlock`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: urlToken }),
          });
          params.delete('token');
          const nextQuery = params.toString();
          const nextUrl = window.location.pathname + (nextQuery ? `?${nextQuery}` : '') + window.location.hash;
          window.history.replaceState({}, '', nextUrl);
        }
        const resp = await fetch(`${API_BASE}/api/auth/status`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (!cancelled && data && data.requires_token && !data.unlocked) {
          setAuthLocked(true);
        }
      } catch {
        // ignore in offline/mocked environments
      }
    };
    initAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleUnlock = async (e) => {
    e.preventDefault();
    if (!tokenInput.trim()) {
      setAuthError('请输入访问口令');
      return;
    }
    setAuthSubmitting(true);
    setAuthError('');
    try {
      const resp = await fetch(`${API_BASE}/api/auth/unlock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tokenInput.trim() }),
      });
      const data = await resp.json();
      if (resp.ok && data.ok && data.unlocked) {
        setAuthLocked(false);
        setTokenInput('');
      } else {
        setAuthError(data.error || '访问口令不正确');
      }
    } catch {
      setAuthError('无法连接服务，请稍后重试');
    } finally {
      setAuthSubmitting(false);
    }
  };

  if (authLocked) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-canvas)', padding: 20 }}>
        <form onSubmit={handleUnlock} style={{ width: '100%', maxWidth: 400, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 16, padding: '28px 26px', boxShadow: 'var(--shadow-md)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, background: 'var(--brand-soft)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Lock size={19} />
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)' }}>OfferForge 在线演示口令验证</div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>每个浏览器拥有独立隐私隔间，互不可见</div>
            </div>
          </div>
          <input
            type="password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="请输入访问口令..."
            autoFocus
            style={{ width: '100%', background: 'var(--input-bg)', border: '1px solid var(--border-light)', color: 'var(--text)', padding: '10px 12px', borderRadius: 9, fontSize: 14, outline: 'none', marginBottom: 10 }}
          />
          {authError && <div style={{ color: 'var(--danger)', fontSize: 12.5, marginBottom: 10 }}>{authError}</div>}
          <button
            type="submit"
            disabled={authSubmitting}
            style={{ width: '100%', background: 'var(--accent-gradient)', color: 'var(--accent-fg)', border: 'none', borderRadius: 9, padding: '10px 16px', fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, opacity: authSubmitting ? 0.65 : 1 }}
          >
            <ShieldCheck size={16} />
            {authSubmitting ? '验证中...' : '解锁进入系统'}
          </button>
        </form>
      </div>
    );
  }

  return <AIAssistant theme={theme} onThemeChange={setTheme} />;
};

export default App;

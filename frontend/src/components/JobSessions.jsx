import { useEffect, useRef, useState } from "react";

const storageLabels = {
  missing: "尚未保存本地会话",
  saved: "已保存本地会话 · 当前登录有效性待检查",
  unreadable: "本地会话无法读取，可清除后重新建立",
};

const actionButton = {
  border: "1px solid var(--brand-border)", borderRadius: 8, padding: "7px 12px",
  background: "var(--brand-soft)", color: "var(--brand)", cursor: "pointer",
};

const secondaryButton = {
  ...actionButton, background: "var(--bg-subtle)",
  borderColor: "rgba(255,255,255,0.15)", color: "var(--text-secondary)",
};

const statusTone = source => {
  if (!source.can_attempt_search || source.statusError || source.session?.storage_status === "unreadable") return "var(--warning)";
  if (source.session?.storage_status === "saved") return "var(--success)";
  return "var(--brand)";
};

const supportsSession = source => source.session_persistence ?? source.can_attempt_search;

export default function JobSessions() {
  const [open, setOpen] = useState(false);
  const [sources, setSources] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const requestId = useRef(0);

  const load = async (quiet = false) => {
    const id = ++requestId.current;
    if (!quiet) { setBusy(true); setMessage(""); }
    try {
      const response = await fetch("/api/jobs/sources");
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "来源信息加载失败");
      const rows = await Promise.all(data.sources.map(async source => {
        if (!supportsSession(source)) return source;
        try {
          const result = await fetch(`/api/jobs/sources/${encodeURIComponent(source.code)}/session`);
          const session = await result.json();
          if (!result.ok || !session.ok) throw new Error(session.error || "会话状态读取失败");
          return { ...source, session };
        } catch (error) {
          return { ...source, statusError: error.message };
        }
      }));
      if (id === requestId.current) setSources(rows);
    } catch (error) {
      if (id === requestId.current) setMessage(error.message || "会话状态读取失败，请重试");
    } finally {
      if (!quiet && id === requestId.current) setBusy(false);
    }
  };

  useEffect(() => {
    if (open) load();
    return () => { requestId.current += 1; };
  }, [open]);

  useEffect(() => {
    if (!open || busy || !sources.some(source => source.session?.login_task?.running)) return;
    const timer = setTimeout(() => load(true), 1500);
    return () => clearTimeout(timer);
  }, [sources, open, busy]);

  const loginAction = async (source, operation, action) => {
    setBusy(true);
    requestId.current += 1;
    try {
      const response = await fetch(`/api/jobs/sources/${encodeURIComponent(source.code)}/session/${operation}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        ...(action ? { body: JSON.stringify({ task_id: source.session.login_task.task_id, action }) } : {}),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "登录操作失败");
      await load();
    } catch (error) {
      setMessage(error.message || "登录操作失败，请重试");
    } finally {
      setBusy(false);
    }
  };

  const clear = async source => {
    if (!window.confirm(`清除${source.name}的本地会话？下次可能需要重新登录。这不会注销网站账号或退出其他设备。`)) return;
    const id = ++requestId.current;
    setBusy(true);
    try {
      const response = await fetch(`/api/jobs/sources/${encodeURIComponent(source.code)}/session/clear`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true }),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "清除失败");
      if (id !== requestId.current) return;
      setSources(rows => rows.map(row => row.code === source.code ? { ...row, session: result, statusError: undefined } : row));
      setMessage(result.message || "本地会话已清除");
    } catch (error) {
      if (id === requestId.current) setMessage(error.message || "清除失败，请重试");
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  };

  return <details style={{ marginTop: 18, fontSize: 13, border: "1px solid rgba(128,221,255,0.16)", borderRadius: 12, background: "var(--bg-inset)" }} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary style={{ cursor: "pointer", color: "var(--brand)", padding: "13px 15px", fontWeight: 700, listStylePosition: "inside" }}>🔐 网站会话管理 <span style={{ marginLeft: 8, color: "var(--text-muted)", fontWeight: 400 }}>登录状态与本地会话</span></summary>
    {open && <div style={{ padding: "2px 15px 15px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <p style={{ opacity: 0.68, lineHeight: 1.65, margin: 0, maxWidth: 760 }}>首次登录请在独立浏览器完成操作，再回到这里保存会话。保存后可重新进入网站；刷新状态只检查，不会保存登录或打开网站。</p>
        <button type="button" style={secondaryButton} disabled={busy} onClick={() => load()}>{busy ? "处理中…" : "刷新会话状态"}</button>
      </div>
      {sources.map(source => <section key={source.code} style={{ padding: 14, marginTop: 10, borderRadius: 10, border: "1px solid var(--border)", background: "var(--bg-inset)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <strong style={{ fontSize: 14 }}>{source.name}</strong>
          <span style={{ padding: "4px 9px", borderRadius: 999, color: statusTone(source), background: `${statusTone(source)}14`, border: `1px solid ${statusTone(source)}42` }}>{source.access_mode === "manual_assist" ? "人工辅助搜索" : source.access_mode === "browser_use_beta" ? "智能浏览器测试版" : !source.can_attempt_search ? "尚未接入采集" : source.statusError || storageLabels[source.session?.storage_status] || "状态未知"}</span>
        </div>
        {supportsSession(source) && <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 12 }}>
          <button style={actionButton} type="button" disabled={busy || source.session?.login_task?.running} onClick={() => loginAction(source, "login")}>{source.session?.storage_status === "saved" ? "使用已保存会话打开网站" : "打开网站登录"}</button>
          <button style={secondaryButton} type="button" disabled={busy || source.session?.login_task?.running} onClick={() => loginAction(source, "check")}>检查登录有效性</button>
          <button style={secondaryButton} type="button" disabled={busy || source.session?.login_task?.running || !source.session || source.session.storage_status === "missing"} onClick={() => clear(source)}>清除本地会话</button>
          {source.session?.login_task?.running && <>
            <button style={actionButton} type="button" disabled={busy || source.session.login_task.stage !== "waiting"} onClick={() => loginAction(source, "action", "save")}>已操作，保存会话</button>
            <button style={secondaryButton} type="button" disabled={busy} onClick={() => loginAction(source, "action", "cancel")}>取消登录操作</button>
          </>}
        </div>}
        {source.session?.login_task && <p style={{ margin: "10px 0 0", color: "var(--text-dim)", lineHeight: 1.55 }}>{source.session.login_task.message}</p>}
      </section>)}
      <p role="status" aria-live="polite" style={{ minHeight: 18, margin: "10px 0 0", color: message ? "var(--warning)" : "transparent" }}>{message || "没有待处理提示"}</p>
    </div>}
  </details>;
}

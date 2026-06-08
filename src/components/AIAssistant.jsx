const API_BASE = "http://localhost:5000";

const AIAssistant = () => {
  React.useEffect(() => {
    var el = document.getElementById("vanta-globe");
    if (!el || el._vanta) return;
    if (typeof VANTA === "undefined") return;
    el._vanta = VANTA.GLOBE({
      el: el,
      color: 0x00d4ff,
      color2: 0x7c4dff,
      backgroundColor: 0x0a0a0f,
      size: 0.8
    });
    return () => { if (el && el._vanta) { el._vanta.destroy(); el._vanta = null; } };
  }, []);

  // Also need to add the canvas to the section
  // Will handle below

  const steps = [
    { id: 1, name: "简历解析", icon: "📄", detail: "上传/解析/删除" },
    { id: 2, name: "智能优化简历", icon: "✨", detail: "DeepSeek AI优化" },
    { id: 3, name: "简历模板", icon: "📐", detail: "6套模板+证件照" },
    { id: 4, name: "岗位采集", icon: "🔍", detail: "51前程无忧/采集历史" },
    { id: 5, name: "JD匹配度评分", icon: "🎯", detail: "AI打分" },
    { id: 6, name: "精准简历优化", icon: "⚡", detail: "JD定向优化" },
    { id: 7, name: "自动打招呼", icon: "📤", detail: "半自动投递" }
  ];

  const [activeStep, setActiveStep] = React.useState(1);
  const [resumes, setResumes] = React.useState([]);
  // Step 1
  const [resumeDetail, setResumeDetail] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);
  const [statusMsg, setStatusMsg] = React.useState("");
  // Step 2
  const [optResume, setOptResume] = React.useState("");
  const [optTarget, setOptTarget] = React.useState("");
  const [optExtra, setOptExtra] = React.useState("");
  const [optResult, setOptResult] = React.useState(null);
  const [optLoading, setOptLoading] = React.useState(false);
  // Step 3
  const [tResume, setTResume] = React.useState("");
  const [tStyle, setTStyle] = React.useState("classic");
  const [tPhoto, setTPhoto] = React.useState(null);
  const [tPhotoStatus, setTPhotoStatus] = React.useState("");
  const [tPreview, setTPreview] = React.useState("");

  const templates = [
    { id: "classic", icon: "📄", name: "经典商务", desc: "稳重专业" },
    { id: "modern", icon: "🎨", name: "现代简约", desc: "紫色渐变" },
    { id: "dual", icon: "📊", name: "双栏技能", desc: "左栏展示" },
    { id: "elegant", icon: "📜", name: "复古暖黄", desc: "卡纸暖调" },
    { id: "minimal", icon: "🤍", name: "极简留白", desc: "干净清爽" },
    { id: "tech", icon: "💻", name: "科技蓝调", desc: "深蓝配色" }
  ];

  React.useEffect(() => { loadResumes(); }, []);

  const loadResumes = async () => {
    try { const r = await fetch(`${API_BASE}/api/resumes/list`); const d = await r.json(); setResumes(d.resumes || []); } catch(e) {}
  };

  // ── Step 1 ──
  const handleUpload = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    setUploading(true); setStatusMsg(`⏳ 解析中: ${file.name}`);
    const fd = new FormData(); fd.append("file", file);
    try { const r = await fetch(`${API_BASE}/api/resumes/upload`, { method: "POST", body: fd }); const d = await r.json(); setStatusMsg(d.ok ? "✅ 解析成功" : `❌ ${d.error || "失败"}`); if (d.ok) loadResumes(); } catch(e) { setStatusMsg(`❌ ${e.message}`); }
    setUploading(false);
  };
  const viewResume = async (fn) => { try { const r = await fetch(`${API_BASE}/api/resumes/detail/${fn}`); const d = await r.json(); if (d.ok) setResumeDetail(d.data); } catch(e) {} };
  const deleteResume = async (fn) => {
    try {
      const r = await fetch(API_BASE + "/api/resumes/delete/" + encodeURIComponent(fn), { method: "DELETE" });
      const d = await r.json();
      if (d.ok) {
        setStatusMsg("已删除: " + fn);
        loadResumes();
        setResumeDetail(null);
      } else {
        setStatusMsg("删除失败: " + (d.error || "未知错误"));
      }
    } catch(e) {
      setStatusMsg("删除错误: " + e.message);
    }
  };

// ── Step 2 ──
  const runOptimize = async () => {
    if (!optResume) { setStatusMsg("请选择简历"); return; }
    if (!optTarget.trim()) { setStatusMsg("请填写求职意向"); return; }
    setOptLoading(true); setOptResult(null); setStatusMsg("⏳ AI优化中...");
    const fd = new FormData(); fd.append("resume_file", optResume); fd.append("target", optTarget.trim()); fd.append("extra", optExtra.trim());
    try { const r = await fetch(`${API_BASE}/api/resume/optimize`, { method: "POST", body: fd }); const d = await r.json(); setStatusMsg(d.ok ? "✅ 优化完成" : `❌ ${d.error}`); if (d.ok) setOptResult(d); } catch(e) { setStatusMsg(`❌ ${e.message}`); }
    setOptLoading(false);
  };
  const exportResume = () => { if (optResult?.resume_file) window.open(`${API_BASE}/api/resume/export/${encodeURIComponent(optResult.resume_file)}`, "_blank"); };
  const overwriteResume = async () => {
    if (!optResult?.resume_file) { alert("没有可覆盖的结果"); return; }
    if (!confirm("确定要用AI优化结果覆盖原简历吗？")) return;
    const fd = new FormData(); fd.append("resume_file", optResult.resume_file); fd.append("optimized_summary", optResult.optimized_summary || ""); fd.append("optimized_projects", JSON.stringify(optResult.optimized_projects || [])); fd.append("optimized_internships", JSON.stringify(optResult.optimized_internships || [])); fd.append("enhanced_skills", JSON.stringify(optResult.enhanced_skills || [])); fd.append("target", optResult.target || "");
    try { const r = await fetch(`${API_BASE}/api/resume/overwrite`, { method: "POST", body: fd }); const d = await r.json(); if (d.ok) { alert("简历已覆盖！"); setStatusMsg("✅ 已覆盖"); loadResumes(); } else alert("失败: " + d.error); } catch(e) { alert("错误: " + e.message); }
  };

  // ── Step 3 ──
  const uploadPhoto = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    setTPhotoStatus("⏳ 上传中...");
    const fd = new FormData(); fd.append("resume_file", tResume || ""); fd.append("photo", file);
    try { const r = await fetch(API_BASE + "/api/resume/photo", { method: "POST", body: fd }); const d = await r.json(); if (d.ok) { setTPhotoStatus("✅ 已上传（可用于任意简历）"); setTPhoto(d.filename || "current_photo.jpg"); } else { setTPhotoStatus("❌ " + (d.error || "失败")); } } catch(e) { setTPhotoStatus("❌ 失败"); }
  }
  const previewTemplate = async () => {
    if (!tResume) { alert("请先选择简历"); return; }
    setTPreview("⏳ 生成中...");
    try {
      const fd = new FormData(); fd.append("resume_file", tResume); fd.append("template_style", tStyle);
      const r = await fetch(`${API_BASE}/api/resume/template`, { method: "POST", body: fd });
      const html = await r.text();
      setTPreview(html);
    } catch(e) { setTPreview(`<p style="color:#ff4081;padding:20px">预览失败: ${e.message}</p>`); }
  };
  const downloadTemplate = async (fmt) => {
    if (!tResume) { alert("请先选择简历"); return; }
    const fd = new FormData(); fd.append("resume_file", tResume); fd.append("template_style", tStyle);
    const r = await fetch(`${API_BASE}/api/resume/template`, { method: "POST", body: fd });
    const html = await r.text();
    if (fmt === "pdf") {
      const w = window.open("", "_blank"); w.document.write(html); w.document.close(); setTimeout(() => w.print(), 500);
    } else {
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `resume_${new Date().toISOString().slice(0,10)}.html`; a.click(); URL.revokeObjectURL(a.href);
    }
  };

  const switchStep = (id) => { setActiveStep(id); setResumeDetail(null); setStatusMsg(""); setOptResult(null); setTPreview(""); setTPhoto(null); setTPhotoStatus(""); };

  // ── Render Step 3 ──
  const renderStep3 = () => (
    <div style={{ animation: "fadeInUp 0.4s ease" }}>
      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>📐 简历模板</h3>
        <p style={{ color: "var(--text-dim)", marginBottom: 16 }}>选择模板风格，上传证件照，一键导出精美简历</p>

        <div style={{ marginBottom: 14 }}>
          <select value={tResume} onChange={e => { setTResume(e.target.value); setTPhoto(null); setTPhotoStatus(""); }} style={selectStyle}>
            <option value="">选择简历...</option>
            {resumes.map(x => <option key={x.filename} value={x.filename}>{x.name}{x.position ? ` - ${x.position}` : ""}</option>)}
          </select>
        </div>

        {/* Template cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
          {templates.map(t => (
            <div key={t.id} onClick={() => setTStyle(t.id)}
              style={{
                padding: "16px 14px", borderRadius: "var(--radius)", cursor: "pointer", textAlign: "center",
                background: tStyle === t.id ? "rgba(0,212,255,0.08)" : "transparent",
                border: `2px solid ${tStyle === t.id ? "var(--accent)" : "var(--border)"}`,
                transition: "var(--transition)"
              }}>
              <div style={{ fontSize: 28, marginBottom: 6 }}>{t.icon}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{t.name}</div>
              <div style={{ fontSize: 11, color: "var(--text-dim)" }}>{t.desc}</div>
            </div>
          ))}
        </div>

        {/* Photo upload */}
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
          <label style={{ padding: "8px 16px", borderRadius: "var(--radius)", border: "1px solid var(--border-light)", color: "var(--text-dim)", cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
            📷 上传证件照
            <input type="file" accept="image/*" onChange={uploadPhoto} style={{ display: "none" }} />
          </label>
          {tPhotoStatus && <span style={{ fontSize: 12, color: tPhotoStatus.includes("✅") ? "var(--accent)" : "var(--text-dim)" }}>{tPhotoStatus}</span>}
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={previewTemplate} style={{ ...btnGlow }}>👁 预览模板</button>
          <button onClick={() => downloadTemplate("html")} style={{ ...btnOutline2 }}>📥 HTML</button>
          <button onClick={() => downloadTemplate("pdf")} style={{ ...btnOutline2 }}>🖨 PDF</button>
        </div>
      </div>

      {/* Preview iframe */}
      {tPreview && (
        <div style={{ ...card, animation: "fadeInUp 0.4s ease" }}>
          {tPreview.startsWith("<") ? (
            <iframe srcDoc={tPreview} style={{ width: "100%", height: 550, border: "none", background: "#fff", borderRadius: 8 }} />
          ) : (
            <p style={{ color: "var(--text-dim)", padding: 20, textAlign: "center" }}>{tPreview}</p>
          )}
        </div>
      )}
    </div>
  );

  // ── Step 1 Render ──
  const renderStep1 = () => {
    if (resumeDetail) {
      const x = resumeDetail;
      return (
        <div style={{ animation: "fadeInUp 0.4s ease" }}>
          <button onClick={() => setResumeDetail(null)} style={btnOutline}>⬅ 返回列表</button>
          <div style={{ ...card, maxHeight: "60vh", overflowY: "auto", marginTop: 16 }}>
            <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16, color: "var(--accent)" }}>{x.name}</h3>
            {x.desired_position && <div style={{ padding: "12px 16px", background: "rgba(0,212,255,0.05)", borderLeft: "3px solid var(--accent)", borderRadius: "0 8px 8px 0", marginBottom: 12 }}><b style={{ color: "var(--accent)" }}>🎯 求职意向：</b>{x.desired_position}</div>}
            {x.desired_salary && <p style={{ color: "var(--accent2)", marginBottom: 12 }}>💰 期望薪资：{x.desired_salary}</p>}
            <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>📋 基本信息</h4>{x.phone && <p style={infoP}>📱 电话：{x.phone}</p>}{x.email && <p style={infoP}>📧 邮箱：{x.email}</p>}{x.education?.length > 0 && <p style={infoP}>🎓 学历：{x.education.map(e => `${e.school} | ${e.major} | ${e.degree} | ${e.year}`).join(" / ")}</p>}</div>
            {x.work_experience?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>💼 工作/实习经历</h4>{x.work_experience.map((w,i) => <div key={i} style={{ padding: "10px 14px", background: "rgba(255,255,255,0.02)", borderRadius: 8, marginBottom: 8 }}><b>{w.position}</b> @ {w.company} <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{w.duration}</span>{w.description && <p style={{ marginTop: 6, color: "var(--text-dim)", fontSize: 13 }}>{w.description}</p>}</div>)}</div>}
            {x.skills?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🛠 技能</h4><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{x.skills.map((s,i) => <span key={i} style={skillTag}>{s}</span>)}</div></div>}
            {x.summary && <div><h4 style={sectionH4}>📝 综合摘要</h4><p style={{ color: "var(--text-dim)", whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{x.summary}</p></div>}
          </div>
        </div>
      );
    }
    return (
      <div style={{ animation: "fadeInUp 0.4s ease" }}>
        <div style={{ ...card, marginBottom: 20 }}><h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>简历解析引擎</h3><p style={{ color: "var(--text-dim)", marginBottom: 16 }}>上传简历（PDF/Word/TXT），AI自动提取关键信息</p><label style={{ ...btnGlow, cursor: "pointer", display: "inline-flex" }}>{uploading ? "⏳ 解析中..." : "📤 上传并解析简历"}<input type="file" accept=".docx,.pdf,.txt" onChange={handleUpload} style={{ display: "none" }} /></label>{statusMsg && <p style={{ marginTop: 12, fontSize: 13, color: statusMsg.includes("✅") ? "var(--accent)" : statusMsg.includes("❌") ? "#ff4081" : "var(--text-dim)", fontFamily: "var(--font-mono)" }}>{statusMsg}</p>}</div>
        {resumes.length > 0 ? <div style={{ ...card }}><h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>已解析 ({resumes.length}份)</h3>{resumes.map((x,i) => <div key={i} onClick={() => viewResume(x.filename)} style={resumeItem} onMouseEnter={e => e.currentTarget.style.borderColor = "var(--accent)"} onMouseLeave={e => e.currentTarget.style.borderColor = "var(--border)"}><div><span style={{ color: "var(--accent)", fontWeight: 600 }}>{x.name}</span>{x.position && <span style={{ color: "var(--accent2)", fontSize: 12, marginLeft: 8 }}>🎯 {x.position}</span>}<br/><span style={{ fontSize: 11, color: "var(--text-dim)" }}>{x.parsed_at}</span></div><button onClick={e => { e.stopPropagation(); deleteResume(x.filename); }} style={deleteBtn}>删除</button></div>)}</div> : <div style={{ ...card, textAlign: "center", color: "var(--text-dim)", padding: "40px" }}><p style={{ fontSize: 40, marginBottom: 10 }}>📭</p><p>暂无解析的简历</p></div>}
      </div>
    );
  };

  // ── Step 2 Render (abbreviated, same as before) ──
  const renderStep2 = () => (
    <div style={{ animation: "fadeInUp 0.4s ease" }}>
      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>✨ AI智能优化简历</h3>
        <p style={{ color: "var(--text-dim)", marginBottom: 16 }}>基于DeepSeek AI，根据求职意向智能优化简历</p>
        <div style={{ marginBottom: 12 }}><select value={optResume} onChange={e => setOptResume(e.target.value)} style={selectStyle}><option value="">选择简历...</option>{resumes.map(x => <option key={x.filename} value={x.filename}>{x.name}{x.position ? ` - ${x.position}` : ""}</option>)}</select></div>
        <div style={{ marginBottom: 12 }}><input value={optTarget} onChange={e => setOptTarget(e.target.value)} placeholder="求职意向（如：新媒体运营经理）" style={inputStyle} /></div>
        <div style={{ marginBottom: 16 }}><textarea value={optExtra} onChange={e => setOptExtra(e.target.value)} placeholder="额外要求（可选）" rows={3} style={textareaStyle} /></div>
        <button onClick={runOptimize} disabled={optLoading} style={{ ...btnGlow, opacity: optLoading ? 0.6 : 1 }}>{optLoading ? "⏳ AI优化中..." : "🚀 开始AI优化"}</button>
        {statusMsg && <p style={{ marginTop: 12, fontSize: 13, color: statusMsg.includes("✅") ? "var(--accent)" : statusMsg.includes("❌") ? "#ff4081" : "var(--text-dim)", fontFamily: "var(--font-mono)" }}>{statusMsg}</p>}
      </div>
      {optResult && (
        <div style={{ ...card, animation: "fadeInUp 0.5s ease" }}>
          <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>✨ 三维度优化结果</h3>
          <div style={{ padding: "12px 16px", background: "rgba(0,212,255,0.05)", borderLeft: "3px solid var(--accent)", borderRadius: "0 8px 8px 0", marginBottom: 12 }}><b style={{ color: "var(--accent)" }}>求职意向：</b>{optResult.target}</div>
          {optResult.job_analysis && <div style={{ padding: "12px 16px", background: "rgba(255,171,0,0.05)", borderLeft: "3px solid #ffab00", borderRadius: "0 8px 8px 0", marginBottom: 16, fontSize: 13, color: "var(--accent2)", lineHeight: 1.6 }}>🔍 <b>岗位分析：</b>{optResult.job_analysis}</div>}
          {optResult.optimized_summary && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>📝 优化后个人总结</h4><p style={{ color: "var(--text)", whiteSpace: "pre-wrap", lineHeight: 1.7, fontSize: 14 }}>{optResult.optimized_summary}</p></div>}
          {optResult.optimized_projects?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent2)", marginBottom: 10 }}>🚀 优化项目经验</h4>{optResult.optimized_projects.map((p,i) => <div key={i} style={{ padding: "12px 16px", background: "rgba(0,255,136,0.05)", borderLeft: "3px solid var(--accent2)", borderRadius: "0 8px 8px 0", marginBottom: 8 }}><b>{p.name}</b> — <span style={{ color: "var(--text-dim)", fontSize: 13 }}>{p.role}</span><p style={{ fontSize: 13, color: "#ccc", marginTop: 6, lineHeight: 1.6 }}>{p.description}</p></div>)}</div>}
          {optResult.optimized_internships?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "#ffab00", marginBottom: 10 }}>💼 优化实习经验</h4>{optResult.optimized_internships.map((intern,i) => <div key={i} style={{ padding: "12px 16px", background: "rgba(255,171,0,0.05)", borderLeft: "3px solid #ffab00", borderRadius: "0 8px 8px 0", marginBottom: 8 }}><b>{intern.company}</b> | {intern.position} <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{intern.duration}</span><p style={{ fontSize: 13, color: "#ccc", marginTop: 6, lineHeight: 1.6 }}>{intern.description}</p></div>)}</div>}
          {optResult.enhanced_skills?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>🔧 增强技能列表</h4><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{optResult.enhanced_skills.map((s,i) => <span key={i} style={skillTag}>{s}</span>)}</div></div>}
          {optResult.suggestions?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--text-dim)", marginBottom: 10 }}>💡 优化建议</h4>{optResult.suggestions.map((s,i) => <div key={i} style={{ fontSize: 13, color: "var(--accent2)", marginBottom: 4, padding: "6px 12px", background: "rgba(0,255,136,0.05)", borderRadius: 6 }}>💡 {s}</div>)}</div>}
          <div style={{ display: "flex", gap: 12, marginTop: 20 }}><button onClick={exportResume} style={{ ...btnGlow, flex: 1 }}>📥 导出简历</button><button onClick={overwriteResume} style={{ flex: 1, ...btnOutline2, borderColor: "#ffab00", color: "#ffab00" }}>💾 覆盖原简历</button></div>
        </div>
      )}
    </div>
  );

﻿  // ── Step 4: Job Scraping State ──
  const [sResume, setSResume] = React.useState("");
  const [sSalary, setSSalary] = React.useState("");
  const [scrapeRunning, setScrapeRunning] = React.useState(false);
  const [scrapeStatus, setScrapeStatus] = React.useState("");
  const [jobsFiles, setJobsFiles] = React.useState([]);
  const [jobsDetail, setJobsDetail] = React.useState(null);
  const pollRef = React.useRef(null);

  React.useEffect(() => { if (activeStep === 4) loadJobsFiles(); }, [activeStep]);

  const loadJobsFiles = async () => {
    try { const r = await fetch(`${API_BASE}/api/jobs/list`); const d = await r.json(); setJobsFiles(d.files || []); } catch(e) {}
  };

  const startScrape = async () => {
    if (scrapeRunning) { setScrapeStatus("采集正在进行中"); return; }
    if (!sResume) { setScrapeStatus("请先选择简历"); return; }
    setScrapeRunning(true); setScrapeStatus("启动采集...");
    const fd = new FormData(); fd.append("platforms", "51job"); fd.append("resume_file", sResume);
    if (sSalary.trim()) fd.append("salary_range", sSalary.trim());
    try {
      const r = await fetch(`${API_BASE}/api/jobs/scrape`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) { setScrapeStatus("采集已启动，正在抓取..."); pollScrapeStatus(); }
      else { setScrapeStatus(d.error || "启动失败"); setScrapeRunning(false); }
    } catch(e) { setScrapeStatus(e.message); setScrapeRunning(false); }
  };

  const pollScrapeStatus = async () => {
    let count = 0;
    const poll = async () => {
      if (count > 180) { setScrapeRunning(false); return; }
      try {
        const r = await fetch(`${API_BASE}/api/jobs/scrape/status`);
        const s = await r.json();
        if (!s.running) { setScrapeRunning(false); setScrapeStatus("完成! " + s.jobs_count + "个岗位"); loadJobsFiles(); return; }
        if (count % 5 === 0) setScrapeStatus("采集中: " + s.progress);
        count++; pollRef.current = setTimeout(poll, 2000);
      } catch(e) { count++; pollRef.current = setTimeout(poll, 2000); }
    };
    poll();
  };

  React.useEffect(() => { return () => { if (pollRef.current) clearTimeout(pollRef.current); }; }, []);

  const viewJobsDetail = async (fn) => {
    try {
      const r = await fetch(`${API_BASE}/api/jobs/detail/${encodeURIComponent(fn)}`);
      const d = await r.json();
      if (d.ok && d.data) setJobsDetail(d.data);
    } catch(e) {}
  };

  const renderStep4 = () => {
    if (jobsDetail) {
      const jd = jobsDetail;
      const jobs = jd.jobs || [];
      return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
        React.createElement("button", { onClick: () => setJobsDetail(null), style: btnOutline }, "返回列表"),
        React.createElement("div", { style: { ...card, maxHeight: "60vh", overflowY: "auto", marginTop: 16 } },
          React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 8 } }, "本次采集共 " + jobs.length + " 个岗位"),
          React.createElement("p", { style: { color: "var(--text-dim)", fontSize: 12, marginBottom: 4 } }, "时间: " + (jd.collected_at || "")),
          jd.keywords && jd.keywords.length > 0 ? React.createElement("p", { style: { color: "var(--text-dim)", fontSize: 12, marginBottom: 16 } }, "搜索关键词: " + jd.keywords.join(", ")) : null,
          jobs.map((j, i) => {
            let uniqueTags = [];
            if (j.tags && j.tags.length > 0) {
              const seen = {};
              j.tags.forEach(t => { String(t).split(/[\n\r]+/).filter(x => x.trim()).forEach(item => { const clean = item.trim(); if (clean && !seen[clean]) { seen[clean] = true; uniqueTags.push(clean); } }); });
            }
            return React.createElement("div", { key: i, style: { padding: 14, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 10, marginBottom: 10 } },
              React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 10, marginBottom: 8 } },
                React.createElement("span", { style: { minWidth: 28, height: 28, borderRadius: "50%", background: "var(--accent2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#fff" } }, i + 1),
                React.createElement("div", { style: { flex: 1 } },
                  React.createElement("div", { style: { fontSize: 15, fontWeight: 600, color: "#fff" } }, j.title),
                  React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)" } }, j.company + " - " + (j.salary||"") + " - " + (j.location||""))
                )
              ),
              (j.experience || j.education) ? React.createElement("div", { style: { fontSize: 11, color: "var(--text-dim)", marginBottom: 6 } },
                j.experience ? React.createElement("span", null, "经验: " + j.experience + "  ") : null,
                j.education ? React.createElement("span", null, "学历: " + j.education) : null
              ) : null,
              uniqueTags.length > 0 ? React.createElement("div", null,
                React.createElement("div", { style: { fontSize: 10, color: "var(--text-dim)", marginBottom: 4 } }, "岗位要求/关键词:"),
                React.createElement("div", { style: { display: "flex", flexWrap: "wrap", gap: 6 } },
                  uniqueTags.slice(0, 20).map((t, idx) => React.createElement("span", { key: idx, style: { padding: "3px 10px", background: "rgba(124,77,255,0.1)", border: "1px solid rgba(124,77,255,0.2)", borderRadius: 12, fontSize: 11, color: "var(--accent2)" } }, t)),
                  uniqueTags.length > 20 ? React.createElement("span", { style: { fontSize: 11, color: "var(--text-dim)" } }, "...等" + uniqueTags.length + "个") : null
                )
              ) : null
            );
          })
        )
      );
    }

    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "岗位采集"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 6 } }, "城市: 广州 | 根据简历求职意向精准采集"),
        React.createElement("p", { style: { color: "var(--accent)", fontSize: 13, marginBottom: 14 } }, "选择简历后将自动匹配求职岗位"),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("select", {
            value: sResume, style: selectStyle,
            onChange: (e) => { setSResume(e.target.value); const opt = e.target.options[e.target.selectedIndex]; const sal = opt.getAttribute("data-salary"); if (sal) setSSalary(sal); }
          },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename, "data-salary": x.desired_salary || "" }, x.name + (x.position ? " - " + x.position : "")))
          )
        ),
        React.createElement("div", { style: { display: "flex", gap: 16, marginBottom: 12, alignItems: "center" } },
          React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 6, color: "var(--accent)", cursor: "pointer", fontSize: 13 } },
            React.createElement("input", { type: "checkbox", defaultChecked: true, readOnly: true, style: { accentColor: "var(--accent)" } }),
            "51前程无忧"
          ),
          React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, "期望薪资:"),
          React.createElement("input", { value: sSalary, onChange: (e) => setSSalary(e.target.value), placeholder: "如 5k-8k", style: { background: "#111", border: "1px solid var(--border)", color: "#fff", padding: "6px 10px", borderRadius: 6, width: 130, fontSize: 13, outline: "none" } })
        ),
        React.createElement("button", { onClick: startScrape, disabled: scrapeRunning, style: { ...btnGlow, opacity: scrapeRunning ? 0.6 : 1 } },
          scrapeRunning ? "采集中..." : "开始采集"
        ),
        scrapeStatus ? React.createElement("p", { style: { marginTop: 12, fontSize: 13, fontFamily: "var(--font-mono)", color: scrapeStatus.includes("完成") ? "var(--accent)" : scrapeStatus.includes("失败") ? "#ff4081" : "var(--text-dim)" } }, scrapeStatus) : null
      ),
      jobsFiles.length > 0 ? React.createElement("div", { style: { ...card } },
        React.createElement("h3", { style: { fontSize: 16, fontWeight: 600, marginBottom: 16 } }, "采集历史 (最近" + Math.min(5, jobsFiles.length) + "次/共" + jobsFiles.length + "次)"),
        jobsFiles.slice(0, 5).map((f, i) =>
          React.createElement("div", { key: i, onClick: () => viewJobsDetail(f.filename),
            style: { padding: "10px 14px", marginBottom: 4, borderRadius: 8, cursor: "pointer", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", transition: "var(--transition)" },
            onMouseEnter: (e) => e.currentTarget.style.background = "rgba(0,212,255,0.06)",
            onMouseLeave: (e) => e.currentTarget.style.background = "rgba(255,255,255,0.03)"
          },
            React.createElement("span", { style: { color: "var(--accent)" } }, "第" + (jobsFiles.length - i) + "次采集"),
            React.createElement("span", { style: { fontSize: 11, color: "var(--text-dim)", marginLeft: 8 } }, (f.keywords && f.keywords[0]) ? f.keywords[0] : "未知"),
            React.createElement("span", { style: { fontSize: 11, color: "var(--text-dim)", marginLeft: 8 } }, " - " + f.count + "个岗位")
          )
        )
      ) : null
    );
  };

﻿  // ── Step 5: JD Match State ──
  const [jdResume, setJdResume] = React.useState("");
  const [jdText, setJdText] = React.useState("");
  const [jdResult, setJdResult] = React.useState(null);
  const [jdLoading, setJdLoading] = React.useState(false);
  // Batch
  const [batchResume, setBatchResume] = React.useState("");
  const [batchFile, setBatchFile] = React.useState("");
  const [batchTh, setBatchTh] = React.useState(70);
  const [batchResult, setBatchResult] = React.useState(null);
  const [batchLoading, setBatchLoading] = React.useState(false);
  const [batchFiles, setBatchFiles] = React.useState([]);
  const [batchShowHi, setBatchShowHi] = React.useState(true);

  React.useEffect(() => { if (activeStep === 5) { loadBatchFilesForStep5(); } }, [activeStep]);

  const loadBatchFilesForStep5 = async () => {
    try { const r = await fetch(`${API_BASE}/api/jobs/list`); const d = await r.json(); setBatchFiles(d.files || []); } catch(e) {}
  };

  const runJDMatch = async () => {
    if (jdText.trim().length < 10) { setStatusMsg("请粘贴岗位描述(至少10字)"); return; }
    if (!jdResume) { setStatusMsg("请选择简历"); return; }
    setJdLoading(true); setJdResult(null);
    const fd = new FormData(); fd.append("jd_text", jdText.trim()); fd.append("resume_file", jdResume);
    try {
      const r = await fetch(`${API_BASE}/api/jd/match`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) setJdResult(d); else setStatusMsg(d.error || "匹配失败");
    } catch(e) { setStatusMsg(e.message); }
    setJdLoading(false);
  };

  const runBatchScore = async () => {
    if (!batchFile) { setStatusMsg("请选择采集记录"); return; }
    setBatchLoading(true); setBatchResult(null);
    try {
      const r = await fetch(`${API_BASE}/api/jobs/batch-score-json`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobs_file: batchFile, resume_file: batchResume, threshold: batchTh })
      });
      const d = await r.json();
      if (d.ok) setBatchResult(d); else setStatusMsg(d.error || "匹配失败");
    } catch(e) { setStatusMsg(e.message); }
    setBatchLoading(false);
  };

  const renderStep5 = () => {
    const sc = jdResult ? jdResult.overall_score || 0 : 0;
    const cc = sc >= 75 ? "#0f0" : sc >= 50 ? "#ffab00" : "#ff4081";

    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      // Part A: Single JD Match
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "JD匹配度评分"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16 } }, "粘贴岗位描述，AI评估匹配度"),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("select", { value: jdResume, onChange: e => setJdResume(e.target.value), style: selectStyle },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, x.name + (x.position ? " - " + x.position : "")))
          )
        ),
        React.createElement("textarea", {
          value: jdText, onChange: e => setJdText(e.target.value),
          placeholder: "粘贴岗位描述(JD)到这里...", rows: 5, style: textareaStyle
        }),
        React.createElement("button", { onClick: runJDMatch, disabled: jdLoading, style: { ...btnGlow, marginTop: 12, opacity: jdLoading ? 0.6 : 1 } },
          jdLoading ? "分析中..." : "开始匹配分析"
        ),
        statusMsg && !jdResult ? React.createElement("p", { style: { ...statusStyle, color: statusMsg.includes("失败") || statusMsg.includes("请") ? "#ff4081" : "var(--accent)" } }, statusMsg) : null,
        jdResult ? React.createElement("div", { style: { marginTop: 20 } },
          React.createElement("div", { style: { textAlign: "center" } },
            React.createElement("div", { style: { fontSize: 52, fontWeight: 800, color: cc } }, sc + "/100")
          ),
          React.createElement("div", { style: { display: "flex", gap: 12, margin: "16px 0" } },
            scoreBar("技能匹配", jdResult.skill_match || 0),
            scoreBar("经验匹配", jdResult.experience_match || 0),
            scoreBar("学历匹配", jdResult.education_match || 0)
          ),
          jdResult.verdict ? React.createElement("div", { style: { padding: "10px 14px", background: "rgba(0,212,255,0.06)", borderLeft: "3px solid var(--accent)", borderRadius: "0 8px 8px 0", marginBottom: 12, fontSize: 14 } }, jdResult.verdict) : null,
          jdResult.strengths && jdResult.strengths.length > 0 ? React.createElement("div", { style: { marginBottom: 8 } },
            React.createElement("b", { style: { color: "#0f0" } }, "匹配优势"),
            jdResult.strengths.map((s, i) => React.createElement("div", { key: i, style: { fontSize: 13, color: "var(--text-dim)", padding: "2px 0" } }, "- " + s))
          ) : null,
          jdResult.weaknesses && jdResult.weaknesses.length > 0 ? React.createElement("div", { style: { marginBottom: 8 } },
            React.createElement("b", { style: { color: "#ffab00" } }, "不足之处"),
            jdResult.weaknesses.map((w, i) => React.createElement("div", { key: i, style: { fontSize: 13, color: "var(--text-dim)", padding: "2px 0" } }, "- " + w))
          ) : null,
          jdResult.suggestions && jdResult.suggestions.length > 0 ? React.createElement("div", null,
            React.createElement("b", { style: { color: "var(--accent)" } }, "建议"),
            jdResult.suggestions.map((s, i) => React.createElement("div", { key: i, style: { fontSize: 13, color: "var(--text-dim)", padding: "2px 0" } }, "- " + s))
          ) : null
        ) : null
      ),

      // Part B: Batch Match
      React.createElement("div", { style: { ...card } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "批量JD匹配"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16 } }, "对采集的岗位一键全量AI评分（三维：技能/经验/学历）"),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("select", { value: batchResume, onChange: e => setBatchResume(e.target.value), style: selectStyle },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, x.name + (x.position ? " - " + x.position : "")))
          )
        ),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("select", { value: batchFile, onChange: e => setBatchFile(e.target.value), style: selectStyle },
            React.createElement("option", { value: "" }, "选择采集记录..."),
            batchFiles.map((f, i) => React.createElement("option", { key: f.filename, value: f.filename }, "第" + (batchFiles.length - i) + "次采集 - " + ((f.keywords && f.keywords[0]) ? f.keywords[0] : "未知") + " - " + f.count + "个岗位"))
          )
        ),
        React.createElement("div", { style: { marginBottom: 16, display: "flex", alignItems: "center", gap: 8 } },
          React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, "阈值:"),
          React.createElement("input", { type: "number", value: batchTh, onChange: e => setBatchTh(parseInt(e.target.value) || 70), min: 0, max: 100, style: { background: "#111", border: "1px solid var(--border)", color: "#fff", padding: "6px 10px", borderRadius: 6, width: 80, fontSize: 13, outline: "none" } })
        ),
        React.createElement("button", { onClick: runBatchScore, disabled: batchLoading, style: { ...btnGlow, opacity: batchLoading ? 0.6 : 1 } },
          batchLoading ? "批量分析中..." : "一键全量匹配"
        ),
        batchResult ? React.createElement("div", { style: { marginTop: 20 } },
          React.createElement("h3", { style: { fontSize: 18, marginBottom: 4 } }, "批量匹配完成"),
          React.createElement("p", { style: { color: "var(--text-dim)", fontSize: 13 } }, "共 " + batchResult.total + " 个岗位"),
          React.createElement("div", { style: { display: "flex", gap: 12, margin: "16px 0" } },
            React.createElement("div", { onClick: () => setBatchShowHi(true), style: { flex: 1, padding: 16, background: batchShowHi ? "rgba(0,255,0,0.1)" : "rgba(0,255,0,0.04)", border: "1px solid " + (batchShowHi ? "rgba(0,255,0,0.3)" : "var(--border)"), borderRadius: 12, textAlign: "center", cursor: "pointer" } },
              React.createElement("div", { style: { fontSize: 36, fontWeight: 800, color: "#0f0" } }, batchResult.jobs.filter(j => (j.match_score || 0) >= batchTh).length),
              React.createElement("div", { style: { color: "var(--text-dim)", fontSize: 12, marginTop: 4 } }, ">= " + batchTh + "分")
            ),
            React.createElement("div", { onClick: () => setBatchShowHi(false), style: { flex: 1, padding: 16, background: !batchShowHi ? "rgba(255,64,129,0.08)" : "rgba(255,64,129,0.04)", border: "1px solid " + (!batchShowHi ? "rgba(255,64,129,0.3)" : "var(--border)"), borderRadius: 12, textAlign: "center", cursor: "pointer" } },
              React.createElement("div", { style: { fontSize: 36, fontWeight: 800, color: "#ff4081" } }, batchResult.jobs.filter(j => (j.match_score || 0) < batchTh).length),
              React.createElement("div", { style: { color: "var(--text-dim)", fontSize: 12, marginTop: 4 } }, "< " + batchTh + "分")
            )
          ),
          React.createElement("div", { style: { maxHeight: "40vh", overflowY: "auto" } },
            batchResult.jobs.filter(j => batchShowHi ? (j.match_score || 0) >= batchTh : (j.match_score || 0) < batchTh).map((j, i) => {
              const sc2 = j.match_score || 0;
              const cc2 = sc2 >= 75 ? "#0f0" : sc2 >= 50 ? "#ffab00" : "#ff4081";
              return React.createElement("div", { key: i, style: { display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--border)" } },
                React.createElement("div", { style: { minWidth: 40, height: 40, borderRadius: "50%", background: cc2, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 800, color: "#000" } }, sc2),
                React.createElement("div", { style: { flex: 1 } },
                  React.createElement("div", { style: { fontSize: 14, fontWeight: 600 } }, j.title || ""),
                  React.createElement("div", { style: { fontSize: 11, color: "var(--text-dim)" } }, (j.company || "") + " - " + (j.salary || "") + " - " + (j.location || ""))
                )
              );
            })
          )
        ) : null
      )
    );
  };

﻿  // ── Step 6: Precision Optimize State ──
  const [pJobsFile, setPJobsFile] = React.useState("");
  const [pResume, setPResume] = React.useState("");
  const [pTh, setPTh] = React.useState(70);
  const [pJobs, setPJobs] = React.useState([]);
  const [pChecked, setPChecked] = React.useState([]);
  const [pResult, setPResult] = React.useState(null);
  const [pLoading, setPLoading] = React.useState(false);
  const [pFilesForStep6, setPFilesForStep6] = React.useState([]);

  React.useEffect(() => { if (activeStep === 6) { loadPFiles(); } }, [activeStep]);

  const loadPFiles = async () => {
    try { const r = await fetch(`${API_BASE}/api/jobs/list`); const d = await r.json(); setPFilesForStep6(d.files || []); } catch(e) {}
  };

  const loadPrecisionJobs = async () => {
    if (!pJobsFile || !pResume) { setStatusMsg("请先选择采集记录和简历"); return; }
    setPLoading(true);
    try {
      const fd = new FormData(); fd.append("jobs_file", pJobsFile); fd.append("resume_file", pResume); fd.append("threshold", pTh);
      const r = await fetch(`${API_BASE}/api/jobs/batch-score-json`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jobs_file: pJobsFile, resume_file: pResume, threshold: pTh }) });
      const d = await r.json();
      if (d.ok) {
        const filtered = d.jobs.filter(j => (j.match_score || 0) >= pTh);
        setPJobs(filtered);
        setPChecked(filtered.map((_, i) => String(i)));
        setStatusMsg("已加载 " + filtered.length + " 个岗位 (>= " + pTh + "分)");
      } else { setStatusMsg(d.error || "加载失败"); }
    } catch(e) { setStatusMsg(e.message); }
    setPLoading(false);
  };

  const toggleAll = (checked) => {
    if (checked) setPChecked(pJobs.map((_, i) => String(i)));
    else setPChecked([]);
  };

  const runPrecisionOptimize = async () => {
    if (pChecked.length === 0) { setStatusMsg("请至少勾选一个岗位"); return; }
    setPLoading(true); setPResult(null);
    try {
      const fd = new FormData(); fd.append("resume_file", pResume); fd.append("jobs_file", pJobsFile); fd.append("job_indices", pChecked.join(","));
      const r = await fetch(`${API_BASE}/api/resume/precision-optimize`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) { setPResult(d); setStatusMsg("优化完成"); }
      else { setStatusMsg(d.error || "优化失败"); }
    } catch(e) { setStatusMsg(e.message); }
    setPLoading(false);
  };

  const overwritePrecision = async () => {
    if (!pResult || !pResult.resume_file) { alert("无结果"); return; }
    if (!confirm("确定覆盖简历？")) return;
    try {
      const fd = new FormData(); fd.append("resume_file", pResult.resume_file);
      fd.append("optimized_summary", pResult.optimized_summary || "");
      fd.append("optimized_projects", JSON.stringify(pResult.optimized_projects || []));
      fd.append("optimized_internships", "[]");
      fd.append("enhanced_skills", JSON.stringify(pResult.enhanced_skills || []));
      fd.append("target", pResult.target_position || "");
      const r = await fetch(`${API_BASE}/api/resume/overwrite`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) { alert("简历已精准覆盖！"); setStatusMsg("已覆盖简历"); loadResumes(); }
      else alert("失败: " + d.error);
    } catch(e) { alert("出错: " + e.message); }
  };

  const copyPrecision = () => {
    if (!pResult) return;
    let text = "";
    if (pResult.target_position) text += "目标岗位: " + pResult.target_position + "\n\n";
    if (pResult.optimized_summary) text += "优化评价:\n" + pResult.optimized_summary + "\n\n";
    if (pResult.optimized_projects) pResult.optimized_projects.forEach(p => { text += "项目: " + p.name + " (" + p.role + ")\n" + p.description + "\n\n"; });
    if (pResult.enhanced_skills) text += "技能: " + pResult.enhanced_skills.join(", ") + "\n";
    navigator.clipboard.writeText(text).then(() => setStatusMsg("已复制到剪贴板"));
  };

  const renderStep6 = () => {
    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "精准简历优化"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16 } }, "针对JD匹配>=70分的岗位，逐岗读取JD定向优化简历"),
        React.createElement("div", { style: { marginBottom: 12, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" } },
          React.createElement("select", { value: pJobsFile, onChange: e => setPJobsFile(e.target.value), style: { ...selectStyle, maxWidth: 200 } },
            React.createElement("option", { value: "" }, "选择采集记录..."),
            pFilesForStep6.map((f, i) => React.createElement("option", { key: f.filename, value: f.filename }, "第" + (pFilesForStep6.length - i) + "次采集 (" + (f.count || 0) + "岗) - " + ((f.keywords && f.keywords[0]) ? f.keywords[0] : "未知")))
          ),
          React.createElement("select", { value: pResume, onChange: e => setPResume(e.target.value), style: { ...selectStyle, maxWidth: 180 } },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, x.name + (x.position ? " - " + x.position : "")))
          ),
          React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, "阈值:"),
          React.createElement("input", { type: "number", value: pTh, onChange: e => setPTh(parseInt(e.target.value) || 70), min: 0, max: 100, style: { background: "#111", border: "1px solid var(--border)", color: "#fff", padding: "6px 10px", borderRadius: 6, width: 70, fontSize: 13, outline: "none" } }),
          React.createElement("button", { onClick: loadPrecisionJobs, style: { ...btnGlow, fontSize: 13, padding: "8px 20px" } }, "加载岗位")
        ),

        statusMsg ? React.createElement("p", { style: { ...statusStyle, color: statusMsg.includes("失败") ? "#ff4081" : statusMsg.includes("已加载") || statusMsg.includes("完成") || statusMsg.includes("覆盖") || statusMsg.includes("复制") ? "var(--accent)" : "var(--text-dim)" } }, statusMsg) : null,

        pJobs.length > 0 ? React.createElement("div", { style: { marginTop: 16 } },
          React.createElement("div", { style: { marginBottom: 8, display: "flex", alignItems: "center", gap: 8 } },
            React.createElement("label", { style: { fontSize: 12, color: "var(--text-dim)", cursor: "pointer" } },
              React.createElement("input", { type: "checkbox", checked: pChecked.length === pJobs.length, onChange: e => toggleAll(e.target.checked), style: { accentColor: "var(--accent)" } }),
              " 全选 (" + pChecked.length + "/" + pJobs.length + ")"
            )
          ),
          React.createElement("div", { style: { maxHeight: "30vh", overflowY: "auto", marginBottom: 16 } },
            pJobs.map((j, i) => {
              const sc2 = j.match_score || 0;
              const cc2 = sc2 >= 75 ? "#0f0" : sc2 >= 50 ? "#ffab00" : "#ff4081";
              return React.createElement("div", { key: i, style: { display: "flex", alignItems: "center", gap: 8, padding: "8px 0", borderBottom: "1px solid var(--border)" } },
                React.createElement("input", { type: "checkbox", value: String(i), checked: pChecked.includes(String(i)), onChange: e => { if (e.target.checked) setPChecked([...pChecked, String(i)]); else setPChecked(pChecked.filter(v => v !== String(i))); }, style: { accentColor: "var(--accent)" } }),
                React.createElement("span", { style: { minWidth: 32, height: 24, borderRadius: 12, background: cc2, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#000" } }, sc2),
                React.createElement("div", { style: { flex: 1 } },
                  React.createElement("div", { style: { fontSize: 13, fontWeight: 600 } }, j.title || ""),
                  React.createElement("div", { style: { fontSize: 11, color: "var(--text-dim)", marginBottom: 4 } }, (j.company || "") + " - " + (j.salary || "")),
                  (j.tags && j.tags.length > 0) ? (function(){
                    var ut = [];
                    var sd = {};
                    j.tags.forEach(function(t){
                      String(t).split(/[\n\r]+/).filter(function(x){ return x.trim(); }).forEach(function(item){
                        var c = item.trim();
                        if(c && !sd[c]){ sd[c] = true; ut.push(c); }
                      });
                    });
                    return React.createElement("div", { style: { display: "flex", flexWrap: "wrap", gap: 4 } },
                      ut.slice(0, 10).map(function(t, idx){
                        return React.createElement("span", { key: idx, style: { padding: "2px 8px", background: "rgba(124,77,255,0.1)", border: "1px solid rgba(124,77,255,0.2)", borderRadius: 10, fontSize: 10, color: "var(--accent2)" } }, t);
                      }),
                      ut.length > 10 ? React.createElement("span", { style: { fontSize: 10, color: "var(--text-dim)" } }, "...等" + ut.length + "个") : null
                    );
                  })() : null
                )
              );
            })
          ),
          React.createElement("button", { onClick: runPrecisionOptimize, disabled: pLoading, style: { ...btnGlow, opacity: pLoading ? 0.6 : 1 } },
            pLoading ? "优化中..." : "开始精准优化"
          )
        ) : null,
        pLoading && !pJobs.length ? React.createElement("p", { style: { textAlign: "center", color: "var(--text-dim)", padding: 40 } }, "选择采集结果和简历后点击加载岗位") : null,

        pResult ? React.createElement("div", { style: { marginTop: 20, ...card, borderColor: "var(--accent)" } },
          React.createElement("h3", { style: { color: "#0f0", marginBottom: 12 } }, "精准优化完成"),
          pResult.target_position ? React.createElement("p", null, React.createElement("b", null, "目标: "), pResult.target_position) : null,
          pResult.optimized_summary ? React.createElement("p", { style: { marginTop: 8 } }, React.createElement("b", null, "优化评价:"), React.createElement("br", null), React.createElement("span", { style: { color: "var(--text-dim)" } }, pResult.optimized_summary)) : null,
          pResult.enhanced_skills && pResult.enhanced_skills.length ? React.createElement("p", { style: { marginTop: 8 } }, React.createElement("b", null, "技能: "), pResult.enhanced_skills.join(", ")) : null,
          pResult.optimized_projects && pResult.optimized_projects.length ? React.createElement("div", { style: { marginTop: 8 } },
            React.createElement("b", null, "项目:"),
            pResult.optimized_projects.map((pj, i) => React.createElement("div", { key: i, style: { marginLeft: 12, marginBottom: 6, padding: 8, background: "rgba(255,255,255,0.03)", borderRadius: 6 } },
              React.createElement("b", null, pj.name), React.createElement("span", { style: { color: "var(--text-dim)" } }, " (" + pj.role + ")"),
              React.createElement("br", null), React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, pj.description)
            ))
          ) : null,
          pResult.optimization_notes ? React.createElement("p", { style: { marginTop: 8, color: "var(--accent2)", fontSize: 12 } }, pResult.optimization_notes) : null,
          React.createElement("div", { style: { marginTop: 16, display: "flex", gap: 8 } },
            React.createElement("button", { onClick: overwritePrecision, style: { ...btnGlow } }, "覆盖简历"),
            React.createElement("button", { onClick: copyPrecision, style: { ...btnOutline2 } }, "复制结果")
          )
        ) : null
      )
    );
  };

﻿  // ── Step 7: Auto Greeting / Delivery State ──
  const [dJobsFile, setDJobsFile] = React.useState("");
  const [dResume, setDResume] = React.useState("");
  const [dTh, setDTh] = React.useState(70);
  const [dDirection, setDDirection] = React.useState("");
  const [dGreeting, setDGreeting] = React.useState("");
  const [dCandidates, setDCandidates] = React.useState([]);
  const [dSummary, setDSummary] = React.useState(null);
  const [dLoading, setDLoading] = React.useState(false);
  const [dFilesForStep7, setDFilesForStep7] = React.useState([]);

  React.useEffect(() => { if (activeStep === 7) loadDFiles(); }, [activeStep]);

  const loadDFiles = async () => {
    try { const r = await fetch(`${API_BASE}/api/jobs/list`); const d = await r.json(); setDFilesForStep7(d.files || []); } catch(e) {}
  };

  const generateGreeting = async () => {
    if (!dResume) { setStatusMsg("请先选择简历"); return; }
    setDGreeting("AI正在生成..."); setDLoading(true);
    try {
      const fd = new FormData(); fd.append("resume_file", dResume); fd.append("direction", dDirection.trim()); fd.append("jobs_file", dJobsFile || "");
      const r = await fetch(`${API_BASE}/api/deliver/greeting`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) { setDGreeting(d.greeting); setStatusMsg("AI开场白已生成"); }
      else { setDGreeting("生成失败: " + d.error); setStatusMsg(d.error); }
    } catch(e) { setDGreeting("网络错误: " + e.message); setStatusMsg(e.message); }
    setDLoading(false);
  };

  const copyGreeting = () => {
    navigator.clipboard.writeText(dGreeting).then(() => setStatusMsg("已复制到剪贴板"));
  };

  const loadDeliverCandidates = async () => {
    if (!dJobsFile || !dResume) { setStatusMsg("请选择采集记录和简历"); return; }
    setDLoading(true); setDCandidates([]);
    try {
      const fd = new FormData(); fd.append("jobs_file", dJobsFile); fd.append("resume_file", dResume); fd.append("threshold", dTh);
      const r = await fetch(`${API_BASE}/api/deliver/list`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) { setDCandidates(d.jobs || []); setDSummary(d); }
      else { setStatusMsg(d.error || "加载失败"); }
    } catch(e) { setStatusMsg(e.message); }
    setDLoading(false);
  };

  const renderStep7 = () => {
    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      // Warning
      React.createElement("div", { style: { padding: "10px 14px", background: "rgba(255,171,0,0.08)", border: "1px solid rgba(255,171,0,0.25)", borderRadius: 8, marginBottom: 16, fontSize: 13, color: "#ffab00", display: "flex", alignItems: "center", gap: 8 } },
        "请自行登录招聘平台后再使用打招呼功能",
        React.createElement("button", {
          onClick: () => window.open("https://we.51job.com/", "_blank"),
          style: { border: "1px solid var(--accent2)", color: "var(--accent2)", background: "transparent", fontSize: 11, padding: "3px 12px", borderRadius: 6, cursor: "pointer", marginLeft: "auto", flexShrink: 0 }
        }, "打开51前程无忧")
      ),

      // Main card
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "自动打招呼 & 投递"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16 } }, "半自动模式：登录后逐条打开详情页，人工确认发送"),

        // Controls row
        React.createElement("div", { style: { display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap", alignItems: "center" } },
          React.createElement("select", { value: dJobsFile, onChange: e => setDJobsFile(e.target.value), style: { ...selectStyle, maxWidth: 200 } },
            React.createElement("option", { value: "" }, "选择采集记录..."),
            dFilesForStep7.map((f, i) => React.createElement("option", { key: f.filename, value: f.filename }, "第" + (dFilesForStep7.length - i) + "次采集 (" + (f.count || 0) + "岗) - " + ((f.keywords && f.keywords[0]) ? f.keywords[0] : "未知")))
          ),
          React.createElement("select", { value: dResume, onChange: e => setDResume(e.target.value), style: { ...selectStyle, maxWidth: 180 } },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, x.name + (x.position ? " - " + x.position : "")))
          ),
          React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, "阈值:"),
          React.createElement("input", { type: "number", value: dTh, onChange: e => setDTh(parseInt(e.target.value) || 70), min: 0, max: 100, style: { background: "#111", border: "1px solid var(--border)", color: "#fff", padding: "6px 10px", borderRadius: 6, width: 70, fontSize: 13, outline: "none" } }),
          React.createElement("button", { onClick: loadDeliverCandidates, disabled: dLoading, style: { ...btnGlow, fontSize: 13, padding: "8px 20px" } }, "筛选")
        ),

        statusMsg ? React.createElement("p", { style: { ...statusStyle, color: statusMsg.includes("失败") || statusMsg.includes("错误") ? "#ff4081" : statusMsg.includes("生成") || statusMsg.includes("复制") ? "var(--accent)" : "var(--text-dim)" } }, statusMsg) : null,

        // AI Greeting generator
        React.createElement("div", { style: { marginTop: 16, padding: "16px 0", borderTop: "1px solid var(--border)" } },
          React.createElement("h4", { style: { fontSize: 14, fontWeight: 600, marginBottom: 8 } }, "AI生成打招呼开场白"),
          React.createElement("div", { style: { marginBottom: 8 } },
            React.createElement("input", { value: dDirection, onChange: e => setDDirection(e.target.value), placeholder: "投递方向（如：前端开发，广州地区）", style: { ...inputStyle, maxWidth: "100%", width: "100%" } })
          ),
          React.createElement("div", { style: { display: "flex", gap: 8 } },
            React.createElement("button", { onClick: generateGreeting, disabled: dLoading, style: { ...btnGlow, fontSize: 13 } }, "生成开场白"),
            React.createElement("button", { onClick: copyGreeting, style: { ...btnOutline2, fontSize: 13 } }, "复制文案")
          ),
          dGreeting ? React.createElement("textarea", { value: dGreeting, readOnly: true, rows: 4, style: { ...textareaStyle, marginTop: 12, color: dGreeting.includes("失败") || dGreeting.includes("错误") ? "#ff4081" : "#fff" } }) : null
        ),

        // Candidates list
        dCandidates.length > 0 ? React.createElement("div", { style: { marginTop: 16, padding: "16px 0", borderTop: "1px solid var(--border)" } },
          dSummary ? React.createElement("p", { style: { color: "var(--text-dim)", fontSize: 12, marginBottom: 12 } }, "共 " + dSummary.total_jobs + " 个岗位, 符合阈值 " + dSummary.candidates + " 个 (已投递 " + (dSummary.already_delivered || 0) + " 个排除)") : null,
          React.createElement("div", { style: { maxHeight: "45vh", overflowY: "auto" } },
            dCandidates.map((j, i) => {
              const sc = j.match_score || 0;
              const scColor = sc >= 75 ? "#0f0" : sc >= 50 ? "#ffab00" : "#ff4081";
              return React.createElement("div", { key: i, style: { display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", marginBottom: 6, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 10 } },
                React.createElement("div", { style: { minWidth: 42, height: 42, borderRadius: "50%", background: "radial-gradient(circle," + scColor + "33,transparent 70%)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700, color: scColor } }, sc),
                React.createElement("div", { style: { flex: 1, minWidth: 0 } },
                  React.createElement("div", { style: { fontSize: 14, fontWeight: 600, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, j.title),
                  React.createElement("div", { style: { fontSize: 11, color: "var(--text-dim)" } }, j.company + " - " + (j.salary || "") + " - " + (j.location || ""))
                ),
                j.url ? React.createElement("button", { onClick: () => window.open(j.url, "_blank"), style: { padding: "4px 12px", borderRadius: 6, background: "transparent", border: "1px solid var(--accent)", color: "var(--accent)", cursor: "pointer", fontSize: 11, whiteSpace: "nowrap" } }, "打开详情") : null
              );
            })
          )
        ) : null
      )
    );
  };

  const renderPlaceholder = (id) => (
    <div style={{ ...card, textAlign: "center", padding: "60px 40px", animation: "fadeInUp 0.4s ease" }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>{steps[id-1].icon}</div>
      <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>{steps[id-1].name}</h3>
      <p style={{ color: "var(--text-dim)" }}>即将上线，敬请期待</p>
    </div>
  );

  const renderContent = () => { switch(activeStep) { case 1: return renderStep1(); case 2: return renderStep2(); case 3: return renderStep3(); case 4: return renderStep4(); case 5: return renderStep5(); case 6: return renderStep6(); case 7: return renderStep7(); default: return renderPlaceholder(activeStep); } };

  return (
    <section id="功能" className="section" style={{ background: "var(--bg-surface)", position: "relative", overflow: "hidden" }}>
      <div id="vanta-globe" style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }} />
      <div className="container" style={{ position: "relative", zIndex: 1 }}>
        <div className="section-label">Core Features</div>
        <h2 className="section-title">AI 智能简历助手</h2>
        <p className="section-desc">七步完成从简历解析到精准投递的全流程</p>

        <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 32, marginTop: 48, alignItems: "start" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, position: "sticky", top: 100 }}>
            {steps.map((s) => {
              const isActive = s.id === activeStep;
              return (
                <div key={s.id} onClick={() => switchStep(s.id)}
                  style={{ padding: "14px 18px", borderRadius: "var(--radius)", cursor: "pointer", background: isActive ? "rgba(0,212,255,0.08)" : "transparent", border: `1px solid ${isActive ? "var(--accent)" : "var(--border)"}`, transition: "var(--transition)", display: "flex", alignItems: "center", gap: 12, position: "relative" }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.borderColor = "var(--border-light)"; }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.borderColor = "var(--border)"; }}>
                  {isActive && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: "var(--accent)", borderRadius: "0 3px 3px 0" }} />}
                  <span style={{ fontSize: 20, opacity: isActive ? 1 : 0.5 }}>{s.icon}</span>
                  <div style={{ flex: 1 }}><div style={{ fontSize: 14, fontWeight: 600, color: isActive ? "var(--text)" : "var(--text-dim)" }}>{s.name}</div><div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{s.detail}</div></div>
                  {isActive && <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />}
                </div>
              );
            })}
          </div>

          <div style={{ minHeight: 400 }}>
            <div style={{ marginBottom: 20 }}><h3 style={{ fontSize: 22, fontWeight: 700 }}>{steps[activeStep-1].name}</h3><p style={{ fontSize: 13, color: "var(--text-dim)", marginTop: 4 }}>{steps[activeStep-1].detail}</p></div>
            {renderContent()}
          </div>
        </div>
      </div>
      <style>{`@keyframes fadeInUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }`}</style>
      <div style={{ height: 100, background: "linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-deep) 100%)", position: "relative", zIndex: 2, pointerEvents: "none" }} />
    </section>
  );
};

const scoreBar = (label, score) => React.createElement("div", { style: { flex: 1, textAlign: "center" } },
  React.createElement("div", { style: { fontSize: 13, color: "var(--text-dim)", marginBottom: 4 } }, label),
  React.createElement("div", { style: { height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden" } },
    React.createElement("div", { style: { height: "100%", width: Math.min(score, 100) + "%", background: score >= 75 ? "linear-gradient(90deg, #0f0, var(--accent))" : score >= 50 ? "linear-gradient(90deg, #ffab00, var(--accent2))" : "#ff4081", borderRadius: 3, transition: "width 0.6s ease" } })
  ),
  React.createElement("div", { style: { fontSize: 11, color: "var(--text-dim)", marginTop: 2 } }, score + "/100")
);

const statusStyle = { marginTop: 12, fontSize: 13, fontFamily: "var(--font-mono)" };

const card = { background: "var(--bg-card)", borderRadius: "var(--radius-lg)", padding: "28px 32px", border: "1px solid var(--border)" };
const btnGlow = { padding: "12px 28px", borderRadius: 50, background: "var(--accent)", color: "#000", fontWeight: 600, fontSize: 14, border: "none", cursor: "pointer", boxShadow: "0 0 20px rgba(0,212,255,0.2)" };
const btnOutline = { padding: "8px 20px", borderRadius: 8, background: "transparent", border: "1px solid var(--accent2)", color: "var(--accent2)", cursor: "pointer", fontSize: 13, fontWeight: 500, marginBottom: 16 };
const btnOutline2 = { padding: "10px 22px", borderRadius: 50, background: "transparent", border: "1px solid var(--border-light)", color: "var(--text-dim)", fontWeight: 500, fontSize: 13, cursor: "pointer" };
const deleteBtn = { background: "none", border: "1px solid #ff4081", color: "#ff4081", padding: "5px 14px", borderRadius: 8, cursor: "pointer", fontSize: 12 };
const infoP = { padding: "4px 0", color: "var(--text-dim)", fontSize: 14 };
const sectionH4 = { color: "var(--text-dim)", borderBottom: "1px solid var(--border)", paddingBottom: 6, marginBottom: 10, fontSize: 14 };
const skillTag = { padding: "4px 14px", background: "rgba(124,77,255,0.1)", border: "1px solid rgba(124,77,255,0.3)", borderRadius: 20, fontSize: 12, color: "var(--accent2)" };
const resumeItem = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 14px", marginBottom: 6, background: "rgba(255,255,255,0.02)", borderRadius: 10, border: "1px solid var(--border)", cursor: "pointer", transition: "var(--transition)" };
const selectStyle = { background: "#111", border: "1px solid var(--border)", color: "#fff", padding: "8px 12px", borderRadius: 8, width: "100%", maxWidth: 400, fontSize: 13, outline: "none" };
const inputStyle = { background: "#111", border: "1px solid var(--border)", color: "#fff", padding: "10px 14px", borderRadius: 8, width: "100%", maxWidth: 400, fontSize: 13, outline: "none" };
const textareaStyle = { width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)", color: "#fff", padding: "10px 14px", borderRadius: 8, fontSize: 13, resize: "vertical", outline: "none", fontFamily: "var(--font-sans)" };

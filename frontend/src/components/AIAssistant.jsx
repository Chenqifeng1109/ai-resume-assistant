import React from 'react';
import {
  FileText,
  Sparkles,
  LayoutTemplate,
  Radar,
  Target,
  Crosshair,
  Mic,
  Send,
  BarChart3,
  Settings,
  Sun,
  Moon,
  FolderOpen,
  Eye,
  Download,
  Printer,
  Upload,
} from 'lucide-react';
import '../index.css';
import JobMarket from './JobMarket';

const API_BASE = window.location.origin;
const OPTIMIZATION_TASK_STORAGE_KEY = "offerforge.resumeOptimizationTaskId";
const OPTIMIZATION_STAGE_LABELS = {
  queued: "已创建任务",
  validating_input: "正在检查输入",
  reading_resume: "正在读取简历底稿",
  calling_ai: "正在调用AI引擎",
  retry_wait: "AI服务暂时异常，准备有限重试",
  parsing_response: "正在解析结构化结果",
  validating_result: "正在检查事实和字段",
  completed: "优化已完成",
  failed: "优化未完成",
};
const VERSION_MODE_LABELS = {
  original: "原始底稿",
  role_targeted: "岗位定向优化",
  jd_targeted: "JD针对性优化",
};

const VersionContentSection = ({ title, items }) => {
  if (!Array.isArray(items) || items.length === 0) return null;
  return <div style={{ marginTop: 12 }}>
    <b style={{ color: "var(--accent)", fontSize: 13 }}>{title}</b>
    {items.map((item, index) => {
      if (typeof item === "string") return <span key={`${title}-${index}`} style={{ display: "inline-block", margin: "6px 6px 0 0", padding: "3px 9px", borderRadius: 999, background: "var(--brand-soft)", color: "var(--text-dim)", fontSize: 12 }}>{item}</span>;
      if (!item || typeof item !== "object") return null;
      const itemTitle = item.name || item.school || item.organization || item.company || item.language || `第 ${index + 1} 项`;
      const metadata = [item.position, item.role, item.major, item.degree, item.duration, item.year, item.level, item.issuer, item.certificate].filter(Boolean).join(" · ");
      return <div key={`${title}-${index}`} style={{ marginTop: 7, paddingLeft: 10, borderLeft: "2px solid var(--border)", color: "var(--text-dim)", fontSize: 12, lineHeight: 1.65 }}><div><b style={{ color: "var(--text)" }}>{itemTitle}</b>{metadata ? ` · ${metadata}` : ""}</div>{item.description && <div>{item.description}</div>}</div>;
    })}
  </div>;
};

const DIFF_TYPE_LABELS = { added: "新增", deleted: "删除", modified: "修改" };
const formatDiffValue = (value) => {
  if (value === null || value === undefined) return "未提供";
  if (typeof value === "string") return value || "空字符串";
  if (Array.isArray(value) && value.length === 0) return "空列表";
  return JSON.stringify(value, null, 2);
};

const ResumeDiffPanel = ({ resumeDiff, open, onToggle }) => {
  if (!resumeDiff) return null;
  const counts = resumeDiff.counts || {};
  return <div style={{ marginTop: 20, border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", background: "var(--bg-inset)" }}>
    <button onClick={onToggle} style={{ width: "100%", display: "flex", justifyContent: "space-between", gap: 12, padding: "14px 16px", border: 0, background: "transparent", color: "var(--text)", cursor: "pointer", textAlign: "left" }}>
      <span><b>🔎 查看本次优化前后对比</b><span style={{ marginLeft: 10, color: "var(--text-dim)", fontSize: 12 }}>共 {counts.total || 0} 个字段变化</span></span>
      <span style={{ color: "var(--accent)" }}>{open ? "收起" : "展开"}</span>
    </button>
    {open && <div style={{ padding: "0 16px 16px" }}>
      {!resumeDiff.has_changes && <div style={{ color: "var(--text-dim)", fontSize: 13 }}>本次优化前后没有检测到字段变化。</div>}
      {resumeDiff.has_changes && <div style={{ marginBottom: 12, color: "var(--text-dim)", fontSize: 12 }}>新增 {counts.added || 0} 项 · 删除 {counts.deleted || 0} 项 · 修改 {counts.modified || 0} 项。这里只展示变化字段，不展示未变化内容。</div>}
      {(resumeDiff.changes || []).map((change) => <details key={change.field} style={{ marginBottom: 10, padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8 }}>
        <summary style={{ cursor: "pointer", color: "var(--text)" }}><b>{change.label}</b><span style={{ marginLeft: 8, color: change.change_type === "deleted" ? "var(--danger)" : change.change_type === "added" ? "var(--accent2)" : "var(--warning)", fontSize: 12 }}>{DIFF_TYPE_LABELS[change.change_type] || "变化"}</span></summary>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12, marginTop: 12 }}>
          <div><b style={{ color: "var(--danger)", fontSize: 12 }}>优化前</b><pre style={{ margin: "6px 0 0", padding: 10, whiteSpace: "pre-wrap", wordBreak: "break-word", background: "var(--danger-soft)", borderRadius: 6, color: "var(--text-dim)", fontFamily: "inherit" }}>{formatDiffValue(change.before)}</pre></div>
          <div><b style={{ color: "var(--accent2)", fontSize: 12 }}>优化后</b><pre style={{ margin: "6px 0 0", padding: 10, whiteSpace: "pre-wrap", wordBreak: "break-word", background: "var(--success-soft)", borderRadius: 6, color: "var(--text-dim)", fontFamily: "inherit" }}>{formatDiffValue(change.after)}</pre></div>
        </div>
        <div style={{ marginTop: 10, color: "var(--text-dim)", fontSize: 12 }}>修改说明：{change.reason}</div>
      </details>)}
    </div>}
  </div>;
};

const AIAssistant = ({ theme = "light", onThemeChange }) => {
  const steps = [
    { id: 1, group: "简历中心", tone: "blue", name: "简历解析", shortName: "解析", Icon: FileText, detail: "上传解析与底稿管理" },
    { id: 2, group: "简历中心", tone: "blue", name: "智能优化简历", shortName: "优化", Icon: Sparkles, detail: "70/30 事实护栏润色" },
    { id: 3, group: "简历中心", tone: "blue", name: "简历模板", shortName: "模板", Icon: LayoutTemplate, detail: "12套排版 + 实时预览" },
    { id: 4, group: "岗位与匹配", tone: "indigo", name: "岗位采集", shortName: "采集", Icon: Radar, detail: "多源直采与溯源库" },
    { id: 5, group: "岗位与匹配", tone: "indigo", name: "JD匹配度评分", shortName: "评分", Icon: Target, detail: "单岗与批量 AI 评估" },
    { id: 6, group: "岗位与匹配", tone: "indigo", name: "精准简历优化", shortName: "精准", Icon: Crosshair, detail: "按目标 JD 定向改写" },
    { id: 7, group: "投递执行", tone: "teal", name: "AI 模拟面试官", shortName: "面试", Icon: Mic, detail: "高频追问 + STAR 答法" },
    { id: 8, group: "投递执行", tone: "teal", name: "投递文案中心", shortName: "文案", Icon: Send, detail: "开场白/自荐信/内推/跟进" },
    { id: 9, group: "投递执行", tone: "teal", name: "求职投递看板", shortName: "看板", Icon: BarChart3, detail: "漏斗统计与表格导出" }
  ];
  const navGroups = [
    { name: "简历中心", dot: "var(--brand)" },
    { name: "岗位与匹配", dot: "var(--accent2)" },
    { name: "投递执行", dot: "var(--teal)" },
  ];

  const [activeStep, setActiveStep] = React.useState(1);
  const [resumes, setResumes] = React.useState([]);
  // Step 1
  const [resumeDetail, setResumeDetail] = React.useState(null);
  const [resumeDetailFile, setResumeDetailFile] = React.useState("");
  const [editingResume, setEditingResume] = React.useState(false);
  const [editDraft, setEditDraft] = React.useState(null);
  const [savingResumeEdit, setSavingResumeEdit] = React.useState(false);
  const [editResumeNotice, setEditResumeNotice] = React.useState("");
  const [openEvidence, setOpenEvidence] = React.useState({});
  const [uploading, setUploading] = React.useState(false);
  const [statusMsg, setStatusMsg] = React.useState("");
  // Step 2
  const [optResume, setOptResume] = React.useState("");
  const [optTarget, setOptTarget] = React.useState("");
  const [optJD, setOptJD] = React.useState("");
  const [optStyle, setOptStyle] = React.useState("balanced");
  const [optExtra, setOptExtra] = React.useState("");
  const [optResult, setOptResult] = React.useState(null);
  const [optLoading, setOptLoading] = React.useState(false);
  const [optTask, setOptTask] = React.useState(null);
  const [resumeDiffOpen, setResumeDiffOpen] = React.useState(false);
  const [expandedGapIndexes, setExpandedGapIndexes] = React.useState([]);
  const [gapConfirmationText, setGapConfirmationText] = React.useState({});
  const [resumeVersions, setResumeVersions] = React.useState([]);
  const [versionsOpen, setVersionsOpen] = React.useState(false);
  const [versionsLoading, setVersionsLoading] = React.useState(false);
  const [versionPreviewLoading, setVersionPreviewLoading] = React.useState(false);
  const [versionLoadError, setVersionLoadError] = React.useState("");
  const [versionPreview, setVersionPreview] = React.useState(null);
  const versionRequestSerial = React.useRef(0);
  const versionDetailRequestSerial = React.useRef(0);
  const selectedResumeRef = React.useRef("");
  // Step 3
  const [tResume, setTResume] = React.useState("");
  const [tStyle, setTStyle] = React.useState("classic");
  const [tPhotoStatus, setTPhotoStatus] = React.useState("");
  const [tPreview, setTPreview] = React.useState("");

  const templates = [
    { id: "classic", icon: "📄", name: "经典商务", desc: "稳重通用" },
    { id: "modern", icon: "🎨", name: "现代渐变", desc: "蓝紫活力" },
    { id: "dual", icon: "📊", name: "双栏技能", desc: "左栏侧写" },
    { id: "magazine", icon: "📰", name: "杂志编辑", desc: "创意排版" },
    { id: "minimal", icon: "🤍", name: "极简留白", desc: "干净清爽" },
    { id: "timeline", icon: "🕒", name: "时间轴叙事", desc: "成长脉络" },
    { id: "elegant", icon: "📜", name: "暖金优雅", desc: "卡纸质感" },
    { id: "tech", icon: "💻", name: "科技蓝调", desc: "深蓝极客" },
    { id: "finance", icon: "🏛️", name: "投行金融", desc: "紧凑衬线" },
    { id: "mint", icon: "🌿", name: "清新薄荷", desc: "校招友好" },
    { id: "gov", icon: "🏢", name: "国企沉稳", desc: "红蓝庄重" },
    { id: "obsidian", icon: "🖤", name: "暗夜黑金", desc: "高管质感" },
  ];

  React.useEffect(() => {
    loadResumes();
    const savedTaskId = window.localStorage.getItem(OPTIMIZATION_TASK_STORAGE_KEY);
    if (savedTaskId) refreshOptimizationTask(savedTaskId);
  }, []);

  React.useEffect(() => {
    if (!optTask?.task_id || !["queued", "running"].includes(optTask.status)) return undefined;
    const timer = window.setInterval(() => refreshOptimizationTask(optTask.task_id), 900);
    return () => window.clearInterval(timer);
  }, [optTask?.task_id, optTask?.status]);

  const loadResumes = async () => {
    try { const r = await fetch(`${API_BASE}/api/resumes/list`); const d = await r.json(); setResumes(d.resumes || []); } catch {}
  };

  const syncAfterResumeOverwrite = async (filename) => {
    await loadResumes();
    if (!filename) return;
    try {
      const detailResp = await fetch(`${API_BASE}/api/resumes/detail/${encodeURIComponent(filename)}`);
      const detailData = await detailResp.json();
      if (detailData.ok && detailData.data) {
        setResumeDetail((prev) => (prev ? detailData.data : prev));
      }
    } catch {}
    if (optResume === filename) {
      await loadResumeVersions(filename);
    }
    if (tResume === filename) {
      setTPreview("");
    }
  };

  // ── Step 1 ──
  const handleUpload = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    setUploading(true); setStatusMsg(`⏳ 解析中: ${file.name}`);
    const fd = new FormData(); fd.append("file", file);
    try { const r = await fetch(`${API_BASE}/api/resumes/upload`, { method: "POST", body: fd }); const d = await r.json(); const warningCount = d.data?.quality_warnings?.length || 0; setStatusMsg(d.ok ? (warningCount ? `⚠️ 解析完成，有 ${warningCount} 项内容需要检查` : "✅ 解析成功") : `❌ ${d.error || "失败"}`); if (d.ok) loadResumes(); } catch(e) { setStatusMsg(`❌ ${e.message}`); }
    setUploading(false);
  };
  const viewResume = async (fn) => {
    try {
      const r = await fetch(`${API_BASE}/api/resumes/detail/${encodeURIComponent(fn)}`);
      const d = await r.json();
      if (d.ok) {
        setResumeDetail(d.data);
        setResumeDetailFile(fn);
        setEditingResume(false);
        setEditDraft(null);
        setEditResumeNotice("");
        setOpenEvidence({});
      }
    } catch {}
  };

  const startEditResume = () => {
    if (!resumeDetail) return;
    setEditDraft({
      name: resumeDetail.name || "",
      desired_position: resumeDetail.desired_position || "",
      desired_salary: resumeDetail.desired_salary || "",
      phone: resumeDetail.phone || "",
      email: resumeDetail.email || "",
      summary: resumeDetail.summary || "",
      skillsText: Array.isArray(resumeDetail.skills) ? resumeDetail.skills.join("，") : "",
      education: Array.isArray(resumeDetail.education)
        ? resumeDetail.education.map((e) => ({ school: e.school || "", major: e.major || "", degree: e.degree || "", year: e.year || "" }))
        : [],
      work_experience: Array.isArray(resumeDetail.work_experience)
        ? resumeDetail.work_experience.map((w) => ({ company: w.company || "", position: w.position || "", duration: w.duration || "", description: w.description || "" }))
        : [],
      project_experience: Array.isArray(resumeDetail.project_experience)
        ? resumeDetail.project_experience.map((p) => ({ name: p.name || "", role: p.role || "", duration: p.duration || "", description: p.description || "" }))
        : [],
      practical_experience: Array.isArray(resumeDetail.practical_experience)
        ? resumeDetail.practical_experience.map((p) => ({ organization: p.organization || "", role: p.role || "", duration: p.duration || "", description: p.description || "" }))
        : [],
      campus_experience: Array.isArray(resumeDetail.campus_experience)
        ? resumeDetail.campus_experience.map((p) => ({ organization: p.organization || "", role: p.role || "", duration: p.duration || "", description: p.description || "" }))
        : [],
      research_experience: Array.isArray(resumeDetail.research_experience)
        ? resumeDetail.research_experience.map((p) => ({ name: p.name || "", role: p.role || "", duration: p.duration || "", description: p.description || "" }))
        : [],
    });
    setEditResumeNotice("");
    setEditingResume(true);
  };

  const cancelEditResume = () => {
    setEditingResume(false);
    setEditDraft(null);
    setEditResumeNotice("");
  };

  const updateEditDraftListItem = (sectionKey, index, field, value) => {
    setEditDraft((prev) => {
      if (!prev) return prev;
      const list = Array.isArray(prev[sectionKey]) ? [...prev[sectionKey]] : [];
      list[index] = { ...(list[index] || {}), [field]: value };
      return { ...prev, [sectionKey]: list };
    });
  };

  const addEditDraftListItem = (sectionKey, template) => {
    setEditDraft((prev) => {
      if (!prev) return prev;
      const list = Array.isArray(prev[sectionKey]) ? [...prev[sectionKey]] : [];
      list.push({ ...template });
      return { ...prev, [sectionKey]: list };
    });
  };

  const removeEditDraftListItem = (sectionKey, index) => {
    setEditDraft((prev) => {
      if (!prev) return prev;
      const list = Array.isArray(prev[sectionKey]) ? [...prev[sectionKey]] : [];
      list.splice(index, 1);
      return { ...prev, [sectionKey]: list };
    });
  };

  const saveResumeEdits = async () => {
    if (!editDraft || !resumeDetailFile) return;
    if (!String(editDraft.name || "").trim()) {
      setEditResumeNotice("❌ 姓名不能为空");
      return;
    }
    setSavingResumeEdit(true);
    setEditResumeNotice("⏳ 正在保存到数据库并写入版本历史...");
    try {
      const skills = String(editDraft.skillsText || "")
        .split(/[,，、;\n\r]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const payload = {
        name: editDraft.name.trim(),
        desired_position: editDraft.desired_position,
        desired_salary: editDraft.desired_salary,
        phone: editDraft.phone,
        email: editDraft.email,
        summary: editDraft.summary,
        skills,
        education: editDraft.education,
        work_experience: editDraft.work_experience,
        project_experience: editDraft.project_experience,
        practical_experience: editDraft.practical_experience,
        campus_experience: editDraft.campus_experience,
        research_experience: editDraft.research_experience,
      };
      const resp = await fetch(`${API_BASE}/api/resumes/${encodeURIComponent(resumeDetailFile)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        setEditResumeNotice(`❌ ${data.error || "保存失败"}`);
      } else {
        setResumeDetail(data.data);
        setEditingResume(false);
        setEditDraft(null);
        await syncAfterResumeOverwrite(resumeDetailFile);
        const count = Array.isArray(data.changed_fields) ? data.changed_fields.length : 0;
        setEditResumeNotice(
          count > 0
            ? `✅ 已保存 ${count} 项修改并同步数据库（原始底稿已保留在版本历史中）`
            : "✅ 已保存（内容与修改前一致）"
        );
      }
    } catch (e) {
      setEditResumeNotice(`❌ 保存出错: ${e.message}`);
    } finally {
      setSavingResumeEdit(false);
    }
  };
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

  const loadResumeVersions = async (filename) => {
    const requestSerial = ++versionRequestSerial.current;
    if (!filename) { setResumeVersions([]); setVersionLoadError(""); return; }
    setVersionsLoading(true);
    setVersionLoadError("");
    try {
      const response = await fetch(`${API_BASE}/api/resumes/versions/${encodeURIComponent(filename)}`);
      const data = await response.json();
      if (requestSerial !== versionRequestSerial.current) return;
      if (!response.ok || !data.ok) throw new Error(data.error || "版本读取失败");
      setResumeVersions(data.versions || []);
    } catch (error) {
      if (requestSerial !== versionRequestSerial.current) return;
      setResumeVersions([]);
      setVersionLoadError(error.message || "版本读取失败");
    } finally {
      if (requestSerial === versionRequestSerial.current) setVersionsLoading(false);
    }
  };

  const viewResumeVersion = async (versionId) => {
    if (!optResume) return;
    const filename = optResume;
    const requestSerial = ++versionDetailRequestSerial.current;
    setVersionPreviewLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/resumes/versions/${encodeURIComponent(filename)}/${encodeURIComponent(versionId)}`);
      const data = await response.json();
      if (requestSerial !== versionDetailRequestSerial.current || selectedResumeRef.current !== filename) return;
      if (!response.ok || !data.ok) throw new Error(data.error || "版本读取失败");
      setVersionPreview(data.version);
    } catch (error) {
      if (requestSerial !== versionDetailRequestSerial.current || selectedResumeRef.current !== filename) return;
      setStatusMsg(`❌ ${error.message}`);
    } finally {
      if (requestSerial === versionDetailRequestSerial.current) setVersionPreviewLoading(false);
    }
  };

  const deleteResumeVersion = async (versionId) => {
    if (!optResume || !window.confirm("确定删除这条非当前优化版本记录吗？")) return;
    const filename = optResume;
    try {
      const response = await fetch(`${API_BASE}/api/resumes/versions/${encodeURIComponent(filename)}/${encodeURIComponent(versionId)}`, { method: "DELETE" });
      const data = await response.json();
      if (selectedResumeRef.current !== filename) return;
      if (!response.ok || !data.ok) throw new Error(data.error || "版本删除失败");
      if (versionPreview?.version_id === versionId) setVersionPreview(null);
      await loadResumeVersions(filename);
      setStatusMsg("✅ 历史优化版本已删除");
    } catch (error) {
      if (selectedResumeRef.current !== filename) return;
      setStatusMsg(`❌ ${error.message}`);
    }
  };

  const activateResumeVersion = async (version) => {
    if (!optResume || version.is_current) return;
    const versionLabel = version.version_type === "original" ? "原始版本" : "AI优化版本";
    const confirmed = window.confirm(`确认使用此${versionLabel}作为当前简历吗？\n\n切换后，简历预览、导出和后续匹配将使用此版本。\n当前版本不会删除，之后仍可切回。`);
    if (!confirmed) return;
    const filename = optResume;
    try {
      const response = await fetch(`${API_BASE}/api/resumes/versions/${encodeURIComponent(filename)}/${encodeURIComponent(version.version_id)}/activate`, { method: "POST" });
      const data = await response.json();
      if (selectedResumeRef.current !== filename) return;
      if (!response.ok || !data.ok) throw new Error(data.error || "版本切换失败");
      setVersionPreview(null);
      setOptResult(null);
      await loadResumes();
      await loadResumeVersions(filename);
      setVersionsOpen(true);
      setStatusMsg("✅ 已切换当前简历版本，历史版本仍保留");
    } catch (error) {
      if (selectedResumeRef.current !== filename) return;
      setStatusMsg(`❌ ${error.message || "版本切换失败"}`);
    }
  };

  React.useEffect(() => {
    selectedResumeRef.current = optResume;
    versionDetailRequestSerial.current += 1;
    setVersionPreviewLoading(false);
    setVersionPreview(null);
    setVersionsOpen(false);
    loadResumeVersions(optResume);
  }, [optResume]);

// ── Step 2 ──
  const applyOptimizationTask = (task) => {
    if (!task?.task_id) return;
    setOptTask(task);
    window.localStorage.setItem(OPTIMIZATION_TASK_STORAGE_KEY, task.task_id);
    const requestData = task.request_data || {};
    if (requestData.resume_file) {
      selectedResumeRef.current = requestData.resume_file;
      setOptResume(requestData.resume_file);
    }
    if (requestData.target) setOptTarget(requestData.target);
    if (requestData.job_description !== undefined) setOptJD(requestData.job_description);
    if (requestData.extra !== undefined) setOptExtra(requestData.extra);
    const running = ["queued", "running"].includes(task.status);
    setOptLoading(running);
    if (task.status === "completed" && task.result_data) {
      setOptResult(task.result_data);
      setStatusMsg("✅ 优化完成");
    } else if (task.status === "failed") {
      setStatusMsg(`❌ ${task.error_message || "优化未完成"}`);
    } else if (running) {
      setStatusMsg(`⏳ ${OPTIMIZATION_STAGE_LABELS[task.stage] || "AI优化中"}`);
    }
  };

  const refreshOptimizationTask = async (taskId) => {
    try {
      const response = await fetch(`${API_BASE}/api/resume/optimize/tasks/${encodeURIComponent(taskId)}`);
      const task = await response.json();
      if (response.ok && task.ok) applyOptimizationTask(task);
      else if (response.status === 404) window.localStorage.removeItem(OPTIMIZATION_TASK_STORAGE_KEY);
    } catch(e) {
      setStatusMsg(`❌ 无法查询优化任务：${e.message}`);
    }
  };

  const runOptimize = async () => {
    if (!optResume) { setStatusMsg("请选择简历"); return; }
    if (!optTarget.trim()) { setStatusMsg("请填写求职意向"); return; }
    setOptLoading(true); setOptTask(null); setOptResult(null); setResumeDiffOpen(false); setExpandedGapIndexes([]); setGapConfirmationText({}); setStatusMsg("⏳ 正在创建优化任务...");
    const intensityVal = ["mild", "balanced", "aggressive"].includes(optStyle) ? optStyle : "balanced";
    const fd = new FormData();
    fd.append("resume_file", optResume);
    fd.append("target", optTarget.trim());
    fd.append("job_description", optJD.trim());
    fd.append("extra", optExtra.trim());
    fd.append("intensity", intensityVal);
    try {
      const response = await fetch(`${API_BASE}/api/resume/optimize/tasks`, { method: "POST", body: fd });
      const task = await response.json();
      if (!response.ok || !task.ok) throw new Error(task.error || "任务创建失败");
      applyOptimizationTask(task);
    } catch(e) {
      setOptLoading(false);
      setStatusMsg(`❌ ${e.message}`);
    }
  };
  const retryOptimizationTask = async () => {
    if (!optTask?.task_id) return;
    setOptLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/resume/optimize/tasks/${encodeURIComponent(optTask.task_id)}/retry`, { method: "POST" });
      const task = await response.json();
      if (!response.ok || !task.ok) throw new Error(task.error || "重试失败");
      applyOptimizationTask(task);
    } catch(e) {
      setOptLoading(false);
      setStatusMsg(`❌ ${e.message}`);
    }
  };
  const updateGapDecision = (gapIndex, decision) => {
    const currentGap = optResult?.capability_analysis?.gaps?.[gapIndex];
    if (!currentGap) return;
    const suggestionId = currentGap.suggestion_id || `gap-${gapIndex}`;
    const confirmedContent = (gapConfirmationText[suggestionId] || currentGap.confirmed_content || "").trim();
    if (decision === "accepted" && !confirmedContent) {
      setStatusMsg("❌ 接受建议前，请先填写你真实做过的经历");
      return;
    }

    setOptResult((currentResult) => {
      const updatedGaps = currentResult.capability_analysis.gaps.map((gap, index) => index === gapIndex ? {
        ...gap,
        decision,
        confirmed_content: decision === "accepted" ? confirmedContent : "",
        decided_at: decision === "pending" ? "" : new Date().toISOString(),
      } : gap);
      const updatedAnalysis = { ...currentResult.capability_analysis, gaps: updatedGaps };
      const updatedResume = {
        ...currentResult.optimized_resume,
        _optimization_meta: {
          ...(currentResult.optimized_resume?._optimization_meta || {}),
          capability_analysis: updatedAnalysis,
        },
      };
      return { ...currentResult, capability_analysis: updatedAnalysis, optimized_resume: updatedResume };
    });
    setStatusMsg(decision === "accepted" ? "✅ 已确认真实内容；保存优化版本后将记录该决定" : decision === "rejected" ? "✅ 已标记为不采用；保存优化版本后将记录该决定" : "已恢复为待确认");
  };
  const exportResume = async () => {
    if (!optResult?.resume_file || !optResult?.optimized_resume) { setStatusMsg("没有可导出的优化结果"); return; }
    const previewWindow = window.open("", "_blank");
    const fd = new FormData(); fd.append("resume_file", optResult.resume_file); fd.append("optimized_resume", JSON.stringify(optResult.optimized_resume));
    try {
      const r = await fetch(`${API_BASE}/api/resume/export-optimized`, { method: "POST", body: fd });
      if (!r.ok) { const d = await r.json(); throw new Error(d.error || "导出失败"); }
      const html = await r.text();
      const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
      if (previewWindow) previewWindow.location.href = url;
      else window.open(url, "_blank");
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch(e) {
      if (previewWindow) previewWindow.close();
      setStatusMsg(`❌ ${e.message}`);
    }
  };
  const overwriteResume = async () => {
    if (!optResult?.resume_file) { alert('没有可覆盖的结果'); return; }
    const invalidAcceptedGap = optResult.capability_analysis?.gaps?.find((gap) => gap.decision === 'accepted' && !gap.confirmed_content?.trim());
    if (invalidAcceptedGap) { alert(`“${invalidAcceptedGap.capability}”已选择接受，但还没有填写真实经历`); return; }
    if (!confirm('确定保存这个优化版本并设为当前简历吗？原始底稿会继续保留。')) return;
    const fd = new FormData(); fd.append('resume_file', optResult.resume_file); fd.append('optimized_summary', optResult.optimized_summary || ''); fd.append('optimized_projects', JSON.stringify(optResult.optimized_projects || [])); fd.append('optimized_internships', JSON.stringify(optResult.optimized_internships || [])); fd.append('enhanced_skills', JSON.stringify(optResult.enhanced_skills || [])); fd.append('target', optResult.target || ''); fd.append('optimized_resume', JSON.stringify(optResult.optimized_resume || {}));
    try {
      const r = await fetch(`${API_BASE}/api/resume/overwrite`, { method: 'POST', body: fd });
      const d = await r.json();
      if (d.ok) {
        alert('优化版本和建议决定已保存，原始底稿仍保留');
        setStatusMsg('✅ 优化版本和建议决定已保存');
        await syncAfterResumeOverwrite(optResult.resume_file);
        await loadResumeVersions(optResult.resume_file);
        setVersionsOpen(true);
      } else alert('失败: ' + d.error);
    } catch(e) { alert('错误: ' + e.message); }
  };

  // ── Step 3 ──
  const uploadPhoto = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    setTPhotoStatus("⏳ 上传中...");
    const fd = new FormData(); fd.append("resume_file", tResume || ""); fd.append("photo", file);
    try { const r = await fetch(API_BASE + "/api/resume/photo", { method: "POST", body: fd }); const d = await r.json(); if (d.ok) { setTPhotoStatus("✅ 已上传（可用于任意简历）"); } else { setTPhotoStatus("❌ " + (d.error || "失败")); } } catch { setTPhotoStatus("❌ 失败"); }
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
      const iframe = document.createElement("iframe");
      iframe.style.position = "fixed";
      iframe.style.right = "0";
      iframe.style.bottom = "0";
      iframe.style.width = "0";
      iframe.style.height = "0";
      iframe.style.border = "0";
      document.body.appendChild(iframe);
      iframe.onload = () => {
        try {
          iframe.contentWindow?.focus();
          iframe.contentWindow?.print();
        } finally {
          window.setTimeout(() => { try { document.body.removeChild(iframe); } catch {} }, 1500);
        }
      };
      iframe.srcdoc = html;
    } else {
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `resume_${new Date().toISOString().slice(0,10)}.html`; a.click(); URL.revokeObjectURL(a.href);
    }
  };

  const formatResumeLabel = (x) => {
    const cleanPos = String(x?.position || "").split(/[@＠]/)[0].trim();
    return cleanPos ? `${x.name} - ${cleanPos}` : x.name;
  };

  const switchStep = (id) => { setActiveStep(id); setResumeDetail(null); setStatusMsg(""); setTPreview(""); setTPhotoStatus(""); };

  // ── Render Step 3 (Split-Screen Live Template Studio) ──
  const renderStep3 = () => (
    <div className="of-split-studio" style={{ animation: "fadeInUp 0.25s ease" }}>
      <div style={{ ...card, padding: "22px 24px" }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>模板与导出配置</div>
        <p style={{ color: "var(--text-dim)", fontSize: 12.5, marginBottom: 16 }}>选择简历与排版风格，右侧实时渲染 A4 高清预览</p>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 6 }}>目标简历</div>
          <select value={tResume} onChange={e => { setTResume(e.target.value); setTPhotoStatus(""); }} style={{ ...selectStyle, maxWidth: "100%" }}>
            <option value="">选择简历...</option>
            {resumes.map(x => <option key={x.filename} value={x.filename}>{formatResumeLabel(x)}</option>)}
          </select>
        </div>

        <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 8 }}>排版风格（{templates.length} 套）</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, marginBottom: 16 }}>
          {templates.map(t => (
            <div key={t.id} onClick={() => setTStyle(t.id)}
              style={{
                padding: "12px 12px", borderRadius: "var(--radius)", cursor: "pointer",
                background: tStyle === t.id ? "var(--brand-soft)" : "var(--bg-inset)",
                border: `1.5px solid ${tStyle === t.id ? "var(--brand)" : "var(--border)"}`,
                transition: "var(--transition)"
              }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 2 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{t.name}</span>
                <span style={{ fontSize: 15 }}>{t.icon}</span>
              </div>
              <div style={{ fontSize: 11.5, color: "var(--text-dim)" }}>{t.desc}</div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 18, flexWrap: "wrap" }}>
          <label style={{ padding: "7px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-light)", background: "var(--bg-inset)", color: "var(--text-secondary)", cursor: "pointer", fontSize: 12.5, fontWeight: 500, display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Upload size={14} /> 上传证件照
            <input type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" onChange={uploadPhoto} style={{ display: "none" }} />
          </label>
          {tPhotoStatus && <span style={{ fontSize: 12, color: tPhotoStatus.includes("✅") ? "var(--success)" : "var(--text-dim)" }}>{tPhotoStatus}</span>}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button onClick={previewTemplate} style={{ ...btnGlow, flex: "1 1 120px", justifyContent: "center" }}><Eye size={14} /> 预览模板</button>
          <button onClick={exportDirectPdf} disabled={tPdfExporting} style={{ ...btnGlow, background: "linear-gradient(135deg, #0ea5e9, #4f46e5)", opacity: tPdfExporting ? 0.6 : 1 }}>
            <Download size={14} /> {tPdfExporting ? "正在生成 PDF..." : "一键直出高清 PDF"}
          </button>
          <button onClick={() => downloadTemplate("html")} style={{ ...btnOutline2 }}><Download size={14} /> HTML</button>
          <button onClick={() => downloadTemplate("pdf")} style={{ ...btnOutline2 }}><Printer size={14} /> 打印</button>
        </div>
        {tPdfMsg && (
          <div style={{ marginTop: 10, padding: "8px 12px", borderRadius: 8, fontSize: 12.5, background: tPdfMsg.includes("❌") ? "var(--danger-soft)" : "var(--brand-soft)", color: tPdfMsg.includes("❌") ? "var(--danger)" : "var(--brand)", border: `1px solid ${tPdfMsg.includes("❌") ? "var(--danger-border)" : "var(--brand-border)"}` }}>
            {tPdfMsg}
          </div>
        )}
      </div>

      <div style={{ ...card, padding: "18px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, paddingBottom: 10, borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>实时排版画布</span>
          <span style={{ fontSize: 11.5, fontFamily: "var(--font-mono)", color: "var(--text-dim)" }}>A4 · {templates.find(item => item.id === tStyle)?.name || tStyle}</span>
        </div>
        {tPreview ? (
          tPreview.startsWith("<") ? (
            <iframe srcDoc={tPreview} style={{ width: "100%", height: 640, border: "1px solid var(--border)", background: "#ffffff", borderRadius: 8 }} />
          ) : (
            <p style={{ color: "var(--text-dim)", padding: 36, textAlign: "center", fontSize: 13.5 }}>{tPreview}</p>
          )
        ) : (
          <div style={{ minHeight: 540, borderRadius: 10, border: "1px dashed var(--border-light)", background: "var(--bg-inset)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10, padding: 32, textAlign: "center" }}>
            <LayoutTemplate size={34} style={{ color: "var(--text-muted)" }} />
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-secondary)" }}>选择简历后点击「预览模板」</div>
            <div style={{ fontSize: 12.5, color: "var(--text-dim)", maxWidth: 320 }}>空板块会自动隐藏且不产生“暂无”占位词，支持一键导出高清 PDF 或独立 HTML 文件</div>
          </div>
        )}
      </div>
    </div>
  );

  // ── Step 1 Render ──
  const renderEvidence = (field) => {
    const entries = resumeDetail?.field_evidence?.[field];
    if (!Array.isArray(entries) || entries.length === 0) return null;
    const isOpen = Boolean(openEvidence[field]);

    return (
      <div style={{ marginTop: 6 }}>
        <button type="button" onClick={() => setOpenEvidence(prev => ({ ...prev, [field]: !prev[field] }))} style={{ border: "none", background: "transparent", color: "var(--accent)", padding: 0, cursor: "pointer", fontSize: 12 }}>
          {isOpen ? "收起依据" : "查看依据"}
        </button>
        {isOpen && <div style={{ marginTop: 6, padding: "8px 10px", background: "var(--brand-soft)", border: "1px solid var(--brand-border)", borderRadius: 8 }}>
          {entries.map((entry, index) => <div key={`${entry.value}-${entry.line_number}-${index}`} style={{ color: "var(--text-dim)", fontSize: 12, lineHeight: 1.6, marginBottom: index === entries.length - 1 ? 0 : 6 }}>
            <span style={{ color: "var(--accent)" }}>第 {entry.line_number} 行</span>
            {entry.value && <span> · {entry.value}</span>}
            <div style={{ whiteSpace: "pre-wrap" }}>原文：{entry.source_text}</div>
          </div>)}
        </div>}
      </div>
    );
  };

  const renderStep1 = () => {
    if (resumeDetail) {
      const x = resumeDetail;
      const renderEditListSection = (title, sectionKey, fields, emptyTemplate) => {
        const items = Array.isArray(editDraft?.[sectionKey]) ? editDraft[sectionKey] : [];
        return (
          <div style={{ marginBottom: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, gap: 8, flexWrap: "wrap" }}>
              <h4 style={{ ...sectionH4, marginBottom: 0 }}>{title}</h4>
              <button
                type="button"
                onClick={() => addEditDraftListItem(sectionKey, emptyTemplate)}
                style={{ ...btnOutline2, padding: "4px 10px", fontSize: 12 }}
              >
                + 新增一条
              </button>
            </div>
            {items.length === 0 && (
              <div style={{ fontSize: 12, color: "var(--text-muted)", padding: "8px 10px", borderRadius: 8, background: "var(--bg-inset)" }}>
                暂无条目，可点击右上角「+ 新增一条」补充
              </div>
            )}
            {items.map((item, idx) => (
              <div key={`${sectionKey}-${idx}`} style={{ padding: 12, borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border)", marginBottom: 10 }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8, marginBottom: fields.some((f) => f.multiline) ? 8 : 0 }}>
                  {fields.filter((f) => !f.multiline).map((f) => (
                    <div key={f.key}>
                      <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 4 }}>{f.label}</div>
                      <input
                        value={item[f.key] || ""}
                        onChange={(e) => updateEditDraftListItem(sectionKey, idx, f.key, e.target.value)}
                        placeholder={f.placeholder || f.label}
                        style={{ ...inputStyle, padding: "8px 10px", fontSize: 13 }}
                      />
                    </div>
                  ))}
                </div>
                {fields.filter((f) => f.multiline).map((f) => (
                  <div key={f.key}>
                    <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 4 }}>{f.label}</div>
                    <textarea
                      rows={3}
                      value={item[f.key] || ""}
                      onChange={(e) => updateEditDraftListItem(sectionKey, idx, f.key, e.target.value)}
                      placeholder={f.placeholder || f.label}
                      style={{ ...textareaStyle, padding: "8px 10px", fontSize: 13 }}
                    />
                  </div>
                ))}
                <div style={{ marginTop: 8, textAlign: "right" }}>
                  <button
                    type="button"
                    onClick={() => removeEditDraftListItem(sectionKey, idx)}
                    style={{ ...deleteBtn, padding: "4px 10px", fontSize: 11.5 }}
                  >
                    删除此条
                  </button>
                </div>
              </div>
            ))}
          </div>
        );
      };

      return (
        <div style={{ animation: "fadeInUp 0.4s ease" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <button onClick={() => { setResumeDetail(null); setResumeDetailFile(""); setEditingResume(false); setEditDraft(null); setEditResumeNotice(""); setOpenEvidence({}); }} style={btnOutline}>⬅ 返回列表</button>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              {!editingResume && resumeDetailFile && (
                <button type="button" onClick={startEditResume} style={{ ...btnGlow, padding: "8px 16px", fontSize: 13 }}>
                  ✏️ 在线微调简历
                </button>
              )}
              {editingResume && (
                <>
                  <button type="button" onClick={saveResumeEdits} disabled={savingResumeEdit} style={{ ...btnGlow, padding: "8px 16px", fontSize: 13, opacity: savingResumeEdit ? 0.6 : 1 }}>
                    {savingResumeEdit ? "⏳ 保存中..." : "💾 保存修改"}
                  </button>
                  <button type="button" onClick={cancelEditResume} disabled={savingResumeEdit} style={{ ...btnOutline, padding: "8px 14px", fontSize: 13 }}>
                    取消
                  </button>
                </>
              )}
            </div>
          </div>
          {editResumeNotice && (
            <div style={{ marginTop: 10, padding: "9px 12px", borderRadius: 8, fontSize: 13, background: editResumeNotice.includes("❌") ? "var(--danger-soft)" : "var(--brand-soft)", color: editResumeNotice.includes("❌") ? "var(--danger)" : "var(--brand)", border: `1px solid ${editResumeNotice.includes("❌") ? "var(--danger-border)" : "var(--brand-border)"}` }}>
              {editResumeNotice}
            </div>
          )}
          <div style={{ ...card, maxHeight: editingResume ? "72vh" : "60vh", overflowY: "auto", marginTop: 16 }}>
            {editingResume && editDraft ? (
              <div>
                <div style={{ marginBottom: 14, fontSize: 12.5, color: "var(--text-dim)" }}>
                  直接修改下方字段，保存后将同步更新 SQLite、模板工坊与版本历史（原始解析底稿会自动保留）。
                </div>
                <h4 style={sectionH4}>📋 基本信息与求职意向</h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10, marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 4 }}>姓名（必填）</div>
                    <input value={editDraft.name} onChange={(e) => setEditDraft((p) => ({ ...p, name: e.target.value }))} style={{ ...inputStyle, padding: "8px 10px", fontSize: 13 }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 4 }}>求职意向</div>
                    <input value={editDraft.desired_position} onChange={(e) => setEditDraft((p) => ({ ...p, desired_position: e.target.value }))} placeholder="如：Python后端工程师" style={{ ...inputStyle, padding: "8px 10px", fontSize: 13 }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 4 }}>期望薪资</div>
                    <input value={editDraft.desired_salary} onChange={(e) => setEditDraft((p) => ({ ...p, desired_salary: e.target.value }))} placeholder="如：12k-18k" style={{ ...inputStyle, padding: "8px 10px", fontSize: 13 }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 4 }}>电话</div>
                    <input value={editDraft.phone} onChange={(e) => setEditDraft((p) => ({ ...p, phone: e.target.value }))} style={{ ...inputStyle, padding: "8px 10px", fontSize: 13 }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 4 }}>邮箱</div>
                    <input value={editDraft.email} onChange={(e) => setEditDraft((p) => ({ ...p, email: e.target.value }))} style={{ ...inputStyle, padding: "8px 10px", fontSize: 13 }} />
                  </div>
                </div>
                <div style={{ marginBottom: 16 }}>
                  <h4 style={sectionH4}>🛠 技能标签（用逗号、顿号或换行分隔）</h4>
                  <textarea
                    rows={2}
                    value={editDraft.skillsText}
                    onChange={(e) => setEditDraft((p) => ({ ...p, skillsText: e.target.value }))}
                    placeholder="如：Python，FastAPI，SQLite，React"
                    style={{ ...textareaStyle, padding: "8px 10px", fontSize: 13 }}
                  />
                </div>
                <div style={{ marginBottom: 18 }}>
                  <h4 style={sectionH4}>📝 自我介绍 / 综合摘要</h4>
                  <textarea
                    rows={4}
                    value={editDraft.summary}
                    onChange={(e) => setEditDraft((p) => ({ ...p, summary: e.target.value }))}
                    placeholder="简要概括核心优势与代表成果"
                    style={{ ...textareaStyle, padding: "8px 10px", fontSize: 13 }}
                  />
                </div>
                {renderEditListSection("🎓 教育背景", "education", [
                  { key: "school", label: "学校" },
                  { key: "major", label: "专业" },
                  { key: "degree", label: "学历" },
                  { key: "year", label: "毕业/在校时间" },
                ], { school: "", major: "", degree: "", year: "" })}
                {renderEditListSection("💼 工作/实习经历", "work_experience", [
                  { key: "company", label: "公司/单位" },
                  { key: "position", label: "职位" },
                  { key: "duration", label: "时间段" },
                  { key: "description", label: "经历描述", multiline: true },
                ], { company: "", position: "", duration: "", description: "" })}
                {renderEditListSection("🚀 项目经验", "project_experience", [
                  { key: "name", label: "项目名称" },
                  { key: "role", label: "担任角色" },
                  { key: "duration", label: "时间段" },
                  { key: "description", label: "项目成果与职责", multiline: true },
                ], { name: "", role: "", duration: "", description: "" })}
                {(editDraft.practical_experience.length > 0 || x.practical_experience?.length > 0) &&
                  renderEditListSection("🌱 个人实践", "practical_experience", [
                    { key: "organization", label: "机构/组织" },
                    { key: "role", label: "角色" },
                    { key: "duration", label: "时间段" },
                    { key: "description", label: "实践描述", multiline: true },
                  ], { organization: "", role: "", duration: "", description: "" })}
                {(editDraft.campus_experience.length > 0 || x.campus_experience?.length > 0) &&
                  renderEditListSection("🏫 校园经历", "campus_experience", [
                    { key: "organization", label: "组织/社团" },
                    { key: "role", label: "职务" },
                    { key: "duration", label: "时间段" },
                    { key: "description", label: "经历描述", multiline: true },
                  ], { organization: "", role: "", duration: "", description: "" })}
                {(editDraft.research_experience.length > 0 || x.research_experience?.length > 0) &&
                  renderEditListSection("🔬 科研经历", "research_experience", [
                    { key: "name", label: "课题名称" },
                    { key: "role", label: "角色" },
                    { key: "duration", label: "时间段" },
                    { key: "description", label: "科研内容与成果", multiline: true },
                  ], { name: "", role: "", duration: "", description: "" })}
              </div>
            ) : (
              <>
                {Array.isArray(x.quality_warnings) && x.quality_warnings.length > 0 && <div style={{ padding: "12px 16px", background: "var(--warning-soft)", border: "1px solid rgba(255,171,0,0.3)", borderRadius: 8, marginBottom: 16 }}><b style={{ color: "var(--warning)" }}>⚠️ 请检查以下内容</b>{x.quality_warnings.map((warning, index) => <div key={`${warning.code}-${warning.field}-${index}`} style={{ color: "var(--text-dim)", fontSize: 13, marginTop: 6 }}>• {warning.message}</div>)}</div>}
                <div style={{ marginBottom: 16 }}><h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 0, color: "var(--accent)" }}>{x.name}</h3>{renderEvidence("name")}</div>
                {x.desired_position && <div style={{ padding: "12px 16px", background: "var(--brand-soft)", borderLeft: "3px solid var(--accent)", borderRadius: "0 8px 8px 0", marginBottom: 12 }}><b style={{ color: "var(--accent)" }}>🎯 求职意向：</b>{x.desired_position}{renderEvidence("desired_position")}</div>}
                {x.desired_salary && <p style={{ color: "var(--accent2)", marginBottom: 12 }}>💰 期望薪资：{x.desired_salary}</p>}
                <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>📋 基本信息</h4>{x.phone && <div style={infoP}>📱 电话：{x.phone}{renderEvidence("phone")}</div>}{x.email && <div style={infoP}>📧 邮箱：{x.email}{renderEvidence("email")}</div>}{x.education?.length > 0 && <p style={infoP}>🎓 学历：{x.education.map(e => `${e.school} | ${e.major} | ${e.degree} | ${e.year}`).join(" / ")}</p>}</div>
                {x.work_experience?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>💼 工作/实习经历</h4>{x.work_experience.map((w,i) => <div key={i} style={{ padding: "10px 14px", background: "var(--bg-inset)", borderRadius: 8, marginBottom: 8 }}><b>{w.position}</b> @ {w.company} <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{w.duration}</span>{w.description && <p style={{ marginTop: 6, color: "var(--text-dim)", fontSize: 13 }}>{w.description}</p>}</div>)}</div>}
                {x.practical_experience?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🌱 个人实践</h4>{x.practical_experience.map((item,i) => <div key={i} style={{ padding: "10px 14px", background: "var(--success-soft)", borderLeft: "2px solid var(--accent2)", borderRadius: 8, marginBottom: 8 }}><b>{item.role || item.organization || item.name}</b>{item.role && item.organization && <> @ {item.organization}</>}<span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 8 }}>{item.duration}</span>{item.description && <p style={{ marginTop: 6, color: "var(--text-dim)", fontSize: 13, lineHeight: 1.6 }}>{item.description}</p>}</div>)}</div>}
                {x.project_experience?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🚀 项目经验</h4>{x.project_experience.map((p,i) => <div key={i} style={{ padding: "10px 14px", background: "var(--success-soft)", borderLeft: "2px solid var(--accent2)", borderRadius: 8, marginBottom: 8 }}><b>{p.name}</b>{p.role && <span style={{ color: "var(--accent2)", fontSize: 12, marginLeft: 8 }}>🔹 {p.role}</span>}<span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 8 }}>{p.duration}</span>{p.description && <p style={{ marginTop: 6, color: "var(--text-dim)", fontSize: 13, lineHeight: 1.6 }}>{p.description}</p>}</div>)}</div>}
                {x.campus_experience?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🏫 校园经历</h4>{x.campus_experience.map((item,i) => <div key={i} style={{ padding: "10px 14px", background: "var(--bg-inset)", borderRadius: 8, marginBottom: 8 }}><b>{item.role || item.organization}</b>{item.role && item.organization && <> @ {item.organization}</>}<span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 8 }}>{item.duration}</span>{item.description && <p style={{ marginTop: 6, color: "var(--text-dim)", fontSize: 13 }}>{item.description}</p>}</div>)}</div>}
                {x.research_experience?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🔬 科研经历</h4>{x.research_experience.map((item,i) => <div key={i} style={{ padding: "10px 14px", background: "rgba(0,229,255,0.03)", borderLeft: "2px solid var(--accent)", borderRadius: 8, marginBottom: 8 }}><b>{item.name}</b>{item.role && <span style={{ color: "var(--accent)", fontSize: 12, marginLeft: 8 }}>{item.role}</span>}<span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 8 }}>{item.duration}</span>{item.description && <p style={{ marginTop: 6, color: "var(--text-dim)", fontSize: 13 }}>{item.description}</p>}</div>)}</div>}
                {x.skills?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🛠 技能</h4><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{x.skills.map((s,i) => <span key={i} style={skillTag}>{s}</span>)}</div>{renderEvidence("skills")}</div>}
                {x.awards?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🏆 获奖荣誉</h4>{x.awards.map((item,i) => <div key={i} style={{ marginBottom: 6 }}><b>{item.name}</b>{item.level && <span style={{ color: "var(--accent2)", marginLeft: 8 }}>{item.level}</span>}{item.year && <span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 8 }}>{item.year}</span>}{item.description && <p style={{ ...infoP, marginTop: 4 }}>{item.description}</p>}</div>)}</div>}
                {x.certificates?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>📜 证书资质</h4>{x.certificates.map((item,i) => <div key={i} style={{ marginBottom: 6 }}><b>{item.name}</b>{item.level && <span style={{ color: "var(--accent)", marginLeft: 8 }}>{item.level}</span>}{item.year && <span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 8 }}>{item.year}</span>}{item.issuer && <span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 8 }}>· {item.issuer}</span>}</div>)}</div>}
                {x.language_skills?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🌐 语言能力</h4><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{x.language_skills.map((item,i) => <span key={i} style={skillTag}>{[item.language, item.level, item.certificate].filter(Boolean).join(" · ")}</span>)}</div></div>}
                {x.interests?.length > 0 && <div style={{ marginBottom: 16 }}><h4 style={sectionH4}>🎨 兴趣爱好</h4><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{x.interests.map((item,i) => <span key={i} style={skillTag}>{item}</span>)}</div></div>}
                {x.summary && <div><h4 style={sectionH4}>📝 自我介绍 / 综合摘要</h4><p style={{ color: "var(--text-dim)", whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{x.summary}</p></div>}
              </>
            )}
          </div>
        </div>
      );
    }
    return (
      <div style={{ animation: "fadeInUp 0.4s ease" }}>
        <div style={{ ...card, marginBottom: 20 }}><h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>简历解析引擎</h3><p style={{ color: "var(--text-dim)", marginBottom: 16 }}>上传简历（PDF/Word/TXT），AI自动提取关键信息</p><label style={{ ...btnGlow, cursor: "pointer", display: "inline-flex" }}>{uploading ? "⏳ 解析中..." : "📤 上传并解析简历"}<input type="file" accept=".docx,.pdf,.txt" onChange={handleUpload} style={{ display: "none" }} /></label>{uploading && <div style={{ marginTop: 14, maxWidth: 460 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 7, fontSize: 12, color: "var(--text-dim)" }}><span>正在解析简历</span><span>上传 · 读取 · AI提取 · 检查</span></div><div style={{ height: 6, overflow: "hidden", borderRadius: 999, background: "var(--brand-soft)" }}><div style={{ width: "42%", height: "100%", borderRadius: "inherit", background: "linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent)", animation: "parseProgressFlow 1.35s ease-in-out infinite" }} /></div></div>}{statusMsg && <p style={{ marginTop: 12, fontSize: 13, color: statusMsg.includes("✅") ? "var(--accent)" : statusMsg.includes("❌") ? "var(--danger)" : "var(--text-dim)", fontFamily: "var(--font-mono)" }}>{statusMsg}</p>}</div>
        {resumes.length > 0 ? <div style={{ ...card }}><h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>已解析 ({resumes.length}份)</h3>{resumes.map((x,i) => <div key={i} onClick={() => viewResume(x.filename)} style={resumeItem} onMouseEnter={e => e.currentTarget.style.borderColor = "var(--accent)"} onMouseLeave={e => e.currentTarget.style.borderColor = "var(--border)"}><div><span style={{ color: "var(--accent)", fontWeight: 600 }}>{x.name}</span>{x.position && <span style={{ color: "var(--accent2)", fontSize: 12, marginLeft: 8 }}>🎯 {x.position}</span>}<br/><span style={{ fontSize: 11, color: "var(--text-dim)" }}>{x.parsed_at}</span></div><button onClick={e => { e.stopPropagation(); deleteResume(x.filename); }} style={deleteBtn}>删除</button></div>)}</div> : <div style={{ ...card, textAlign: "center", color: "var(--text-dim)", padding: "40px" }}><p style={{ fontSize: 40, marginBottom: 10 }}>📭</p><p>暂无解析的简历</p></div>}
      </div>
    );
  };

  // ── Step 2 Render (abbreviated, same as before) ──
  const renderStep2 = () => (
    <div style={{ animation: "fadeInUp 0.4s ease", display: "flex", flexDirection: "column" }}>
      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>✨ AI智能优化简历</h3>
        <p style={{ color: "var(--text-dim)", marginBottom: 16 }}>根据具体岗位和JD，把真实经历转换成目标岗位更容易理解的表达</p>
        <div style={{ marginBottom: 12 }}><select value={optResume} onChange={e => { selectedResumeRef.current = e.target.value; setOptResume(e.target.value); }} style={selectStyle}><option value="">选择简历...</option>{resumes.map(x => <option key={x.filename} value={x.filename}>{formatResumeLabel(x)}</option>)}</select></div>
        <div style={{ marginBottom: 12 }}><input value={optTarget} onChange={e => setOptTarget(e.target.value)} placeholder="具体岗位（如：金融产品运营，不能只写金融行业）" style={inputStyle} /></div>
        <div style={{ marginBottom: 12 }}><textarea value={optJD} onChange={e => setOptJD(e.target.value)} placeholder="粘贴目标岗位JD（推荐，包含职责和任职要求）" rows={6} style={textareaStyle} /></div>
        <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12.5, color: "var(--text-dim)", fontWeight: 600 }}>改写力度（温度）：</span>
          {[
            { id: "mild", label: "🌱 微调档 (0.25)", title: "仅润色语病与动词，最大限度贴近原文" },
            { id: "balanced", label: "⚖️ 均衡档 (0.55·推荐)", title: "STAR 结构重写 + 术语升级，明显提升质感" },
            { id: "aggressive", label: "🔥 激进档 (0.85)", title: "深度对标目标 JD 重塑叙事（不造假公司/学历）" },
          ].map((st) => (
            <button
              key={st.id}
              type="button"
              title={st.title}
              onClick={() => setOptStyle(st.id)}
              style={{
                padding: "5px 12px",
                borderRadius: 999,
                fontSize: 12,
                fontWeight: optStyle === st.id ? 600 : 500,
                cursor: "pointer",
                background: optStyle === st.id ? "var(--brand-soft)" : "var(--bg-inset)",
                color: optStyle === st.id ? "var(--brand)" : "var(--text-secondary)",
                border: `1px solid ${optStyle === st.id ? "var(--brand-border)" : "var(--border)"}`,
              }}
            >
              {st.label}
            </button>
          ))}
        </div>
        <div style={{ marginBottom: 16 }}><textarea value={optExtra} onChange={e => setOptExtra(e.target.value)} placeholder="额外要求（可选，例如：突出数据复盘和跨部门协作）" rows={3} style={textareaStyle} /></div>
        <button onClick={runOptimize} disabled={optLoading} style={{ ...btnGlow, opacity: optLoading ? 0.6 : 1 }}>{optLoading ? "⏳ AI优化中..." : "🚀 开始AI优化"}</button>
        {optTask && <div style={{ marginTop: 14, maxWidth: 560, padding: "12px 14px", border: "1px solid var(--border)", borderRadius: 10, background: "var(--bg-inset)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 7, fontSize: 12, color: "var(--text-dim)" }}><span>{OPTIMIZATION_STAGE_LABELS[optTask.stage] || "处理中"}</span><span>{optTask.progress || 0}%</span></div>
          <div style={{ height: 7, overflow: "hidden", borderRadius: 999, background: "var(--brand-soft)" }}><div style={{ width: `${optTask.progress || 0}%`, height: "100%", borderRadius: "inherit", background: "linear-gradient(90deg, var(--accent), var(--accent2))", transition: "width 0.35s ease" }} /></div>
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--text-dim)" }}>任务编号：{optTask.task_id}{optTask.attempts > 0 ? ` · AI请求 ${optTask.attempts} 次` : ""}</div>
          {optTask.status === "failed" && <div style={{ marginTop: 10 }}><div style={{ color: "var(--danger)", fontSize: 12 }}>失败阶段：{OPTIMIZATION_STAGE_LABELS[optTask.stage] || optTask.stage} · {optTask.error_message || "未知错误"}</div><div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 4 }}>原简历、目标岗位和JD已保留，不需要重新填写。</div><button onClick={retryOptimizationTask} style={{ ...btnOutline2, marginTop: 8 }}>重新尝试</button></div>}
        </div>}
        {statusMsg && <p style={{ marginTop: 12, fontSize: 13, color: statusMsg.includes("✅") ? "var(--accent)" : statusMsg.includes("❌") ? "var(--danger)" : "var(--text-dim)", fontFamily: "var(--font-mono)" }}>{statusMsg}</p>}
      </div>
      {optResume && <div style={{ ...card, marginBottom: 20, order: 3 }}>
        <button
          onClick={() => setVersionsOpen((open) => !open)}
          style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", padding: 0, border: 0, background: "transparent", color: "var(--text)", cursor: "pointer", textAlign: "left" }}
        >
          <span style={{ fontSize: 16, fontWeight: 700 }}>🗂 简历版本记录 <span style={{ color: "var(--text-dim)", fontSize: 12 }}>({resumeVersions.length})</span></span>
          <span style={{ color: "var(--accent)" }}>{versionsOpen ? "收起" : "展开"}</span>
        </button>
        {versionsOpen && <div style={{ marginTop: 14 }}>
          {versionsLoading && <div style={{ color: "var(--text-dim)", fontSize: 13 }}>正在读取版本记录...</div>}
          {!versionsLoading && versionLoadError && <div style={{ color: "var(--danger)", fontSize: 13 }}>版本读取失败：{versionLoadError} <button onClick={() => loadResumeVersions(optResume)} style={{ ...btnOutline2, padding: "4px 8px", marginLeft: 8, fontSize: 11 }}>重新读取</button></div>}
          {!versionsLoading && !versionLoadError && resumeVersions.length === 0 && <div style={{ color: "var(--text-dim)", fontSize: 13 }}>暂无可查看的版本记录</div>}
          {resumeVersions.map((version) => <div key={version.version_id} style={{ padding: "12px 14px", border: "1px solid var(--border)", borderRadius: 10, marginBottom: 10, background: version.is_current ? "rgba(0,212,255,0.06)" : "rgba(255,255,255,0.02)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
              <div>
                <div style={{ fontWeight: 700, color: version.version_type === "original" ? "var(--accent2)" : "var(--accent)" }}>
                  {version.version_type === "original" ? (version.source_status === "legacy_unverified" ? "旧数据底稿（原始性待确认）" : "原始版本") : "AI优化版本"}
                  {version.is_current && <span style={{ marginLeft: 8, padding: "2px 7px", borderRadius: 999, background: "var(--brand-soft)", fontSize: 11 }}>当前版本</span>}
                </div>
                <div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 5 }}>{version.created_at || "保存时间未记录"}</div>
                <div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 3 }}>
                  模式：{VERSION_MODE_LABELS[version.optimization_mode] || (version.version_type === "optimized" ? "历史优化" : "原始底稿")}
                  {version.target ? ` · 目标：${version.target}` : ""}
                </div>
                <div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 3 }}>Prompt：{version.prompt_version || "历史版本未记录"}</div>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                <button onClick={() => viewResumeVersion(version.version_id)} style={{ ...btnOutline2, padding: "5px 10px", fontSize: 12 }}>查看版本</button>
                {!version.is_current && <button onClick={() => activateResumeVersion(version)} style={{ ...btnOutline2, padding: "5px 10px", fontSize: 12, borderColor: "var(--accent2)", color: "var(--accent2)" }}>设为当前版本</button>}
                {version.version_type === "optimized" && !version.is_current && <button onClick={() => deleteResumeVersion(version.version_id)} style={{ ...btnOutline2, padding: "5px 10px", fontSize: 12, borderColor: "var(--danger)", color: "var(--danger)" }}>删除记录</button>}
              </div>
            </div>
          </div>)}
          {versionPreviewLoading && <div style={{ color: "var(--text-dim)", fontSize: 13 }}>正在读取版本内容...</div>}
          {versionPreview && <div style={{ marginTop: 14, padding: "14px 16px", borderLeft: "3px solid var(--accent2)", borderRadius: "0 8px 8px 0", background: "var(--success-soft)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><b style={{ color: "var(--accent2)" }}>版本内容预览</b><button onClick={() => setVersionPreview(null)} style={{ border: 0, background: "transparent", color: "var(--text-dim)", cursor: "pointer" }}>关闭</button></div>
            <div style={{ marginTop: 8, fontSize: 14 }}><b>{versionPreview.content?.name || "未填写姓名"}</b>{versionPreview.content?.desired_position ? ` · ${versionPreview.content.desired_position}` : ""}</div>
            <div style={{ marginTop: 5, color: "var(--text-dim)", fontSize: 12 }}>{[versionPreview.content?.phone, versionPreview.content?.email].filter(Boolean).join(" · ") || "联系方式未填写"}</div>
            {versionPreview.content?.summary && <p style={{ marginTop: 8, color: "var(--text-dim)", fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{versionPreview.content.summary}</p>}
            <div style={{ marginTop: 8, color: "var(--text-dim)", fontSize: 12 }}>技能：{versionPreview.content?.skills?.length ? versionPreview.content.skills.join("、") : "未填写"}</div>
            <VersionContentSection title="教育经历" items={versionPreview.content?.education} />
            <VersionContentSection title="工作经历" items={versionPreview.content?.work_experience} />
            <VersionContentSection title="项目经历" items={versionPreview.content?.project_experience} />
            <VersionContentSection title="个人实践" items={versionPreview.content?.practical_experience} />
            <VersionContentSection title="校园经历" items={versionPreview.content?.campus_experience} />
            <VersionContentSection title="科研经历" items={versionPreview.content?.research_experience} />
            <VersionContentSection title="获奖荣誉" items={versionPreview.content?.awards} />
            <VersionContentSection title="证书资质" items={versionPreview.content?.certificates} />
            <VersionContentSection title="语言能力" items={versionPreview.content?.language_skills} />
            <VersionContentSection title="兴趣爱好" items={versionPreview.content?.interests} />
          </div>}
        </div>}
      </div>}
      {optResult && (
        <div style={{ ...card, animation: "fadeInUp 0.5s ease", order: 2, marginBottom: 20 }}>
          <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>✨ 完整优化结果</h3>
          <div style={{ padding: "12px 16px", background: "var(--brand-soft)", borderLeft: "3px solid var(--accent)", borderRadius: "0 8px 8px 0", marginBottom: 12 }}><b style={{ color: "var(--accent)" }}>求职意向：</b>{optResult.target}</div>
          {optResult.job_analysis && <div style={{ padding: "12px 16px", background: "rgba(255,171,0,0.05)", borderLeft: "3px solid #ffab00", borderRadius: "0 8px 8px 0", marginBottom: 16, fontSize: 13, color: "var(--accent2)", lineHeight: 1.6 }}>🔍 <b>岗位分析：</b>{optResult.job_analysis}</div>}
          {optResult.capability_analysis && <div style={{ marginBottom: 20 }}>
            <h4 style={{ color: "var(--accent)", marginBottom: 10 }}>🧭 岗位能力映射</h4>
            {optResult.capability_analysis.direct_matches?.map((item,i) => <div key={`direct-${i}`} style={{ ...infoP, marginBottom: 8 }}><b style={{ color: "var(--accent2)" }}>直接匹配：</b>{item.capability}<div style={{ fontSize: 12, color: "var(--text-dim)" }}>依据：{item.source_evidence}</div><div style={{ fontSize: 12, color: "var(--text-dim)" }}>{item.target_relevance}</div></div>)}
            {optResult.capability_analysis.transferable_matches?.map((item,i) => <div key={`transfer-${i}`} style={{ ...infoP, marginBottom: 8 }}><b style={{ color: "var(--warning)" }}>可迁移：</b>{item.capability}<div style={{ fontSize: 12, color: "var(--text-dim)" }}>依据：{item.source_evidence}</div><div style={{ fontSize: 12, color: "var(--text-dim)" }}>{item.target_relevance}</div></div>)}
            {optResult.capability_analysis.gaps?.map((item,i) => {
              const isGapExpanded = expandedGapIndexes.includes(i);
              const toggleGapDetail = () => setExpandedGapIndexes((currentIndexes) => currentIndexes.includes(i) ? currentIndexes.filter(index => index !== i) : [...currentIndexes, i]);
              const suggestionId = item.suggestion_id || `gap-${i}`;
              const decisionText = item.decision === "accepted" ? "已接受" : item.decision === "rejected" ? "不采用" : "待确认";
              const decisionColor = item.decision === "accepted" ? "var(--accent2)" : item.decision === "rejected" ? "var(--text-dim)" : "var(--warning)";
              return <div key={suggestionId} style={{ ...infoP, marginBottom: 8 }}>
                <b style={{ color: "var(--danger)" }}>能力缺口：</b>{item.capability}
                <span style={{ marginLeft: 8, fontSize: 11, color: item.priority === "high" ? "var(--danger)" : "var(--text-dim)" }}>{item.priority === "high" ? "高优先级" : item.priority === "low" ? "低优先级" : "中优先级"}</span>
                <span style={{ marginLeft: 8, fontSize: 11, color: decisionColor }}>状态：{decisionText}</span>
                <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>建议：{item.action}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                  <button onClick={toggleGapDetail} style={{ ...btnOutline2, padding: "5px 10px", fontSize: 12 }}>{isGapExpanded ? "收起" : "查看建议"}</button>
                  <button onClick={() => { if (!isGapExpanded) toggleGapDetail(); }} style={{ ...btnOutline2, padding: "5px 10px", fontSize: 12, borderColor: "var(--accent2)", color: "var(--accent2)" }}>接受并补充真实经历</button>
                  <button onClick={() => updateGapDecision(i, "rejected")} style={{ ...btnOutline2, padding: "5px 10px", fontSize: 12 }}>不采用</button>
                  {item.decision !== "pending" && <button onClick={() => updateGapDecision(i, "pending")} style={{ ...btnOutline2, padding: "5px 10px", fontSize: 12 }}>撤销选择</button>}
                </div>
                {isGapExpanded && <div style={{ marginTop: 10, paddingTop: 8, borderTop: "1px solid var(--border)", fontSize: 12, color: "var(--text-dim)", lineHeight: 1.7 }}>
                  <div><b>岗位依据：</b>{item.jd_evidence}</div>
                  <div><b>当前状态：</b>{item.resume_status}</div>
                  <div><b>写入条件：</b>{item.write_condition}</div>
                  {item.decision !== "rejected" && <div style={{ marginTop: 10 }}>
                    <textarea
                      value={gapConfirmationText[suggestionId] ?? item.confirmed_content ?? ""}
                      onChange={(event) => setGapConfirmationText((current) => ({ ...current, [suggestionId]: event.target.value }))}
                      placeholder="只填写你真实做过、并愿意写入本次优化记录的经历"
                      rows={3}
                      maxLength={1200}
                      style={{ ...textareaStyle, marginBottom: 8 }}
                    />
                    <button onClick={() => updateGapDecision(i, "accepted")} style={{ ...btnGlow, padding: "6px 12px", fontSize: 12 }}>确认接受真实内容</button>
                  </div>}
                </div>}
              </div>;
            })}
            {optResult.capability_analysis.gaps?.length > 0 && <div style={{ marginTop: 10, fontSize: 12, color: "var(--text-dim)" }}>确认进度：已接受 {optResult.capability_analysis.gaps.filter((gap) => gap.decision === "accepted").length} 条 · 不采用 {optResult.capability_analysis.gaps.filter((gap) => gap.decision === "rejected").length} 条 · 待确认 {optResult.capability_analysis.gaps.filter((gap) => !gap.decision || gap.decision === "pending").length} 条</div>}
          </div>}
          {optResult.optimized_summary && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>📝 优化后个人总结</h4><p style={{ color: "var(--text)", whiteSpace: "pre-wrap", lineHeight: 1.7, fontSize: 14 }}>{optResult.optimized_summary}</p></div>}
          {optResult.optimized_projects?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent2)", marginBottom: 10 }}>🚀 优化项目经验</h4>{optResult.optimized_projects.map((p,i) => <div key={i} style={{ padding: "12px 16px", background: "var(--success-soft)", borderLeft: "3px solid var(--accent2)", borderRadius: "0 8px 8px 0", marginBottom: 8 }}><b>{p.name}</b> — <span style={{ color: "var(--text-dim)", fontSize: 13 }}>{p.role}</span><p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 6, lineHeight: 1.6 }}>{p.description}</p></div>)}</div>}
          {optResult.optimized_internships?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--warning)", marginBottom: 10 }}>💼 优化实习经验</h4>{optResult.optimized_internships.map((intern,i) => <div key={i} style={{ padding: "12px 16px", background: "rgba(255,171,0,0.05)", borderLeft: "3px solid #ffab00", borderRadius: "0 8px 8px 0", marginBottom: 8 }}><b>{intern.company}</b> | {intern.position} <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{intern.duration}</span><p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 6, lineHeight: 1.6 }}>{intern.description}</p></div>)}</div>}
          {optResult.enhanced_skills?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>🔧 增强技能列表</h4><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{optResult.enhanced_skills.map((s,i) => <span key={i} style={skillTag}>{s}</span>)}</div></div>}
          {optResult.optimized_resume?.education?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>🎓 教育经历（原事实保留）</h4>{optResult.optimized_resume.education.map((item,i) => <div key={i} style={{ ...infoP, marginBottom: 6 }}><b>{item.school}</b> · {[item.major,item.degree,item.year].filter(Boolean).join(" | ")}</div>)}</div>}
          {optResult.optimized_resume?.practical_experience?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent2)", marginBottom: 10 }}>🌱 个人实践</h4>{optResult.optimized_resume.practical_experience.map((item,i) => <div key={i} style={{ ...infoP, marginBottom: 8 }}><b>{item.organization || item.role || item.name}</b>{item.role && <> · {item.role}</>}<p>{item.description}</p></div>)}</div>}
          {optResult.optimized_resume?.campus_experience?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>🏫 校园经历</h4>{optResult.optimized_resume.campus_experience.map((item,i) => <div key={i} style={{ ...infoP, marginBottom: 8 }}><b>{item.organization || item.role}</b>{item.role && <> · {item.role}</>}<p>{item.description}</p></div>)}</div>}
          {optResult.optimized_resume?.research_experience?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>🔬 科研经历</h4>{optResult.optimized_resume.research_experience.map((item,i) => <div key={i} style={{ ...infoP, marginBottom: 8 }}><b>{item.name}</b>{item.role && <> · {item.role}</>}<p>{item.description}</p></div>)}</div>}
          {optResult.optimized_resume?.awards?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent2)", marginBottom: 10 }}>🏆 获奖荣誉</h4>{optResult.optimized_resume.awards.map((item,i) => <div key={i} style={infoP}>{item.name} · {[item.level,item.year].filter(Boolean).join(" | ")}</div>)}</div>}
          {optResult.optimized_resume?.certificates?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>📜 证书资质</h4>{optResult.optimized_resume.certificates.map((item,i) => <div key={i} style={infoP}>{item.name} · {[item.level,item.issuer,item.year].filter(Boolean).join(" | ")}</div>)}</div>}
          {optResult.optimized_resume?.language_skills?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--accent)", marginBottom: 10 }}>🌐 语言能力</h4>{optResult.optimized_resume.language_skills.map((item,i) => <span key={i} style={skillTag}>{[item.language,item.level,item.certificate].filter(Boolean).join(" · ")}</span>)}</div>}
          {optResult.optimized_resume?.interests?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--text-dim)", marginBottom: 10 }}>🎨 兴趣爱好</h4>{optResult.optimized_resume.interests.map((item,i) => <span key={i} style={skillTag}>{item}</span>)}</div>}
          {optResult.optimization_warnings?.length > 0 && <div style={{ padding: "12px 16px", background: "var(--warning-soft)", border: "1px solid rgba(255,171,0,0.3)", borderRadius: 8, marginBottom: 16 }}><b style={{ color: "var(--warning)" }}>⚠️ 真实性检查</b>{optResult.optimization_warnings.map((warning,index) => <div key={`${warning.code}-${index}`} style={{ color: "var(--text-dim)", fontSize: 13, marginTop: 6 }}>• {warning.message}</div>)}</div>}
          {optResult.suggestions?.length > 0 && <div style={{ marginBottom: 20 }}><h4 style={{ color: "var(--text-dim)", marginBottom: 10 }}>💡 优化建议</h4>{optResult.suggestions.map((s,i) => <div key={i} style={{ fontSize: 13, color: "var(--accent2)", marginBottom: 4, padding: "6px 12px", background: "var(--success-soft)", borderRadius: 6 }}>💡 {s}</div>)}</div>}
          <ResumeDiffPanel resumeDiff={optResult.resume_diff} open={resumeDiffOpen} onToggle={() => setResumeDiffOpen((current) => !current)} />
          <div style={{ display: "flex", gap: 12, marginTop: 20 }}><button onClick={exportResume} style={{ ...btnGlow, flex: 1 }}>📥 导出简历</button><button onClick={overwriteResume} style={{ flex: 1, ...btnOutline2, borderColor: "var(--warning)", color: "var(--warning)" }}>💾 保存优化版本</button></div>
        </div>
      )}
    </div>
  );

  // ── Step 4: Job Scraping State ──
  const [sResume, setSResume] = React.useState("");
  const [sSalary, setSSalary] = React.useState("");

  const renderStep4 = () => {
    return <JobMarket 
        resumes={resumes} 
        sResume={sResume} 
        setSResume={setSResume} 
        sSalary={sSalary} 
        setSSalary={setSSalary} 
        onPrecisionOptimize={jumpToPrecisionOptimize}
    />;
  };

  // ── Step 5: JD Match State ──
  const [jdResume, setJdResume] = React.useState("");
  const [jdText, setJdText] = React.useState("");
  const [jdRestrictions, setJdRestrictions] = React.useState("");
  const [jdResult, setJdResult] = React.useState(null);
  const [jdLoading, setJdLoading] = React.useState(false);
  // Batch
  const [batchResume, setBatchResume] = React.useState("");
  const [batchFile, setBatchFile] = React.useState("");
  const [batchRestrictions, setBatchRestrictions] = React.useState("");
  const [batchTh, setBatchTh] = React.useState(70);
  const [batchResult, setBatchResult] = React.useState(null);
  const [batchLoading, setBatchLoading] = React.useState(false);
  const [batchFiles, setBatchFiles] = React.useState([]);
  const [batchShowHi, setBatchShowHi] = React.useState(true);
  // Stage 2.2: AI Mock Interviewer (shared between Step 5, Step 6 & Step 7)
  const [interviewLoading, setInterviewLoading] = React.useState(false);
  const [interviewResult, setInterviewResult] = React.useState(null);
  const [interviewError, setInterviewError] = React.useState("");
  const [revealedAnswers, setRevealedAnswers] = React.useState({});

  React.useEffect(() => { if (activeStep === 5) { loadBatchFilesForStep5(); } }, [activeStep]);

  const loadBatchFilesForStep5 = async () => {
    try { const r = await fetch(`${API_BASE}/api/jobs/list`); const d = await r.json(); setBatchFiles(d.files || []); } catch {}
  };

  const runJDMatch = async () => {
    if (jdText.trim().length < 10) { setStatusMsg("请粘贴岗位描述(至少10字)"); return; }
    if (!jdResume) { setStatusMsg("请选择简历"); return; }
    setJdLoading(true); setJdResult(null); setInterviewResult(null); setInterviewError(""); setStatusMsg("");
    const fd = new FormData();
    fd.append("jd_text", jdText.trim());
    fd.append("resume_file", jdResume);
    if (jdRestrictions.trim()) fd.append("restrictions", jdRestrictions.trim());
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
        body: JSON.stringify({
          jobs_file: batchFile,
          resume_file: batchResume,
          threshold: batchTh,
          restrictions: batchRestrictions.trim() || undefined,
        })
      });
      const d = await r.json();
      if (d.ok) setBatchResult(d); else setStatusMsg(d.error || "匹配失败");
    } catch(e) { setStatusMsg(e.message); }
    setBatchLoading(false);
  };

  const lastInterviewReqRef = React.useRef(null);
  const askedQuestionsRef = React.useRef([]);

  const runInterviewPrep = async ({ resumeFile, jdTextInput = "", jobsFileInput = "", jobIndexInput = -1, targetPosition = "", restrictionsInput = "", avoidQuestions = [] }) => {
    if (!resumeFile) {
      setInterviewError("请先选择一份简历");
      return;
    }
    lastInterviewReqRef.current = { resumeFile, jdTextInput, jobsFileInput, jobIndexInput, targetPosition, restrictionsInput };
    if (!Array.isArray(avoidQuestions) || avoidQuestions.length === 0) {
      askedQuestionsRef.current = [];
    }
    setInterviewLoading(true);
    setInterviewError("");
    setInterviewResult(null);
    setRevealedAnswers({});
    try {
      const fd = new FormData();
      fd.append("resume_file", resumeFile);
      if (jdTextInput) fd.append("jd_text", jdTextInput);
      if (jobsFileInput) fd.append("jobs_file", jobsFileInput);
      if (typeof jobIndexInput === "number" && jobIndexInput >= 0) fd.append("job_index", String(jobIndexInput));
      if (targetPosition) fd.append("target_position", targetPosition);
      if (restrictionsInput) fd.append("restrictions", restrictionsInput);
      fd.append("temperature", String(prefsForm.interviewTemp || 0.72));
      fd.append("question_count", String(prefsForm.interviewCount || 5));
      if (Array.isArray(avoidQuestions) && avoidQuestions.length > 0) {
        fd.append("avoid_questions", JSON.stringify(avoidQuestions.slice(-16)));
      }
      const r = await fetch(`${API_BASE}/api/resume/interview-prep`, { method: "POST", body: fd });
      const d = await r.json();
      if (r.ok && d.ok) {
        setInterviewResult(d);
        const newQs = (d.questions || []).map((q) => q?.question).filter(Boolean);
        askedQuestionsRef.current = Array.from(new Set([...askedQuestionsRef.current, ...newQs])).slice(-16);
      } else {
        setInterviewError(d.error || "生成模拟面试题失败，请重试");
      }
    } catch (e) {
      setInterviewError("请求模拟面试失败: " + e.message);
    } finally {
      setInterviewLoading(false);
    }
  };

  const refreshInterviewQuestions = () => {
    const req = lastInterviewReqRef.current;
    if (!req || interviewLoading) return;
    const currentQs = (interviewResult?.questions || []).map((q) => q?.question).filter(Boolean);
    const mergedAvoid = Array.from(new Set([...askedQuestionsRef.current, ...currentQs])).slice(-16);
    runInterviewPrep({ ...req, avoidQuestions: mergedAvoid });
  };

  const copyInterviewPrep = () => {
    if (!interviewResult) return;
    const lines = [];
    lines.push(`【AI 模拟面试清单】${interviewResult.target_role || ""}${interviewResult.company ? " @ " + interviewResult.company : ""}`);
    if (interviewResult.overall_strategy) lines.push(`核心策略：${interviewResult.overall_strategy}`);
    lines.push("");
    (interviewResult.questions || []).forEach((q, idx) => {
      lines.push(`${idx + 1}. [${q.category}] ${q.question}`);
      if (q.intent) lines.push(`   考察意图：${q.intent}`);
      if (q.standard_answer) lines.push(`   示范标准口语答案：${q.standard_answer}`);
      const s = q.star_answer || {};
      if (s.situation) lines.push(`   S(背景)：${s.situation}`);
      if (s.task) lines.push(`   T(任务)：${s.task}`);
      if (s.action) lines.push(`   A(行动)：${s.action}`);
      if (s.result) lines.push(`   R(结果)：${s.result}`);
      if (Array.isArray(q.follow_ups) && q.follow_ups.length) {
        lines.push(`   可能追问：${q.follow_ups.join(" / ")}`);
      }
      lines.push("");
    });
    if (Array.isArray(interviewResult.reverse_questions) && interviewResult.reverse_questions.length) {
      lines.push("【建议反问面试官】");
      interviewResult.reverse_questions.forEach((rq, i) => lines.push(`${i + 1}. ${rq}`));
    }
    navigator.clipboard.writeText(lines.join("\n")).then(() => setStatusMsg("已复制模拟面试清单到剪贴板"));
  };

  const renderRestrictionReport = (report) => {
    if (!report || !Array.isArray(report.items) || report.items.length === 0) return null;
    const sum = report.summary || {};
    return React.createElement("div", {
      style: { padding: "14px 16px", marginBottom: 18, borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border)" }
    },
      React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 10 } },
        React.createElement("b", { style: { fontSize: 14, color: "var(--text)" } }, "🚦 个人底线避坑红绿灯"),
        React.createElement("div", { style: { display: "flex", gap: 8, fontSize: 12 } },
          React.createElement("span", { style: { color: "var(--success)", fontWeight: 600 } }, `🟢 满足 ${sum.green || 0}`),
          React.createElement("span", { style: { color: "var(--warning)", fontWeight: 600 } }, `🟡 待确认 ${sum.yellow || 0}`),
          React.createElement("span", { style: { color: "var(--danger)", fontWeight: 600 } }, `🔴 踩雷 ${sum.red || 0}`)
        )
      ),
      React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 8 } },
        report.items.map((item, idx) => {
          const icon = item.status === "green" ? "🟢" : item.status === "red" ? "🔴" : "🟡";
          const tone = item.status === "green" ? "var(--success)" : item.status === "red" ? "var(--danger)" : "var(--warning)";
          const bg = item.status === "green" ? "var(--success-soft)" : item.status === "red" ? "var(--danger-soft)" : "var(--warning-soft)";
          return React.createElement("div", {
            key: idx,
            style: { padding: "8px 12px", borderRadius: 8, background: bg, borderLeft: `3px solid ${tone}`, fontSize: 12.5 }
          },
            React.createElement("div", { style: { display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" } },
              React.createElement("b", { style: { color: "var(--text)" } }, `${icon} ${item.restriction}`),
              React.createElement("span", { style: { color: tone, fontWeight: 600 } }, item.label)
            ),
            item.evidence ? React.createElement("div", { style: { marginTop: 4, fontSize: 11.5, color: "var(--text-dim)" } }, `原文片段：${item.evidence}`) : null
          );
        })
      )
    );
  };

  const renderInterviewPrepCard = () => {
    if (!interviewLoading && !interviewError && !interviewResult) return null;
    const allQuestions = interviewResult?.questions || [];
    const allRevealed = allQuestions.length > 0 && allQuestions.every((_, idx) => !!revealedAnswers[idx]);
    const toggleAllRevealed = () => {
      if (allRevealed) {
        setRevealedAnswers({});
      } else {
        const nextMap = {};
        allQuestions.forEach((_, idx) => { nextMap[idx] = true; });
        setRevealedAnswers(nextMap);
      }
    };
    return React.createElement("div", {
      style: { marginTop: 18, padding: "18px 20px", borderRadius: 12, background: "var(--bg-inset)", border: "1.5px solid var(--accent2-border)" }
    },
      React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 12 } },
        React.createElement("div", null,
          React.createElement("h4", { style: { fontSize: 16, fontWeight: 700, color: "var(--accent2)", margin: 0 } }, "🎤 AI 模拟面试官（先盲答自测 · 点击揭晓标准答案）"),
          interviewResult ? React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginTop: 3 } },
            `目标岗位：${interviewResult.target_role || ""}${interviewResult.company ? " @ " + interviewResult.company : ""} · 答案默认遮盖，可先自行作答再揭晓对照`
          ) : null
        ),
        interviewResult ? React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap" } },
          React.createElement("button", {
            type: "button",
            disabled: interviewLoading,
            onClick: refreshInterviewQuestions,
            style: { ...btnGlow, padding: "5px 12px", fontSize: 12, opacity: interviewLoading ? 0.6 : 1 }
          }, interviewLoading ? "⏳ 换题中..." : "🔄 换一批题库"),
          React.createElement("button", {
            type: "button",
            onClick: toggleAllRevealed,
            style: { ...btnOutline2, padding: "5px 12px", fontSize: 12, color: "var(--accent2)", borderColor: "var(--accent2-border)" }
          }, allRevealed ? "🙈 全部遮盖" : "👁 全部揭晓答案"),
          React.createElement("button", { type: "button", onClick: copyInterviewPrep, style: { ...btnOutline2, padding: "5px 12px", fontSize: 12 } }, "📋 复制整套面试题")
        ) : null
      ),
      interviewLoading ? React.createElement("div", { style: { fontSize: 13, color: "var(--text-dim)", padding: "12px 0" } }, "⏳ 正在模拟真实面试官结合你的简历与目标 JD 出题并整理示范标准答案...") : null,
      interviewError ? React.createElement("div", { style: { fontSize: 13, color: "var(--danger)", padding: "6px 0" } }, `❌ ${interviewError}`) : null,
      interviewResult ? React.createElement("div", null,
        interviewResult.overall_strategy ? React.createElement("div", { style: { padding: "10px 12px", borderRadius: 8, background: "var(--accent2-soft)", color: "var(--text)", fontSize: 13, marginBottom: 14, lineHeight: 1.6 } },
          React.createElement("b", { style: { color: "var(--accent2)" } }, "🎯 核心策略："),
          interviewResult.overall_strategy
        ) : null,
        React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 12 } },
          allQuestions.map((q, idx) => {
            const star = q.star_answer || {};
            const isRevealed = !!revealedAnswers[idx];
            return React.createElement("details", {
              key: idx,
              open: true,
              style: { padding: "12px 14px", borderRadius: 10, background: "var(--bg-card)", border: "1px solid var(--border)" }
            },
              React.createElement("summary", { style: { cursor: "pointer", fontSize: 13.5, fontWeight: 600, color: "var(--text)", lineHeight: 1.5 } },
                React.createElement("span", { style: { display: "inline-block", marginRight: 8, padding: "1px 8px", borderRadius: 999, fontSize: 11, background: "var(--brand-soft)", color: "var(--brand)" } }, q.category || "综合"),
                `Q${idx + 1}. ${q.question}`
              ),
              React.createElement("div", { style: { marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)", fontSize: 12.5, lineHeight: 1.7, color: "var(--text-secondary)" } },
                q.intent ? React.createElement("div", { style: { marginBottom: 10, color: "var(--text-dim)" } }, React.createElement("b", { style: { color: "var(--warning)" } }, "💡 考察意图："), q.intent) : null,
                !isRevealed ? React.createElement("div", {
                  style: {
                    padding: "14px 16px",
                    borderRadius: 10,
                    background: "var(--bg-inset)",
                    border: "1px dashed var(--accent2-border)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 12,
                    flexWrap: "wrap",
                  }
                },
                  React.createElement("div", { style: { fontSize: 12.5, color: "var(--text-dim)" } },
                    "🔒 ",
                    React.createElement("b", { style: { color: "var(--text-secondary)" } }, "参考标准答案已遮盖"),
                    " — 建议先试着自己口述或理清思路，再点击揭晓对照"
                  ),
                  React.createElement("button", {
                    type: "button",
                    onClick: () => setRevealedAnswers((prev) => ({ ...prev, [idx]: true })),
                    style: { ...btnGlow, padding: "6px 14px", fontSize: 12, background: "linear-gradient(135deg, var(--accent2), var(--brand))" }
                  }, "👁 揭晓标准答案")
                ) : React.createElement("div", null,
                  q.standard_answer ? React.createElement("div", {
                    style: { padding: "12px 14px", borderRadius: 9, background: "var(--success-soft)", border: "1px solid var(--border)", marginBottom: 10 }
                  },
                    React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" } },
                      React.createElement("b", { style: { color: "var(--success)", fontSize: 13 } }, "💬 示范标准口语答案（立足真实简历）"),
                      React.createElement("button", {
                        type: "button",
                        onClick: () => setRevealedAnswers((prev) => ({ ...prev, [idx]: false })),
                        style: { ...btnOutline2, padding: "2px 9px", fontSize: 11 }
                      }, "🙈 重新遮盖")
                    ),
                    React.createElement("div", { style: { whiteSpace: "pre-wrap", color: "var(--text)", lineHeight: 1.75 } }, q.standard_answer)
                  ) : null,
                  React.createElement("div", { style: { padding: "10px 12px", borderRadius: 8, background: "var(--bg-inset)", marginBottom: 8 } },
                    React.createElement("div", { style: { fontWeight: 700, color: "var(--brand)", marginBottom: 4 } }, "⭐ STAR 结构拆解"),
                    star.situation ? React.createElement("div", null, React.createElement("b", null, "S（背景）："), star.situation) : null,
                    star.task ? React.createElement("div", null, React.createElement("b", null, "T（任务）："), star.task) : null,
                    star.action ? React.createElement("div", null, React.createElement("b", null, "A（行动）："), star.action) : null,
                    star.result ? React.createElement("div", null, React.createElement("b", null, "R（结果）："), star.result) : null
                  ),
                  Array.isArray(q.follow_ups) && q.follow_ups.length > 0 ? React.createElement("div", { style: { fontSize: 12, color: "var(--accent2)" } },
                    React.createElement("b", null, "🔥 可能继续追问："),
                    q.follow_ups.join(" ｜ ")
                  ) : null
                )
              )
            );
          })
        ),
        Array.isArray(interviewResult.reverse_questions) && interviewResult.reverse_questions.length > 0 ? React.createElement("div", {
          style: { marginTop: 14, padding: "12px 14px", borderRadius: 10, background: "var(--brand-soft)", border: "1px solid var(--brand-border)", fontSize: 12.5, lineHeight: 1.7 }
        },
          React.createElement("b", { style: { color: "var(--brand)" } }, "🤝 建议反问面试官（含个人底线自然核实）："),
          interviewResult.reverse_questions.map((rq, ri) => React.createElement("div", { key: ri, style: { marginTop: 4, color: "var(--text-secondary)" } }, `${ri + 1}. ${rq}`))
        ) : null
      ) : null
    );
  };

  const renderStep5 = () => {
    const sc = jdResult ? jdResult.overall_score || 0 : 0;
    const cc = sc >= 75 ? "var(--success)" : sc >= 50 ? "var(--warning)" : "var(--danger)";
    const jdAnalysis = jdResult ? jdResult.jd_analysis : null;
    const renderJDAnalysisGroup = (title, items, color) => {
      if (!Array.isArray(items) || items.length === 0) return null;
      return React.createElement("div", { style: { marginBottom: 14 } },
        React.createElement("h4", { style: { color, marginBottom: 7, fontSize: 14 } }, title),
        items.map((item, index) => React.createElement("div", {
          key: title + index,
          style: { padding: "9px 12px", marginBottom: 7, background: "rgba(255,255,255,0.035)", borderRadius: 7, borderLeft: "2px solid " + color }
        },
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" } },
            React.createElement("b", { style: { fontSize: 13 } }, item.value),
            Object.prototype.hasOwnProperty.call(item, "required") ? React.createElement("span", {
              style: { fontSize: 11, color: item.required ? "var(--danger)" : "var(--warning)", border: "1px solid " + (item.required ? "var(--danger)" : "var(--warning)"), borderRadius: 10, padding: "1px 7px" }
            }, item.required ? "必须" : "优先/加分") : null
          ),
          React.createElement("div", { style: { color: "var(--text-dim)", fontSize: 12, marginTop: 4, lineHeight: 1.5 } },
            "原文第" + item.line_number + "行：" + item.evidence
          )
        ))
      );
    };

    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      // Part A: Single JD Match
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "JD匹配度评分"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16 } }, "粘贴岗位描述，AI评估匹配度"),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("select", { value: jdResume, onChange: e => setJdResume(e.target.value), style: selectStyle },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, formatResumeLabel(x)))
          )
        ),
        React.createElement("textarea", {
          value: jdText, onChange: e => setJdText(e.target.value),
          placeholder: "粘贴岗位描述(JD)到这里...", rows: 5, style: textareaStyle
        }),
        React.createElement("input", {
          value: jdRestrictions,
          onChange: e => setJdRestrictions(e.target.value),
          placeholder: "个人底线/限制条件（选填，逗号或顿号分隔，如：双休、五险一金、不接受外包、不接受长期出差）",
          style: { ...inputStyle, marginTop: 10, fontSize: 13 }
        }),
        React.createElement("button", { onClick: runJDMatch, disabled: jdLoading, style: { ...btnGlow, marginTop: 12, opacity: jdLoading ? 0.6 : 1 } },
          jdLoading ? "正在解析JD并匹配..." : "解析JD并匹配"
        ),
        statusMsg && !jdResult ? React.createElement("p", { style: { ...statusStyle, color: statusMsg.includes("失败") || statusMsg.includes("请") ? "var(--danger)" : "var(--accent)" } }, statusMsg) : null,
        jdResult ? React.createElement("div", { style: { marginTop: 20 } },
          renderRestrictionReport(jdResult.restriction_report),
          jdAnalysis ? React.createElement("div", {
            style: { padding: 16, marginBottom: 20, background: "var(--brand-soft)", border: "1px solid var(--brand-border)", borderRadius: 10 }
          },
            React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" } },
              React.createElement("h3", { style: { fontSize: 16, color: "var(--accent)" } }, "JD解析与原文依据"),
              React.createElement("span", {
                style: { fontSize: 11, color: jdAnalysis.quality_status === "evidence_checked" ? "var(--success)" : "var(--warning)" }
              }, jdAnalysis.quality_status === "evidence_checked" ? "证据已核对" : "部分内容需复核")
            ),
            jdAnalysis.job_title ? React.createElement("div", { style: { marginBottom: 14, padding: "10px 12px", background: "var(--success-soft)", borderRadius: 7 } },
              React.createElement("b", { style: { color: "var(--success)" } }, "岗位名称："),
              jdAnalysis.job_title.value,
              React.createElement("div", { style: { color: "var(--text-dim)", fontSize: 12, marginTop: 4 } }, "原文第" + jdAnalysis.job_title.line_number + "行：" + jdAnalysis.job_title.evidence)
            ) : null,
            renderJDAnalysisGroup("岗位职责", jdAnalysis.responsibilities, "var(--brand)"),
            renderJDAnalysisGroup("硬技能", jdAnalysis.hard_skills, "var(--accent2)"),
            renderJDAnalysisGroup("软技能", jdAnalysis.soft_skills, "var(--accent2)"),
            renderJDAnalysisGroup("硬性门槛", jdAnalysis.hard_thresholds, "var(--danger)"),
            renderJDAnalysisGroup("优先与加分项", jdAnalysis.preferred_qualifications, "var(--warning)"),
            renderJDAnalysisGroup("关键词", jdAnalysis.keywords, "var(--success)"),
            Array.isArray(jdAnalysis.quality_warnings) && jdAnalysis.quality_warnings.length > 0 ? React.createElement("div", {
              style: { padding: "9px 12px", color: "var(--warning)", background: "rgba(255,202,92,0.06)", borderRadius: 7, fontSize: 12 }
            }, "有" + jdAnalysis.quality_warnings.length + "项AI提取内容没有找到原文证据，已自动移除。") : null
          ) : null,
          React.createElement("div", { style: { textAlign: "center" } },
            React.createElement("div", { style: { fontSize: 52, fontWeight: 800, color: cc } }, sc + "/100")
          ),
          React.createElement("div", { style: { display: "flex", gap: 12, margin: "16px 0" } },
            scoreBar("技能匹配", jdResult.skill_match || 0),
            scoreBar("经验匹配", jdResult.experience_match || 0),
            scoreBar("学历匹配", jdResult.education_match || 0)
          ),
          jdResult.verdict ? React.createElement("div", { style: { padding: "10px 14px", background: "var(--brand-soft)", borderLeft: "3px solid var(--accent)", borderRadius: "0 8px 8px 0", marginBottom: 12, fontSize: 14 } }, jdResult.verdict) : null,
          jdResult.strengths && jdResult.strengths.length > 0 ? React.createElement("div", { style: { marginBottom: 8 } },
            React.createElement("b", { style: { color: "var(--success)" } }, "匹配优势"),
            jdResult.strengths.map((s, i) => React.createElement("div", { key: i, style: { fontSize: 13, color: "var(--text-dim)", padding: "2px 0" } }, "- " + s))
          ) : null,
          jdResult.weaknesses && jdResult.weaknesses.length > 0 ? React.createElement("div", { style: { marginBottom: 8 } },
            React.createElement("b", { style: { color: "var(--warning)" } }, "不足之处"),
            jdResult.weaknesses.map((w, i) => React.createElement("div", { key: i, style: { fontSize: 13, color: "var(--text-dim)", padding: "2px 0" } }, "- " + w))
          ) : null,
          jdResult.suggestions && jdResult.suggestions.length > 0 ? React.createElement("div", null,
            React.createElement("b", { style: { color: "var(--accent)" } }, "建议"),
            jdResult.suggestions.map((s, i) => React.createElement("div", { key: i, style: { fontSize: 13, color: "var(--text-dim)", padding: "2px 0" } }, "- " + s))
          ) : null,
          React.createElement("div", { style: { marginTop: 16 } },
            React.createElement("button", {
              type: "button",
              disabled: interviewLoading,
              onClick: () => jumpToInterviewStep({
                resumeFile: jdResume,
                jdTextInput: jdText.trim(),
                targetPosition: jdAnalysis?.job_title?.value || "",
                restrictionsInput: jdRestrictions.trim(),
              }),
              style: { ...btnGlow, background: "linear-gradient(135deg, var(--accent2), var(--brand))", opacity: interviewLoading ? 0.6 : 1 }
            }, interviewLoading ? "⏳ 正在生成模拟面试追问..." : "🎤 生成模拟面试追问（高频题 + STAR 答法）")
          ),
          renderInterviewPrepCard()
        ) : null
      ),

      // Part B: Batch Match
      React.createElement("div", { style: { ...card } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "批量JD匹配"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16 } }, "对采集的岗位一键全量AI评分（三维：技能/经验/学历）"),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("select", { value: batchResume, onChange: e => setBatchResume(e.target.value), style: selectStyle },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, formatResumeLabel(x)))
          )
        ),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("select", { value: batchFile, onChange: e => setBatchFile(e.target.value), style: selectStyle },
            React.createElement("option", { value: "" }, "选择采集记录..."),
            batchFiles.map((f, i) => React.createElement("option", { key: f.filename, value: f.filename }, "第" + (batchFiles.length - i) + "次采集 - " + ((f.keywords && f.keywords[0]) ? f.keywords[0] : "未知") + " - " + f.count + "个岗位"))
          )
        ),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("input", {
            value: batchRestrictions,
            onChange: e => setBatchRestrictions(e.target.value),
            placeholder: "避坑底线（选填，如：双休、不接受外包；留空则自动读取该批次采集时填写的限制条件）",
            style: { ...inputStyle, fontSize: 13 }
          })
        ),
        React.createElement("div", { style: { marginBottom: 16, display: "flex", alignItems: "center", gap: 8 } },
          React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, "阈值:"),
          React.createElement("input", { type: "number", value: batchTh, onChange: e => setBatchTh(parseInt(e.target.value) || 70), min: 0, max: 100, style: { background: "var(--input-bg)", border: "1px solid var(--border)", color: "var(--text)", padding: "6px 10px", borderRadius: 6, width: 80, fontSize: 13, outline: "none" } })
        ),
        React.createElement("button", { onClick: runBatchScore, disabled: batchLoading, style: { ...btnGlow, opacity: batchLoading ? 0.6 : 1 } },
          batchLoading ? "批量分析中..." : "一键全量匹配"
        ),
        batchLoading ? React.createElement("div", { style: { marginTop: 14, maxWidth: 460 } },
          React.createElement("div", { style: { display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 7, fontSize: 12, color: "var(--text-dim)" } },
            React.createElement("span", null, "正在批量匹配岗位"),
            React.createElement("span", null, "读取岗位 · 逐岗评分 · 筛选结果 · 保存")
          ),
          React.createElement("div", { style: { height: 6, overflow: "hidden", borderRadius: 999, background: "var(--brand-soft)" } },
            React.createElement("div", { style: { width: "42%", height: "100%", borderRadius: "inherit", background: "linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent)", animation: "parseProgressFlow 1.35s ease-in-out infinite" } })
          )
        ) : null,
        batchResult ? React.createElement("div", { style: { marginTop: 20 } },
          React.createElement("h3", { style: { fontSize: 18, marginBottom: 4 } }, "批量匹配完成"),
          React.createElement("p", { style: { color: "var(--text-dim)", fontSize: 13 } }, "共 " + batchResult.total + " 个岗位"),
          React.createElement("div", { style: { display: "flex", gap: 12, margin: "16px 0" } },
            React.createElement("div", { onClick: () => setBatchShowHi(true), style: { flex: 1, padding: 16, background: batchShowHi ? "rgba(0,255,0,0.1)" : "rgba(0,255,0,0.04)", border: "1px solid " + (batchShowHi ? "rgba(0,255,0,0.3)" : "var(--border)"), borderRadius: 12, textAlign: "center", cursor: "pointer" } },
              React.createElement("div", { style: { fontSize: 36, fontWeight: 800, color: "var(--success)" } }, batchResult.jobs.filter(j => (j.match_score || 0) >= batchTh).length),
              React.createElement("div", { style: { color: "var(--text-dim)", fontSize: 12, marginTop: 4 } }, ">= " + batchTh + "分")
            ),
            React.createElement("div", { onClick: () => setBatchShowHi(false), style: { flex: 1, padding: 16, background: !batchShowHi ? "rgba(255,64,129,0.08)" : "rgba(255,64,129,0.04)", border: "1px solid " + (!batchShowHi ? "rgba(255,64,129,0.3)" : "var(--border)"), borderRadius: 12, textAlign: "center", cursor: "pointer" } },
              React.createElement("div", { style: { fontSize: 36, fontWeight: 800, color: "var(--danger)" } }, batchResult.jobs.filter(j => (j.match_score || 0) < batchTh).length),
              React.createElement("div", { style: { color: "var(--text-dim)", fontSize: 12, marginTop: 4 } }, "< " + batchTh + "分")
            )
          ),
          React.createElement("div", { style: { maxHeight: "40vh", overflowY: "auto" } },
            batchResult.jobs
              .map((j, origIdx) => ({ ...j, _origIdx: origIdx }))
              .filter(j => batchShowHi ? (j.match_score || 0) >= batchTh : (j.match_score || 0) < batchTh)
              .map((j, i) => {
                const sc2 = j.match_score || 0;
                const cc2 = sc2 >= 75 ? "var(--success)" : sc2 >= 50 ? "var(--warning)" : "var(--danger)";
                return React.createElement("div", { key: (j.job_id || j._origIdx) + "-" + i, style: { display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--border)" } },
                  React.createElement("div", { style: { minWidth: 40, height: 40, borderRadius: "50%", background: cc2, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 800, color: "var(--accent-fg)" } }, sc2),
                  React.createElement("div", { style: { flex: 1, minWidth: 0 } },
                    React.createElement("div", { style: { fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" } },
                      React.createElement("span", null, j.title || ""),
                      j.restriction_report?.summary?.red > 0 ? React.createElement("span", {
                        style: { padding: "1px 7px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: "var(--danger-soft)", color: "var(--danger)", border: "1px solid var(--danger-border)" }
                      }, `🔴 踩雷 ${j.restriction_report.summary.red}`) : null,
                      j.restriction_report?.summary?.red === 0 && j.restriction_report?.summary?.green > 0 ? React.createElement("span", {
                        style: { padding: "1px 7px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: "var(--success-soft)", color: "var(--success)" }
                      }, `🟢 符合 ${j.restriction_report.summary.green}`) : null,
                      j.restriction_report?.summary?.red === 0 && j.restriction_report?.summary?.green === 0 && j.restriction_report?.summary?.yellow > 0 ? React.createElement("span", {
                        style: { padding: "1px 7px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: "var(--warning-soft)", color: "var(--warning)" }
                      }, `🟡 待确认 ${j.restriction_report.summary.yellow}`) : null
                    ),
                    React.createElement("div", { style: { fontSize: 11, color: "var(--text-dim)" } }, (j.company || "") + " - " + (j.salary || "") + " - " + (j.location || ""))
                  ),
                  batchFile ? React.createElement("button", {
                    type: "button",
                    onClick: () => jumpToPrecisionOptimize({ batchId: batchFile, resumeFile: batchResume, job: j, jobIndex: j._origIdx }),
                    style: { background: "var(--accent2-soft)", border: "1px solid var(--accent2-border)", color: "var(--accent2)", padding: "5px 11px", borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: "pointer", flexShrink: 0 }
                  }, "🎯 精准优化") : null
                );
              })
          )
        ) : null
      )
    );
  };

  // ── Step 6: Precision Optimize State ──
  const [pJobsFile, setPJobsFile] = React.useState("");
  const [pResume, setPResume] = React.useState("");
  const [pTh, setPTh] = React.useState(70);
  const [pJobs, setPJobs] = React.useState([]);
  const [pChecked, setPChecked] = React.useState([]);
  const [pResult, setPResult] = React.useState(null);
  const [pLoading, setPLoading] = React.useState(false);
  const [pFilesForStep6, setPFilesForStep6] = React.useState([]);
  const [pOverwritten, setPOverwritten] = React.useState(false);
  const [pOverwriteInfo, setPOverwriteInfo] = React.useState(null);
  const [pRecheckLoading, setPRecheckLoading] = React.useState(false);
  const [pRecheckResult, setPRecheckResult] = React.useState(null);

  const FIELD_LABELS = {
    summary: "自我评价",
    desired_position: "目标岗位",
    skills: "技能排序",
    work_experience: "工作/实习经历",
    project_experience: "项目经历",
    practical_experience: "个人实践",
    campus_experience: "校园经历",
    research_experience: "科研经历",
  };

  React.useEffect(() => { if (activeStep === 6) { loadPFiles(); } }, [activeStep]);

  const loadPFiles = async () => {
    try { const r = await fetch(`${API_BASE}/api/jobs/list`); const d = await r.json(); setPFilesForStep6(d.files || []); } catch {}
  };

  const jumpToPrecisionOptimize = async ({ batchId, resumeFile, job, jobIndex }) => {
    const targetBatch = String(batchId || "").trim();
    const targetResume = String(
      resumeFile || pResume || batchResume || sResume || (resumes[0]?.filename || "")
    ).trim();
    if (!targetBatch) {
      setStatusMsg("未找到可跳转的岗位批次");
      return;
    }
    setActiveStep(6);
    setPJobsFile(targetBatch);
    if (targetResume) setPResume(targetResume);
    setPResult(null);
    setPOverwritten(false);
    setPOverwriteInfo(null);
    setPRecheckResult(null);
    setPLoading(true);
    setStatusMsg("正在精准定位目标岗位并同步到步骤 6...");
    loadPFiles();
    try {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {}
    try {
      const r = await fetch(`${API_BASE}/api/jobs/detail/${encodeURIComponent(targetBatch)}`);
      const d = await r.json();
      if (d.ok && d.data && Array.isArray(d.data.jobs)) {
        const indexed = d.data.jobs.map((item, origIdx) => ({ ...item, _origIdx: origIdx }));
        const targetJobId = String(job?.job_id || "").trim();
        let targetItem = null;
        if (targetJobId) {
          targetItem = indexed.find((it) => String(it.job_id || "").trim() === targetJobId) || null;
        }
        if (!targetItem && typeof jobIndex === "number" && jobIndex >= 0 && jobIndex < indexed.length) {
          targetItem = indexed[jobIndex];
        }
        if (targetItem) {
          const ordered = [targetItem, ...indexed.filter((it) => it._origIdx !== targetItem._origIdx)];
          setPJobs(ordered);
          setPChecked([String(targetItem._origIdx)]);
          const label = `${targetItem.title || "目标岗位"}${targetItem.company ? " @ " + targetItem.company : ""}`;
          setStatusMsg(
            targetResume
              ? `已定位「${label}」（已自动选中批次与简历并勾选该岗位，点击下方「开始精准优化」即可）`
              : `已定位「${label}」，请先在上方选择一份简历后点击「开始精准优化」`
          );
        } else {
          setPJobs(indexed);
          setPChecked(indexed.length ? [String(indexed[0]._origIdx)] : []);
          setStatusMsg("已加载对应批次岗位，请勾选目标岗位后点击「开始精准优化」");
        }
      } else {
        setStatusMsg(d.error || "读取目标岗位批次失败");
      }
    } catch (e) {
      setStatusMsg("跳转加载岗位出错: " + e.message);
    } finally {
      setPLoading(false);
    }
  };

  const loadPrecisionJobs = async () => {
    if (!pJobsFile || !pResume) { setStatusMsg("请先选择采集记录和简历"); return; }
    setPLoading(true);
    setPResult(null);
    setPOverwritten(false);
    setPOverwriteInfo(null);
    setPRecheckResult(null);
    try {
      const r = await fetch(`${API_BASE}/api/jobs/batch-score-json`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jobs_file: pJobsFile, resume_file: pResume, threshold: pTh }) });
      const d = await r.json();
      if (d.ok) {
        const filtered = (d.jobs || [])
          .map((j, origIdx) => ({ ...j, _origIdx: origIdx }))
          .filter(j => (j.match_score || 0) >= pTh);
        setPJobs(filtered);
        setPChecked(filtered.map(j => String(j._origIdx)));
        setStatusMsg("已加载 " + filtered.length + " 个岗位 (>= " + pTh + "分)");
      } else { setStatusMsg(d.error || "加载失败"); }
    } catch(e) { setStatusMsg(e.message); }
    setPLoading(false);
  };

  const toggleAll = (checked) => {
    if (checked) setPChecked(pJobs.map(j => String(j._origIdx)));
    else setPChecked([]);
  };

  const [pMode, setPMode] = React.useState("batch");
  const [pCustomTarget, setPCustomTarget] = React.useState("");
  const [pCustomJd, setPCustomJd] = React.useState("");
  const [pIntensity, setPIntensity] = React.useState("balanced");

  const runPrecisionOptimize = async () => {
    if (!pResume) { setStatusMsg("请先选择简历"); return; }
    if (pMode === "jd") {
      if (!pCustomJd.trim() || pCustomJd.trim().length < 20) {
        setStatusMsg("请粘贴完整的目标岗位 JD（至少 20 字）");
        return;
      }
    } else if (pChecked.length === 0) {
      setStatusMsg("请至少勾选一个岗位");
      return;
    }
    setPLoading(true);
    setPResult(null);
    setPOverwritten(false);
    setPOverwriteInfo(null);
    setPRecheckResult(null);
    try {
      const fd = new FormData();
      fd.append("resume_file", pResume);
      fd.append("intensity", pIntensity);
      if (pMode === "jd") {
        fd.append("custom_jd", pCustomJd.trim());
        fd.append("custom_target", pCustomTarget.trim());
      } else {
        fd.append("jobs_file", pJobsFile);
        fd.append("job_indices", pChecked.join(","));
      }
      const r = await fetch(`${API_BASE}/api/resume/precision-optimize`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) { setPResult(d); setStatusMsg("优化完成，核对下方内容后可点击「覆盖简历」写入数据库"); }
      else { setStatusMsg(d.error || "优化失败"); }
    } catch(e) { setStatusMsg(e.message); }
    setPLoading(false);
  };

  const overwritePrecision = async () => {
    if (!pResult || !pResult.resume_file) { alert("无结果"); return; }
    if (!confirm("确定将本次精准优化结果覆盖写入数据库？原始底稿仍会保留在版本历史中。")) return;
    try {
      const fd = new FormData();
      fd.append("resume_file", pResult.resume_file);
      fd.append("optimized_summary", pResult.optimized_summary || "");
      fd.append("optimized_projects", JSON.stringify(pResult.optimized_projects || []));
      fd.append("optimized_internships", JSON.stringify(pResult.optimized_work_experience || []));
      fd.append("enhanced_skills", JSON.stringify(pResult.enhanced_skills || []));
      fd.append("target", pResult.target_position || "");
      if (pResult.optimized_resume && typeof pResult.optimized_resume === "object") {
        fd.append("optimized_resume", JSON.stringify(pResult.optimized_resume));
      }
      const r = await fetch(`${API_BASE}/api/resume/overwrite`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) {
        const changedFields = Array.isArray(d.changed_fields) ? d.changed_fields : [];
        const actionableWarnings = (d.optimization_warnings || []).filter(w => w && w.code !== "HUMAN_REVIEW_REQUIRED");
        await syncAfterResumeOverwrite(pResult.resume_file);
        setPOverwritten(true);
        setPRecheckResult(null);
        setPOverwriteInfo({
          changedFields,
          warnings: actionableWarnings,
          savedAt: d.profile_summary?.parsed_at || "",
        });
        if (changedFields.length > 0) {
          const labels = changedFields.map(f => FIELD_LABELS[f] || f).join("、");
          setStatusMsg(`已覆盖写入数据库（更新：${labels}），可点击下方「重新检测匹配度」查看前后分数变化`);
        } else {
          setStatusMsg("版本已记录，但正文与覆盖前无差异（可能因事实护栏保留了原文），可检查下方提示");
        }
      } else {
        setStatusMsg("覆盖失败: " + (d.error || "未知错误"));
      }
    } catch(e) { setStatusMsg("覆盖出错: " + e.message); }
  };

  const recheckPrecisionMatch = async () => {
    if (!pResult || !pResult.resume_file) return;
    // 自定义粘贴任意 JD 模式：直接调用单岗 JD 匹配复测
    if (pMode === "jd" || (!pResult.jobs_file && !pJobsFile)) {
      const jdSource = pCustomJd.trim() || pResult.optimized_resume?._optimization_meta?.job_description || "";
      if (!jdSource) { setStatusMsg("未找到可用于复测的目标 JD 内容"); return; }
      setPRecheckLoading(true);
      setStatusMsg("正在用覆盖后的最新简历重新检测与目标 JD 的匹配度...");
      try {
        const fd = new FormData();
        fd.append("resume_file", pResult.resume_file);
        fd.append("jd_text", jdSource);
        const r = await fetch(`${API_BASE}/api/jd/match`, { method: "POST", body: fd });
        const d = await r.json();
        if (r.ok && d.ok) {
          const score = Number(d.overall_score || 0);
          setPRecheckResult({
            ok: true,
            count: 1,
            avg_before: 0,
            avg_after: score,
            avg_delta: score,
            improved_count: 1,
            items: [{
              index: 0,
              title: pCustomTarget.trim() || pResult.target_position || "自定义目标岗位",
              company: "自定义 JD",
              before_score: 0,
              after_score: score,
              delta: score,
              skill_match: Number(d.skill_match || 0),
              experience_match: Number(d.experience_match || 0),
              education_match: Number(d.education_match || 0),
              after_brief: d.verdict || `技能 ${d.skill_match || 0} / 经验 ${d.experience_match || 0} / 学历 ${d.education_match || 0}`,
            }],
          });
          setStatusMsg(`复测完成：覆盖后最新简历与该 JD 匹配度为 ${score} 分（${d.verdict || "已完成评估"}）`);
        } else {
          setStatusMsg("重新检测失败: " + (d.error || "未知错误"));
        }
      } catch (e) {
        setStatusMsg("重新检测出错: " + e.message);
      }
      setPRecheckLoading(false);
      return;
    }
    const targetIndices = (pResult.selected_jobs && pResult.selected_jobs.length > 0)
      ? pResult.selected_jobs.map(j => String(j.index))
      : pChecked;
    if (!targetIndices.length) { setStatusMsg("没有可复测的目标岗位"); return; }
    const beforeScores = {};
    (pResult.selected_jobs || []).forEach(j => {
      beforeScores[String(j.index)] = { before_score: j.before_score || 0, before_brief: j.before_brief || "" };
    });
    if (Object.keys(beforeScores).length === 0) {
      pJobs.forEach(j => {
        if (targetIndices.includes(String(j._origIdx))) {
          beforeScores[String(j._origIdx)] = { before_score: j.match_score || 0, before_brief: j.match_brief || "" };
        }
      });
    }
    setPRecheckLoading(true);
    setStatusMsg("正在用覆盖后的最新简历重新检测与所选 JD 的匹配度与关联性...");
    try {
      const fd = new FormData();
      fd.append("resume_file", pResult.resume_file);
      fd.append("jobs_file", pResult.jobs_file || pJobsFile);
      fd.append("job_indices", targetIndices.join(","));
      fd.append("before_scores", JSON.stringify(beforeScores));
      const r = await fetch(`${API_BASE}/api/resume/precision-recheck`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) {
        setPRecheckResult(d);
        const byIdx = {};
        (d.items || []).forEach(item => { byIdx[item.index] = item; });
        setPJobs(prev => prev.map(j => byIdx[j._origIdx] ? { ...j, match_score: byIdx[j._origIdx].after_score, match_brief: byIdx[j._origIdx].after_brief } : j));
        const sign = d.avg_delta > 0 ? "+" : "";
        setStatusMsg(`复测完成：平均匹配分 ${d.avg_before} → ${d.avg_after}（${sign}${d.avg_delta}分），${d.improved_count}/${d.count} 个岗位分数提升`);
      } else {
        setStatusMsg("重新检测失败: " + (d.error || "未知错误"));
      }
    } catch(e) {
      setStatusMsg("重新检测出错: " + e.message);
    }
    setPRecheckLoading(false);
  };

  const inspectOverwrittenResume = async () => {
    if (!pResult?.resume_file) return;
    setActiveStep(1);
    await loadResumes();
    await viewResume(pResult.resume_file);
  };

  const copyPrecision = () => {
    if (!pResult) return;
    let text = "";
    if (pResult.target_position) text += "目标岗位: " + pResult.target_position + "\n\n";
    if (pResult.optimized_summary) text += "优化评价:\n" + pResult.optimized_summary + "\n\n";
    if (pResult.optimized_work_experience && pResult.optimized_work_experience.length) {
      pResult.optimized_work_experience.forEach(w => { text += "工作经历: " + (w.position || "") + " @ " + (w.company || "") + "\n" + (w.description || "") + "\n\n"; });
    }
    if (pResult.optimized_projects && pResult.optimized_projects.length) {
      pResult.optimized_projects.forEach(p => { text += "项目: " + (p.name || "") + " (" + (p.role || "") + ")\n" + (p.description || "") + "\n\n"; });
    }
    if (pResult.enhanced_skills) text += "技能: " + pResult.enhanced_skills.join(", ") + "\n";
    navigator.clipboard.writeText(text).then(() => setStatusMsg("已复制到剪贴板"));
  };

  const renderStep6 = () => {
    const actionablePreviewWarnings = (pResult?.optimization_warnings || []).filter(w => w && w.code !== "HUMAN_REVIEW_REQUIRED");
    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "精准简历优化"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 14 } }, "支持从已采集岗位选择，或直接粘贴任意目标岗位 JD 定向重写简历，并支持自由调节改写力度（温度档位）"),
        React.createElement("div", { style: { display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" } },
          React.createElement("button", {
            type: "button",
            onClick: () => setPMode("batch"),
            style: pMode === "batch" ? { ...btnGlow, padding: "6px 14px", fontSize: 12.5 } : { ...btnOutline2, padding: "6px 14px", fontSize: 12.5 }
          }, "从已采集岗位中选择"),
          React.createElement("button", {
            type: "button",
            onClick: () => setPMode("jd"),
            style: pMode === "jd" ? { ...btnGlow, padding: "6px 14px", fontSize: 12.5 } : { ...btnOutline2, padding: "6px 14px", fontSize: 12.5 }
          }, "直接粘贴任意岗位 JD")
        ),
        React.createElement("div", { style: { marginBottom: 12, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" } },
          React.createElement("span", { style: { fontSize: 12.5, color: "var(--text-dim)", fontWeight: 600 } }, "改写力度（温度）："),
          [
            { id: "mild", label: "🌱 微调档 (0.25)" },
            { id: "balanced", label: "⚖️ 均衡档 (0.55·推荐)" },
            { id: "aggressive", label: "🔥 激进档 (0.85)" },
          ].map((st) => React.createElement("button", {
            key: st.id,
            type: "button",
            onClick: () => setPIntensity(st.id),
            style: {
              padding: "5px 12px",
              borderRadius: 999,
              fontSize: 12,
              fontWeight: pIntensity === st.id ? 600 : 500,
              cursor: "pointer",
              background: pIntensity === st.id ? "var(--brand-soft)" : "var(--bg-inset)",
              color: pIntensity === st.id ? "var(--brand)" : "var(--text-secondary)",
              border: `1px solid ${pIntensity === st.id ? "var(--brand-border)" : "var(--border)"}`,
            }
          }, st.label))
        ),
        pMode === "batch" ? React.createElement("div", { style: { marginBottom: 12, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" } },
          React.createElement("select", { value: pJobsFile, onChange: e => setPJobsFile(e.target.value), style: { ...selectStyle, maxWidth: 200 } },
            React.createElement("option", { value: "" }, "选择采集记录..."),
            pFilesForStep6.map((f, i) => React.createElement("option", { key: f.filename, value: f.filename }, "第" + (pFilesForStep6.length - i) + "次采集 (" + (f.count || 0) + "岗) - " + ((f.keywords && f.keywords[0]) ? f.keywords[0] : "未知")))
          ),
          React.createElement("select", { value: pResume, onChange: e => setPResume(e.target.value), style: { ...selectStyle, maxWidth: 180 } },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, formatResumeLabel(x)))
          ),
          React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, "阈值:"),
          React.createElement("input", { type: "number", value: pTh, onChange: e => setPTh(parseInt(e.target.value) || 70), min: 0, max: 100, style: { background: "var(--input-bg)", border: "1px solid var(--border)", color: "var(--text)", padding: "6px 10px", borderRadius: 6, width: 70, fontSize: 13, outline: "none" } }),
          React.createElement("button", { onClick: loadPrecisionJobs, style: { ...btnGlow, fontSize: 13, padding: "8px 20px" } }, "加载岗位")
        ) : React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 10, flexWrap: "wrap" } },
            React.createElement("select", { value: pResume, onChange: e => setPResume(e.target.value), style: { ...selectStyle, maxWidth: 220 } },
              React.createElement("option", { value: "" }, "选择简历..."),
              resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, formatResumeLabel(x)))
            ),
            React.createElement("input", {
              value: pCustomTarget,
              onChange: e => setPCustomTarget(e.target.value),
              placeholder: "目标岗位名称（选填，如：AI 产品经理）",
              style: { ...inputStyle, flex: 1, minWidth: 200, maxWidth: "100%" }
            })
          ),
          React.createElement("textarea", {
            value: pCustomJd,
            onChange: e => setPCustomJd(e.target.value),
            placeholder: "直接粘贴你想定向冲刺的任意岗位 JD（岗位职责 + 任职要求）...",
            rows: 6,
            style: { ...textareaStyle, marginBottom: 12 }
          }),
          React.createElement("button", {
            type: "button",
            onClick: runPrecisionOptimize,
            disabled: pLoading,
            style: { ...btnGlow, opacity: pLoading ? 0.6 : 1 }
          }, pLoading ? "⏳ AI 正在按 JD 精准重写简历..." : "🎯 开始按此 JD 精准优化")
        ),

        statusMsg ? React.createElement("p", { style: { ...statusStyle, color: statusMsg.includes("失败") || statusMsg.includes("出错") ? "var(--danger)" : statusMsg.includes("已加载") || statusMsg.includes("已定位") || statusMsg.includes("完成") || statusMsg.includes("覆盖") || statusMsg.includes("复制") || statusMsg.includes("复测") ? "var(--accent)" : "var(--text-dim)" } }, statusMsg) : null,

        pMode === "batch" && pJobs.length > 0 ? React.createElement("div", { style: { marginTop: 16 } },
          React.createElement("div", { style: { marginBottom: 8, display: "flex", alignItems: "center", gap: 8 } },
            React.createElement("label", { style: { fontSize: 12, color: "var(--text-dim)", cursor: "pointer" } },
              React.createElement("input", { type: "checkbox", checked: pChecked.length === pJobs.length, onChange: e => toggleAll(e.target.checked), style: { accentColor: "var(--accent)" } }),
              " 全选 (" + pChecked.length + "/" + pJobs.length + ")"
            )
          ),
          React.createElement("div", { style: { maxHeight: "30vh", overflowY: "auto", marginBottom: 16 } },
            pJobs.map((j, i) => {
              const hasScore = typeof j.match_score === "number";
              const sc2 = hasScore ? j.match_score : null;
              const cc2 = !hasScore ? "var(--text-muted)" : sc2 >= 75 ? "var(--success)" : sc2 >= 50 ? "var(--warning)" : "var(--danger)";
              const idxKey = String(j._origIdx);
              return React.createElement("div", { key: idxKey + "-" + i, style: { display: "flex", alignItems: "center", gap: 8, padding: "8px 0", borderBottom: "1px solid var(--border)" } },
                React.createElement("input", { type: "checkbox", value: idxKey, checked: pChecked.includes(idxKey), onChange: e => { if (e.target.checked) setPChecked([...pChecked, idxKey]); else setPChecked(pChecked.filter(v => v !== idxKey)); }, style: { accentColor: "var(--accent)" } }),
                React.createElement("span", { style: { minWidth: 34, height: 24, padding: "0 6px", borderRadius: 12, background: cc2, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "var(--accent-fg)" } }, hasScore ? sc2 : "待评"),
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
          React.createElement("h3", { style: { color: "var(--success)", marginBottom: 12 } }, "精准优化完成（已过事实护栏，所见即所存）"),
          pResult.target_position ? React.createElement("p", null, React.createElement("b", null, "目标岗位: "), pResult.target_position) : null,
          pResult.optimized_summary ? React.createElement("p", { style: { marginTop: 8, lineHeight: 1.65 } }, React.createElement("b", null, "优化评价:"), React.createElement("br", null), React.createElement("span", { style: { color: "var(--text-dim)" } }, pResult.optimized_summary)) : null,
          pResult.enhanced_skills && pResult.enhanced_skills.length ? React.createElement("p", { style: { marginTop: 8 } }, React.createElement("b", null, "技能排序: "), pResult.enhanced_skills.join(", ")) : null,
          pResult.optimized_work_experience && pResult.optimized_work_experience.length ? React.createElement("div", { style: { marginTop: 10 } },
            React.createElement("b", null, "工作/实习经历:"),
            pResult.optimized_work_experience.map((wk, i) => React.createElement("div", { key: i, style: { marginLeft: 12, marginTop: 6, marginBottom: 6, padding: 8, background: "var(--bg-inset)", borderRadius: 6 } },
              React.createElement("b", null, wk.position || ""), React.createElement("span", { style: { color: "var(--text-dim)" } }, (wk.company ? " @ " + wk.company : "") + (wk.duration ? " (" + wk.duration + ")" : "")),
              React.createElement("br", null), React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12, whiteSpace: "pre-wrap" } }, wk.description || "")
            ))
          ) : null,
          pResult.optimized_projects && pResult.optimized_projects.length ? React.createElement("div", { style: { marginTop: 10 } },
            React.createElement("b", null, "项目经历:"),
            pResult.optimized_projects.map((pj, i) => React.createElement("div", { key: i, style: { marginLeft: 12, marginTop: 6, marginBottom: 6, padding: 8, background: "var(--bg-inset)", borderRadius: 6 } },
              React.createElement("b", null, pj.name || ""), React.createElement("span", { style: { color: "var(--text-dim)" } }, pj.role ? " (" + pj.role + ")" : ""),
              React.createElement("br", null), React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12, whiteSpace: "pre-wrap" } }, pj.description || "")
            ))
          ) : null,
          pResult.optimization_notes ? React.createElement("p", { style: { marginTop: 8, color: "var(--accent2)", fontSize: 12 } }, "优化建议：", pResult.optimization_notes) : null,
          actionablePreviewWarnings.length > 0 ? React.createElement("div", { style: { marginTop: 10, padding: "8px 12px", borderRadius: 8, background: "var(--warning-soft)", border: "1px solid var(--warning-border)", fontSize: 12, color: "var(--warning)" } },
            React.createElement("b", null, "事实护栏提醒："),
            actionablePreviewWarnings.map((w, wi) => React.createElement("div", { key: wi, style: { marginTop: 3 } }, "• " + (w.message || w.code)))
          ) : null,

          React.createElement("div", { style: { marginTop: 16, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" } },
            React.createElement("button", { onClick: overwritePrecision, style: { ...btnGlow } }, pOverwritten ? "✓ 重新覆盖简历" : "💾 覆盖简历并写入数据库"),
            pOverwritten ? React.createElement("button", {
              onClick: recheckPrecisionMatch,
              disabled: pRecheckLoading,
              style: { ...btnGlow, background: "var(--teal)", opacity: pRecheckLoading ? 0.6 : 1 }
            }, pRecheckLoading ? "⏳ 正在重新检测匹配度..." : "🔍 重新检测匹配度（对比覆盖前后）") : null,
            pOverwritten ? React.createElement("button", { onClick: inspectOverwrittenResume, style: { ...btnOutline2 } }, "📄 查看已覆盖简历") : null,
            React.createElement("button", {
              type: "button",
              disabled: interviewLoading,
              onClick: () => {
                const firstIdx = (pResult.selected_jobs && pResult.selected_jobs.length > 0)
                  ? Number(pResult.selected_jobs[0].index)
                  : Number(pChecked[0] ?? 0);
                jumpToInterviewStep({
                  resumeFile: pResult.resume_file || pResume,
                  jobsFileInput: pResult.jobs_file || pJobsFile,
                  jobIndexInput: Number.isNaN(firstIdx) ? 0 : firstIdx,
                  targetPosition: pResult.target_position || "",
                });
              },
              style: { ...btnGlow, background: "linear-gradient(135deg, var(--accent2), var(--brand))", opacity: interviewLoading ? 0.6 : 1 }
            }, interviewLoading ? "⏳ 正在生成模拟面试追问..." : "🎤 生成模拟面试追问"),
            React.createElement("button", { onClick: copyPrecision, style: { ...btnOutline2 } }, "复制结果")
          ),
          renderInterviewPrepCard(),

          pOverwriteInfo ? React.createElement("div", { style: { marginTop: 14, padding: "10px 14px", borderRadius: 10, background: pOverwriteInfo.changedFields.length > 0 ? "var(--success-soft)" : "var(--warning-soft)", border: "1px solid " + (pOverwriteInfo.changedFields.length > 0 ? "var(--success-border, var(--border))" : "var(--warning-border)"), fontSize: 12.5, lineHeight: 1.6 } },
            React.createElement("div", { style: { fontWeight: 600, color: pOverwriteInfo.changedFields.length > 0 ? "var(--success)" : "var(--warning)" } },
              pOverwriteInfo.changedFields.length > 0
                ? `✅ 已同步写入数据库与简历库（更新字段：${pOverwriteInfo.changedFields.map(f => FIELD_LABELS[f] || f).join("、")}）`
                : "⚠️ 版本已保存，但正文未检测到字段变化"
            ),
            pOverwriteInfo.savedAt ? React.createElement("div", { style: { fontSize: 11.5, color: "var(--text-dim)", marginTop: 2 } }, `写入时间：${pOverwriteInfo.savedAt} · 建议点击上方「重新检测匹配度」验证覆盖后分数与关联性是否提升`) : null
          ) : null,

          pRecheckResult ? React.createElement("div", { style: { marginTop: 16, padding: "16px 18px", borderRadius: 12, background: "var(--bg-inset)", border: "1.5px solid var(--brand-border)" } },
            React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 14 } },
              React.createElement("div", null,
                React.createElement("div", { style: { fontSize: 15, fontWeight: 700, color: "var(--text)" } }, "📊 覆盖前后 JD 匹配度与关联性复测对比"),
                React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginTop: 2 } }, `基于覆盖后最新简历（${pRecheckResult.resume_updated_at || "刚更新"}）逐岗重新评估`)
              ),
              React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 10 } },
                React.createElement("span", { style: { fontSize: 13, color: "var(--text-secondary)" } }, `平均分 ${pRecheckResult.avg_before} → `),
                React.createElement("span", { style: { fontSize: 18, fontWeight: 800, color: "var(--brand)" } }, `${pRecheckResult.avg_after}分`),
                React.createElement("span", {
                  style: {
                    padding: "3px 10px",
                    borderRadius: 999,
                    fontSize: 12,
                    fontWeight: 700,
                    background: pRecheckResult.avg_delta > 0 ? "var(--success-soft)" : pRecheckResult.avg_delta < 0 ? "var(--danger-soft)" : "var(--bg-card)",
                    color: pRecheckResult.avg_delta > 0 ? "var(--success)" : pRecheckResult.avg_delta < 0 ? "var(--danger)" : "var(--text-dim)",
                    border: "1px solid var(--border)",
                  }
                }, pRecheckResult.avg_delta > 0 ? `+${pRecheckResult.avg_delta} 分 ↗` : pRecheckResult.avg_delta < 0 ? `${pRecheckResult.avg_delta} 分 ↘` : "持平 (0)")
              )
            ),
            React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 10 } },
              (pRecheckResult.items || []).map((item, idx) => {
                const delta = item.score_delta || 0;
                const deltaText = delta > 0 ? `+${delta}分 ↗` : delta < 0 ? `${delta}分 ↘` : "持平";
                const deltaColor = delta > 0 ? "var(--success)" : delta < 0 ? "var(--danger)" : "var(--text-dim)";
                return React.createElement("div", { key: idx, style: { padding: "12px 14px", borderRadius: 10, background: "var(--bg-card)", border: "1px solid var(--border)" } },
                  React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" } },
                    React.createElement("div", null,
                      React.createElement("div", { style: { fontSize: 14, fontWeight: 600, color: "var(--text)" } }, item.title || ""),
                      React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)" } }, `${item.company || ""} · ${item.location || ""} · ${item.salary || "面议"}`)
                    ),
                    React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8 } },
                      React.createElement("span", { style: { fontSize: 12.5, color: "var(--text-dim)" } }, `覆盖前 ${item.before_score}分`),
                      React.createElement("span", { style: { color: "var(--text-muted)" } }, "→"),
                      React.createElement("span", { style: { fontSize: 15, fontWeight: 700, color: "var(--brand)" } }, `覆盖后 ${item.after_score}分`),
                      React.createElement("span", { style: { padding: "2px 8px", borderRadius: 999, fontSize: 11.5, fontWeight: 700, color: deltaColor, background: "var(--bg-inset)", border: "1px solid var(--border)" } }, deltaText)
                    )
                  ),
                  React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8, fontSize: 11.5, color: "var(--text-secondary)" } },
                    React.createElement("span", { style: { padding: "2px 8px", borderRadius: 6, background: "var(--bg-inset)" } }, `技能匹配 ${item.skill_match}分`),
                    React.createElement("span", { style: { padding: "2px 8px", borderRadius: 6, background: "var(--bg-inset)" } }, `经验匹配 ${item.experience_match}分`),
                    React.createElement("span", { style: { padding: "2px 8px", borderRadius: 6, background: "var(--bg-inset)" } }, `学历匹配 ${item.education_match}分`)
                  ),
                  item.after_brief ? React.createElement("div", { style: { marginTop: 8, fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.55 } }, React.createElement("b", null, "覆盖后关联性简评："), item.after_brief) : null,
                  item.weaknesses && item.weaknesses.length ? React.createElement("div", { style: { marginTop: 4, fontSize: 11.5, color: "var(--text-dim)" } }, "仍可加强：" + item.weaknesses.join("；")) : null
                );
              })
            )
          ) : null
        ) : null
      )
    );
  };

  // ── Step 7: AI Mock Interviewer State ──
  const [ivResume, setIvResume] = React.useState("");
  const [ivMode, setIvMode] = React.useState("batch");
  const [ivBatchFiles, setIvBatchFiles] = React.useState([]);
  const [ivBatchFile, setIvBatchFile] = React.useState("");
  const [ivBatchJobs, setIvBatchJobs] = React.useState([]);
  const [ivJobIndex, setIvJobIndex] = React.useState(0);
  const [ivJdText, setIvJdText] = React.useState("");
  const [ivRestrictions, setIvRestrictions] = React.useState("");

  React.useEffect(() => {
    if (activeStep === 7) {
      fetch(`${API_BASE}/api/jobs/list`)
        .then((r) => r.json())
        .then((d) => setIvBatchFiles(d.files || []))
        .catch(() => {});
      if (resumes.length > 0) {
        setIvResume((curr) => curr || resumes[0].filename);
      }
    }
  }, [activeStep, resumes]);

  React.useEffect(() => {
    if (!ivBatchFile) {
      setIvBatchJobs([]);
      return;
    }
    fetch(`${API_BASE}/api/jobs/detail/${encodeURIComponent(ivBatchFile)}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.ok && d.data && Array.isArray(d.data.jobs)) {
          setIvBatchJobs(d.data.jobs);
        } else {
          setIvBatchJobs([]);
        }
      })
      .catch(() => setIvBatchJobs([]));
  }, [ivBatchFile]);

  const jumpToInterviewStep = ({ resumeFile, jdTextInput = "", jobsFileInput = "", jobIndexInput = -1, targetPosition = "", restrictionsInput = "" }) => {
    const resolvedResume = resumeFile || ivResume || (resumes[0]?.filename || "");
    setActiveStep(7);
    if (resolvedResume) setIvResume(resolvedResume);
    if (jobsFileInput) {
      setIvMode("batch");
      setIvBatchFile(jobsFileInput);
      setIvJobIndex(jobIndexInput >= 0 ? jobIndexInput : 0);
    } else if (jdTextInput) {
      setIvMode("jd");
      setIvJdText(jdTextInput);
    }
    if (restrictionsInput) setIvRestrictions(restrictionsInput);
    try {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {}
    runInterviewPrep({
      resumeFile: resolvedResume,
      jdTextInput,
      jobsFileInput,
      jobIndexInput,
      targetPosition,
      restrictionsInput,
    });
  };

  const renderStep7 = () => {
    const selectedJob = ivBatchJobs[ivJobIndex] || null;
    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 8 } }, "🎤 AI 模拟面试官"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16, fontSize: 13 } },
          "结合你的当前简历与目标岗位 JD，生成高频面试追问、立足真实经历的 STAR 参考答法，以及高情商反问面试官清单（绝不虚构经历与数据）。"
        ),
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginBottom: 5 } }, "1. 选择当前简历"),
          React.createElement("select", { value: ivResume, onChange: e => setIvResume(e.target.value), style: selectStyle },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, formatResumeLabel(x)))
          )
        ),
        React.createElement("div", { style: { display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" } },
          React.createElement("button", {
            type: "button",
            onClick: () => setIvMode("batch"),
            style: ivMode === "batch" ? { ...btnGlow, padding: "6px 14px", fontSize: 12.5 } : { ...btnOutline2, padding: "6px 14px", fontSize: 12.5 }
          }, "从已采集岗位中选择"),
          React.createElement("button", {
            type: "button",
            onClick: () => setIvMode("jd"),
            style: ivMode === "jd" ? { ...btnGlow, padding: "6px 14px", fontSize: 12.5 } : { ...btnOutline2, padding: "6px 14px", fontSize: 12.5 }
          }, "直接粘贴任意岗位 JD")
        ),
        ivMode === "batch" ? React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10, marginBottom: 12 } },
          React.createElement("div", null,
            React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginBottom: 5 } }, "2. 选择采集批次"),
            React.createElement("select", {
              value: ivBatchFile,
              onChange: e => { setIvBatchFile(e.target.value); setIvJobIndex(0); },
              style: { ...selectStyle, maxWidth: "100%" }
            },
              React.createElement("option", { value: "" }, "选择采集记录..."),
              ivBatchFiles.map((f, i) => React.createElement("option", { key: f.filename, value: f.filename }, "第" + (ivBatchFiles.length - i) + "次采集 (" + (f.count || 0) + "岗) - " + ((f.keywords && f.keywords[0]) ? f.keywords[0] : "未知")))
            )
          ),
          React.createElement("div", null,
            React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginBottom: 5 } }, "3. 选择目标岗位"),
            React.createElement("select", {
              value: ivJobIndex,
              disabled: ivBatchJobs.length === 0,
              onChange: e => setIvJobIndex(Number(e.target.value) || 0),
              style: { ...selectStyle, maxWidth: "100%" }
            },
              ivBatchJobs.length === 0
                ? React.createElement("option", { value: 0 }, "请先选择采集批次...")
                : ivBatchJobs.map((j, idx) => React.createElement("option", { key: (j.job_id || idx) + "-" + idx, value: idx }, `${idx + 1}. ${j.title || "未知岗位"} @ ${j.company || ""}${typeof j.match_score === "number" ? " (" + j.match_score + "分)" : ""}`))
            )
          )
        ) : React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginBottom: 5 } }, "2. 粘贴目标岗位 JD"),
          React.createElement("textarea", {
            value: ivJdText,
            onChange: e => setIvJdText(e.target.value),
            placeholder: "粘贴你想准备面试的目标岗位描述 (JD)...",
            rows: 5,
            style: textareaStyle
          })
        ),
        React.createElement("div", { style: { marginBottom: 14 } },
          React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginBottom: 5 } }, "个人底线 / 想重点核实的问题（选填，将自然融入反问面试官清单）"),
          React.createElement("input", {
            value: ivRestrictions,
            onChange: e => setIvRestrictions(e.target.value),
            placeholder: "如：双休、五险一金、不接受外包、不接受长期出差",
            style: { ...inputStyle, maxWidth: "100%", fontSize: 13 }
          })
        ),
        React.createElement("button", {
          type: "button",
          disabled: interviewLoading,
          onClick: () => runInterviewPrep({
            resumeFile: ivResume,
            jdTextInput: ivMode === "jd" ? ivJdText.trim() : "",
            jobsFileInput: ivMode === "batch" ? ivBatchFile : "",
            jobIndexInput: ivMode === "batch" ? ivJobIndex : -1,
            targetPosition: ivMode === "batch" && selectedJob ? (selectedJob.title || "") : "",
            restrictionsInput: ivRestrictions.trim(),
          }),
          style: { ...btnGlow, background: "linear-gradient(135deg, var(--accent2), var(--brand))", opacity: interviewLoading ? 0.6 : 1 }
        }, interviewLoading ? "⏳ 正在模拟面试官出题..." : "🎤 生成模拟面试追问（高频题 + STAR 答法）"),
        renderInterviewPrepCard()
      )
    );
  };

  // ── Step 8: Delivery Copy Center (4-in-1) ──
  const [dJobsFile, setDJobsFile] = React.useState("");
  const [dResume, setDResume] = React.useState("");
  const [dTh, setDTh] = React.useState(70);
  const [dDirection, setDDirection] = React.useState("");
  const [dScene, setDScene] = React.useState("greeting");
  const [dTone, setDTone] = React.useState("professional");
  const [dSelectedJob, setDSelectedJob] = React.useState(null);
  const [dGreeting, setDGreeting] = React.useState("");
  const [dCandidates, setDCandidates] = React.useState([]);
  const [dSummary, setDSummary] = React.useState(null);
  const [dLoading, setDLoading] = React.useState(false);
  const [dFilesForStep7, setDFilesForStep7] = React.useState([]);

  // ── Step 9: Job Tracking Board State ──
  const [boardData, setBoardData] = React.useState(null);
  const [boardLoading, setBoardLoading] = React.useState(false);
  const [boardFilter, setBoardFilter] = React.useState("active");

  // ── Topbar: PC Desktop Settings Center Modal (4 Tabs) ──
  const [llmModalOpen, setLlmModalOpen] = React.useState(false);
  const [settingsTab, setSettingsTab] = React.useState("llm");
  const [llmConfig, setLlmConfig] = React.useState(null);
  const [llmForm, setLlmForm] = React.useState({ provider: "zhipu", model: "", api_key: "" });
  const [llmShowKey, setLlmShowKey] = React.useState(false);
  const [llmSaving, setLlmSaving] = React.useState(false);
  const [llmTesting, setLlmTesting] = React.useState(false);
  const [llmNotice, setLlmNotice] = React.useState("");
  const [desktopInfo, setDesktopInfo] = React.useState(null);
  const [desktopMsg, setDesktopMsg] = React.useState("");
  const [copiedAuthorField, setCopiedAuthorField] = React.useState("");
  const [tPdfExporting, setTPdfExporting] = React.useState(false);
  const [tPdfMsg, setTPdfMsg] = React.useState("");
  const [clipboardJdWatch, setClipboardJdWatch] = React.useState(() => {
    const saved = localStorage.getItem("offerforge_clipboard_jd_watch");
    return saved === null ? true : saved === "1";
  });
  const [clipboardJdBanner, setClipboardJdBanner] = React.useState(null);
  const dismissedClipHashRef = React.useRef("");

  const toggleClipboardJdWatch = (enabled) => {
    setClipboardJdWatch(enabled);
    try { localStorage.setItem("offerforge_clipboard_jd_watch", enabled ? "1" : "0"); } catch {}
    if (!enabled) setClipboardJdBanner(null);
  };

  React.useEffect(() => {
    if (!clipboardJdWatch) return undefined;
    const probeClipboard = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/system/clipboard-jd`);
        const d = await r.json();
        if (d && d.ok && d.is_jd && d.hash && d.hash !== dismissedClipHashRef.current) {
          setClipboardJdBanner(d);
        }
      } catch {}
    };
    const onFocus = () => { probeClipboard(); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [clipboardJdWatch]);

  const applyClipboardJdToMatch = () => {
    if (!clipboardJdBanner?.text) return;
    dismissedClipHashRef.current = clipboardJdBanner.hash || "";
    setJdText(clipboardJdBanner.text);
    setClipboardJdBanner(null);
    switchStep(5);
    setStatusMsg("已从剪贴板自动填入岗位 JD，可直接点击「解析JD并匹配」");
  };

  const applyClipboardJdToInterview = () => {
    if (!clipboardJdBanner?.text) return;
    dismissedClipHashRef.current = clipboardJdBanner.hash || "";
    setIvMode("jd");
    setIvJdText(clipboardJdBanner.text);
    setClipboardJdBanner(null);
    switchStep(7);
  };

  const applyClipboardJdToPrecision = () => {
    if (!clipboardJdBanner?.text) return;
    dismissedClipHashRef.current = clipboardJdBanner.hash || "";
    setPMode("jd");
    setPCustomJd(clipboardJdBanner.text);
    setClipboardJdBanner(null);
    switchStep(6);
  };

  const dismissClipboardBanner = () => {
    if (clipboardJdBanner?.hash) dismissedClipHashRef.current = clipboardJdBanner.hash;
    setClipboardJdBanner(null);
  };
  const [prefsForm, setPrefsForm] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("offerforge_user_prefs") || "{}");
      return {
        defaultCity: saved.defaultCity || "",
        defaultSalaryMin: saved.defaultSalaryMin || "",
        defaultSalaryMax: saved.defaultSalaryMax || "",
        defaultIntensity: saved.defaultIntensity || "balanced",
        interviewCount: Number(saved.interviewCount) || 5,
        interviewTemp: Number(saved.interviewTemp) || 0.72,
        modeLabel: saved.modeLabel || "本地模式",
      };
    } catch {
      return {
        defaultCity: "",
        defaultSalaryMin: "",
        defaultSalaryMax: "",
        defaultIntensity: "balanced",
        interviewCount: 5,
        interviewTemp: 0.72,
        modeLabel: "本地模式",
      };
    }
  });
  const [prefsMsg, setPrefsMsg] = React.useState("");

  const exportDirectPdf = async () => {
    if (!tResume) { setTPdfMsg("❌ 请先选择一份目标简历"); return; }
    setTPdfExporting(true);
    setTPdfMsg("⏳ 正在静默渲染 A4 高清 PDF 并定位文件...");
    try {
      const fd = new FormData();
      fd.append("resume_file", tResume);
      fd.append("template_style", tStyle);
      fd.append("open_folder", "true");
      const r = await fetch(`${API_BASE}/api/resume/export-pdf`, { method: "POST", body: fd });
      const d = await r.json();
      if (r.ok && d.ok) {
        setTPdfMsg(`✅ 已直出高清 PDF：${d.filename}（${d.size_kb} KB），已在文件夹中为你高亮定位`);
      } else {
        setTPdfMsg(`❌ ${d.error || "PDF 生成失败"}`);
      }
    } catch (err) {
      setTPdfMsg(`❌ 导出失败：${err.message}`);
    } finally {
      setTPdfExporting(false);
    }
  };

  const normalizeProvider = (d) => {
    const codes = (d?.presets || []).map((p) => p.code);
    return codes.includes(d?.provider) ? d.provider : (codes[0] || "zhipu");
  };

  React.useEffect(() => {
    fetch(`${API_BASE}/api/system/llm-config`)
      .then((r) => r.json())
      .then((d) => {
        if (d && d.ok) {
          setLlmConfig(d);
          setLlmForm({ provider: normalizeProvider(d), model: d.model || "", api_key: "" });
        }
      })
      .catch(() => {});
  }, []);

  const loadDesktopInfo = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/system/desktop-info`);
      const d = await r.json();
      if (d && d.ok) setDesktopInfo(d);
    } catch {}
  };

  const openLlmModal = async (initialTab = "llm") => {
    setSettingsTab(typeof initialTab === "string" ? initialTab : "llm");
    setLlmModalOpen(true);
    setLlmNotice("");
    setDesktopMsg("");
    setPrefsMsg("");
    setLlmShowKey(false);
    loadDesktopInfo();
    try {
      const r = await fetch(`${API_BASE}/api/system/llm-config`);
      const d = await r.json();
      if (d && d.ok) {
        setLlmConfig(d);
        setLlmForm({ provider: normalizeProvider(d), model: d.model || "", api_key: "" });
      }
    } catch {}
  };

  const testLlmConnection = async () => {
    setLlmTesting(true);
    setLlmNotice("⏳ 正在向当前大模型发送连通性探测...");
    try {
      const r = await fetch(`${API_BASE}/api/system/llm-test`, { method: "POST" });
      const d = await r.json();
      if (r.ok && d.ok) {
        setLlmNotice(`✅ 连接成功！${d.provider} / ${d.model} · 响应延迟 ${d.latency_ms} ms`);
      } else {
        setLlmNotice(`❌ ${d.error || "连接测试失败"}`);
      }
    } catch (err) {
      setLlmNotice(`❌ 测试出错：${err.message}`);
    } finally {
      setLlmTesting(false);
    }
  };

  const openLocalFolder = async (target) => {
    setDesktopMsg("");
    try {
      const r = await fetch(`${API_BASE}/api/system/open-folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target }),
      });
      const d = await r.json();
      if (r.ok && d.ok) setDesktopMsg(`✅ 已在资源管理器打开：${d.path}`);
      else setDesktopMsg(`❌ ${d.error || "打开目录失败"}`);
    } catch (err) {
      setDesktopMsg(`❌ ${err.message}`);
    }
  };

  const clearLocalLogs = async () => {
    setDesktopMsg("");
    try {
      const r = await fetch(`${API_BASE}/api/system/clear-logs`, { method: "POST" });
      const d = await r.json();
      if (r.ok && d.ok) {
        setDesktopMsg("✅ 本地运行日志已清空");
        loadDesktopInfo();
      } else {
        setDesktopMsg(`❌ ${d.error || "清理失败"}`);
      }
    } catch (err) {
      setDesktopMsg(`❌ ${err.message}`);
    }
  };

  const saveUserPrefs = () => {
    try {
      localStorage.setItem("offerforge_user_prefs", JSON.stringify(prefsForm));
      if (prefsForm.defaultIntensity) {
        setOptStyle(prefsForm.defaultIntensity);
        setPIntensity(prefsForm.defaultIntensity);
      }
      setPrefsMsg("✅ 自定义偏好已保存并即时生效");
    } catch {
      setPrefsMsg("❌ 偏好保存失败");
    }
  };

  const copyAuthorText = (label, value) => {
    navigator.clipboard?.writeText(value).then(() => {
      setCopiedAuthorField(label);
      setTimeout(() => setCopiedAuthorField(""), 1800);
    }).catch(() => {});
  };

  const saveLlmSettings = async (e) => {
    e.preventDefault();
    setLlmSaving(true);
    setLlmNotice("");
    try {
      const r = await fetch(`${API_BASE}/api/system/llm-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(llmForm),
      });
      const d = await r.json();
      if (r.ok && d.ok) {
        setLlmNotice(`✅ 已保存并切换至 ${d.provider} / ${d.model}（即时生效）`);
        setLlmForm((prev) => ({ ...prev, api_key: "" }));
        const fresh = await fetch(`${API_BASE}/api/system/llm-config`).then((res) => res.json()).catch(() => null);
        if (fresh && fresh.ok) setLlmConfig(fresh);
      } else {
        setLlmNotice(`❌ ${d.error || "保存失败"}`);
      }
    } catch (err) {
      setLlmNotice(`❌ 保存出错: ${err.message}`);
    } finally {
      setLlmSaving(false);
    }
  };

  const loadTrackingBoard = async () => {
    setBoardLoading(true);
    try {
      const r = await fetch(`${API_BASE}/api/jobs/tracking-board`);
      const d = await r.json();
      if (d && d.ok) setBoardData(d);
    } catch {}
    setBoardLoading(false);
  };

  const updateBoardItemStatus = async (item, nextStatus) => {
    try {
      const r = await fetch(`${API_BASE}/api/jobs/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          batch_id: item.batch_id,
          job_id: item.job_id || "",
          job_index: item.job_index,
          status: nextStatus,
          note: item.tracking_note || "",
        }),
      });
      const d = await r.json();
      if (r.ok && d.ok) {
        loadTrackingBoard();
      }
    } catch {}
  };

  const exportTrackingCsv = () => {
    const items = boardData?.items || [];
    if (!items.length) return;
    const statusMap = { unsent: "未投递", sent: "已投递", interview: "一面中", rejected: "不合适" };
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const header = ["状态", "岗位名称", "公司", "城市", "薪资", "匹配分", "来源", "跟进备注", "更新时间", "官方链接"];
    const rows = items.map((it) => [
      statusMap[it.status] || it.status,
      it.title,
      it.company,
      it.location,
      it.salary,
      typeof it.match_score === "number" ? it.match_score : "",
      it.source,
      it.tracking_note,
      it.tracked_at || it.collected_at,
      it.url,
    ].map(esc).join(","));
    const csv = "\uFEFF" + [header.map(esc).join(","), ...rows].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `OfferForge_求职投递看板_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  React.useEffect(() => { if (activeStep === 8) loadDFiles(); }, [activeStep]);
  React.useEffect(() => { if (activeStep === 9) loadTrackingBoard(); }, [activeStep]);

  const loadDFiles = async () => {
    try { const r = await fetch(`${API_BASE}/api/jobs/list`); const d = await r.json(); setDFilesForStep7(d.files || []); } catch {}
  };

  const generateGreeting = async () => {
    if (!dResume) { setStatusMsg("请先选择简历"); return; }
    setDGreeting("AI正在生成..."); setDLoading(true);
    try {
      const fd = new FormData();
      fd.append("resume_file", dResume);
      fd.append("direction", dDirection.trim());
      fd.append("jobs_file", dJobsFile || "");
      fd.append("scene", dScene);
      fd.append("tone", dTone);
      if (dSelectedJob) {
        fd.append("target_job", JSON.stringify({
          title: dSelectedJob.title || "",
          company: dSelectedJob.company || "",
          salary: dSelectedJob.salary || "",
          location: dSelectedJob.location || "",
          tags: dSelectedJob.tags || [],
          description: dSelectedJob.description || "",
        }));
      }
      const r = await fetch(`${API_BASE}/api/deliver/greeting`, { method: "POST", body: fd });
      const d = await r.json();
      if (d.ok) { setDGreeting(d.greeting); setStatusMsg("AI 投递文案已生成"); }
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

  const renderStep8 = () => {
    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      // Main card
      React.createElement("div", { style: { ...card, marginBottom: 20 } },
        React.createElement("h3", { style: { fontSize: 18, fontWeight: 700, marginBottom: 12 } }, "投递开场白 & 精选岗位清单"),
        React.createElement("p", { style: { color: "var(--text-dim)", marginBottom: 16 } }, "按目标岗位一键生成高回复率开场白，并快速打开官方原网页完成投递"),

        // Controls row
        React.createElement("div", { style: { display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap", alignItems: "center" } },
          React.createElement("select", { value: dJobsFile, onChange: e => { setDJobsFile(e.target.value); setDSelectedJob(null); }, style: { ...selectStyle, maxWidth: 200 } },
            React.createElement("option", { value: "" }, "选择采集记录..."),
            dFilesForStep7.map((f, i) => React.createElement("option", { key: f.filename, value: f.filename }, "第" + (dFilesForStep7.length - i) + "次采集 (" + (f.count || 0) + "岗) - " + ((f.keywords && f.keywords[0]) ? f.keywords[0] : "未知")))
          ),
          React.createElement("select", { value: dResume, onChange: e => setDResume(e.target.value), style: { ...selectStyle, maxWidth: 180 } },
            React.createElement("option", { value: "" }, "选择简历..."),
            resumes.map(x => React.createElement("option", { key: x.filename, value: x.filename }, formatResumeLabel(x)))
          ),
          React.createElement("span", { style: { color: "var(--text-dim)", fontSize: 12 } }, "阈值:"),
          React.createElement("input", { type: "number", value: dTh, onChange: e => setDTh(parseInt(e.target.value) || 70), min: 0, max: 100, style: { background: "var(--input-bg)", border: "1px solid var(--border)", color: "var(--text)", padding: "6px 10px", borderRadius: 6, width: 70, fontSize: 13, outline: "none" } }),
          React.createElement("button", { onClick: loadDeliverCandidates, disabled: dLoading, style: { ...btnGlow, fontSize: 13, padding: "8px 20px" } }, "筛选")
        ),

        statusMsg ? React.createElement("p", { style: { ...statusStyle, color: statusMsg.includes("失败") || statusMsg.includes("错误") ? "var(--danger)" : statusMsg.includes("生成") || statusMsg.includes("复制") ? "var(--accent)" : "var(--text-dim)" } }, statusMsg) : null,

        // AI Copy Center (4-in-1)
        React.createElement("div", { style: { marginTop: 16, padding: "16px 0", borderTop: "1px solid var(--border)" } },
          React.createElement("h4", { style: { fontSize: 14.5, fontWeight: 700, marginBottom: 10 } }, "✨ AI 求职沟通文案中心（4 大场景一键生成）"),
          React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 } },
            [
              { id: "greeting", label: "💬 平台打招呼开场白" },
              { id: "cover_letter", label: "📧 邮箱自荐信 (Cover Letter)" },
              { id: "referral", label: "🤝 高情商求内推话术" },
              { id: "followup", label: "📩 面试感谢 / 进度跟进" },
            ].map((sc) => React.createElement("button", {
              key: sc.id,
              type: "button",
              onClick: () => setDScene(sc.id),
              style: dScene === sc.id
                ? { ...btnGlow, padding: "6px 12px", fontSize: 12 }
                : { ...btnOutline2, padding: "6px 12px", fontSize: 12 }
            }, sc.label))
          ),
          React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 10 } },
            React.createElement("span", { style: { fontSize: 12, color: "var(--text-dim)" } }, "语气风格："),
            [
              { id: "professional", label: "专业精炼" },
              { id: "warm", label: "热情主动" },
              { id: "concise", label: "大厂干练" },
            ].map((tn) => React.createElement("button", {
              key: tn.id,
              type: "button",
              onClick: () => setDTone(tn.id),
              style: {
                padding: "3px 10px",
                borderRadius: 999,
                fontSize: 11.5,
                cursor: "pointer",
                background: dTone === tn.id ? "var(--brand-soft)" : "var(--bg-inset)",
                color: dTone === tn.id ? "var(--brand)" : "var(--text-secondary)",
                border: `1px solid ${dTone === tn.id ? "var(--brand-border)" : "var(--border)"}`,
              }
            }, tn.label))
          ),
          dSelectedJob ? React.createElement("div", {
            style: { marginBottom: 10, padding: "8px 12px", borderRadius: 8, background: "var(--accent2-soft)", border: "1px solid var(--accent2-border)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap", fontSize: 12.5 }
          },
            React.createElement("span", { style: { color: "var(--text)" } },
              "🎯 ",
              React.createElement("b", { style: { color: "var(--accent2)" } }, `已锁定目标 JD：${dSelectedJob.title || ""}${dSelectedJob.company ? " @ " + dSelectedJob.company : ""}`),
              "（点击生成将精准对照此岗位 JD 专项撰写）"
            ),
            React.createElement("button", {
              type: "button",
              onClick: () => setDSelectedJob(null),
              style: { background: "transparent", border: "none", color: "var(--text-dim)", cursor: "pointer", fontSize: 12 }
            }, "✕ 取消锁定")
          ) : null,
          React.createElement("div", { style: { marginBottom: 8 } },
            React.createElement("input", { value: dDirection, onChange: e => setDDirection(e.target.value), placeholder: "投递方向 / 目标公司或面试阶段（如：腾讯 AI产品经理，刚结束一面）", style: { ...inputStyle, maxWidth: "100%", width: "100%" } })
          ),
          React.createElement("div", { style: { display: "flex", gap: 8 } },
            React.createElement("button", { onClick: generateGreeting, disabled: dLoading, style: { ...btnGlow, fontSize: 13 } }, dLoading ? "⏳ 生成中..." : "✨ 生成文案"),
            React.createElement("button", { onClick: copyGreeting, style: { ...btnOutline2, fontSize: 13 } }, "📋 复制文案")
          ),
          dGreeting ? React.createElement("textarea", { value: dGreeting, readOnly: true, rows: dScene === "cover_letter" ? 8 : 5, style: { ...textareaStyle, marginTop: 12, color: dGreeting.includes("失败") || dGreeting.includes("错误") ? "var(--danger)" : "var(--text)" } }) : null
        ),

        // Candidates list (always show summary feedback even when 0 jobs meet threshold)
        (dSummary || dCandidates.length > 0) ? React.createElement("div", { style: { marginTop: 16, padding: "16px 0", borderTop: "1px solid var(--border)" } },
          dSummary ? React.createElement("p", { style: { color: dCandidates.length === 0 ? "var(--warning)" : "var(--text-dim)", fontSize: 12.5, marginBottom: 12, fontWeight: dCandidates.length === 0 ? 600 : 400 } },
            dCandidates.length === 0
              ? `共 ${dSummary.total_jobs} 个岗位，当前暂无 >= ${dTh} 分的岗位（可把上方阈值调低到 50 再点「筛选」，或先去步骤 5 跑一次全量匹配）`
              : `共 ${dSummary.total_jobs} 个岗位，符合阈值 ${dSummary.candidates} 个（已投递 ${dSummary.already_delivered || 0} 个已排除）`
          ) : null,
          dCandidates.length > 0 ? React.createElement("div", { style: { maxHeight: "45vh", overflowY: "auto" } },
            dCandidates.map((j, i) => {
              const sc = j.match_score || 0;
              const scColor = sc >= 75 ? "var(--success)" : sc >= 50 ? "var(--warning)" : "var(--danger)";
              const isSelected = dSelectedJob && dSelectedJob.title === j.title && dSelectedJob.company === j.company && dSelectedJob.url === j.url;
              return React.createElement("div", { key: i, style: { display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", marginBottom: 6, background: isSelected ? "var(--accent2-soft)" : "var(--bg-inset)", border: `1px solid ${isSelected ? "var(--accent2-border)" : "var(--border)"}`, borderRadius: 10 } },
                React.createElement("div", { style: { minWidth: 42, height: 42, borderRadius: "50%", background: "radial-gradient(circle," + scColor + "33,transparent 70%)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700, color: scColor } }, sc),
                React.createElement("div", { style: { flex: 1, minWidth: 0 } },
                  React.createElement("div", { style: { fontSize: 14, fontWeight: 600, color: "var(--text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, j.title),
                  React.createElement("div", { style: { fontSize: 11, color: "var(--text-dim)" } }, j.company + " - " + (j.salary || "") + " - " + (j.location || ""))
                ),
                React.createElement("button", {
                  type: "button",
                  onClick: () => {
                    setDSelectedJob(j);
                    setDDirection(`${j.company ? j.company + " " : ""}${j.title || ""}`.trim());
                    setStatusMsg(`已锁定「${j.title} @ ${j.company}」，点击上方「✨ 生成文案」即可针对该 JD 专项撰写`);
                  },
                  style: { padding: "5px 11px", borderRadius: 16, background: isSelected ? "var(--accent2)" : "var(--accent2-soft)", border: "1px solid var(--accent2-border)", color: isSelected ? "#fff" : "var(--accent2)", cursor: "pointer", fontSize: 11.5, fontWeight: 600, whiteSpace: "nowrap" }
                }, isSelected ? "✓ 已锁定此岗" : "✨ 针对此岗写文案"),
                j.url ? React.createElement("button", { onClick: () => window.open(j.url, "_blank"), style: { padding: "4px 12px", borderRadius: 6, background: "transparent", border: "1px solid var(--accent)", color: "var(--accent)", cursor: "pointer", fontSize: 11, whiteSpace: "nowrap" } }, "打开详情") : null
              );
            })
          ) : null
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

  const renderStep9 = () => {
    const sum = boardData?.summary || { total: 0, unsent: 0, sent: 0, interview: 0, rejected: 0, applied: 0, interview_rate: 0 };
    const allItems = boardData?.items || [];
    const shownItems = allItems.filter((it) => {
      if (boardFilter === "active") return it.status === "interview" || it.status === "sent";
      if (boardFilter === "all") return true;
      return it.status === boardFilter;
    });
    return React.createElement("div", { style: { animation: "fadeInUp 0.4s ease" } },
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 18 } },
        [
          { label: "累计采集岗位", value: sum.total, color: "var(--brand)" },
          { label: "已投递（含进展）", value: sum.applied, color: "var(--success)" },
          { label: "🔥 面试中", value: sum.interview, color: "var(--warning)" },
          { label: "面试转化率", value: `${sum.interview_rate || 0}%`, color: "var(--accent2)" },
        ].map((kpi, idx) => React.createElement("div", {
          key: idx,
          style: { ...card, padding: "16px 18px", textAlign: "center" }
        },
          React.createElement("div", { style: { fontSize: 28, fontWeight: 800, color: kpi.color } }, kpi.value),
          React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginTop: 4 } }, kpi.label)
        ))
      ),
      React.createElement("div", { style: { ...card } },
        React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 14 } },
          React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap" } },
            [
              { id: "active", label: `重点跟进 (${sum.sent + sum.interview})` },
              { id: "interview", label: `🔥 一面中 (${sum.interview})` },
              { id: "sent", label: `✅ 已投递 (${sum.sent})` },
              { id: "unsent", label: `📝 未投递 (${sum.unsent})` },
              { id: "rejected", label: `⏸ 不合适 (${sum.rejected})` },
              { id: "all", label: `全部 (${sum.total})` },
            ].map((tab) => React.createElement("button", {
              key: tab.id,
              type: "button",
              onClick: () => setBoardFilter(tab.id),
              style: boardFilter === tab.id
                ? { ...btnGlow, padding: "5px 12px", fontSize: 12 }
                : { ...btnOutline2, padding: "5px 12px", fontSize: 12 }
            }, tab.label))
          ),
          React.createElement("div", { style: { display: "flex", gap: 8 } },
            React.createElement("button", { type: "button", onClick: loadTrackingBoard, disabled: boardLoading, style: { ...btnOutline2, padding: "6px 12px", fontSize: 12 } }, boardLoading ? "刷新中..." : "🔄 刷新"),
            React.createElement("button", { type: "button", onClick: exportTrackingCsv, disabled: allItems.length === 0, style: { ...btnGlow, padding: "6px 14px", fontSize: 12, opacity: allItems.length === 0 ? 0.5 : 1 } }, "📥 导出 Excel/CSV")
          )
        ),
        shownItems.length === 0 ? React.createElement("div", { style: { textAlign: "center", padding: "36px 0", color: "var(--text-dim)", fontSize: 13.5 } },
          boardFilter === "active"
            ? "还没有标记「已投递」或「一面中」的岗位，去步骤 4 岗位集市点一下状态即可自动同步到这里！"
            : "该分类下暂无岗位记录"
        ) : React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 10, maxHeight: "55vh", overflowY: "auto" } },
          shownItems.map((it, idx) => React.createElement("div", {
            key: `${it.batch_id}-${it.job_index}-${idx}`,
            style: { padding: "12px 14px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }
          },
            React.createElement("div", { style: { flex: 1, minWidth: 200 } },
              React.createElement("div", { style: { fontSize: 14, fontWeight: 600, color: "var(--text)" } },
                it.title,
                typeof it.match_score === "number" ? React.createElement("span", { style: { marginLeft: 8, padding: "1px 7px", borderRadius: 999, fontSize: 11, background: "var(--brand-soft)", color: "var(--brand)" } }, `${it.match_score}分`) : null
              ),
              React.createElement("div", { style: { fontSize: 12, color: "var(--text-dim)", marginTop: 3 } }, `${it.company} · ${it.location || "未知"} · ${it.salary || "面议"}`),
              it.tracking_note ? React.createElement("div", { style: { fontSize: 12, color: "var(--accent2)", marginTop: 4 } }, `📌 ${it.tracking_note}`) : null
            ),
            React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" } },
              React.createElement("select", {
                value: it.status,
                onChange: (e) => updateBoardItemStatus(it, e.target.value),
                style: { background: "var(--bg-card)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "5px 9px", borderRadius: 16, fontSize: 12, cursor: "pointer" }
              },
                React.createElement("option", { value: "unsent" }, "📝 未投递"),
                React.createElement("option", { value: "sent" }, "✅ 已投递"),
                React.createElement("option", { value: "interview" }, "🔥 一面中"),
                React.createElement("option", { value: "rejected" }, "⏸ 不合适")
              ),
              it.url ? React.createElement("a", {
                href: it.url,
                target: "_blank",
                rel: "noopener noreferrer",
                style: { padding: "5px 10px", borderRadius: 16, fontSize: 12, background: "var(--brand-soft)", color: "var(--brand)", border: "1px solid var(--brand-border)", textDecoration: "none" }
              }, "🔗 原网页") : null
            )
          ))
        )
      )
    );
  };

  const renderContent = () => { switch(activeStep) { case 1: return renderStep1(); case 2: return renderStep2(); case 3: return renderStep3(); case 4: return renderStep4(); case 5: return renderStep5(); case 6: return renderStep6(); case 7: return renderStep7(); case 8: return renderStep8(); case 9: return renderStep9(); default: return renderPlaceholder(activeStep); } };

  const currentStep = steps[activeStep - 1] || steps[0];
  const CurrentIcon = currentStep.Icon;

  return (
    <div id="功能" className="of-shell">
      {/* Desktop / PC Left Sidebar */}
      <aside className="of-sidebar" aria-label="主导航">
        <div className="of-brand">
          <div className="of-brand-mark">OF</div>
          <span className="of-brand-name">OfferForge</span>
          <span className="of-brand-badge">Studio</span>
        </div>

        <nav className="of-nav-scroll">
          {navGroups.map((grp) => (
            <div key={grp.name}>
              <div className="of-nav-group-label">
                <span className="of-group-dot" style={{ background: grp.dot }} />
                {grp.name}
              </div>
              <div className="of-nav-list">
                {steps.filter((s) => s.group === grp.name).map((s) => {
                  const isActive = s.id === activeStep;
                  const IconComp = s.Icon;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => switchStep(s.id)}
                      className={`of-nav-item tone-${s.tone}${isActive ? " active" : ""}`}
                    >
                      <span className="of-nav-item-icon"><IconComp size={16} strokeWidth={1.9} /></span>
                      <span className="of-nav-item-meta">
                        <span className="of-nav-item-title">{s.name}</span>
                        <span className="of-nav-item-sub">{s.detail}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="of-sidebar-footer">
          {(() => {
            const activePreset = (llmConfig?.presets || []).find((p) => p.code === llmConfig?.provider);
            const hasActiveKey = Boolean(activePreset?.has_key);
            const providerTitle = activePreset?.label ? activePreset.label.split(" ")[0] : (llmConfig?.provider || "智谱清言");
            const modelTitle = llmConfig?.model || "glm-4.7";
            return (
              <div
                className="of-engine-card"
                onClick={() => openLlmModal("llm")}
                title="点击切换大模型引擎或自定义工作模式"
                style={{ cursor: "pointer" }}
              >
                <div className="of-engine-row">
                  <span>
                    <span
                      className="of-status-dot"
                      style={{ background: hasActiveKey ? undefined : "var(--warning)" }}
                    />
                    {hasActiveKey ? "AI 引擎就绪" : "待配置 API Key"}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--text-dim)" }}>{prefsForm.modeLabel || "本地模式"}</span>
                </div>
                <div className="of-engine-sub">{`${providerTitle} · ${modelTitle}`}</div>
              </div>
            );
          })()}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="of-main">
        <header className="of-topbar">
          <div className="of-topbar-left">
            <span className="of-topbar-crumb">OfferForge</span>
            <span className="of-topbar-sep">/</span>
            <span className="of-topbar-crumb">{currentStep.group}</span>
            <span className="of-topbar-sep">/</span>
            <span className="of-topbar-title">{currentStep.name}</span>
          </div>

          <div className="of-topbar-right">
            <button
              type="button"
              onClick={() => openLlmModal("llm")}
              title="PC 桌面端设置中心（模型 / 本地工具 / 偏好 / 关于作者）"
              className="of-stat-pill"
              style={{ cursor: "pointer", border: "1px solid var(--border-light)" }}
            >
              <Settings size={13} />
              <span>设置中心</span>
            </button>
            <div className="of-stat-pill">
              <FolderOpen size={13} />
              <span>已解析简历 {resumes.length} 份</span>
            </div>
            <div className="of-theme-switch" role="group" aria-label="界面主题切换">
              <button
                type="button"
                className={`of-theme-btn${theme === "light" ? " active" : ""}`}
                onClick={() => onThemeChange && onThemeChange("light")}
              >
                <Sun size={13} /> 浅色
              </button>
              <button
                type="button"
                className={`of-theme-btn${theme === "dark" ? " active" : ""}`}
                onClick={() => onThemeChange && onThemeChange("dark")}
              >
                <Moon size={13} /> 石墨暗色
              </button>
            </div>
          </div>
        </header>

        <main className="of-workspace">
          {clipboardJdBanner && (
            <div style={{ marginBottom: 14, padding: "11px 16px", borderRadius: 12, background: "var(--brand-soft)", border: "1px solid var(--brand-border)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", animation: "fadeInUp 0.25s ease" }}>
              <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5, minWidth: 220, flex: 1 }}>
                <b style={{ color: "var(--brand)" }}>📋 检测到剪贴板岗位 JD</b>
                <span style={{ color: "var(--text-dim)", marginLeft: 8, fontSize: 12 }}>
                  （命中：{(clipboardJdBanner.signals || []).join(" + ")}）
                </span>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>「{clipboardJdBanner.preview}」</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <button type="button" onClick={applyClipboardJdToMatch} style={{ ...btnGlow, padding: "6px 12px", fontSize: 12 }}>🎯 去匹配评分</button>
                <button type="button" onClick={applyClipboardJdToPrecision} style={{ ...btnOutline2, padding: "6px 12px", fontSize: 12 }}>✨ 去精准优化</button>
                <button type="button" onClick={applyClipboardJdToInterview} style={{ ...btnOutline2, padding: "6px 12px", fontSize: 12 }}>🎤 去模拟面试</button>
                <button type="button" onClick={dismissClipboardBanner} title="忽略本次提示" style={{ background: "transparent", border: "none", color: "var(--text-dim)", fontSize: 18, cursor: "pointer", padding: "0 4px", lineHeight: 1 }}>×</button>
              </div>
            </div>
          )}
          <div className="of-page-header">
            <div className="of-page-header-left">
              <div className={`of-page-icon-tile tone-${currentStep.tone}`}>
                <CurrentIcon size={20} strokeWidth={1.9} />
              </div>
              <div>
                <h1 className="of-page-title">{currentStep.name}</h1>
                <p className="of-page-desc">{currentStep.detail}</p>
              </div>
            </div>
            <span className="of-step-chip">Step 0{currentStep.id} / 0{steps.length}</span>
          </div>
          {renderContent()}
        </main>
      </div>

      {/* Responsive Mobile / Android Bottom Bar */}
      <nav className="of-mobile-nav" aria-label="移动端导航">
        {steps.map((s) => {
          const isActive = s.id === activeStep;
          const IconComp = s.Icon;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => switchStep(s.id)}
              className={`of-mobile-nav-btn${isActive ? " active" : ""}`}
            >
              <IconComp size={16} strokeWidth={1.85} />
              <span>{s.shortName}</span>
            </button>
          );
        })}
      </nav>

      {/* Local Model & API Settings Modal (Desktop-ready) */}
      {llmModalOpen && (
        <div
          onClick={() => setLlmModalOpen(false)}
          style={{ position: "fixed", inset: 0, zIndex: 9999, background: "rgba(15,23,42,0.52)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", maxWidth: 590, maxHeight: "90vh", overflowY: "auto", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 16, padding: "20px 24px 22px", boxShadow: "var(--shadow-md)" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h3 style={{ margin: 0, fontSize: 16.5, fontWeight: 700, color: "var(--text)" }}>⚙️ OfferForge PC 设置中心</h3>
              <button type="button" onClick={() => setLlmModalOpen(false)} style={{ background: "transparent", border: "none", color: "var(--text-dim)", fontSize: 20, cursor: "pointer", lineHeight: 1 }}>×</button>
            </div>

            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid var(--border)" }}>
              {[
                { id: "llm", label: "🤖 模型与 Key" },
                { id: "desktop", label: "💻 桌面端工具" },
                { id: "prefs", label: "🎨 界面与偏好" },
                { id: "author", label: "👤 关于作者" },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSettingsTab(t.id)}
                  style={{
                    padding: "7px 13px",
                    borderRadius: 9,
                    fontSize: 12.5,
                    fontWeight: settingsTab === t.id ? 700 : 500,
                    cursor: "pointer",
                    border: `1px solid ${settingsTab === t.id ? "var(--brand)" : "var(--border-light)"}`,
                    background: settingsTab === t.id ? "var(--brand-soft)" : "var(--bg-inset)",
                    color: settingsTab === t.id ? "var(--brand)" : "var(--text-secondary)",
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {settingsTab === "llm" && (
              <form onSubmit={saveLlmSettings}>
                <p style={{ fontSize: 12.5, color: "var(--text-dim)", marginBottom: 14, lineHeight: 1.55 }}>
                  每位用户均使用自己本地的 API Key，保存后即时生效并自动写入同级 <code>.env</code>（绝不回显明文密钥）。
                </p>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 5 }}>模型厂商</div>
                  <select
                    value={llmForm.provider}
                    onChange={(e) => {
                      const nextProvider = e.target.value;
                      const preset = (llmConfig?.presets || []).find((p) => p.code === nextProvider);
                      setLlmForm((prev) => ({ ...prev, provider: nextProvider, model: preset?.default_model || prev.model }));
                    }}
                    style={{ ...selectStyle, maxWidth: "100%" }}
                  >
                    {(llmConfig?.presets || [{ code: "zhipu", label: "智谱清言 (GLM)" }]).map((p) => (
                      <option key={p.code} value={p.code}>
                        {p.label} {p.has_key ? `（已配置 ${p.masked_key}）` : "（未配置 Key）"}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 5 }}>模型名称（留空使用厂商默认）</div>
                  <input
                    value={llmForm.model}
                    onChange={(e) => setLlmForm((prev) => ({ ...prev, model: e.target.value }))}
                    placeholder="如：glm-4.7 / deepseek-chat / gemini-3.8-flash"
                    style={{ ...inputStyle, maxWidth: "100%" }}
                  />
                </div>
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 5 }}>新 API Key（不改密钥则留空）</div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type={llmShowKey ? "text" : "password"}
                      value={llmForm.api_key}
                      onChange={(e) => setLlmForm((prev) => ({ ...prev, api_key: e.target.value }))}
                      placeholder="粘贴对应厂商的 API Key..."
                      style={{ ...inputStyle, flex: 1, maxWidth: "100%" }}
                    />
                    <button
                      type="button"
                      onClick={() => setLlmShowKey((v) => !v)}
                      title={llmShowKey ? "隐藏 API Key" : "显示 API Key"}
                      style={{ ...btnOutline2, padding: "8px 12px", fontSize: 12.5, whiteSpace: "nowrap", flexShrink: 0 }}
                    >
                      {llmShowKey ? "🙈 隐藏" : "👁 显示"}
                    </button>
                  </div>
                </div>
                {llmNotice && (
                  <div style={{ marginBottom: 12, fontSize: 12.5, color: llmNotice.includes("❌") ? "var(--danger)" : llmNotice.includes("⏳") ? "var(--text-dim)" : "var(--success)", fontWeight: 600 }}>
                    {llmNotice}
                  </div>
                )}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <button type="button" onClick={testLlmConnection} disabled={llmTesting} style={{ ...btnOutline2, opacity: llmTesting ? 0.6 : 1 }}>
                    {llmTesting ? "⏳ 检测中..." : "🔌 测试当前连接"}
                  </button>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button type="button" onClick={() => setLlmModalOpen(false)} style={btnOutline2}>关闭</button>
                    <button type="submit" disabled={llmSaving} style={{ ...btnGlow, opacity: llmSaving ? 0.6 : 1 }}>
                      {llmSaving ? "保存中..." : "💾 保存并生效"}
                    </button>
                  </div>
                </div>
              </form>
            )}

            {settingsTab === "desktop" && (
              <div>
                <p style={{ fontSize: 12.5, color: "var(--text-dim)", marginBottom: 12, lineHeight: 1.55 }}>
                  PC 桌面端专属本地工具：一键打开数据文件夹、打包迁移备份（自动剔除 <code>.env</code> 密钥防泄露）与清理运行日志。
                </p>
                <div style={{ padding: "12px 14px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border)", marginBottom: 14, fontSize: 12.5, lineHeight: 1.7, color: "var(--text-secondary)" }}>
                  <div><b>当前版本：</b>{desktopInfo?.version || "OfferForge 3.0 Desktop"}（原生 WebView2 独立窗口）</div>
                  <div><b>安装目录：</b><span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5 }}>{desktopInfo?.base_dir || "本地目录"}</span></div>
                  <div><b>本地 SQLite 占用：</b>{desktopInfo ? `${desktopInfo.db_size_kb} KB` : "--"} · <b>运行日志：</b>{desktopInfo ? `${desktopInfo.log_size_kb} KB` : "--"}</div>
                </div>
                <div style={{ padding: "10px 12px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border)", marginBottom: 14, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text)" }}>📋 剪贴板岗位 JD 自动捕获</div>
                    <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginTop: 2 }}>切回窗口时纯本地 0ms 规则识别（命中「岗位职责/任职要求/招聘条件」≥2项才提示，绝不上传）</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={clipboardJdWatch}
                    onChange={(e) => toggleClipboardJdWatch(e.target.checked)}
                    style={{ width: 18, height: 18, accentColor: "var(--brand)", cursor: "pointer", flexShrink: 0 }}
                  />
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>📂 一键打开 Windows 本地目录</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, marginBottom: 14 }}>
                  <button type="button" onClick={() => openLocalFolder("resumes")} style={{ ...btnOutline2, justifyContent: "center" }}>📄 简历文件目录</button>
                  <button type="button" onClick={() => openLocalFolder("exports")} style={{ ...btnOutline2, justifyContent: "center" }}>📑 高清 PDF 导出目录</button>
                  <button type="button" onClick={() => openLocalFolder("data")} style={{ ...btnOutline2, justifyContent: "center" }}>🗄️ SQLite 数据库目录</button>
                  <button type="button" onClick={() => openLocalFolder("logs")} style={{ ...btnOutline2, justifyContent: "center" }}>📝 桌面运行日志目录</button>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                  <a href={`${API_BASE}/api/system/backup-zip`} download style={{ ...btnGlow, textDecoration: "none" }}>📦 一键打包备份数据 (ZIP)</a>
                  <button type="button" onClick={clearLocalLogs} style={btnOutline2}>🧹 清空运行日志</button>
                </div>
                {desktopMsg && <div style={{ marginTop: 8, fontSize: 12.5, color: desktopMsg.includes("❌") ? "var(--danger)" : "var(--success)", fontWeight: 600 }}>{desktopMsg}</div>}
              </div>
            )}

            {settingsTab === "prefs" && (
              <div>
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>界面外观主题</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button type="button" onClick={() => onThemeChange && onThemeChange("light")} style={theme === "light" ? btnGlow : btnOutline2}>☀️ 极简浅色</button>
                    <button type="button" onClick={() => onThemeChange && onThemeChange("dark")} style={theme === "dark" ? btnGlow : btnOutline2}>🌙 石墨暗色</button>
                  </div>
                </div>
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>一键场景模式预设（点选自动联动下方参数，仍支持随时自由微调）</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, marginBottom: 8 }}>
                    {[
                      { label: "本地模式", desc: "均衡改写(0.55) · 面试5题 · 随机0.72", intensity: "balanced", count: 5, temp: 0.72 },
                      { label: "面试冲刺模式", desc: "均衡改写(0.55) · 面试8题 · 高随机0.88", intensity: "balanced", count: 8, temp: 0.88 },
                      { label: "极速投递模式", desc: "微调改写(0.30) · 面试4题 · 稳健0.45", intensity: "mild", count: 4, temp: 0.45 },
                      { label: "深度打磨模式", desc: "激进改写(0.85) · 面试6题 · 多样0.72", intensity: "aggressive", count: 6, temp: 0.72 },
                    ].map((preset) => {
                      const active = prefsForm.modeLabel === preset.label;
                      return (
                        <button
                          key={preset.label}
                          type="button"
                          onClick={() => setPrefsForm((p) => ({
                            ...p,
                            modeLabel: preset.label,
                            defaultIntensity: preset.intensity,
                            interviewCount: preset.count,
                            interviewTemp: preset.temp,
                          }))}
                          style={{
                            textAlign: "left",
                            padding: "8px 11px",
                            borderRadius: 10,
                            cursor: "pointer",
                            border: `1.5px solid ${active ? "var(--brand)" : "var(--border-light)"}`,
                            background: active ? "var(--brand-soft)" : "var(--bg-inset)",
                            color: "var(--text)",
                          }}
                        >
                          <div style={{ fontSize: 12.5, fontWeight: 700, color: active ? "var(--brand)" : "var(--text)" }}>{preset.label}</div>
                          <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>{preset.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                  <input
                    value={prefsForm.modeLabel}
                    onChange={(e) => setPrefsForm((p) => ({ ...p, modeLabel: e.target.value.slice(0, 12) }))}
                    placeholder="或输入自定义模式名（最多12字，实时显示在左下角）"
                    style={{ ...inputStyle, maxWidth: "100%" }}
                  />
                </div>
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>默认简历改写力度（同步 Step 2 & Step 6）</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {[
                      { id: "mild", label: "🌱 微调档 (0.3)" },
                      { id: "balanced", label: "⚖️ 均衡档 (0.55)" },
                      { id: "aggressive", label: "🔥 激进档 (0.85)" },
                    ].map((it) => (
                      <button
                        key={it.id}
                        type="button"
                        onClick={() => setPrefsForm((p) => ({ ...p, defaultIntensity: it.id }))}
                        style={prefsForm.defaultIntensity === it.id ? { ...btnGlow, padding: "5px 11px", fontSize: 12 } : { ...btnOutline2, padding: "5px 11px", fontSize: 12 }}
                      >
                        {it.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 5 }}>模拟面试默认出题数</div>
                    <select
                      value={prefsForm.interviewCount}
                      onChange={(e) => setPrefsForm((p) => ({ ...p, interviewCount: Number(e.target.value) || 5 }))}
                      style={{ ...selectStyle, maxWidth: "100%" }}
                    >
                      {[4, 5, 6, 8].map((n) => <option key={n} value={n}>{n} 道题</option>)}
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 5 }}>模拟面试题库随机度（温度）</div>
                    <select
                      value={prefsForm.interviewTemp}
                      onChange={(e) => setPrefsForm((p) => ({ ...p, interviewTemp: Number(e.target.value) || 0.72 }))}
                      style={{ ...selectStyle, maxWidth: "100%" }}
                    >
                      <option value={0.45}>稳健经典 (0.45)</option>
                      <option value={0.72}>多样新鲜 (0.72 · 推荐)</option>
                      <option value={0.88}>高随机脑暴 (0.88)</option>
                    </select>
                  </div>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Step 4 岗位采集默认城市（打开自动预填）</div>
                  <input
                    value={prefsForm.defaultCity}
                    onChange={(e) => setPrefsForm((p) => ({ ...p, defaultCity: e.target.value }))}
                    placeholder="例如：广州 / 深圳 / 北京 / 上海"
                    style={{ ...inputStyle, maxWidth: "100%" }}
                  />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 5 }}>默认最低月薪（元）</div>
                    <input
                      value={prefsForm.defaultSalaryMin}
                      onChange={(e) => setPrefsForm((p) => ({ ...p, defaultSalaryMin: e.target.value }))}
                      placeholder="如：8000"
                      style={{ ...inputStyle, maxWidth: "100%" }}
                    />
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 5 }}>默认最高月薪（元）</div>
                    <input
                      value={prefsForm.defaultSalaryMax}
                      onChange={(e) => setPrefsForm((p) => ({ ...p, defaultSalaryMax: e.target.value }))}
                      placeholder="如：15000"
                      style={{ ...inputStyle, maxWidth: "100%" }}
                    />
                  </div>
                </div>
                {prefsMsg && <div style={{ marginBottom: 10, fontSize: 12.5, color: "var(--success)", fontWeight: 600 }}>{prefsMsg}</div>}
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button type="button" onClick={saveUserPrefs} style={btnGlow}>💾 保存自定义偏好</button>
                </div>
              </div>
            )}

            {settingsTab === "author" && (
              <div>
                <div style={{ borderRadius: 14, padding: "20px 22px", background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 55%, #1d4ed8 100%)", color: "#f8fafc", position: "relative", overflow: "hidden", marginBottom: 14, boxShadow: "0 12px 30px rgba(30,27,75,0.28)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      <div style={{ width: 52, height: 52, borderRadius: 14, background: "linear-gradient(135deg, #38bdf8, #818cf8)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 800, color: "#0f172a", boxShadow: "0 4px 14px rgba(56,189,248,0.4)" }}>
                        陈
                      </div>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: 0.5 }}>陈其锋</span>
                          <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 999, background: "rgba(255,255,255,0.16)", color: "#e0e7ff", fontWeight: 600 }}>独立开发者</span>
                        </div>
                        <div style={{ fontSize: 12, color: "#cbd5e1", marginTop: 3 }}>OfferForge 3.0 创造者 · 把简历写成可运行的桌面产品</div>
                      </div>
                    </div>
                    <span style={{ fontSize: 11, padding: "4px 10px", borderRadius: 999, background: "rgba(16,185,129,0.2)", border: "1px solid rgba(52,211,153,0.45)", color: "#6ee7b7", fontWeight: 600 }}>
                      ● Open to Opportunities
                    </span>
                  </div>

                  <div style={{ fontSize: 13, lineHeight: 1.75, color: "#e2e8f0", background: "rgba(15,23,42,0.38)", borderRadius: 10, padding: "12px 14px", border: "1px solid rgba(255,255,255,0.1)", marginBottom: 14 }}>
                    你好，我是陈其锋。比起在纸面简历里堆砌漂亮名词，我更习惯直接把想法做成能跑、能用、解决真实痛点的软件——你正在体验的 <b>OfferForge 3.0</b>，就是我从 0 到 1 独立设计、架构、编码并封装成 Windows 桌面端交出的一份<b>「活简历」</b>。<br />
                    如果你是 <b>HR / 面试官</b>，欢迎随手点点看，用它检验我的产品直觉与工程落地力；如果你是<b>朋友</b>，祝你早日拿到心仪 Offer，有好点子随时来聊！
                  </div>

                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                    <span style={{ fontSize: 11.5, padding: "4px 10px", borderRadius: 8, background: "rgba(251,191,36,0.18)", color: "#fde68a", fontWeight: 600 }}>⚡ 从 0 到 1 独立交付</span>
                    <span style={{ fontSize: 11.5, padding: "4px 10px", borderRadius: 8, background: "rgba(56,189,248,0.18)", color: "#bae6fd", fontWeight: 600 }}>🧠 AI 工作流 + 全栈工程</span>
                    <span style={{ fontSize: 11.5, padding: "4px 10px", borderRadius: 8, background: "rgba(167,139,250,0.2)", color: "#ddd6fe", fontWeight: 600 }}>🛡️ 100% 本地隐私优先</span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 8 }}>
                    <button
                      type="button"
                      onClick={() => copyAuthorText("wechat", "Clex620")}
                      style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 12px", borderRadius: 9, background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.18)", color: "#ffffff", cursor: "pointer", fontSize: 12.5 }}
                    >
                      <span>💬 微信：<b>Clex620</b></span>
                      <span style={{ fontSize: 11, color: copiedAuthorField === "wechat" ? "#6ee7b7" : "#93c5fd" }}>{copiedAuthorField === "wechat" ? "✓ 已复制" : "点击复制"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => copyAuthorText("email", "2367538177@qq.com")}
                      style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 12px", borderRadius: 9, background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.18)", color: "#ffffff", cursor: "pointer", fontSize: 12.5 }}
                    >
                      <span>✉️ 邮箱：<b>2367538177@qq.com</b></span>
                      <span style={{ fontSize: 11, color: copiedAuthorField === "email" ? "#6ee7b7" : "#93c5fd" }}>{copiedAuthorField === "email" ? "✓ 已复制" : "点击复制"}</span>
                    </button>
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <button type="button" onClick={() => setLlmModalOpen(false)} style={btnOutline2}>关闭</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const scoreBar = (label, score) => React.createElement("div", { style: { flex: 1, textAlign: "center" } },
  React.createElement("div", { style: { fontSize: 12.5, color: "var(--text-dim)", marginBottom: 6, fontWeight: 500 } }, label),
  React.createElement("div", { style: { height: 6, background: "var(--bg-subtle)", borderRadius: 999, overflow: "hidden" } },
    React.createElement("div", { style: { height: "100%", width: Math.min(score, 100) + "%", background: score >= 75 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--danger)", borderRadius: 999, transition: "width 0.5s ease" } })
  ),
  React.createElement("div", { style: { fontSize: 11.5, color: "var(--text-secondary)", marginTop: 4, fontFamily: "var(--font-mono)" } }, score + "/100")
);

const statusStyle = { marginTop: 12, fontSize: 13, fontFamily: "var(--font-mono)" };

const card = { background: "var(--bg-card)", borderRadius: "var(--radius-lg)", padding: "24px 26px", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" };
const btnGlow = { display: "inline-flex", alignItems: "center", gap: 6, padding: "9px 18px", borderRadius: 8, background: "var(--accent-gradient)", color: "var(--accent-fg)", fontWeight: 600, fontSize: 13.5, border: "1px solid transparent", cursor: "pointer", boxShadow: "var(--accent-shadow)" };
const btnOutline = { display: "inline-flex", alignItems: "center", gap: 6, padding: "7px 14px", borderRadius: 8, background: "var(--brand-soft)", border: "1px solid var(--brand-border)", color: "var(--brand)", cursor: "pointer", fontSize: 13, fontWeight: 600, marginBottom: 14 };
const btnOutline2 = { display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 8, background: "var(--bg-card)", border: "1px solid var(--border-light)", color: "var(--text-secondary)", fontWeight: 500, fontSize: 13, cursor: "pointer" };
const deleteBtn = { background: "var(--danger-soft)", border: "1px solid var(--danger-border)", color: "var(--danger)", padding: "5px 12px", borderRadius: 7, cursor: "pointer", fontSize: 12, fontWeight: 500 };
const infoP = { padding: "4px 0", color: "var(--text-secondary)", fontSize: 13.5 };
const sectionH4 = { color: "var(--text-secondary)", borderBottom: "1px solid var(--border)", paddingBottom: 6, marginBottom: 10, fontSize: 13.5, fontWeight: 600 };
const skillTag = { padding: "4px 12px", background: "var(--accent2-soft)", border: "1px solid var(--accent2-border)", borderRadius: 999, fontSize: 12, color: "var(--accent2)", fontWeight: 500 };
const resumeItem = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 14px", marginBottom: 8, background: "var(--bg-inset)", borderRadius: 10, border: "1px solid var(--border)", cursor: "pointer", transition: "var(--transition)" };
const selectStyle = { background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "8px 12px", borderRadius: 8, width: "100%", maxWidth: 400, fontSize: 13, outline: "none" };
const inputStyle = { background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "9px 12px", borderRadius: 8, width: "100%", maxWidth: 400, fontSize: 13, outline: "none" };
const textareaStyle = { width: "100%", background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "10px 12px", borderRadius: 8, fontSize: 13, resize: "vertical", outline: "none", fontFamily: "var(--font-sans)" };

export default AIAssistant;

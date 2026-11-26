import React, { useState, useEffect } from 'react';
import { Check, Landmark, Building2, Globe, Sparkles, MessageSquareText, Briefcase, ChevronDown } from 'lucide-react';

const API_BASE = window.location.origin;

const emptyIntent = {
  position: "",
  city: "",
  salary_min: "",
  salary_max: "",
  restrictions: []
};

const parseSalaryRange = (value) => {
  const text = String(value || "").toLowerCase();
  const numbers = text.match(/\d+(?:\.\d+)?/g);
  if (!numbers || numbers.length === 0) return ["", ""];
  const normalized = numbers.slice(0, 2).map(number => {
    const numericValue = Number(number);
    if (text.includes("万") || text.includes("w")) return Math.round(numericValue * 10000);
    if (text.includes("千") || text.includes("k")) return Math.round(numericValue * 1000);
    return numericValue >= 1000 ? Math.round(numericValue) : Math.round(numericValue * 1000);
  });
  return [normalized[0] || "", normalized[1] || normalized[0] || ""];
};

const formatIntentSalaryRange = (salaryMin, salaryMax, fallback = "") => {
  const hasMin = salaryMin !== "" && salaryMin !== null && salaryMin !== undefined && Number(salaryMin) > 0;
  const hasMax = salaryMax !== "" && salaryMax !== null && salaryMax !== undefined && Number(salaryMax) > 0;
  const fmtK = (val) => {
    const num = Number(val);
    const k = num >= 1000 ? num / 1000 : num;
    return Number.isInteger(k) ? `${k}k` : `${Number(k.toFixed(1))}k`;
  };
  if (hasMin && hasMax) return `${fmtK(salaryMin)}-${fmtK(salaryMax)}`;
  if (hasMin) return `${fmtK(salaryMin)}-`;
  if (hasMax) return `0k-${fmtK(salaryMax)}`;
  return String(fallback || "").trim();
};

const JobMarket = ({ sResume, setSResume, sSalary, setSSalary, resumes, onPrecisionOptimize }) => {
  // New UI states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBatch, setSelectedBatch] = useState("");
  const [intentText, setIntentText] = useState("");
  const [intent, setIntent] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("offerforge_user_prefs") || "{}");
      return {
        ...emptyIntent,
        city: saved.defaultCity || "",
        salary_min: saved.defaultSalaryMin || "",
        salary_max: saved.defaultSalaryMax || "",
      };
    } catch {
      return emptyIntent;
    }
  });
  const [intentConfirmed, setIntentConfirmed] = useState(false);
  const [intentLoading, setIntentLoading] = useState(false);
  const [intentElapsed, setIntentElapsed] = useState(0);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [scrapeCancelling, setScrapeCancelling] = useState(false);
  const [scrapeTaskId, setScrapeTaskId] = useState(() => localStorage.getItem("offerforge_job_task_id") || "");
  const [scrapeStatus, setScrapeStatus] = useState({ progress: "", jobs_count: 0, last_run: "" });
  const [intentMessage, setIntentMessage] = useState("");
  const COMPANY_OFFICIAL_SOURCES = [
    { code: "meituan", name: "美团", group: "互联网/AI" },
    { code: "tencent", name: "腾讯", group: "互联网/AI" },
    { code: "netease", name: "网易", group: "互联网/AI" },
    { code: "jd", name: "京东", group: "互联网/AI" },
    { code: "baidu", name: "百度", group: "互联网/AI" },
    { code: "iflytek", name: "科大讯飞", group: "互联网/AI" },
    { code: "mihoyo", name: "米哈游", group: "互联网/AI" },
    { code: "wuxiapptec", name: "药明康德", group: "跨行业龙头" },
    { code: "mindray", name: "迈瑞医疗", group: "跨行业龙头" },
    { code: "mengniu", name: "蒙牛集团", group: "跨行业龙头" },
    { code: "vivo", name: "vivo", group: "跨行业龙头" },
  ];
  const ALL_COMPANY_CODES = COMPANY_OFFICIAL_SOURCES.map((item) => item.code);
  const DEFAULT_FAST_HTTP_CODES = ["ncss", "iguopin", "nowcoder", ...ALL_COMPANY_CODES];
  const ALL_FAST_HTTP_CODES = ["sasac", ...DEFAULT_FAST_HTTP_CODES];

  const [selectedSources, setSelectedSources] = useState(DEFAULT_FAST_HTTP_CODES);
  const [companyPickerOpen, setCompanyPickerOpen] = useState(false);
  const [wechatOpen, setWechatOpen] = useState(false);
  const [wechatText, setWechatText] = useState("");
  const [wechatUrl, setWechatUrl] = useState("");
  const [wechatLoading, setWechatLoading] = useState(false);
  const [wechatMessage, setWechatMessage] = useState("");
  const [hoveredSourceCard, setHoveredSourceCard] = useState("");
  const collectionSource = selectedSources.join(",");

  const selectedCompanyCount = ALL_COMPANY_CODES.filter((c) => selectedSources.includes(c)).length;

  const toggleSingleSource = (code) => {
    if (scrapeLoading) return;
    setSelectedSources((prev) => {
      if (prev.includes(code)) {
        if (prev.length <= 1) return prev;
        return prev.filter((item) => item !== code);
      }
      return [...prev, code];
    });
  };

  const toggleCompanyGroup = () => {
    if (scrapeLoading) return;
    setSelectedSources((prev) => {
      const hasAny = ALL_COMPANY_CODES.some((c) => prev.includes(c));
      if (hasAny) {
        const rest = prev.filter((c) => !ALL_COMPANY_CODES.includes(c));
        return rest.length > 0 ? rest : prev;
      }
      return [...new Set([...prev, ...ALL_COMPANY_CODES])];
    });
  };

  const handleParseWechatPost = async () => {
    if (wechatText.trim().length < 20) {
      setWechatMessage("请先粘贴至少 20 字以上的微信公众号招聘正文或公告内容");
      return;
    }
    setWechatLoading(true);
    setWechatMessage("正在调用 AI 引擎拆解微信公众号招聘推文...");
    try {
      const resp = await fetch(`${API_BASE}/api/jobs/wechat/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: wechatText.trim(),
          article_url: wechatUrl.trim(),
          resume_file: sResume || "",
        }),
      });
      const data = await resp.json();
      if (resp.ok && data.ok) {
        setWechatMessage(`✅ ${data.message}`);
        setWechatText("");
        setWechatUrl("");
        await loadBatches();
        if (data.jobs_file) {
          setSelectedBatch(data.jobs_file);
          loadJobsForBatch(data.jobs_file);
        }
      } else {
        setWechatMessage(`❌ ${data.error || data.detail || "解析失败"}`);
      }
    } catch {
      setWechatMessage("❌ 网络连接失败，请确认本地服务正常运行");
    }
    setWechatLoading(false);
  };

  const SOURCE_PRESETS = [
    { id: "all_fast", label: `全部免登录源 (${ALL_FAST_HTTP_CODES.length})`, codes: ALL_FAST_HTTP_CODES },
    { id: "gov_public", label: "仅国家发布 + 国聘 (3)", codes: ["sasac", "ncss", "iguopin"] },
    { id: "companies", label: `仅企业官网直招 (${ALL_COMPANY_CODES.length})`, codes: ALL_COMPANY_CODES },
    { id: "legacy_51", label: "传统 51job", codes: ["51job"] },
  ];

  const isPresetActive = (codes) =>
    codes.length === selectedSources.length && codes.every((code) => selectedSources.includes(code));

  const TOP_SOURCE_CARDS = [
    {
      id: "sasac",
      name: "国务院国资委",
      subtitle: "国家发布 · 央企招聘公告",
      tone: "brand",
      Icon: Landmark,
      active: selectedSources.includes("sasac"),
      onToggle: () => toggleSingleSource("sasac"),
      pros: "国家权威首发，央企及委属单位绝对真实",
      cons: "以综合性招聘公告为主，无单岗薪资标注",
    },
    {
      id: "ncss",
      name: "中国人社 / 24365",
      subtitle: "国家发布 · 公共就业服务",
      tone: "brand",
      Icon: Landmark,
      active: selectedSources.includes("ncss"),
      onToggle: () => toggleSingleSource("ncss"),
      pros: "国家级公共就业平台直连，覆盖全国全行业与应届/社招",
      cons: "部分岗位偏高校与国企体系，社招高薪岗占比有限",
    },
    {
      id: "company_official",
      name: "企业官网",
      subtitle: `美团·腾讯·网易·京东·百度·讯飞·药明·迈瑞等 ${selectedCompanyCount}/${ALL_COMPANY_CODES.length} 家`,
      tone: "indigo",
      Icon: Building2,
      active: selectedCompanyCount > 0,
      onToggle: toggleCompanyGroup,
      pros: "11 家互联网/AI/医药/医疗/快消/硬件龙头官网直连，JD 极其完整且直达网申",
      cons: "企业官网通常不公开具体月薪，标为面议",
    },
    {
      id: "wechat",
      name: "微信公众号",
      subtitle: "官方发布 · 推文 AI 拆解",
      tone: "teal",
      Icon: MessageSquareText,
      active: wechatOpen,
      onToggle: () => setWechatOpen((prev) => !prev),
      pros: "官方公众号首发绝对真实，粘贴推文 3 秒由 AI 拆成标准岗位并自动打分",
      cons: "微信无全网免登录搜索接口，需粘贴推文正文或公告文字触发解析",
    },
    {
      id: "iguopin",
      name: "国聘网",
      subtitle: "求职平台 · 央国企/全行业",
      tone: "brand",
      Icon: Briefcase,
      active: selectedSources.includes("iguopin"),
      onToggle: () => toggleSingleSource("iguopin"),
      pros: "央国企与重点行业聚合度高，附薪资区间与真实详情链接",
      cons: "泛关键词搜索可能混入少量关联行业岗位（已启用相关性过滤）",
    },
    {
      id: "nowcoder",
      name: "牛客招聘",
      subtitle: "求职平台 · 全网综合/带薪资",
      tone: "indigo",
      Icon: Briefcase,
      active: selectedSources.includes("nowcoder"),
      onToggle: () => toggleSingleSource("nowcoder"),
      pros: "覆盖全网数万家互联网/金融/成长型企业，普遍标明真实薪资区间",
      cons: "偏技术、产品、运营与金融类岗位，传统蓝领岗位较少",
    },
    {
      id: "51job",
      name: "51前程无忧",
      subtitle: "求职平台 · 传统浏览器采集",
      tone: "warning",
      Icon: Globe,
      active: selectedSources.includes("51job"),
      onToggle: () => toggleSingleSource("51job"),
      pros: "老牌全行业综合招聘站，传统行业与中小企业岗位多",
      cons: "需启动本机浏览器且可能触发登录/安全验证，速度较慢",
    },
    {
      id: "liepin",
      name: "猎聘网",
      subtitle: "求职平台 · AI浏览器测试版",
      tone: "warning",
      Icon: Globe,
      active: selectedSources.includes("liepin"),
      onToggle: () => toggleSingleSource("liepin"),
      pros: "中高端社招与猎头岗位丰富",
      cons: "需启动本机 Edge 由 AI 操作，遇登录或验证码会安全停止",
    },
  ];

  const [batches, setBatches] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [expandedJobKey, setExpandedJobKey] = useState(null);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [noteDrafts, setNoteDrafts] = useState({});
  const [savingTrackKey, setSavingTrackKey] = useState("");
  const [savedNoticeKey, setSavedNoticeKey] = useState("");

  const sourceLabel = (src) => {
    const map = {
      sasac: "国务院国资委",
      iguopin: "国聘网",
      ncss: "国家24365",
      nowcoder: "牛客招聘",
      meituan: "美团官方",
      tencent: "腾讯官方",
      netease: "网易官方",
      jd: "京东官方",
      baidu: "百度官方",
      mihoyo: "米哈游官方",
      iflytek: "科大讯飞",
      wuxiapptec: "药明康德",
      mindray: "迈瑞医疗",
      mengniu: "蒙牛集团",
      vivo: "vivo官方",
      wechat: "微信公众号",
      "51job": "51前程无忧",
      liepin: "猎聘",
      boss: "BOSS直聘",
      zhilian: "智联招聘",
    };
    return map[String(src || "").toLowerCase()] || (src || "未知来源");
  };

  const safeExternalUrl = (rawUrl) => {
    const text = String(rawUrl || "").trim();
    return /^https?:\/\//i.test(text) ? text : "";
  };

  useEffect(() => {
    if (!intentLoading) return;
    const started = Date.now();
    const timer = setInterval(() => setIntentElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [intentLoading]);

  useEffect(() => {
    loadBatches();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const restoreRunningTask = async () => {
      try {
        const savedTaskId = localStorage.getItem("offerforge_job_task_id") || "";
        const query = savedTaskId ? `?task_id=${encodeURIComponent(savedTaskId)}` : "";
        const response = await fetch(`${API_BASE}/api/jobs/scrape/status${query}`);
        const status = await response.json();
        if (!cancelled && response.ok && status.running) {
          if (status.task_id) {
            setScrapeTaskId(status.task_id);
            localStorage.setItem("offerforge_job_task_id", status.task_id);
          }
          setScrapeStatus(status);
          setScrapeLoading(true);
          setIntentMessage("检测到未结束的岗位采集，已恢复状态跟踪");
        } else if (!cancelled && response.ok && status.status === "interrupted") {
          localStorage.removeItem("offerforge_job_task_id");
          setScrapeTaskId("");
          setIntentMessage(status.progress || "上一次岗位采集因服务重启而中断，请重新启动");
        }
      } catch {}
    };
    restoreRunningTask();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!scrapeLoading || !scrapeTaskId) return;
    let cancelled = false;
    let timer;
    const pollScrapeStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/jobs/scrape/status?task_id=${encodeURIComponent(scrapeTaskId)}`);
        const status = await response.json();
        if (!response.ok) throw new Error("状态查询失败");
        if (cancelled) return;
        setScrapeStatus(status);
        if (status.running) {
          timer = setTimeout(pollScrapeStatus, 1500);
          return;
        }
        setScrapeLoading(false);
        setScrapeCancelling(false);
        localStorage.removeItem("offerforge_job_task_id");
        setScrapeTaskId("");
        if (String(status.progress || "").startsWith("出错:")) {
          setIntentMessage(status.progress);
          return;
        }
        const finalMessage = status.jobs_count > 0
          ? `岗位采集完成，共 ${status.jobs_count} 个岗位`
          : (status.progress || "岗位采集已结束，未找到岗位");
        setIntentMessage(finalMessage);
        await loadBatches();
      } catch {
        if (!cancelled) {
          setScrapeLoading(false);
          setIntentMessage("无法读取岗位采集状态，请稍后刷新页面重试");
        }
      }
    };
    pollScrapeStatus();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [scrapeLoading, scrapeTaskId]);

  const loadBatches = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/jobs/list`);
      const d = await r.json();
      if (d.files) {
        setBatches(d.files);
        if (d.files.length > 0) {
          setSelectedBatch(d.files[0].filename);
        }
      }
    } catch {}
  };

  useEffect(() => {
    if (selectedBatch) {
      loadJobsForBatch(selectedBatch);
    }
  }, [selectedBatch]);

  const loadJobsForBatch = async (batchId) => {
    try {
      const r = await fetch(`${API_BASE}/api/jobs/detail/${encodeURIComponent(batchId)}`);
      const d = await r.json();
      if (d.ok && d.data && d.data.jobs) {
        const validStatuses = new Set(["unsent", "sent", "interview", "rejected"]);
        const loadedJobs = d.data.jobs.map((j, origIdx) => ({
          ...j,
          _origIdx: origIdx,
          status: validStatuses.has(j.status) ? j.status : "unsent",
          tracking_note: j.tracking_note || "",
          tracked_at: j.tracked_at || "",
        }));
        setJobs(loadedJobs);
        setNoteDrafts({});
        setSourceFilter("all");
      } else {
        setJobs([]);
        setNoteDrafts({});
        setSourceFilter("all");
      }
    } catch {
      setJobs([]);
    }
  };

  const updateIntent = (field, value) => {
    setIntent(current => ({ ...current, [field]: value }));
    setIntentConfirmed(false);
  };

  const handleResumeChange = (filename) => {
    setSResume(filename);
    const selectedResume = (resumes || []).find(item => item.filename === filename);
    const salaryText = selectedResume?.desired_salary || "";
    const [salaryMin, salaryMax] = parseSalaryRange(salaryText);
    let savedPrefs = {};
    try { savedPrefs = JSON.parse(localStorage.getItem("offerforge_user_prefs") || "{}"); } catch {}
    const p0City = String(savedPrefs.defaultCity || "").trim();
    const p0Min = String(savedPrefs.defaultSalaryMin || "").trim();
    const p0Max = String(savedPrefs.defaultSalaryMax || "").trim();
    const finalMin = p0Min || salaryMin;
    const finalMax = p0Max || salaryMax;
    setSSalary(p0Min || p0Max ? formatIntentSalaryRange(finalMin, finalMax, salaryText) : salaryText);
    setIntent({
      ...emptyIntent,
      position: selectedResume?.position || "",
      city: p0City || "",
      salary_min: finalMin,
      salary_max: finalMax,
    });
    setIntentText("");
    setIntentConfirmed(false);
    setIntentMessage(
      filename
        ? (p0City || p0Min || p0Max
          ? "已载入简历岗位，并优先保留「设置中心」预设的城市与薪资（预设 P0 > 简历 P1）"
          : "已载入岗位与薪资；目标城市请按当前求职计划填写，或在右上角「设置中心」预设默认城市")
        : ""
    );
  };

  const extractIntent = async () => {
    const fallbackText = [
      intent.position && `目标岗位${intent.position}`,
      intent.city && `目标城市${intent.city}`,
      sSalary && `期望薪资${sSalary}`,
      intent.restrictions.length > 0 && intent.restrictions.join("，")
    ].filter(Boolean).join("，");
    const sourceText = intentText.trim() || fallbackText;
    if (sourceText.length < 2) {
      setIntentMessage("请先填写一段求职意向，或选择包含求职意向的简历");
      return;
    }
    setIntentLoading(true);
    setIntentElapsed(0);
    setIntentConfirmed(false);
    setIntentMessage("AI正在整理求职意向...");
    try {
      const response = await fetch(`${API_BASE}/api/jobs/intent/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent_text: sourceText })
      });
      const data = await response.json();
      if (!response.ok || !data.ok || !data.intent) {
        setIntentMessage(data.error || "求职意向提取失败，请手动填写");
        return;
      }
      setIntent({
        position: data.intent.position || "",
        city: data.intent.city || "",
        salary_min: data.intent.salary_min ?? "",
        salary_max: data.intent.salary_max ?? "",
        restrictions: data.intent.restrictions || []
      });
      setIntentConfirmed(false);
      const missing = data.intent.missing_fields || [];
      const missingLabels = missing.map(field => ({ position: "目标岗位", city: "目标城市", salary: "薪资范围（选填）" }[field] || field));
      setIntentMessage(missing.length > 0 ? `AI已整理，尚未提取：${missingLabels.join("、")}。请核对原文或手动补充后确认` : "AI已整理，请检查并确认");
    } catch {
      setIntentMessage("无法连接本地服务，请检查后端是否启动");
    } finally {
      setIntentLoading(false);
    }
  };

  const confirmIntent = async () => {
    const missing = [];
    if (!String(intent.position || "").trim()) missing.push("目标岗位");
    if (!String(intent.city || "").trim()) missing.push("目标城市");
    if (missing.length > 0) {
      setIntentConfirmed(false);
      setIntentMessage(`⚠️ 无法确认：请先填写必填项【${missing.join("、")}】`);
      return;
    }
    const minSal = intent.salary_min === "" ? null : Number(intent.salary_min);
    const maxSal = intent.salary_max === "" ? null : Number(intent.salary_max);
    if (minSal !== null && maxSal !== null && minSal > maxSal) {
      setIntentConfirmed(false);
      setIntentMessage("⚠️ 无法确认：最低月薪不能高于最高月薪");
      return;
    }
    setIntentMessage("正在校验采集条件...");
    try {
      const response = await fetch(`${API_BASE}/api/jobs/intent/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          position: intent.position,
          city: intent.city,
          salary_min: minSal,
          salary_max: maxSal,
          restrictions: intent.restrictions
        })
      });
      const data = await response.json();
      if (!response.ok || !data.ok || !data.intent) {
        setIntentConfirmed(false);
        const detailHint = Array.isArray(data.details) && data.details.length > 0
          ? data.details.map(item => item.message || item.field).filter(Boolean).join("；")
          : "";
        setIntentMessage(`⚠️ ${data.error || detailHint || "采集条件校验失败，请检查目标岗位和城市"}`);
        return;
      }
      setIntentConfirmed(true);
      setIntentMessage(
        sResume
          ? "求职意向已确认，可以启动岗位采集"
          : "求职意向已确认（提示：启动采集前请先在上方选择一份简历）"
      );
      setSSalary(formatIntentSalaryRange(data.intent.salary_min, data.intent.salary_max, ""));
    } catch {
      setIntentConfirmed(false);
      setIntentMessage("⚠️ 无法连接本地服务，暂时无法确认");
    }
  };

  const startScrape = async () => {
    if (!sResume || !intentConfirmed) {
      setIntentMessage("请先选择简历并确认求职意向");
      return;
    }
    setScrapeLoading(true);
    setScrapeCancelling(false);
    setScrapeStatus({ progress: "正在提交采集任务", jobs_count: 0, last_run: "" });
    setIntentMessage("正在启动岗位采集...");
    try {
      const effectiveSalaryRange = formatIntentSalaryRange(intent.salary_min, intent.salary_max, sSalary);
      const formData = new FormData();
      formData.append("platforms", collectionSource);
      formData.append("resume_file", sResume);
      formData.append("salary_range", effectiveSalaryRange);
      formData.append("target_position", intent.position);
      formData.append("target_city", intent.city);
      formData.append("restrictions", intent.restrictions.join("\n"));
      formData.append("related_keywords", "[]");
      const response = await fetch(`${API_BASE}/api/jobs/scrape`, {
        method: "POST",
        body: formData
      });
      const data = await response.json();
      if (data.ok) {
        if (!data.task_id) {
          setScrapeLoading(false);
          setIntentMessage("后端没有返回采集任务编号，任务未进入状态跟踪");
          return;
        }
        setScrapeTaskId(data.task_id);
        localStorage.setItem("offerforge_job_task_id", data.task_id);
        setIntentMessage("岗位采集已启动，正在读取后台状态");
      } else {
        setScrapeLoading(false);
        setIntentMessage(data.error || "启动失败");
      }
    } catch {
      setScrapeLoading(false);
      setIntentMessage("无法连接本地服务，岗位采集未启动");
    }
  };

  const cancelScrape = async () => {
    if (!scrapeTaskId || !window.confirm("确定停止当前岗位采集吗？已经完成的页面不会继续保存为新批次。")) return;
    setScrapeCancelling(true);
    setIntentMessage("正在请求采集器安全停止...");
    try {
      const response = await fetch(`${API_BASE}/api/jobs/scrape/${encodeURIComponent(scrapeTaskId)}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        setScrapeCancelling(false);
        setIntentMessage(data.error || "取消请求失败");
        return;
      }
      setScrapeStatus(data);
      setIntentMessage("取消请求已提交，正在关闭当前采集页面");
    } catch {
      setScrapeCancelling(false);
      setIntentMessage("无法连接本地服务，取消请求未提交");
    }
  };

  const cardStyle = {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "14px",
    padding: "22px 24px",
    boxShadow: "var(--shadow-xs)"
  };

  const btnGlow = {
    background: "var(--accent-gradient)",
    color: "var(--accent-fg)",
    border: "1px solid transparent",
    padding: "9px 18px",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: "600",
    boxShadow: "var(--accent-shadow)",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px"
  };

  const persistJobTracking = async (job, nextStatus, nextNote, itemKey) => {
    if (!selectedBatch) return;
    const prevJobs = jobs;
    setSavingTrackKey(itemKey);
    setJobs((curr) =>
      curr.map((it) =>
        it._origIdx === job._origIdx
          ? { ...it, status: nextStatus, tracking_note: nextNote }
          : it
      )
    );
    try {
      const resp = await fetch(`${API_BASE}/api/jobs/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          batch_id: selectedBatch,
          job_id: job.job_id || "",
          job_index: typeof job._origIdx === "number" ? job._origIdx : -1,
          status: nextStatus,
          note: nextNote,
        }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        setJobs(prevJobs);
      } else {
        setJobs((curr) =>
          curr.map((it) =>
            it._origIdx === job._origIdx
              ? { ...it, status: data.status, tracking_note: data.tracking_note, tracked_at: data.tracked_at || "" }
              : it
          )
        );
        setSavedNoticeKey(itemKey);
        setTimeout(() => {
          setSavedNoticeKey((k) => (k === itemKey ? "" : k));
        }, 2000);
      }
    } catch {
      setJobs(prevJobs);
    } finally {
      setSavingTrackKey("");
    }
  };

  const sourceBreakdown = Object.entries(
    jobs.reduce((acc, item) => {
      const key = String(item.source || "unknown");
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]);

  const filteredJobs = jobs.filter(j => {
    if (sourceFilter !== 'all' && String(j.source || "unknown") !== sourceFilter) return false;
    if (searchQuery && !j.title.includes(searchQuery) && !j.company.includes(searchQuery)) return false;
    return true;
  });

  return (
    <div style={{ animation: "fadeInUp 0.4s ease", color: "var(--text)" }}>
      <style>{`@keyframes jobProgressFlow { from { transform:translateX(-120%); } to { transform:translateX(340%); } }`}</style>
      {/* Top Section: Scraper Control */}
      <div style={{ ...cardStyle, marginBottom: 20 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🔍</span> 岗位采集引擎
        </h3>
        <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 14 }}>根据简历精准定向抓取全网最新岗位，存入云端数据库</p>
        
        <div style={{ display: "flex", gap: 16, marginBottom: 16, alignItems: "center", flexWrap: "wrap" }}>
          <select 
            value={sResume} 
            disabled={intentLoading}
            onChange={(e) => handleResumeChange(e.target.value)}
            style={{ background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "8px 12px", borderRadius: 8, outline: "none", minWidth: 200 }}
          >
            <option value="">选择简历...</option>
            {resumes && resumes.map(x => (
              <option key={x.filename} value={x.filename}>{x.name}</option>
            ))}
          </select>
        </div>
        <textarea
          value={intentText}
          disabled={intentLoading}
          onChange={(e) => { setIntentText(e.target.value); setIntentConfirmed(false); }}
          placeholder="用一句话说明求职意向，例如：想在广州找AI产品助理，期望8k-10k，不接受长期出差"
          rows={2}
          style={{ width: "100%", background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "10px 12px", borderRadius: 8, outline: "none", resize: "vertical", marginBottom: 12 }}
        />
        <button onClick={extractIntent} disabled={intentLoading} style={{ ...btnGlow, opacity: intentLoading ? 0.6 : 1, marginBottom: 14 }}>
          {intentLoading ? "⏳ AI识别中..." : "✨ AI识别求职意向"}
        </button>
        <p style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 0 }}>AI优先识别上方文字；留空时识别下方已有条件，不会读取整份简历。请明确写出目标城市，例如“想在广州找AI产品助理”。</p>
        {intentLoading && <div role="status" aria-live="polite" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 7, fontSize: 12 }}>
            <span>{intentElapsed >= 30 ? "AI响应较慢，仍在等待；请勿重复提交" : "正在等待AI整理岗位、城市、薪资和限制条件…"}</span>
            <span>已等待 {intentElapsed} 秒</span>
          </div>
          <div role="progressbar" aria-label="求职意向识别处理中" aria-valuetext="处理中，完成比例未知" style={{ height: 6, overflow: "hidden", borderRadius: 999, background: "var(--brand-soft)" }}>
            <div style={{ width: "42%", height: "100%", borderRadius: "inherit", background: "linear-gradient(90deg, transparent, var(--brand), transparent)", animation: "jobProgressFlow 1.35s ease-in-out infinite" }} />
          </div>
        </div>}
        <fieldset disabled={intentLoading} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 10 }}>
          <input value={intent.position} onChange={(e) => updateIntent("position", e.target.value)} placeholder="目标岗位（必填）" style={{ background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "8px 12px", borderRadius: 8, outline: "none" }} />
          <input value={intent.city} onChange={(e) => updateIntent("city", e.target.value)} placeholder="目标城市（必填）" style={{ background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "8px 12px", borderRadius: 8, outline: "none" }} />
          <input type="number" min="0" value={intent.salary_min} onChange={(e) => updateIntent("salary_min", e.target.value)} placeholder="最低月薪（元）" style={{ background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "8px 12px", borderRadius: 8, outline: "none" }} />
          <input type="number" min="0" value={intent.salary_max} onChange={(e) => updateIntent("salary_max", e.target.value)} placeholder="最高月薪（元）" style={{ background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "8px 12px", borderRadius: 8, outline: "none" }} />
        </div>
        <textarea
          value={intent.restrictions.join("\n")}
          onChange={(e) => updateIntent("restrictions", e.target.value.split(/\r?\n/).filter(Boolean))}
          placeholder="限制条件，每行一条，例如：不接受长期出差"
          rows={2}
          style={{ width: "100%", background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "10px 12px", borderRadius: 8, outline: "none", resize: "vertical", marginBottom: 14 }}
        />
        <div style={{ marginBottom: 16, padding: "16px 18px", borderRadius: 12, background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 13.5, fontWeight: 700, color: "var(--text)" }}>全网岗位采集渠道</span>
              <span style={{ fontSize: 11.5, fontWeight: 600, padding: "2px 9px", borderRadius: 999, background: "var(--brand-soft)", color: "var(--brand)", border: "1px solid var(--brand-border)" }}>
                已激活 {selectedSources.length} 个直采通道
              </span>
              <span style={{ fontSize: 11.5, color: "var(--text-muted)" }}>悬停卡片查看优缺点</span>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {SOURCE_PRESETS.map((preset) => {
                const active = isPresetActive(preset.codes);
                return (
                  <button
                    key={preset.id}
                    type="button"
                    disabled={scrapeLoading}
                    onClick={() => setSelectedSources(preset.codes)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "4px 10px",
                      borderRadius: 999,
                      fontSize: 11.5,
                      fontWeight: active ? 600 : 500,
                      cursor: "pointer",
                      background: active ? "var(--accent-gradient)" : "var(--bg-card)",
                      color: active ? "var(--accent-fg)" : "var(--text-secondary)",
                      border: active ? "1px solid transparent" : "1px solid var(--border-light)",
                      boxShadow: active ? "var(--accent-shadow)" : "none",
                    }}
                  >
                    {preset.id === "all_fast" && <Sparkles size={11} />}
                    {preset.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 8 大类精简开关卡片网格（企业官网聚合为单栏+副标题侧写+悬停优缺点提示） */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(235px, 1fr))", gap: 10 }}>
            {TOP_SOURCE_CARDS.map((card) => {
              const IconComp = card.Icon;
              const toneColor =
                card.tone === "indigo" ? "var(--accent2)" :
                card.tone === "teal" ? "var(--teal)" :
                card.tone === "warning" ? "var(--warning)" : "var(--brand)";
              const toneSoft =
                card.tone === "indigo" ? "var(--accent2-soft)" :
                card.tone === "teal" ? "var(--teal-soft)" :
                card.tone === "warning" ? "var(--warning-soft)" : "var(--brand-soft)";
              const toneBorder =
                card.tone === "indigo" ? "var(--accent2-border)" :
                card.tone === "teal" ? "var(--teal-border)" :
                card.tone === "warning" ? "var(--warning-border)" : "var(--brand-border)";
              const isHovered = hoveredSourceCard === card.id;
              return (
                <div
                  key={card.id}
                  onMouseEnter={() => setHoveredSourceCard(card.id)}
                  onMouseLeave={() => setHoveredSourceCard((curr) => (curr === card.id ? "" : curr))}
                  style={{
                    position: "relative",
                    padding: "11px 13px",
                    borderRadius: 11,
                    background: card.active ? "var(--bg-card)" : "var(--bg-subtle)",
                    border: `1.5px solid ${card.active ? toneBorder : "var(--border)"}`,
                    boxShadow: card.active ? "var(--shadow-xs)" : "none",
                    transition: "var(--transition)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0, flex: 1 }}>
                      <span style={{ width: 30, height: 30, borderRadius: 8, background: toneSoft, color: toneColor, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <IconComp size={15} strokeWidth={1.9} />
                      </span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--text)", lineHeight: 1.25 }}>{card.name}</div>
                        <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={card.subtitle}>
                          {card.subtitle}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={card.active}
                      aria-label={`切换${card.name}`}
                      disabled={scrapeLoading && card.id !== "wechat"}
                      onClick={card.onToggle}
                      style={{
                        width: 36,
                        height: 20,
                        borderRadius: 999,
                        border: "none",
                        padding: 2,
                        cursor: "pointer",
                        background: card.active ? toneColor : "var(--border-light)",
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: card.active ? "flex-end" : "flex-start",
                        flexShrink: 0,
                      }}
                    >
                      <span style={{ width: 16, height: 16, borderRadius: "50%", background: "#ffffff", boxShadow: "0 1px 2px rgba(0,0,0,0.2)" }} />
                    </button>
                  </div>

                  {card.id === "company_official" && (
                    <div style={{ marginTop: 8, paddingTop: 7, borderTop: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
                      <span style={{ fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>11 家跨行业龙头直连</span>
                      <button
                        type="button"
                        onClick={() => setCompanyPickerOpen((prev) => !prev)}
                        style={{ border: "none", background: "transparent", color: "var(--accent2)", fontSize: 11.5, fontWeight: 600, cursor: "pointer", padding: 0, display: "inline-flex", alignItems: "center", gap: 2, whiteSpace: "nowrap", flexShrink: 0 }}
                      >
                        {companyPickerOpen ? "收起明细" : "筛选子企业"} <ChevronDown size={12} style={{ transform: companyPickerOpen ? "rotate(180deg)" : "none", transition: "transform 0.15s" }} />
                      </button>
                    </div>
                  )}

                  {card.id === "ncss" && (
                    <div style={{ marginTop: 8, paddingTop: 7, borderTop: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>直连 24365 实时岗位</span>
                      <a href="https://www.jobonline.cn/" target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: "var(--brand)", textDecoration: "none", fontWeight: 500 }}>
                        人社就业在线 ↗
                      </a>
                    </div>
                  )}

                  {isHovered && (
                    <div
                      role="tooltip"
                      style={{
                        position: "absolute",
                        left: 0,
                        right: 0,
                        bottom: "calc(100% + 8px)",
                        zIndex: 40,
                        padding: "9px 11px",
                        borderRadius: 9,
                        background: "#0f172a",
                        color: "#f8fafc",
                        fontSize: 11.5,
                        lineHeight: 1.5,
                        boxShadow: "0 8px 24px rgba(15,23,42,0.28)",
                        border: "1px solid rgba(148,163,184,0.25)",
                        pointerEvents: "none",
                      }}
                    >
                      <div><strong style={{ color: "#4ade80" }}>优势：</strong>{card.pros}</div>
                      <div style={{ marginTop: 3 }}><strong style={{ color: "#fbbf24" }}>缺点：</strong>{card.cons}</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* 展开的企业官网子企业勾选面板（默认收起保持整洁） */}
          {companyPickerOpen && (
            <div style={{ marginTop: 12, padding: "12px 14px", borderRadius: 10, background: "var(--bg-card)", border: "1px solid var(--accent2-border)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
                <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text)" }}>企业官网聚合明细（已选 {selectedCompanyCount}/{ALL_COMPANY_CODES.length} 家）</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button type="button" onClick={() => setSelectedSources((prev) => [...new Set([...prev, ...ALL_COMPANY_CODES])])} style={{ padding: "3px 9px", borderRadius: 6, border: "1px solid var(--accent2-border)", background: "var(--accent2-soft)", color: "var(--accent2)", fontSize: 11.5, cursor: "pointer", fontWeight: 500 }}>全选 11 家</button>
                  <button type="button" onClick={() => setSelectedSources((prev) => { const rest = prev.filter((c) => !ALL_COMPANY_CODES.includes(c)); return rest.length ? rest : prev; })} style={{ padding: "3px 9px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-subtle)", color: "var(--text-dim)", fontSize: 11.5, cursor: "pointer" }}>清空官网</button>
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                {COMPANY_OFFICIAL_SOURCES.map((comp) => {
                  const checked = selectedSources.includes(comp.code);
                  return (
                    <button
                      key={comp.code}
                      type="button"
                      disabled={scrapeLoading}
                      onClick={() => toggleSingleSource(comp.code)}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 5,
                        padding: "5px 11px",
                        borderRadius: 999,
                        fontSize: 12,
                        fontWeight: checked ? 600 : 500,
                        cursor: "pointer",
                        background: checked ? "var(--accent2-soft)" : "var(--bg-subtle)",
                        color: checked ? "var(--accent2)" : "var(--text-dim)",
                        border: `1px solid ${checked ? "var(--accent2)" : "var(--border)"}`,
                      }}
                    >
                      {checked && <Check size={12} strokeWidth={2.5} />}
                      <span>{comp.name}</span>
                      <span style={{ fontSize: 10.5, opacity: 0.72 }}>· {comp.group}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* 微信公众号官方招聘推文 AI 拆解面板（点微信公众号开关展开） */}
          {wechatOpen && (
            <div style={{ marginTop: 12, padding: "14px 16px", borderRadius: 10, background: "var(--bg-card)", border: "1px solid var(--teal-border)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--teal)" }}>💬 微信公众号招聘推文 AI 结构化拆解</span>
                <span style={{ fontSize: 11.5, color: "var(--text-dim)" }}>粘贴央国企/大厂官方公众号招聘正文，3 秒入库参与匹配打分</span>
              </div>
              <input
                value={wechatUrl}
                onChange={(e) => setWechatUrl(e.target.value)}
                placeholder="选填：微信公众号文章原链接（https://mp.weixin.qq.com/s/...，用于岗位溯源）"
                style={{ width: "100%", background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "8px 11px", borderRadius: 8, outline: "none", fontSize: 12.5, marginBottom: 8 }}
              />
              <textarea
                rows={4}
                value={wechatText}
                onChange={(e) => setWechatText(e.target.value)}
                placeholder="粘贴公众号招聘公告全文（含公司名、招聘岗位、城市、学历/技能要求等）..."
                style={{ width: "100%", background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "9px 11px", borderRadius: 8, outline: "none", fontSize: 12.5, resize: "vertical", marginBottom: 8 }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <button
                  type="button"
                  disabled={wechatLoading}
                  onClick={handleParseWechatPost}
                  style={{ ...btnGlow, padding: "7px 15px", fontSize: 12.5 }}
                >
                  {wechatLoading ? "⏳ AI 拆解中..." : "✨ AI 拆解推文并存入岗位库"}
                </button>
                {wechatMessage && <span style={{ fontSize: 12, color: wechatMessage.startsWith("✅") ? "var(--success)" : wechatMessage.startsWith("❌") ? "var(--danger)" : "var(--text-dim)" }}>{wechatMessage}</span>}
              </div>
            </div>
          )}

          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              当前并发直采队列（{selectedSources.length} 源）：<strong style={{ color: "var(--text)" }}>{selectedSources.slice(0, 6).map((c) => sourceLabel(c)).join(" · ")}{selectedSources.length > 6 ? ` 等 ${selectedSources.length} 源` : ""}</strong>
            </div>
            {selectedSources.some((c) => ALL_FAST_HTTP_CODES.includes(c)) && (
              <p style={{ color: "var(--brand)", fontSize: 12, lineHeight: 1.55, margin: 0 }}>
                免登录官方源走 6 线程并发纯 HTTP 直连，无需打开浏览器即可几秒拉回真实岗位、保留官方原网页链接并做相关性过滤。
              </p>
            )}
            {selectedSources.includes("liepin") && (
              <p style={{ color: "var(--warning)", fontSize: 12, lineHeight: 1.55, margin: 0 }}>
                猎聘路线会启动独立 Edge 并由 AI 操作网页；遇到登录、验证码或访问限制会安全停止，不会绕过。
              </p>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button onClick={confirmIntent} style={{ ...btnGlow, background: "var(--brand-soft)", color: "var(--brand)", border: "1px solid var(--brand-border)" }}>✓ 确认采集条件</button>
          <button onClick={startScrape} disabled={!intentConfirmed || scrapeLoading} style={{ ...btnGlow, opacity: !intentConfirmed || scrapeLoading ? 0.45 : 1 }}>
            {scrapeLoading ? "⏳ 采集中..." : "🚀 启动采集"}
          </button>
          {scrapeLoading && <button type="button" onClick={cancelScrape} disabled={scrapeCancelling} style={{ ...btnGlow, background: "rgba(255,100,120,0.12)", border: "1px solid rgba(255,100,120,0.65)", opacity: scrapeCancelling ? 0.5 : 1 }}>
            {scrapeCancelling ? "正在停止..." : "停止采集"}
          </button>}
          <span style={{
            color:
              intentMessage && (intentMessage.includes("⚠️") || intentMessage.includes("出错") || intentMessage.includes("失败") || intentMessage.includes("无法"))
                ? "var(--danger)"
                : intentConfirmed
                  ? "var(--success)"
                  : "var(--text-secondary)",
            fontSize: 12.5,
            fontWeight:
              intentMessage && (intentMessage.includes("⚠️") || intentMessage.includes("出错") || intentMessage.includes("失败") || intentConfirmed)
                ? 600
                : 400
          }}>{intentMessage}</span>
        </div>
        </fieldset>
        {scrapeLoading && <div role="status" aria-live="polite" style={{ marginTop: 14, maxWidth: 460 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 7, fontSize: 12, color: "var(--text-dim)" }}><span>{scrapeStatus.progress || "正在读取后台采集状态"}</span><span>{scrapeStatus.progress_percent ?? 0}% · 完成数量：{scrapeStatus.jobs_count || 0}</span></div><div role="progressbar" aria-label="岗位采集处理中" aria-valuemin="0" aria-valuemax="100" aria-valuenow={scrapeStatus.progress_percent ?? 0} aria-valuetext={scrapeStatus.progress || "处理中"} style={{ height: 6, overflow: "hidden", borderRadius: 999, background: "var(--brand-soft)" }}><div style={{ width: `${scrapeStatus.progress_percent ?? 0}%`, minWidth: scrapeStatus.running ? 8 : 0, height: "100%", borderRadius: "inherit", background: "var(--brand)", transition: "width 0.35s ease" }} /></div></div>}
      </div>

      {/* Main Section: Job Market UI */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>💼 智能岗位集市</h3>
          
          {/* Dropdown for Batches */}
          <select 
            value={selectedBatch}
            onChange={(e) => setSelectedBatch(e.target.value)}
            style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "6px 12px", borderRadius: 8, outline: "none", fontSize: 13 }}
          >
            {batches.map((b, i) => (
              <option key={b.filename} value={b.filename} style={{ background: "var(--bg-card)", color: "var(--text)" }}>
                第{batches.length - i}次采集 - {b.keywords && b.keywords[0] ? b.keywords[0] : "未知"} ({b.count}个)
              </option>
            ))}
          </select>
        </div>

        {/* Global Search Box */}
        <div style={{ marginBottom: 20, position: "relative" }}>
          <span style={{ position: "absolute", left: 14, top: 10, color: "var(--text-muted)" }}>🔍</span>
          <input 
            type="text" 
            placeholder="在当前批次中搜索公司、职位..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: "100%", background: "var(--input-bg)", border: "1px solid var(--border)", color: "var(--text)", padding: "10px 14px 10px 40px", borderRadius: 12, outline: "none", fontSize: 14, transition: "all 0.3s" }} 
            onFocus={(e) => e.target.style.border = "1px solid rgba(0, 212, 255, 0.5)"}
            onBlur={(e) => e.target.style.border = "1px solid var(--bg-subtle)"}
          />
        </div>

        {/* Total count bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, paddingBottom: 10, borderBottom: "1px solid var(--bg-subtle)", fontSize: 13, color: "var(--text-secondary)" }}>
          <span>当前批次共 <strong style={{ color: "var(--brand)" }}>{jobs.length}</strong> 个岗位{filteredJobs.length !== jobs.length ? `（当前筛选显示 ${filteredJobs.length} 个）` : ""}</span>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>投递进度统计已汇总至 Step 9「求职投递看板」</span>
        </div>

        {/* 各渠道出岗统计（可点击按出处筛选） */}
        {sourceBreakdown.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", marginBottom: 16, padding: "9px 12px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginRight: 2 }}>各渠道出岗：</span>
            <button
              type="button"
              onClick={() => setSourceFilter("all")}
              style={{
                padding: "3px 10px",
                borderRadius: 999,
                fontSize: 11.5,
                fontWeight: sourceFilter === "all" ? 600 : 500,
                cursor: "pointer",
                background: sourceFilter === "all" ? "var(--accent-gradient)" : "var(--bg-card)",
                color: sourceFilter === "all" ? "var(--accent-fg)" : "var(--text-secondary)",
                border: sourceFilter === "all" ? "1px solid transparent" : "1px solid var(--border-light)",
              }}
            >
              全部 {jobs.length}
            </button>
            {sourceBreakdown.map(([srcCode, count]) => {
              const active = sourceFilter === srcCode;
              return (
                <button
                  key={srcCode}
                  type="button"
                  onClick={() => setSourceFilter(active ? "all" : srcCode)}
                  style={{
                    padding: "3px 10px",
                    borderRadius: 999,
                    fontSize: 11.5,
                    fontWeight: active ? 600 : 500,
                    cursor: "pointer",
                    background: active ? "var(--brand-soft)" : "var(--bg-card)",
                    color: active ? "var(--brand)" : "var(--text-secondary)",
                    border: `1px solid ${active ? "var(--brand-border)" : "var(--border-light)"}`,
                  }}
                >
                  {sourceLabel(srcCode)} <strong>{count}</strong>
                </button>
              );
            })}
          </div>
        )}

        {/* Job List */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, maxHeight: "560px", overflowY: "auto" }}>
          {filteredJobs.map((job, idx) => {
            const itemKey = job.job_id || `${job.source || "job"}-${job._origIdx ?? idx}`;
            const isExpanded = expandedJobKey === itemKey;
            const officialUrl = safeExternalUrl(job.url);
            const hasScore = typeof job.match_score === "number";
            const currentStatus = job.status || "unsent";
            const noteDraft = noteDrafts[itemKey] !== undefined ? noteDrafts[itemKey] : (job.tracking_note || "");
            const statusTone =
              currentStatus === "interview"
                ? { bg: "var(--warning-soft)", color: "var(--warning)", border: "var(--warning-border)" }
                : currentStatus === "sent"
                  ? { bg: "var(--success-soft)", color: "var(--success)", border: "var(--success-border, var(--border))" }
                  : currentStatus === "rejected"
                    ? { bg: "var(--danger-soft)", color: "var(--danger)", border: "var(--danger-border)" }
                    : { bg: "var(--bg-subtle)", color: "var(--text-secondary)", border: "var(--border-light)" };
            return (
              <div key={itemKey} style={{ padding: 16, background: "var(--bg-card)", border: isExpanded ? "1px solid rgba(0, 212, 255, 0.35)" : "1px solid var(--bg-subtle)", borderRadius: 12, transition: "all 0.25s" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text)", marginBottom: 6 }}>
                      {job.title}
                      {job.relation_type && <span style={{ marginLeft: 8, padding: "2px 7px", borderRadius: 10, fontSize: 11, color: job.relation_type === "primary" ? "var(--success)" : "var(--accent2)", background: job.relation_type === "primary" ? "rgba(102,255,166,0.1)" : "rgba(124,77,255,0.15)" }}>{job.relation_type === "primary" ? "主岗位" : "关联岗位"}</span>}
                      {hasScore && <span style={{ marginLeft: 8, padding: "2px 8px", borderRadius: 10, fontSize: 11, color: job.match_score >= 70 ? "var(--success)" : "var(--warning)", background: job.match_score >= 70 ? "rgba(102,255,166,0.12)" : "rgba(255,210,138,0.12)" }}>匹配 {job.match_score}分</span>}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--text-dim)", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      <span>{job.company} · {job.location || "未知"} · <span style={{ color: "var(--brand)" }}>{job.salary || "面议"}</span></span>
                      <span style={{ padding: "1px 8px", borderRadius: 999, fontSize: 11, color: "var(--brand)", background: "var(--brand-soft)", border: "1px solid rgba(0,212,255,0.22)" }}>出处：{sourceLabel(job.source)}</span>
                      {job.tracking_note && (
                        <span style={{ padding: "1px 8px", borderRadius: 999, fontSize: 11, color: "var(--accent2)", background: "var(--accent2-soft)", border: "1px solid var(--accent2-border)" }} title={job.tracking_note}>
                          📌 {job.tracking_note.length > 22 ? `${job.tracking_note.slice(0, 22)}...` : job.tracking_note}
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0, flexWrap: "wrap" }}>
                    <select
                      aria-label={`更新${job.title}投递状态`}
                      value={currentStatus}
                      disabled={savingTrackKey === itemKey}
                      onChange={(e) => persistJobTracking(job, e.target.value, job.tracking_note || "", itemKey)}
                      style={{
                        background: statusTone.bg,
                        color: statusTone.color,
                        border: `1px solid ${statusTone.border}`,
                        padding: "5px 10px",
                        borderRadius: 20,
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        outline: "none",
                      }}
                    >
                      <option value="unsent" style={{ background: "var(--bg-card)", color: "var(--text)" }}>📝 未投递</option>
                      <option value="sent" style={{ background: "var(--bg-card)", color: "var(--text)" }}>✅ 已投递</option>
                      <option value="interview" style={{ background: "var(--bg-card)", color: "var(--text)" }}>🔥 一面中</option>
                      <option value="rejected" style={{ background: "var(--bg-card)", color: "var(--text)" }}>⏸ 不合适</option>
                    </select>
                    {typeof onPrecisionOptimize === "function" && selectedBatch && (
                      <button
                        type="button"
                        onClick={() => onPrecisionOptimize({ batchId: selectedBatch, resumeFile: sResume, job, jobIndex: job._origIdx })}
                        style={{ background: "var(--accent2-soft)", border: "1px solid var(--accent2-border)", color: "var(--accent2)", padding: "6px 12px", borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                      >
                        🎯 精准优化
                      </button>
                    )}
                    {officialUrl && (
                      <a
                        href={officialUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ background: "var(--brand-soft)", border: "1px solid var(--brand-border)", color: "var(--brand)", padding: "6px 12px", borderRadius: 20, fontSize: 12, textDecoration: "none", display: "inline-block" }}
                      >
                        🔗 原网页
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => setExpandedJobKey(isExpanded ? null : itemKey)}
                      style={{ background: isExpanded ? "var(--brand-soft)" : "var(--bg-subtle)", border: "none", color: "var(--text)", padding: "6px 14px", borderRadius: 20, fontSize: 12, cursor: "pointer" }}
                    >
                      {isExpanded ? "收起详情" : "查看详情"}
                    </button>
                  </div>
                </div>
                {isExpanded && (
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--border)", fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
                    {/* 投递与面试跟进备注编辑栏（持久化写入 SQLite） */}
                    <div style={{ marginBottom: 10, padding: "10px 12px", borderRadius: 9, background: "var(--bg-inset)", border: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>📌 跟进备注：</span>
                      <input
                        type="text"
                        value={noteDraft}
                        maxLength={1000}
                        placeholder="记录投递进度或面试时间，如：周四 15:00 腾讯会议一面（回车保存）"
                        onChange={(e) => setNoteDrafts((prev) => ({ ...prev, [itemKey]: e.target.value }))}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            persistJobTracking(job, currentStatus, noteDraft, itemKey);
                          }
                        }}
                        style={{ flex: 1, minWidth: 220, background: "var(--input-bg)", border: "1px solid var(--border-light)", color: "var(--text)", padding: "6px 10px", borderRadius: 7, fontSize: 12.5, outline: "none" }}
                      />
                      <button
                        type="button"
                        disabled={savingTrackKey === itemKey}
                        onClick={() => persistJobTracking(job, currentStatus, noteDraft, itemKey)}
                        style={{ ...btnGlow, padding: "5px 12px", fontSize: 12 }}
                      >
                        {savingTrackKey === itemKey ? "保存中..." : "保存备注"}
                      </button>
                      {savedNoticeKey === itemKey && <span style={{ fontSize: 11.5, color: "var(--success)", fontWeight: 600 }}>✓ 已写入数据库</span>}
                      {job.tracked_at && savedNoticeKey !== itemKey && <span style={{ fontSize: 11, color: "var(--text-muted)" }}>更新于 {job.tracked_at}</span>}
                    </div>
                    {job.match_brief && (
                      <div style={{ marginBottom: 8, padding: "8px 10px", borderRadius: 8, background: "var(--brand-soft)", color: "var(--text-secondary)" }}>
                        <strong>AI 匹配简评：</strong>{job.match_brief}
                      </div>
                    )}
                    {Array.isArray(job.tags) && job.tags.length > 0 && (
                      <div style={{ marginBottom: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {job.tags.map((tag, ti) => (
                          <span key={ti} style={{ padding: "2px 8px", borderRadius: 6, fontSize: 11, background: "var(--bg-subtle)", color: "var(--text-secondary)" }}>{tag}</span>
                        ))}
                      </div>
                    )}
                    <div style={{ whiteSpace: "pre-wrap", color: "var(--text-secondary)" }}>
                      {job.description || "该来源暂未返回完整岗位描述，可点击上方「原网页」前往官方页面查看详情。"}
                    </div>
                    {officialUrl && (
                      <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-muted)", wordBreak: "break-all" }}>
                        官方溯源链接：<a href={officialUrl} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand)" }}>{officialUrl}</a>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
          {filteredJobs.length === 0 && (
            <div style={{ textAlign: "center", padding: "40px 0", color: "rgba(255,255,255,0.3)", fontSize: 14 }}>
              未找到匹配的岗位
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default JobMarket;

"""OfferForge 2.0 一键多维全链路体检脚本（阶段 B 固化版）。

特点：
1. 每次运行自动生成一份全新编号、不同排版格式、不同内容与不同空白板块组合的模拟 .docx 简历。
2. 全程运行在隔离的 TemporaryDirectory（通过 OFFERFORGE_RUNTIME_DIR），绝不污染真实 data/ 与 resumes/。
3. 实时流式输出 7 步后端真机指标（解析保真、70/30 优化、双模板屏蔽空项、多源采集数量/精准度/薪资匹配率/溯源率、批量缓存、单 JD 匹配、精准优化）。
4. 同步运行前端 Playwright 模拟测试（含构建产物同源资源核验与零 ReferenceError 控制台断言）。

用法示例：
  python scripts/e2e_health_check.py
  python scripts/e2e_health_check.py --variant 2 --skip-frontend
  python scripts/e2e_health_check.py --temp-resume --report-json report.json
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEMO_RESUME_DIR = Path(r"C:\Users\MR\Desktop\简历\模拟测试简历")


# ---------------------------------------------------------------------------
# 3 套完全不同格式、不同行业内容、不同刻意留空板块的模拟简历模板
# ---------------------------------------------------------------------------
RESUME_VARIANTS: list[dict[str, Any]] = [
    {
        "id": "table_ops_no_awards_certs",
        "layout": "table_card",
        "name": "周明远",
        "slug": "周明远_无获奖证书",
        "target_position": "产品运营",
        "target_city": "北京",
        "salary_range": "18k-30k",
        "target_salary_k": (18.0, 30.0),
        "related_keywords": ["用户运营", "数据分析"],
        "relevance_terms": ["运营", "产品", "数据", "增长", "活动", "用户", "分析", "商业"],
        "omitted_fields": ["awards", "certificates"],
        "omitted_headings": ["获奖荣誉", "证书资质"],
        "expected_numbers": ["12%", "18%", "28%", "35%"],
        "required_markers": ["周明远", "星云互动"],
        "extra_opt_req": "突出用户留存漏斗搭建、活动ROI复盘与SQL分析能力",
    },
    {
        "id": "dual_header_ai_pm_no_certs_interests",
        "layout": "dual_header",
        "name": "沈知行",
        "slug": "沈知行_无证书无兴趣",
        "target_position": "产品经理",
        "target_city": "北京",
        "salary_range": "20k-35k",
        "target_salary_k": (20.0, 35.0),
        "related_keywords": ["AI产品经理", "策略产品经理"],
        "relevance_terms": ["产品", "AI", "策略", "大模型", "算法", "需求", "规划", "智能"],
        "omitted_fields": ["certificates", "interests"],
        "omitted_headings": ["证书资质", "兴趣爱好"],
        "expected_numbers": ["62%", "79%", "38%", "11%"],
        "required_markers": ["沈知行", "星图智算最佳产品创新奖"],
        "extra_opt_req": "突出大模型RAG评测体系、A/B实验与跨团队协同成果",
    },
    {
        "id": "section_tags_backend_no_awards_interests",
        "layout": "section_tags",
        "name": "陆承宇",
        "slug": "陆承宇_无获奖无兴趣",
        "target_position": "后端开发",
        "target_city": "北京",
        "salary_range": "20k-35k",
        "target_salary_k": (20.0, 35.0),
        "related_keywords": ["Python开发", "服务端开发"],
        "relevance_terms": ["后端", "开发", "研发", "工程", "Python", "Java", "Go", "服务", "系统", "架构", "平台"],
        "omitted_fields": ["awards", "interests"],
        "omitted_headings": ["获奖荣誉", "兴趣爱好"],
        "expected_numbers": ["42%", "99.95%", "35%"],
        "required_markers": ["陆承宇", "软件设计师"],
        "extra_opt_req": "突出高并发接口性能调优、数据库慢查询治理与自动化监控落地",
    },
]


def next_resume_sequence(resume_dir: Path) -> int:
    """扫描目录中已有 NN_*.docx 文件，返回下一个递增编号。"""
    if not resume_dir.exists():
        return 1
    max_num = 0
    for item in resume_dir.glob("*.docx"):
        m = re.match(r"^(\d{2,})_", item.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def select_variant(variant_arg: str, seq_num: int) -> dict[str, Any]:
    """根据参数或序号自动轮换不同排版和人物内容的简历变体。"""
    if variant_arg == "auto":
        return RESUME_VARIANTS[(seq_num - 1) % len(RESUME_VARIANTS)]
    idx = int(variant_arg) % len(RESUME_VARIANTS)
    return RESUME_VARIANTS[idx]


def generate_varied_demo_docx(
    resume_dir: Path,
    variant_arg: str = "auto",
) -> tuple[Path, dict[str, Any]]:
    """生成带递增编号的全新格式模拟 .docx 简历。"""
    from docx import Document
    from docx.shared import Pt

    resume_dir.mkdir(parents=True, exist_ok=True)
    seq = next_resume_sequence(resume_dir)
    variant = select_variant(variant_arg, seq)
    date_tag = datetime.now().strftime("%Y%m%d")
    out_path = resume_dir / f"{seq:02d}_模拟简历_{variant['slug']}_{date_tag}.docx"

    doc = Document()
    layout = variant["layout"]

    if layout == "table_card":
        # 样式 1：信息表格 + 项目符号列表（刻意去掉获奖与证书）
        t = doc.add_table(rows=3, cols=2)
        t.cell(0, 0).text = "姓名：周明远"
        t.cell(0, 1).text = "求职意向：产品运营经理（北京 18-30K）"
        t.cell(1, 0).text = "电话：13800138002"
        t.cell(1, 1).text = "邮箱：zhoumingyuan@example.com"
        t.cell(2, 0).text = "学历：北京邮电大学 · 信息管理与信息系统（本科）"
        t.cell(2, 1).text = "毕业时间：2022.06"

        doc.add_heading("个人优势", level=2)
        doc.add_paragraph(
            "3年互联网产品运营与数据分析经验，熟悉用户增长漏斗、留存分析与活动复盘，熟练使用SQL、Python和Tableau。"
        )
        doc.add_heading("工作经历", level=2)
        doc.add_paragraph("星云互动科技有限公司 | 产品运营专员 | 2023.07 - 至今")
        doc.add_paragraph("负责核心内容频道日常运营与留存分析；搭建用户留存漏斗看板，推动次月留存提升12%。", style="List Bullet")
        doc.add_paragraph("策划6场站内促活活动，完成转化归因复盘，活动ROI提升18%。", style="List Bullet")
        doc.add_paragraph("蓝鲸数据服务有限公司 | 数据分析助理 | 2022.07 - 2023.06")
        doc.add_paragraph("使用SQL与Python清洗业务日活数据并输出周报，识别3个低效投放渠道。", style="List Bullet")
        doc.add_heading("项目经验", level=2)
        doc.add_paragraph("新用户7日留存提升专项 | 核心运营 | 2024.03 - 2024.09")
        doc.add_paragraph("通过SQL拆解新用户首日流失节点，联合产品优化新手引导流程，7日留存率由28%提升至35%。")
        doc.add_heading("专业技能", level=2)
        doc.add_paragraph("SQL、Python、Tableau、Excel、用户增长、活动运营、数据分析")

    elif layout == "dual_header":
        # 样式 2：双栏无框抬头 + 方括号加粗小节（刻意去掉证书与兴趣，保留获奖）
        hdr = doc.add_table(rows=2, cols=2)
        hdr.cell(0, 0).text = "沈知行"
        hdr.cell(0, 1).text = "求职意向：AI产品经理 / 策略产品经理（北京，20-35K）"
        hdr.cell(1, 0).text = "电话：13900139003"
        hdr.cell(1, 1).text = "邮箱：shenzhixing@example.com"

        def _banner(title: str):
            p = doc.add_paragraph()
            r = p.add_run(f"【{title}】")
            r.bold = True
            r.font.size = Pt(12)

        _banner("个人简介")
        doc.add_paragraph(
            "4年互联网及AI策略产品经验，主导过智能推荐排序与大模型知识库问答产品从0到1落地，"
            "擅长需求拆解、A/B实验评估与跨研发算法团队协同推进。"
        )
        _banner("教育背景")
        doc.add_paragraph("2017.09 - 2021.06 | 浙江大学 | 软件工程 | 本科")
        _banner("工作经历")
        doc.add_paragraph("2023.04 - 至今 | 星图智算科技有限公司 | 高级AI产品经理")
        doc.add_paragraph(
            "负责企业级智能客服与RAG知识库检索产品规划；构建多维度评测集并推动算法迭代，"
            "首问解决率由62%提升至79%，月活企业客户增长至140家。"
        )
        doc.add_paragraph("2021.07 - 2023.03 | 云策数科有限公司 | 策略产品经理")
        doc.add_paragraph(
            "负责内容分发排序策略与冷启动机制优化；主导12次核心A/B实验，"
            "推动信息流点击率提升9.5%，次日留存提升4.2个百分点。"
        )
        _banner("项目经历")
        doc.add_paragraph("2024.01 - 2024.10 | 智能知识库问答2.0重构 | 产品负责人")
        doc.add_paragraph(
            "重新设计文档切片与检索重排交互流程，上线引用溯源高亮功能，"
            "将人工复核耗时降低38%，客户续费率提升11%。"
        )
        _banner("核心技能")
        doc.add_paragraph("产品规划 / PRD撰写 / Axure / Figma / SQL / Python基础 / RAG评测 / A/B实验 / 策略排序")
        _banner("获奖荣誉")
        doc.add_paragraph("2024年度星图智算最佳产品创新奖")

    else:
        # 样式 3：纯分段紧凑排版 + 证书保留（刻意去掉获奖与兴趣）
        p0 = doc.add_paragraph()
        r0 = p0.add_run("陆承宇  |  后端开发工程师（北京 · 20-35K）")
        r0.bold = True
        r0.font.size = Pt(14)
        doc.add_paragraph("手机：13700137004   邮箱：luchengyu@example.com")

        doc.add_heading("一、个人总结", level=2)
        doc.add_paragraph(
            "4年Python与Go服务端研发经验，熟悉FastAPI、PostgreSQL、Redis与分布式任务队列，"
            "注重接口性能调优与系统高可用治理。"
        )
        doc.add_heading("二、教育经历", level=2)
        doc.add_paragraph("哈尔滨工业大学 | 计算机科学与技术 | 本科 | 2017.09 - 2021.06")
        doc.add_heading("三、工作经历", level=2)
        doc.add_paragraph("极光数联科技有限公司 — 后端开发工程师（2022.08 - 至今）")
        doc.add_paragraph(
            "负责订单与数据采集核心微服务开发；重构热点接口缓存与慢SQL索引，"
            "将P99响应延迟降低42%，核心服务可用性稳定在99.95%。"
        )
        doc.add_paragraph("清风互娱信息有限公司 — 初级后端开发（2021.07 - 2022.07）")
        doc.add_paragraph(
            "参与用户中心与消息推送模块开发，编写自动化集成测试脚本，线上缺陷率下降35%。"
        )
        doc.add_heading("四、代表项目", level=2)
        doc.add_paragraph("异步任务调度与限流网关改造 | 核心研发 | 2023.09 - 2024.06")
        doc.add_paragraph(
            "基于Redis与FastAPI实现分层令牌桶限流与失败重试队列，支撑日均300万次接口调用平稳运行。"
        )
        doc.add_heading("五、技术栈", level=2)
        doc.add_paragraph("Python, FastAPI, Go, PostgreSQL, MySQL, Redis, Docker, Linux, Git")
        doc.add_heading("六、证书资质", level=2)
        doc.add_paragraph("全国计算机技术与软件专业技术资格（中级）——软件设计师")

    doc.save(str(out_path))
    return out_path, variant


def parse_salary_range_k(text: str) -> tuple[float, float] | None:
    """解析常见中文岗位薪资文本为 (最低K, 最高K) 区间；无法解析返回 None。"""
    if not isinstance(text, str) or not text.strip():
        return None
    s = text.strip().lower().replace("—", "-").replace("–", "-").replace("~", "-").replace("至", "-")
    if any(w in s for w in ("面议", "薪资面议", "不限")):
        return None

    # 匹配如 15k-25k / 15-25k / 15K-25K·14薪
    m_k = re.search(r"(\d+(?:\.\d+)?)\s*k?\s*-\s*(\d+(?:\.\d+)?)\s*k", s)
    if m_k:
        lo, hi = float(m_k.group(1)), float(m_k.group(2))
        return (min(lo, hi), max(lo, hi))

    # 匹配如 1.5万-2.5万 / 15-25万/年
    m_w = re.search(r"(\d+(?:\.\d+)?)\s*万?\s*-\s*(\d+(?:\.\d+)?)\s*万", s)
    if m_w:
        lo, hi = float(m_w.group(1)), float(m_w.group(2))
        if "年" in s or hi >= 8:
            # 视为年薪（万/年 -> 月K）
            return (round(lo * 10 / 12, 1), round(hi * 10 / 12, 1))
        return (round(lo * 10, 1), round(hi * 10, 1))

    # 匹配纯数字元/月 如 15000-25000
    m_yuan = re.search(r"(\d{4,6})\s*-\s*(\d{4,6})", s)
    if m_yuan:
        lo, hi = float(m_yuan.group(1)) / 1000.0, float(m_yuan.group(2)) / 1000.0
        return (round(min(lo, hi), 1), round(max(lo, hi), 1))

    return None


def compute_job_collection_metrics(
    jobs: list[dict[str, Any]],
    relevance_terms: list[str],
    target_salary_k: tuple[float, float],
) -> dict[str, Any]:
    """计算岗位采集的多维质量指标：数量、来源、溯源率、精准度、薪资匹配率、打分分布。"""
    total = len(jobs)
    if total == 0:
        return {
            "total": 0,
            "sources": {},
            "url_valid_count": 0,
            "url_valid_rate": 0.0,
            "relevant_count": 0,
            "precision_rate": 0.0,
            "salary_labeled_count": 0,
            "salary_matched_count": 0,
            "salary_match_rate": 0.0,
            "scored_count": 0,
            "score_avg": 0.0,
            "score_max": None,
            "score_min": None,
        }

    sources: dict[str, int] = {}
    url_valid = 0
    relevant = 0
    salary_labeled = 0
    salary_matched = 0
    scores: list[float] = []

    lowered_terms = [t.lower() for t in relevance_terms if t]
    t_lo, t_hi = target_salary_k

    for job in jobs:
        src = str(job.get("source") or job.get("platform") or "unknown")
        sources[src] = sources.get(src, 0) + 1

        url = str(job.get("url") or "").strip()
        if url.startswith(("http://", "https://")):
            url_valid += 1

        title_blob = f"{job.get('title', '')} {job.get('category', '')}".lower()
        if any(term in title_blob for term in lowered_terms):
            relevant += 1

        parsed_sal = parse_salary_range_k(str(job.get("salary") or ""))
        if parsed_sal is not None:
            salary_labeled += 1
            j_lo, j_hi = parsed_sal
            # 区间有交集即视为薪资匹配
            if j_hi >= t_lo and j_lo <= t_hi:
                salary_matched += 1

        sc = job.get("match_score")
        if isinstance(sc, (int, float)):
            scores.append(float(sc))

    return {
        "total": total,
        "sources": sources,
        "url_valid_count": url_valid,
        "url_valid_rate": round(url_valid / total * 100, 1),
        "relevant_count": relevant,
        "precision_rate": round(relevant / total * 100, 1),
        "salary_labeled_count": salary_labeled,
        "salary_matched_count": salary_matched,
        "salary_match_rate": round(salary_matched / salary_labeled * 100, 1) if salary_labeled else 0.0,
        "scored_count": len(scores),
        "score_avg": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "score_max": max(scores) if scores else None,
        "score_min": min(scores) if scores else None,
    }


def _log(msg: str) -> None:
    print(msg, flush=True)


def run_frontend_smoke_check() -> dict[str, Any]:
    """运行前端 Playwright 模拟测试 + 构建产物零控制台报错核查。"""
    t0 = time.perf_counter()
    res: dict[str, Any] = {"ok": False, "ui_tests_ok": False, "dist_smoke_ok": False, "console_errors": []}

    # 1. 运行仓库现有 Playwright 前端 UI 进度/意图测试
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests/test_job_scrape_progress_ui.py",
            "tests/test_job_intent_progress_ui.py",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    res["ui_tests_ok"] = proc.returncode == 0
    if proc.returncode != 0:
        res["ui_tests_error"] = (proc.stderr or proc.stdout)[-400:]

    # 2. 对 frontend/dist 启一个同进程临时静态服务，验证同源资源 200 及 Step 3 简历模板零 ReferenceError
    dist_dir = PROJECT_ROOT / "frontend" / "dist"
    if not dist_dir.exists():
        res["dist_error"] = "frontend/dist 不存在，请先执行 npm run build"
        res["elapsed_s"] = round(time.perf_counter() - t0, 2)
        return res

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(dist_dir))

    class _QuietTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    class _SilentHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dist_dir), **kwargs)

        def log_message(self, format, *args):
            return

    httpd = _QuietTCPServer(("127.0.0.1", 0), _SilentHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    page_errors: list[str] = []
    failed_assets: list[str] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = None
            last_launch_err = None
            for launch_kwargs in (
                {"channel": "msedge", "headless": True},
                {"channel": "chrome", "headless": True},
                {"headless": True},
            ):
                try:
                    browser = pw.chromium.launch(**launch_kwargs)
                    break
                except Exception as exc:
                    last_launch_err = exc
            if browser is None:
                raise RuntimeError(f"无法启动 Playwright 浏览器: {last_launch_err}")
            context = browser.new_context()
            page = context.new_page()
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            def _mock_api(route):
                url = route.request.url
                if "/api/resumes/list" in url:
                    body = {
                        "ok": True,
                        "resumes": [
                            {"filename": "demo_a.json", "name": "示例甲"},
                            {"filename": "demo_b.json", "name": "示例乙"},
                        ],
                    }
                elif "/api/jobs/list" in url:
                    body = {"ok": True, "files": []}
                elif "/api/jobs/sources" in url:
                    body = {"ok": True, "sources": []}
                elif "/api/status" in url:
                    body = {"ok": True, "steps": {}}
                else:
                    body = {"ok": True, "data": {}}
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(body, ensure_ascii=False),
                )

            page.route("**/api/**", _mock_api)
            page.on(
                "response",
                lambda resp: failed_assets.append(f"{resp.status} {resp.url}")
                if f"127.0.0.1:{port}/assets/" in resp.url and resp.status >= 400
                else None,
            )

            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle", timeout=20000)
            # 切到 AI 助手 -> 简历模板并切换下拉框，验证 setTPhoto ReferenceError 已彻底根除
            for label in ("AI 助手", "简历模板"):
                loc = page.get_by_text(label).first
                if loc.count() > 0:
                    loc.click()
                    page.wait_for_timeout(300)
            sel = page.locator("select").first
            if sel.count() > 0:
                opts = sel.locator("option").all()
                if len(opts) >= 2:
                    val = opts[1].get_attribute("value")
                    if val:
                        sel.select_option(val)
                        page.wait_for_timeout(300)

            browser.close()

        res["console_errors"] = page_errors
        res["failed_assets"] = failed_assets
        res["dist_smoke_ok"] = len(page_errors) == 0 and len(failed_assets) == 0
    except Exception as exc:
        res["dist_error"] = str(exc)
        res["dist_smoke_ok"] = False
    finally:
        httpd.shutdown()
        httpd.server_close()

    res["ok"] = bool(res["ui_tests_ok"] and res["dist_smoke_ok"])
    res["elapsed_s"] = round(time.perf_counter() - t0, 2)
    return res


def run_health_check(args: argparse.Namespace) -> dict[str, Any]:
    """执行完整隔离 7 步后端真机测试 + 前端模拟验证。"""
    t_total = time.perf_counter()
    report: dict[str, Any] = {
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "steps": {},
        "passed": False,
    }

    tmp_ctx = tempfile.TemporaryDirectory(prefix="offerforge_health_")
    runtime_dir = tmp_ctx.name if not args.keep_runtime else tempfile.mkdtemp(prefix="offerforge_health_keep_")
    if args.keep_runtime:
        tmp_ctx.cleanup()

    os.environ["OFFERFORGE_RUNTIME_DIR"] = runtime_dir
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    try:
        from config import DATA_DIR, LOGS_DIR, RESUMES_DIR
        from modules.deepseek_client import resolve_llm_config
        from fastapi.testclient import TestClient

        for d in (DATA_DIR, LOGS_DIR, RESUMES_DIR):
            os.makedirs(d, exist_ok=True)

        cfg = resolve_llm_config()
        report["llm"] = {
            "provider": cfg["provider"],
            "model": cfg["model"],
            "fallback_model": cfg.get("fallback_model", ""),
            "timeout": cfg["timeout"],
        }
        _log(
            f"[INIT] provider={cfg['provider']} | model={cfg['model']} | "
            f"fallback={cfg.get('fallback_model', '')} | runtime={runtime_dir}"
        )

        # STEP 1: 生成全新格式编号简历
        resume_dir = Path(runtime_dir) / "demo_resumes" if args.temp_resume else Path(args.resume_dir)
        docx_path, variant = generate_varied_demo_docx(resume_dir, args.variant)
        report["steps"]["step1_generate_resume"] = {
            "ok": True,
            "file": str(docx_path),
            "variant": variant["id"],
            "layout": variant["layout"],
            "omitted_fields": variant["omitted_fields"],
        }
        _log(f"[STEP 1/7] 生成新简历完成: {docx_path.name} (layout={variant['layout']}, 刻意留空={variant['omitted_fields']})")

        import app as offerforge_app

        with TestClient(offerforge_app.app) as client:
            # STEP 2: 导入与结构化解析
            t0 = time.perf_counter()
            with open(docx_path, "rb") as fh:
                r_up = client.post(
                    "/api/resumes/upload",
                    files={
                        "file": (
                            docx_path.name,
                            fh,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                )
            t2 = round(time.perf_counter() - t0, 2)
            up_json = r_up.json()
            assert r_up.status_code == 200 and up_json.get("ok"), f"Step 2 上传解析失败: {r_up.status_code} {up_json}"

            resume_file = (
                up_json.get("file")
                or up_json.get("filename")
                or (up_json.get("data") or {}).get("filename")
            )
            if not resume_file:
                rlist = client.get("/api/resumes/list").json()
                items = rlist.get("resumes") or rlist.get("files") or rlist.get("data") or []
                if items:
                    first = items[0]
                    resume_file = first.get("filename") if isinstance(first, dict) else first
            assert resume_file, "无法获取解析后的简历文件名"

            profile = up_json.get("profile") or up_json.get("data") or {}
            if not profile.get("name"):
                det = client.get(f"/api/resumes/detail/{resume_file}").json()
                profile = det.get("data") or det

            omitted_clean = all(not profile.get(f) for f in variant["omitted_fields"])
            profile_blob = json.dumps(profile, ensure_ascii=False)
            numbers_ok = all(num in profile_blob for num in variant["expected_numbers"])
            markers_ok = all(mk in profile_blob for mk in variant["required_markers"])

            report["steps"]["step2_parse"] = {
                "ok": bool(omitted_clean and numbers_ok and markers_ok),
                "elapsed_s": t2,
                "resume_file": resume_file,
                "name": profile.get("name"),
                "omitted_zero_hallucination": omitted_clean,
                "numbers_preserved": numbers_ok,
                "markers_preserved": markers_ok,
            }
            _log(
                f"[STEP 2/7] 导入解析完成 ({t2}s) | name={profile.get('name')} | "
                f"空板块零编造={omitted_clean} | 关键数字保真={numbers_ok} | 核心标识保真={markers_ok}"
            )

            # STEP 3: 70/30 专项优化
            t0 = time.perf_counter()
            r_opt = client.post(
                "/api/resume/optimize",
                data={
                    "resume_file": resume_file,
                    "target": variant["target_position"],
                    "extra": variant["extra_opt_req"],
                    "job_description": "",
                },
            )
            t3 = round(time.perf_counter() - t0, 2)
            opt_json = r_opt.json()
            assert r_opt.status_code == 200 and opt_json.get("ok"), f"Step 3 专项优化失败: {r_opt.status_code} {opt_json}"

            opt_resume = opt_json.get("optimized_resume") or {}
            opt_summary = opt_json.get("optimized_summary") or opt_resume.get("summary") or ""
            opt_omitted_clean = all(not opt_resume.get(f) for f in variant["omitted_fields"])
            opt_blob = json.dumps(opt_resume, ensure_ascii=False)
            opt_nums_ok = all(num in opt_blob for num in variant["expected_numbers"])
            report["steps"]["step3_optimize"] = {
                "ok": bool(len(opt_summary) >= 60 and opt_omitted_clean and opt_nums_ok),
                "elapsed_s": t3,
                "summary_len": len(opt_summary),
                "warnings_count": len(opt_json.get("optimization_warnings") or []),
                "omitted_zero_hallucination": opt_omitted_clean,
                "numbers_preserved": opt_nums_ok,
            }
            _log(
                f"[STEP 3/7] 70/30专项优化完成 ({t3}s) | 新摘要={len(opt_summary)}字 | "
                f"空板块零编造={opt_omitted_clean} | 数字保真={opt_nums_ok} | 告警={len(opt_json.get('optimization_warnings') or [])}"
            )

            # STEP 4: 双模板渲染
            t0 = time.perf_counter()
            tpl_res: dict[str, Any] = {}
            all_tpl_ok = True
            for style in ("classic", "dual"):
                r_tpl = client.post(
                    "/api/resume/template",
                    data={"resume_file": resume_file, "template_style": style},
                )
                ctype = (r_tpl.headers.get("content-type") or "").lower()
                html = (r_tpl.json().get("html") or "") if "application/json" in ctype else (r_tpl.text or "")
                headings_hidden = all(h not in html for h in variant["omitted_headings"])
                has_name = variant["name"] in html
                no_placeholder = "暂无" not in html
                ok_style = r_tpl.status_code == 200 and len(html) > 200 and headings_hidden and has_name and no_placeholder
                all_tpl_ok = all_tpl_ok and ok_style
                tpl_res[style] = {
                    "ok": ok_style,
                    "html_len": len(html),
                    "has_name": has_name,
                    "omitted_headings_hidden": headings_hidden,
                    "no_placeholder": no_placeholder,
                }
            t4 = round(time.perf_counter() - t0, 2)
            report["steps"]["step4_templates"] = {"ok": all_tpl_ok, "elapsed_s": t4, "styles": tpl_res}
            _log(f"[STEP 4/7] 双模板渲染完成 ({t4}s) | all_ok={all_tpl_ok} | styles={list(tpl_res.keys())}")

            # STEP 5: 多源真实岗位采集 + 自动打分
            t0 = time.perf_counter()
            r_sc = client.post(
                "/api/jobs/scrape",
                data={
                    "platforms": "iguopin,ncss,meituan",
                    "resume_file": resume_file,
                    "salary_range": variant["salary_range"],
                    "target_position": variant["target_position"],
                    "target_city": variant["target_city"],
                    "restrictions": "",
                    "related_keywords": json.dumps(variant["related_keywords"], ensure_ascii=False),
                },
            )
            sc_json = r_sc.json()
            assert r_sc.status_code == 200 and sc_json.get("ok"), f"Step 5 采集启动失败: {sc_json}"

            final_status = None
            for _ in range(180):
                st = client.get("/api/jobs/scrape/status").json()
                status_obj = st.get("data") if isinstance(st.get("data"), dict) else st
                if not status_obj.get("running") or status_obj.get("status") in ("completed", "done", "error", "cancelled", "failed"):
                    final_status = status_obj
                    break
                time.sleep(1.0)
            t5 = round(time.perf_counter() - t0, 2)
            assert final_status and final_status.get("status") in ("completed", "done"), f"Step 5 采集未正常结束: {final_status}"

            jlist = client.get("/api/jobs/list").json()
            batches = jlist.get("files") or jlist.get("data") or []
            assert batches, "未生成岗位批次"
            jobs_file = batches[0]["filename"] if isinstance(batches[0], dict) else batches[0]
            bdet = client.get(f"/api/jobs/detail/{jobs_file}").json()
            jobs = bdet.get("jobs") or (bdet.get("data") or {}).get("jobs") or []

            metrics = compute_job_collection_metrics(
                jobs, variant["relevance_terms"], variant["target_salary_k"]
            )
            step5_ok = metrics["total"] >= 5 and metrics["url_valid_rate"] >= 90.0 and metrics["scored_count"] >= 1
            report["steps"]["step5_collect_and_score"] = {
                "ok": step5_ok,
                "elapsed_s": t5,
                "jobs_file": jobs_file,
                **metrics,
            }
            _log(
                f"[STEP 5/7] 多源采集+自动打分完成 ({t5}s) | 总数={metrics['total']} | 来源={metrics['sources']} | "
                f"溯源URL率={metrics['url_valid_rate']}% | 标题精准度={metrics['precision_rate']}% | "
                f"薪资匹配率={metrics['salary_match_rate']}% ({metrics['salary_matched_count']}/{metrics['salary_labeled_count']}) | "
                f"自动打分={metrics['scored_count']}条(均分{metrics['score_avg']})"
            )

            # STEP 6A: 批量 JD 匹配缓存秒开
            t0 = time.perf_counter()
            r_bs = client.post(
                "/api/jobs/batch-score-json",
                json={"resume_file": resume_file, "jobs_file": jobs_file},
            )
            t6a_ms = int((time.perf_counter() - t0) * 1000)
            bs_json = r_bs.json()
            step6a_ok = r_bs.status_code == 200 and bool(bs_json.get("ok")) and bool(bs_json.get("cached"))
            report["steps"]["step6a_batch_cache"] = {
                "ok": step6a_ok,
                "elapsed_ms": t6a_ms,
                "cached": bs_json.get("cached"),
                "returned_jobs": len(bs_json.get("jobs") or []),
            }
            _log(f"[STEP 6A/7] 批量JD匹配缓存秒开 ({t6a_ms} ms) | cached={bs_json.get('cached')} | jobs={len(bs_json.get('jobs') or [])}")

            # STEP 6B: 单份真实 JD 深度匹配
            pick_idx = 0
            pick_job = jobs[0]
            for idx, j in enumerate(jobs):
                if len(str(j.get("description") or "")) >= 40:
                    pick_idx = idx
                    pick_job = j
                    break

            t0 = time.perf_counter()
            r_jm = client.post(
                "/api/jd/match",
                data={
                    "resume_file": resume_file,
                    "jd_text": f"{pick_job.get('title', '')} @ {pick_job.get('company', '')}\n{pick_job.get('description', '')}",
                },
            )
            t6b = round(time.perf_counter() - t0, 2)
            jm_json = r_jm.json()
            step6b_ok = r_jm.status_code == 200 and bool(jm_json.get("ok")) and isinstance(jm_json.get("overall_score"), (int, float))
            report["steps"]["step6b_single_jd_match"] = {
                "ok": step6b_ok,
                "elapsed_s": t6b,
                "job": f"{pick_job.get('title', '')} @ {pick_job.get('company', '')}",
                "overall_score": jm_json.get("overall_score"),
                "verdict": jm_json.get("verdict", ""),
            }
            _log(
                f"[STEP 6B/7] 单份真实JD深度匹配完成 ({t6b}s) | {pick_job.get('title')}@{pick_job.get('company')} | "
                f"score={jm_json.get('overall_score')} | verdict={jm_json.get('verdict')}"
            )

            # STEP 7: 针对真实 JD 精准简历优化
            t0 = time.perf_counter()
            r_po = client.post(
                "/api/resume/precision-optimize",
                data={
                    "resume_file": resume_file,
                    "jobs_file": jobs_file,
                    "job_indices": str(pick_idx),
                },
            )
            t7 = round(time.perf_counter() - t0, 2)
            po_json = r_po.json()
            po_res = po_json.get("result") or po_json.get("data") or po_json
            po_sum = po_res.get("optimized_summary") or po_res.get("summary") or ""
            step7_ok = r_po.status_code == 200 and bool(po_json.get("ok")) and len(po_sum) >= 40
            report["steps"]["step7_precision_optimize"] = {
                "ok": step7_ok,
                "elapsed_s": t7,
                "summary_len": len(po_sum),
                "preview": po_sum[:80],
            }
            _log(f"[STEP 7/7] 针对真实JD精准优化完成 ({t7}s) | ok={step7_ok} | summary_len={len(po_sum)}")

        # Frontend Simulation Check
        if not args.skip_frontend:
            _log("[FRONTEND] 开始执行 Playwright 前端模拟与构建产物零报错核验...")
            fe_res = run_frontend_smoke_check()
            report["steps"]["frontend_simulation"] = fe_res
            _log(
                f"[FRONTEND] 前端模拟核验完成 ({fe_res.get('elapsed_s')}s) | "
                f"ui_tests={fe_res.get('ui_tests_ok')} | dist_zero_errors={fe_res.get('dist_smoke_ok')} | "
                f"page_errors={len(fe_res.get('console_errors') or [])}"
            )

        report["total_elapsed_s"] = round(time.perf_counter() - t_total, 2)
        report["passed"] = all(bool(v.get("ok")) for v in report["steps"].values())
        return report
    finally:
        if not args.keep_runtime:
            tmp_ctx.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="OfferForge 2.0 一键多维全链路体检脚本")
    parser.add_argument("--variant", default="auto", help="简历模板变体: auto | 0 | 1 | 2")
    parser.add_argument("--resume-dir", default=str(DEFAULT_DEMO_RESUME_DIR), help="模拟简历输出目录")
    parser.add_argument("--temp-resume", action="store_true", help="将模拟简历也生成到临时目录（不写入桌面）")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过 Playwright 前端模拟检查")
    parser.add_argument("--frontend-only", action="store_true", help="仅运行 Playwright 前端模拟与零报错核验")
    parser.add_argument("--keep-runtime", action="store_true", help="保留隔离临时运行目录用于排错")
    parser.add_argument("--report-json", default="", help="可选：将完整多维报告保存为 JSON 文件")
    args = parser.parse_args()

    if args.frontend_only:
        fe = run_frontend_smoke_check()
        _log(
            f"[FRONTEND] 前端模拟核验完成 ({fe.get('elapsed_s')}s) | "
            f"ui_tests={fe.get('ui_tests_ok')} | dist_zero_errors={fe.get('dist_smoke_ok')} | "
            f"page_errors={len(fe.get('console_errors') or [])}"
        )
        if not fe.get("ok"):
            _log(json.dumps(fe, ensure_ascii=False, indent=2))
        return 0 if fe.get("ok") else 1

    report = run_health_check(args)
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    _log("\n" + "=" * 68)
    _log(f"OfferForge 2.0 多维体检总结 | 总耗时: {report.get('total_elapsed_s')}s | 结果: {'PASS' if report['passed'] else 'FAIL'}")
    for k, v in report["steps"].items():
        status = "PASS" if v.get("ok") else "FAIL"
        _log(f"  - {k:26s}: {status}")
    _log("=" * 68)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

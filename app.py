# ============================================
# app.py — Web 后端服务器（完整版 v3：加入简历历史管理）
# ============================================
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
from datetime import datetime
from config import *

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 智能简历助手 · 控制台</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <!-- 粒子背景 -->
    <canvas id="particleCanvas"></canvas>

    <!-- 主应用 -->
    <div id="app">
        <!-- ====== 顶部状态栏 ====== -->
        <header class="topbar">
            <div class="logo">
                <div class="icon">⚡</div>
                <h1>AI 智能简历助手</h1>
            </div>
            <div class="stats" id="statsBar"></div>
            <div class="status-dot">
                <div class="dot"></div>
                <span id="uptime">系统运行中</span>
            </div>
        </header>

        <!-- ====== 三栏主体 ====== -->
        <div class="main-content">
            <!-- 左侧：步骤导航 -->
            <aside class="sidebar">
                <div class="sidebar-header">📋 项目进度</div>
                <div class="steps-container" id="stepsList"></div>
            </aside>

            <!-- 中央：操作区 -->
            <main class="center">
                <div class="center-header">
                    <h2 id="centerTitle">控制台</h2>
                    <div class="subtitle" id="centerSubtitle">AI 驱动的智能求职助手</div>
                </div>
                <div class="center-body" id="centerBody">
                    <!-- 动态填充 -->
                </div>
            </main>

            <!-- 右侧：实时日志 -->
            <aside class="log-panel">
                <div class="log-header">
                    <span>🔴 实时日志</span>
                    <div class="live-dot"></div>
                </div>
                <div class="log-stream" id="logStream"></div>
            </aside>
        </div>

        <!-- ====== 底部 ====== -->
        <footer class="footer">
            AI 智能简历助手 v1.0 · DeepSeek 驱动 · 本地运行 · <span id="wsStatus">🟡 连接中...</span>
        </footer>
    </div>

    <script src="/static/v7.js"></script>
</body>
</html>
"""
from modules.resume_parser import parse_resume, save_parsed_result, list_resumes
from modules.deepseek_client import DeepSeekClient
from modules.job_scraper import JobScraper, load_profile, extract_keywords, extract_location
from modules.jd_matcher import match_resume_to_jd, quick_match

# ============================================
# 步骤状态
# ============================================
STEPS = [
    {"id": 1,  "name": "简历解析",            "icon": "file-text",  "status": "done",       "detail": "上传/解析/删除"},
    {"id": 2,  "name": "智能优化简历",        "icon": "sparkles",   "status": "done",       "detail": "DeepSeek AI优化"},
    {"id": 3,  "name": "简历模板",            "icon": "layout",     "status": "done",       "detail": "6套模板+证件照"},
    {"id": 4,  "name": "岗位采集",            "icon": "search",     "status": "done",       "detail": "51前程无忧/采集历史"},
    {"id": 5,  "name": "JD 匹配度评分",       "icon": "target",     "status": "done",       "detail": "AI 打分"},
    {"id": 6,  "name": "精准简历优化",        "icon": "sparkles",   "status": "done",       "detail": "JD定向优化"},
    {"id": 7,  "name": "自动打招呼",          "icon": "send",       "status": "done",       "detail": "半自动投递"},
]

STATS = {
    "resumes": 0,
    "jobs_found": 0,
    "deliveries": 0,
    "replies": 0,
    "interviews": 0,
    "uptime": datetime.now().strftime("%H:%M:%S")
}

connected_clients = set()
scraper_status = {"running": False, "progress": "", "jobs_count": 0, "last_run": ""}
log_buffer = []


def add_log(msg: str, level: str = "info"):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "level": level, "msg": msg}
    log_buffer.append(entry)
    if len(log_buffer) > 100:
        log_buffer.pop(0)
    for ws in list(connected_clients):
        try:
            asyncio.ensure_future(ws.send_json({"type": "log", "data": entry}))
        except:
            connected_clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    add_log("系统启动", "success")
    yield
    add_log("系统关闭", "warning")

app = FastAPI(title="AI 智能简历助手", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 自定义静态文件服务（禁用缓存，确保前端更新生效）
from starlette.staticfiles import StaticFiles as _StaticFiles
class NoCacheStaticFiles(_StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.mount("/static", NoCacheStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.get("/")
async def root():
    import time
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/app?t={int(time.time())}")


@app.get("/go")
async def go():
    import glob, os, time
    files = sorted(glob.glob(os.path.join(BASE_DIR, "static", "dashboard_*.html")), reverse=True)
    if files:
        newest = os.path.basename(files[0])
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/static/{newest}")
    return {"error": "no dashboard found"}


@app.get("/app")
async def app_page():
    import time
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(BASE_DIR, "static", "v7.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    t = str(int(time.time()))
    html = html.replace("v8.js?v=", "v8.js?v=" + t)
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})


@app.get("/api/status")
async def get_status():
    data_dir = DATA_DIR
    parsed_count = 0
    if os.path.exists(data_dir):
        parsed_count = len([f for f in os.listdir(data_dir) if f.startswith("resume_") and f.endswith(".json")])
    STATS["resumes"] = parsed_count
        # 统计投递数
    dh_path = os.path.join(data_dir, "deliver_history.json")
    if os.path.exists(dh_path):
        try:
            with open(dh_path, "r", encoding="utf-8") as f:
                dh = json.load(f)
            STATS["deliveries"] = len(dh) if isinstance(dh, dict) else 0
        except:
            STATS["deliveries"] = 0
    return {"steps": STEPS, "stats": STATS}


@app.post("/api/steps/{step_id}/start")
async def start_step(step_id: int):
    for s in STEPS:
        if s["id"] == step_id:
            s["status"] = "in_progress"
            add_log(f"开始步骤: {s['name']}", "info")
            return {"ok": True, "step": s}
    return {"ok": False, "error": "步骤不存在"}


@app.post("/api/steps/{step_id}/complete")
async def complete_step(step_id: int):
    for s in STEPS:
        if s["id"] == step_id:
            s["status"] = "done"
            add_log(f"完成步骤: {s['name']}", "success")
            return {"ok": True, "step": s}
    return {"ok": False, "error": "步骤不存在"}


@app.get("/api/resumes/files")
async def get_resume_files():
    """列出 resumes 文件夹里所有简历文件"""
    files = list_resumes()
    return {"files": files, "count": len(files)}


@app.post("/api/resumes/upload")
async def upload_resume(file: UploadFile = File(...)):
    """上传简历文件并解析"""
    os.makedirs(RESUMES_DIR, exist_ok=True)
    file_path = os.path.join(RESUMES_DIR, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    add_log(f"收到简历文件: {file.filename}", "info")
    
    result = parse_resume(file_path)
    
    if "error" in result:
        add_log(f"简历解析失败: {result['error']}", "error")
        return {"ok": False, "error": result["error"]}
    
    json_path = save_parsed_result(result)
    add_log(f"简历解析成功: {result.get('name', '未知')}", "success")
    
    return {"ok": True, "data": result, "saved_to": json_path}


@app.get("/api/resumes/list")
async def list_parsed_resumes():
    """
    列出所有已解析的简历（带摘要，方便翻阅）
    大白话：返回一个列表，每条包含姓名、岗位、解析时间，让你知道有哪些简历
    """
    data_dir = DATA_DIR
    resumes = []
    if os.path.exists(data_dir):
        for f in sorted(os.listdir(data_dir), reverse=True):
            if f.startswith("resume_") and f.endswith(".json"):
                filepath = os.path.join(data_dir, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    resumes.append({
                        "filename": f,
                        "name": data.get("name", "未知"),
                        "position": data.get("desired_position", ""),
                        "desired_salary": data.get("desired_salary", ""),
                        "skills": data.get("skills", [])[:5],
                        "parsed_at": data.get("parsed_at", ""),
                        "summary": data.get("summary", "")[:80]
                    })
                except:
                    resumes.append({"filename": f, "name": "解析失败", "error": True})
    return {"resumes": resumes, "count": len(resumes)}


@app.get("/api/resumes/detail/{filename}")
async def get_resume_detail(filename: str):
    """
    查看某一份简历的完整解析结果
    大白话：传入文件名，返回完整的结构化数据
    """
    data_dir = DATA_DIR
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "简历文件不存在"}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/resumes/latest")
async def get_latest_parsed():
    """获取最近解析的一份简历（兼容旧版）"""
    data_dir = DATA_DIR
    json_files = []
    if os.path.exists(data_dir):
        for f in os.listdir(data_dir):
            if f.startswith("resume_") and f.endswith(".json"):
                json_files.append(os.path.join(data_dir, f))
    if json_files:
        json_files.sort(key=os.path.getmtime, reverse=True)
        with open(json_files[0], "r", encoding="utf-8") as f:
            return {"ok": True, "data": json.load(f)}
    return {"ok": False, "error": "没有已解析的简历"}


@app.post("/api/resume/optimize")
async def optimize_resume(
    resume_file: str = Form(""),
    target: str = Form(""),
    extra: str = Form("")
):
    """AI智能优化简历 - 三维度优化：项目经验/实习经验/技能能力"""
    if not resume_file or not target:
        return {"ok": False, "error": "缺少简历文件或求职意向"}
    data_dir = DATA_DIR
    filepath = os.path.join(data_dir, resume_file)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "简历文件不存在"}
    with open(filepath, "r", encoding="utf-8") as f:
        profile = json.load(f)
    
    # Extract experiences: separate projects from internships
    work_exp = profile.get("work_experience", [])
    projects = []
    internships = []
    for w in work_exp:
        pos = w.get("position", "")
        company = w.get("company", "")
        desc = w.get("description", "")
        dur = w.get("duration", "")
        # Classify: personal projects vs company internships
        if "个人" in company or "项目" in pos or "创作者" in pos:
            projects.append(f"- {pos}：{desc}（{dur}）")
        else:
            internships.append(f"- {company} | {pos} | {dur}：{desc}")
    
        projects_str = "\n".join(projects) if projects else "无项目经验记录"
    internships_str = "\n".join(internships) if internships else "无实习经验记录"
    skills_list = profile.get("skills", [])
    skills_str = "、".join(skills_list) if skills_list else "无技能记录"
    edu = profile.get("education", [])
    edu_str = ""
    for e in edu[:2]:
        edu_str += f"- {e.get('school','')} | {e.get('major','')} | {e.get('degree','')}\n"
    has_target = extra and len(extra.strip()) > 0
    extra_reqs = extra.strip() if extra else ""

    prompt = f"""你是一位拥有20年经验的资深猎头和简历顾问，深谙各行业的真实用人标准和招聘习惯。

## 核心使命
根据目标岗位，为客户量身定制一份高匹配度、真实可信的优化简历。

## 额外要求（必须100%遵守，优先级最高）
如果用户提交了额外要求，以下每条要求都是铁律，AI不得擅自修改、忽略、或超越：
- 用户写明的年限、数字、规模、地点必须完全尊重
- 例如用户说"1年经验"，就不能写成"半年"或"2年"或任何不同数字
- 例如用户说"广州的公司"，就不能写成深圳、北京或其他城市
- 不得添加用户未提及的夸大描述（如"领导整个团队""独立负责百万项目"）
- 优化必须基于用户提供的原始信息做润色，不能无中生有
- 当额外要求与上述行业规则冲突时，以额外要求为准
{("\n\n【额外要求】\n" + extra_reqs) if extra_reqs else ""}

## 行业真实性铁律（必须遵守）

### 1. 技能匹配必须精准
不同行业的核心技能截然不同，严禁跨行业污染：
- 金融/银行/保险：Excel、财务分析、风控、合规、估值建模、尽职调查、Bloomberg、Wind
- 建筑/工程/施工：CAD、BIM、工程测量、施工管理、材料验收、安全规范、进度控制
- 医疗/护理：临床操作、病历书写、医患沟通、急救技能、无菌操作
- 教育/培训：课程设计、教学评估、班级管理、教案编写、学生辅导
- 餐饮/酒店：成本控制、食品安全、排班管理、库存管理、客户投诉处理
- IT/互联网：编程语言、框架、数据库、Linux、Git、云计算（相关即可，不强行塞AI）
- 销售/零售：客户开发、商务谈判、CRM系统、渠道管理、回款跟进
- 设计/创意：PS、AI、Figma、色彩搭配、版式设计、品牌VI
- 物流/供应链：WMS、TMS、路径规划、库存优化、供应商管理
- 行政/人事：办公软件、档案管理、招聘流程、考勤统计、会议组织
- 传媒/新媒体：内容策划、热点追踪、数据分析、平台运营（AI工具仅限内容创作辅助）

### 2. 杜撰经验必须真实可信
当需要杜撰项目或实习经历时，必须：
- 使用该行业真实存在的公司类型（如金融用"XX证券/XX基金"，餐饮用"XX连锁餐饮/XX酒店"）
- 描述该岗位日常真实会做的工作内容，不是编造的"高级任务"
- 数据要合理：实习生不可能"提升公司利润30%"，应写"协助完成12份日报、参与3次供应商比价"
- 项目规模要匹配：新人不可能"管理500万项目"，应写"参与XX项目，负责数据整理和文档归档"

### 3. 杜绝万能技能的滥用
- 不要什么岗位都写"数据分析"、"Python"、"AI工具"
- 护士不需要Python，会计不需要ChatGPT，建筑工人不需要机器学习
- 金融分析岗才需要Excel建模，设计岗才需要PS，开发岗才需要Git

## 优化流程

### 第一步：深度岗位分析
请你先深入了解"{target}"这个岗位：
- 这个岗位在真实企业中每天做什么？
- 行业通用的核心技能和工具是什么？
- 新人入职后前3个月通常负责什么？
- 晋升需要积累哪些经验和证书？

### 第二步：三维度精准优化
根据岗位分析结果，从以下三个维度优化：

1. **项目经验**：{'根据目标岗位杜撰1-2个合理项目。项目必须是该岗位新人能接触到的真实工作场景，描述具体做了什么、用了什么工具、产出了什么成果。' if not has_target else '扩写现有项目，添加行业相关的具体数据和工具。'}
2. **实习经验**：{'根据目标岗位杜撰1-2段合理实习。实习内容必须是该岗位实习生日常真实工作，如整理文档、协助同事、参与基础任务，不要编造成"主导项目"。' if not has_target else '丰富实习内容，突出与目标岗位实际匹配的点。'}
3. **技能能力**：只保留与目标岗位真正相关的技能。删掉无关技能。补充该岗位行业通用技能。

### 第三步：输出格式
严格按照以下JSON格式返回（不要包含任何其他文字）：
{{
  "job_analysis": "对{target}的深度分析(80-120字)：真实工作内容、核心技能、行业特点",
  "optimized_summary": "个人总结(150-250字)，语气真实不浮夸，突出与岗位的匹配点",
  "optimized_projects": [
    {{"name": "具体项目名称", "role": "担任角色", "description": "项目描述(80-150字)，包含真实工作细节、行业工具、合理数据"}}
  ],
  "optimized_internships": [
    {{"company": "行业典型公司名", "position": "实习职位", "duration": "时间段(如2025.07-2025.09)", "description": "实习描述(80-150字)，写实习生真实会做的事"}}
  ],
  "enhanced_skills": ["只保留该行业真实需要的技能"],
  "suggestions": ["3条针对性建议：证书、技能提升、经验积累方向"]
}}

只返回JSON，不要其他文字"""
    
    try:
        client = DeepSeekClient()
        result = client.chat(
            system_prompt="你是一个专业的简历优化师和职业顾问。用户可能会有额外要求（extra字段），你必须100%遵守额外要求中的每一条，不得修改、忽略或夸大数据。请根据原始简历和目标岗位生成优化后的JSON简历内容。只返回JSON格式。",
            user_message=prompt,
            temperature=0.7
        )
        # Parse JSON from response
        import re as _re
        json_match = _re.search(r'\{.*\}', result, _re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "ok": True,
                "target": target,
                "job_analysis": data.get("job_analysis", ""),
                "optimized_summary": data.get("optimized_summary", ""),
                "optimized_projects": data.get("optimized_projects", []),
                "optimized_internships": data.get("optimized_internships", []),
                "enhanced_skills": data.get("enhanced_skills", []),
                "suggestions": data.get("suggestions", []),
                "resume_file": resume_file
            }
        return {"ok": False, "error": "AI响应解析失败"}
    except Exception as e:
        return {"ok": False, "error": f"AI调用失败: {str(e)}"}


@app.post("/api/resume/overwrite")
async def overwrite_resume(
    resume_file: str = Form(""),
    optimized_summary: str = Form(""),
    optimized_projects: str = Form("[]"),
    optimized_internships: str = Form("[]"),
    enhanced_skills: str = Form("[]"),
    target: str = Form("")
):
    """用AI优化结果覆盖简历文件，同时更新求职意向"""
    if not resume_file:
        return {"ok": False, "error": "缺少简历文件名"}
    data_dir = DATA_DIR
    filepath = os.path.join(data_dir, resume_file)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "简历文件不存在"}
    
    try:
        # Read current resume
        with open(filepath, "r", encoding="utf-8") as f:
            profile = json.load(f)
        
        # Replace fields with optimized data
        if optimized_summary:
            profile["summary"] = optimized_summary
        if enhanced_skills:
            import json as _json
            skills = _json.loads(enhanced_skills)
            if skills:
                profile["skills"] = skills
        if optimized_projects:
            import json as _json
            projects = _json.loads(optimized_projects)
            if projects:
                # Merge: keep original work_experience, replace project-like entries
                new_work_exp = []
                project_added = False
                for w in profile.get("work_experience", []):
                    company = w.get("company", "")
                    pos = w.get("position", "")
                    if "个人" in company or "项目" in pos or "创作者" in pos:
                        if not project_added:
                            for proj in projects:
                                new_work_exp.append({
                                    "company": proj.get("name", "个人项目"),
                                    "position": proj.get("role", "项目负责人"),
                                    "duration": "",
                                    "description": proj.get("description", "")
                                })
                            project_added = True
                    else:
                        new_work_exp.append(w)
                if not project_added:
                    for proj in projects:
                        new_work_exp.append({
                            "company": proj.get("name", "个人项目"),
                            "position": proj.get("role", "项目负责人"),
                            "duration": "",
                            "description": proj.get("description", "")
                        })
                profile["work_experience"] = new_work_exp
        
        if optimized_internships:
            import json as _json
            internships = _json.loads(optimized_internships)
            if internships:
                # Replace internship entries
                new_work_exp = []
                for w in profile.get("work_experience", []):
                    company = w.get("company", "")
                    pos = w.get("position", "")
                    # Keep non-internship entries
                    if "个人" in company or "项目" in pos or "创作者" in pos:
                        new_work_exp.append(w)
                for intern in internships:
                    new_work_exp.insert(0, {
                        "company": intern.get("company", ""),
                        "position": intern.get("position", ""),
                        "duration": intern.get("duration", ""),
                        "description": intern.get("description", "")
                    })
                profile["work_experience"] = new_work_exp
        
        # Update parse timestamp
        from datetime import datetime as _dt
        profile["parsed_at"] = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        profile["optimized"] = True
        if target:
            profile["desired_position"] = target
        
        # Save
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        
        add_log(f"已覆盖简历: {profile.get("name", "")}", "success")
        return {"ok": True, "message": "简历已覆盖更新"}
    except Exception as e:
        return {"ok": False, "error": f"覆盖失败: {str(e)}"}



@app.post("/api/resume/template")
async def resume_template(
    resume_file: str = Form(""),
    template_style: str = Form("classic")
):
    data_dir = DATA_DIR
    filepath = os.path.join(data_dir, resume_file)
    if not os.path.exists(filepath):
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)
    with open(filepath, "r", encoding="utf-8") as f:
        p = json.load(f)
    name = p.get("name", "")
    desired = p.get("desired_position", "")
    phone = p.get("phone", "")
    email = p.get("email", "")
    summary = p.get("summary", "")
    skills = p.get("skills", [])
    exp = p.get("work_experience", [])
    edu = p.get("education", [])
    photo_html = ""
    photo_dir = os.path.join(os.path.dirname(data_dir), "photos")
    photo_file = resume_file.replace(".json", "") + ".photo.jpg"
    photo_path = os.path.join(photo_dir, photo_file)
    if os.path.exists(photo_path):
        import base64
        with open(photo_path, "rb") as pf:
            b64 = base64.b64encode(pf.read()).decode()
        photo_html = f'<img src="data:image/jpeg;base64,{b64}" class="photo" alt="photo">'
    skills_html = "".join([f'<span class="skill-tag">{s}</span>' for s in skills])
    exp_html = ""
    for w in exp:
        exp_html += f'<div class="exp-item"><div class="exp-title">{w.get("position","")}</div><div class="exp-sub">{w.get("company","")} | {w.get("duration","")}</div><div class="exp-desc">{w.get("description","")}</div></div>'
    edu_html = ""
    for e in edu:
        edu_html += f'<div class="exp-item"><div class="exp-title">{e.get("school","")}</div><div class="exp-sub">{e.get("major","")} | {e.get("degree","")} | {e.get("year","")}</div></div>'
    
    css_map = {"classic": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f7fafc;padding:40px 20px;color:#1a202c}
.page{max-width:800px;margin:0 auto;background:#fff;padding:48px 56px;box-shadow:0 1px 3px rgba(0,0,0,0.1);border-radius:4px}
.header{text-align:center;border-bottom:2px solid #1a56db;padding-bottom:20px;margin-bottom:24px}
h1{font-size:28px;color:#1a202c;margin-bottom:4px}
.job{font-size:16px;color:#4a5568;margin-bottom:8px}
.contact{font-size:13px;color:#718096;display:flex;justify-content:center;gap:24px}
.photo{width:90px;height:120px;object-fit:cover;border:1px solid #e2e8f0;float:right;margin-left:16px;margin-bottom:8px}
.section{margin-bottom:24px}
.section h2{font-size:16px;color:#1a56db;border-bottom:2px solid #1a56db;padding-bottom:6px;margin-bottom:12px;letter-spacing:2px;text-transform:uppercase}
.summary{font-size:14px;color:#2d3748;line-height:1.7;margin-bottom:8px}
.exp-item{margin-bottom:14px;padding-left:14px;border-left:2px solid #cbd5e0}
.exp-title{font-size:15px;font-weight:700;color:#1a202c}
.exp-sub{font-size:12px;color:#718096;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#4a5568;line-height:1.6}
.skill-tag{display:inline-block;background:#ebf4ff;color:#1a56db;padding:4px 12px;margin:4px;border-radius:16px;font-size:12px;border:1px solid #bee3f8}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}}""", "modern": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#0f172a;padding:30px;color:#e2e8f0}
.page{max-width:780px;margin:0 auto;background:#1e293b;border-radius:12px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.5)}
.header{background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:36px 40px;color:#fff}
.header h1{font-size:30px;font-weight:700;margin-bottom:4px}
.header .job{font-size:16px;opacity:0.9;margin-bottom:12px}
.header .contact{font-size:13px;opacity:0.8;display:flex;gap:24px}
.body{padding:32px 40px}
.section{margin-bottom:28px}
.section h2{font-size:16px;color:#a78bfa;border-bottom:2px solid #334155;padding-bottom:8px;margin-bottom:14px;letter-spacing:2px;text-transform:uppercase}
.summary{font-size:14px;color:#cbd5e1;line-height:1.8;margin-bottom:4px}
.exp-item{margin-bottom:16px;padding-left:16px;border-left:3px solid #6366f1}
.exp-title{font-size:15px;font-weight:700;color:#f1f5f9}
.exp-sub{font-size:12px;color:#64748b;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#94a3b8;line-height:1.6}
.skill-tag{display:inline-block;background:rgba(99,102,241,0.15);color:#a5b4fc;padding:4px 12px;margin:4px;border-radius:20px;font-size:12px;border:1px solid rgba(99,102,241,0.3)}
.photo{width:80px;height:80px;border-radius:50%;object-fit:cover;border:3px solid rgba(255,255,255,0.3);float:right;margin-top:-10px}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}}""", "dual": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f8fafc;padding:24px;color:#1e293b}
.page{max-width:800px;margin:0 auto;display:flex;min-height:100vh;box-shadow:0 4px 24px rgba(0,0,0,0.08);border-radius:8px;overflow:hidden}
.left{width:260px;background:#1e293b;color:#e2e8f0;padding:32px 24px;flex-shrink:0}
.left .name{font-size:22px;font-weight:700;margin-bottom:4px;color:#fff}
.left .job{font-size:13px;color:#94a3b8;margin-bottom:16px}
.left .photo{width:100px;height:100px;border-radius:50%;object-fit:cover;border:3px solid #6366f1;margin:0 auto 16px;display:block}
.left .info{font-size:12px;color:#94a3b8;margin-bottom:8px;line-height:1.6}
.left h3{font-size:13px;color:#a78bfa;border-bottom:1px solid #334155;padding-bottom:6px;margin:20px 0 10px;letter-spacing:1px}
.left .skill-tag{display:block;background:rgba(99,102,241,0.15);color:#a5b4fc;padding:5px 12px;margin:4px 0;border-radius:4px;font-size:12px}
.right{flex:1;padding:32px 36px;background:#fff}
.right h2{font-size:16px;color:#6366f1;border-bottom:2px solid #e2e8f0;padding-bottom:8px;margin:24px 0 12px;letter-spacing:1px}
.summary{font-size:14px;color:#475569;line-height:1.8}
.exp-item{margin-bottom:14px}
.exp-title{font-size:15px;font-weight:700;color:#1e293b}
.exp-sub{font-size:12px;color:#64748b;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#475569;line-height:1.6}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}}""",
    "magazine": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f0eb;padding:32px;color:#2c2c2c}
.page{max-width:800px;margin:0 auto;background:#fff;box-shadow:0 4px 24px rgba(0,0,0,0.08)}
.top-bar{background:#1a1a2e;color:#fff;padding:36px 48px 24px}
.top-bar h1{font-size:34px;font-weight:300;letter-spacing:5px;margin-bottom:4px}
.top-bar .job{font-size:15px;color:#a0a0b8;font-weight:300}
.top-bar .contact{font-size:11px;color:#888;margin-top:14px;display:flex;gap:20px}
.content{padding:32px 48px 40px}
.section{margin-bottom:28px}
.section h2{font-size:13px;color:#1a1a2e;border-bottom:1px solid #1a1a2e;padding-bottom:8px;margin-bottom:16px;letter-spacing:6px;text-transform:uppercase;font-weight:400}
.summary{font-size:14px;color:#555;line-height:2;margin-bottom:6px;font-weight:300}
.exp-item{display:flex;margin-bottom:20px;gap:24px}
.exp-left{width:130px;flex-shrink:0;font-size:11px;color:#999;text-align:right;padding-top:2px}
.exp-right{flex:1}
.exp-title{font-size:15px;font-weight:500;color:#1a1a2e}
.exp-sub{font-size:12px;color:#777;margin:2px 0 6px}
.exp-desc{font-size:13px;color:#666;line-height:1.8;font-weight:300}
.skill-tag{display:inline-block;border:1px solid #d0d0d0;color:#555;padding:4px 14px;margin:3px;font-size:11px;font-weight:300}
.photo{width:80px;height:80px;border-radius:50%;object-fit:cover;float:right;margin-top:-56px;border:2px solid #fff}
@media print{body{background:#fff;padding:0}.page{box-shadow:none}}""",
    "minimal": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#fff;padding:36px;color:#333}
.page{max-width:760px;margin:0 auto}
.header{padding-bottom:22px;margin-bottom:28px}
.header h1{font-size:24px;font-weight:500;color:#111;margin-bottom:2px}
.header .job{font-size:13px;color:#999;font-weight:400;margin-bottom:10px}
.header .contact{font-size:11px;color:#bbb;display:flex;gap:18px}
.line{height:1px;background:#e0e0e0;margin:22px 0}
.section{margin-bottom:24px}
.section h2{font-size:11px;color:#999;font-weight:500;margin-bottom:14px;letter-spacing:4px;text-transform:uppercase}
.summary{font-size:13px;color:#666;line-height:2}
.exp-item{margin-bottom:16px}
.exp-title{font-size:14px;font-weight:500;color:#333}
.exp-sub{font-size:11px;color:#bbb;margin:2px 0 4px}
.exp-desc{font-size:12px;color:#777;line-height:1.8}
.skill-tag{display:inline-block;color:#777;padding:3px 10px;margin:3px;font-size:11px;border:1px solid #eee;border-radius:2px}
.photo{width:60px;height:60px;border-radius:4px;object-fit:cover;float:right;margin-left:20px}
@media print{body{padding:0}}""",
    "timeline": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#fafafa;padding:32px;color:#1a1a1a}
.page{max-width:780px;margin:0 auto;background:#fff;padding:44px 52px;box-shadow:0 2px 12px rgba(0,0,0,0.06);border-radius:6px}
.header{text-align:center;margin-bottom:32px}
.header h1{font-size:26px;font-weight:600;color:#1a1a1a}
.header .job{font-size:14px;color:#666;margin:6px 0 10px}
.header .contact{font-size:12px;color:#999;display:flex;justify-content:center;gap:20px}
.divider{width:60px;height:3px;background:#0891b2;margin:18px auto}
.section{margin-bottom:28px}
.section h2{font-size:14px;color:#0891b2;display:flex;align-items:center;gap:12px;margin-bottom:18px}
.section h2:after{content:"";flex:1;height:1px;background:#e5e5e5}
.summary{font-size:14px;color:#555;line-height:2;text-align:center;padding:0 24px}
.timeline{position:relative;padding-left:30px}
.timeline:before{content:"";position:absolute;left:8px;top:10px;bottom:10px;width:2px;background:#0891b2;opacity:0.2}
.tl-item{position:relative;margin-bottom:20px}
.tl-item:before{content:"";position:absolute;left:-26px;top:7px;width:10px;height:10px;background:#0891b2;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 2px #0891b2}
.tl-title{font-size:15px;font-weight:600;color:#1a1a1a}
.tl-sub{font-size:12px;color:#999;margin:2px 0 4px}
.tl-desc{font-size:13px;color:#666;line-height:1.7}
.skill-tag{display:inline-block;background:#ecfeff;color:#0891b2;padding:4px 14px;margin:4px;border-radius:20px;font-size:12px;font-weight:500}
.photo{width:72px;height:72px;border-radius:50%;object-fit:cover;margin:0 auto 14px;display:block;border:3px solid #0891b2}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}}""",
    "elegant": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Noto Serif SC","PingFang SC","Source Han Serif CN",serif;background:#d4c5a9;padding:40px 20px;color:#2c1810}
.page{max-width:780px;margin:0 auto;background:#faf6ee;padding:56px 60px;box-shadow:0 4px 40px rgba(44,24,16,0.12);border:1px solid #e8ddcc}
.header{text-align:center;border-bottom:1px solid #d4c5a9;padding-bottom:20px;margin-bottom:32px;position:relative}
.header:after{content:"";position:absolute;bottom:-4px;left:50%;transform:translateX(-50%);width:60px;height:1px;background:#8b6f47}
.header h1{font-size:34px;font-weight:400;color:#2c1810;letter-spacing:6px;margin-bottom:6px;font-family:"Noto Serif SC","PingFang SC",serif}
.header .job{font-size:13px;color:#6b5b4e;font-weight:400;letter-spacing:3px;font-style:italic;margin-bottom:4px}
.header .contact{font-size:11px;color:#8b7d72;display:flex;justify-content:center;gap:24px;letter-spacing:1px}
.section{margin-bottom:28px}
.section h2{font-size:13px;color:#5c3a2a;font-weight:400;letter-spacing:4px;text-transform:uppercase;margin-bottom:14px;border-bottom:1px solid #e0d5c5;padding-bottom:6px;font-family:"Noto Serif SC","PingFang SC",serif}
.summary{font-size:13px;color:#4a3d36;line-height:2;font-weight:400;text-align:justify}
.exp-item{margin-bottom:18px;padding-left:14px;border-left:2px solid #d4c5a9}
.exp-title{font-size:15px;font-weight:600;color:#2c1810}
.exp-sub{font-size:12px;color:#7d6e62;margin:2px 0 6px;font-style:italic}
.exp-desc{font-size:12px;color:#4a3d36;line-height:1.8}
.skill-tag{display:inline-block;border:1px solid #d4c5a9;color:#6b5b4e;background:rgba(139,111,71,0.06);padding:4px 14px;margin:4px;font-size:11px;letter-spacing:1px}
.photo{width:76px;height:96px;object-fit:cover;border-radius:2px;filter:sepia(40%)saturate(0.8);border:1px solid #c4b49a;margin-bottom:16px}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border:none}}""",
    "tech": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#0a1628;padding:30px;color:#c8d6e5}
.page{max-width:780px;margin:0 auto;background:#0f2247;border-radius:8px;overflow:hidden;box-shadow:0 8px 40px rgba(0,100,255,0.15)}
.header{background:linear-gradient(135deg,#0d3b7a,#1a56db);padding:36px 40px;color:#fff;display:flex;align-items:center;gap:24px}
.header h1{font-size:28px;font-weight:700;letter-spacing:1px}
.header .job{font-size:14px;opacity:0.85;margin-top:4px}
.header .contact{font-size:12px;opacity:0.7;display:flex;gap:18px;margin-top:8px}
.body{padding:32px 40px}
.section{margin-bottom:28px}
.section h2{font-size:13px;color:#4dabf7;font-weight:600;letter-spacing:3px;text-transform:uppercase;border-bottom:2px solid #1a3a5c;padding-bottom:8px;margin-bottom:14px}
.summary{font-size:14px;color:#94aec5;line-height:1.9}
.exp-item{margin-bottom:16px;padding-left:14px;border-left:3px solid #1a56db}
.exp-title{font-size:15px;font-weight:600;color:#e8f0f8}
.exp-sub{font-size:12px;color:#5a7a9a;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#7d9db9;line-height:1.7}
.skill-tag{display:inline-block;background:rgba(26,86,219,0.15);color:#4dabf7;padding:4px 14px;margin:4px;border-radius:4px;font-size:12px;font-weight:500;border:1px solid rgba(77,171,247,0.2)}
.photo{width:75px;height:100px;object-fit:cover;border-radius:6px;border:2px solid #4dabf7}
@media print{body{background:#fff;padding:0;color:#000}.page{background:#fff;box-shadow:none}.header{background:#1a56db;-webkit-print-color-adjust:exact}}"""}
    css = css_map.get(template_style, css_map["classic"])
    
    # Use work experience as-is
    work_html = ""
    for w in exp:
        pos = w.get("position", "")
        company = w.get("company", "")
        desc = w.get("description", "")
        dur = w.get("duration", "")
        work_html += f'<div class="exp-item"><div class="exp-title">{pos}</div><div class="exp-sub">{company} | {dur}</div><div class="exp-desc">{desc}</div></div>'
    if not work_html:
        work_html = '<div class="exp-item" style="color:var(--text-dim)">暂无工作经历</div>'

    if template_style == "dual":
        body = f'<div class="left">{photo_html}<div class="name">{name}</div><div class="info"><p>电话 {phone}</p><p>邮箱 {email}</p></div><div class="job"><h3>求职意向</h3><p>{desired}</p></div><h3>个人优势</h3>{skills_html}</div><div class="right"><div class="summary">{summary}</div><h2>工作经历</h2>{work_html}<h2>教育经历</h2>{edu_html}</div>'
    else:
        body = f'<div class="header">{photo_html}<h1>{name}</h1><div class="contact"><span>电话 {phone}</span><span>邮箱 {email}</span></div></div><div class="section"><h2>基本信息</h2><p>姓名：{name}</p><p>电话：{phone}</p><p>邮箱：{email}</p></div><div class="section"><h2>求职意向</h2><div class="job" style="font-size:14px">{desired}</div></div><div class="section"><h2>自我介绍</h2><div class="summary">{summary}</div></div><div class="section"><h2>工作经历</h2>{work_html}</div><div class="section"><h2>教育经历</h2>{edu_html}</div><div class="section"><h2>个人优势</h2><div style="margin-top:8px">{skills_html}</div></div>'
    
    html = f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>{name} - resume</title><style>{css}</style></head><body><div class="page">{body}</div></body></html>'
    return HTMLResponse(content=html, status_code=200, headers={"X-Template-Style": template_style})


@app.post("/api/resume/photo")
async def upload_photo(resume_file: str = Form(""), photo: UploadFile = File(None)):
    if not photo:
        return {"ok": False, "error": "missing photo"}
    photo_dir = os.path.join(os.path.dirname(DATA_DIR), "photos")
    os.makedirs(photo_dir, exist_ok=True)
    safe_name = resume_file.replace(".json", "").replace("/", "_").replace("\\", "_")
    filepath = os.path.join(photo_dir, f"{safe_name}.photo.jpg")
    content = await photo.read()
    with open(filepath, "wb") as f:
        f.write(content)
    add_log(f"photo uploaded for {resume_file}: {len(content)} bytes", "success")
    return {"ok": True, "message": "ok", "filename": f"{safe_name}.photo.jpg"}


@app.get("/api/resume/export/{filename}")

@app.get("/api/resume/export/{filename}")
async def export_resume(filename: str):
    data_dir = DATA_DIR
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(filepath):
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)
    with open(filepath, "r", encoding="utf-8") as f:
        p = json.load(f)
    name = p.get("name", "")
    skills_html = "".join([f'<span style="display:inline-block;background:#f0f4ff;color:#1a56db;padding:4px 12px;margin:4px;border-radius:16px;font-size:13px">{s}</span>' for s in p.get("skills", [])])
    exp_html = ""
    for w in p.get("work_experience", []):
        exp_html += f'<div style="margin-bottom:16px;padding-left:16px;border-left:3px solid #1a56db"><div style="font-size:15px;font-weight:700">{w.get("position","")}</div><div style="font-size:13px;color:#4a5568;margin:2px 0">{w.get("company","")} {w.get("duration","")}</div><div style="font-size:13px;color:#2d3748;line-height:1.6;margin-top:4px">{w.get("description","")}</div></div>'
    edu_html = ""
    for e in p.get("education", []):
        edu_html += f'<div style="margin-bottom:12px"><div style="font-size:15px;font-weight:700">{e.get("school","")}</div><div style="font-size:13px;color:#4a5568">{e.get("major","")} | {e.get("degree","")} | {e.get("year","")}</div></div>'
    desired = p.get("desired_position", "")
    phone = p.get("phone", "")
    email = p.get("email", "")
    summary = p.get("summary", "")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{name} - 简历</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f7fafc;padding:40px 20px}}
.page{{max-width:800px;margin:0 auto;background:#fff;padding:48px 56px;box-shadow:0 1px 3px rgba(0,0,0,0.1);border-radius:4px}}
h1{{font-size:28px;color:#1a202c;margin-bottom:4px}}
h2{{font-size:16px;color:#4a5568;font-weight:400;margin-bottom:8px}}
h3{{font-size:15px;color:#1a56db;border-bottom:2px solid #1a56db;padding-bottom:6px;margin:28px 0 14px;letter-spacing:1px}}
.contact{{font-size:13px;color:#718096;margin-bottom:20px}}
.contact span{{margin-right:20px}}
.summary{{font-size:14px;color:#2d3748;line-height:1.7;margin-bottom:8px}}
@media print{{body{{background:#fff;padding:0}}.page{{box-shadow:none;border-radius:0}}}}
</style></head>
<body><div class="page">
<h1>{name}</h1><h2>{desired}</h2>
<div class="contact"><span>tel {phone}</span><span>email {email}</span></div>
<div class="summary">{summary}</div>
<h3>工作经验</h3>{exp_html}
<h3>教育背景</h3>{edu_html}
<h3>技能</h3><div style="margin-top:8px">{skills_html}</div>
</div></body></html>"""
    from urllib.parse import quote
    safe_name = quote(f"{name}_简历.html")
    return HTMLResponse(content=html, status_code=200, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}"})

@app.delete("/api/resumes/delete/{filename}")
async def delete_resume(filename: str):
    """删除指定简历"""
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        add_log(f"已删除简历: {filename}", "info")
        return {"ok": True}
    return {"ok": False, "error": "文件不存在"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    add_log("新的客户端已连接", "info")
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        connected_clients.discard(ws)
        add_log("客户端已断开", "info")



# ============================================================
# 岗位采集 API（步骤5）
# ============================================================

@app.get("/api/jobs/list")
async def list_collected_jobs():
    """
    列出所有采集的岗位文件
    大白话：返回已保存的岗位文件列表
    """
    data_dir = DATA_DIR
    files = []
    if os.path.exists(data_dir):
        for f in sorted(os.listdir(data_dir), reverse=True):
            if f.startswith("jobs_") and f.endswith(".json"):
                filepath = os.path.join(data_dir, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    files.append({
                        "filename": f,
                        "collected_at": data.get("collected_at", ""),
                        "count": data.get("count", 0),
                        "keywords": data.get("keywords", []),
                        "profile_name": data.get("profile", {}).get("name", "")
                    })
                except:
                    files.append({"filename": f, "error": True})
    return {"files": files, "count": len(files)}


@app.get("/api/jobs/detail/{filename}")
async def get_job_detail(filename: str):
    """查看某次采集的完整岗位列表"""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "文件不存在"}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/jobs/scrape")
async def start_scrape(platforms: str = Form("51前程无忧,liepin"), resume_file: str = Form(""), salary_range: str = Form("")):
    """启动岗位采集。resume_file: 必须指定简历文件名"""
    """
    启动岗位采集（后台运行）
    大白话：点击后自动打开浏览器抓取51前程无忧岗位，完成后保存
    """
    global scraper_status
    if scraper_status["running"]:
        return {"ok": False, "error": "采集任务正在进行中"}

    # 选择简历
    if not resume_file:
        return {"ok": False, "error": "请先选择一份简历，系统需要根据求职意向精准采集"}
    filepath = os.path.join(DATA_DIR, resume_file)
    if not os.path.exists(filepath):
        return {"ok": False, "error": f"简历文件不存在: {resume_file}"}
    with open(filepath, "r", encoding="utf-8") as f:
        profile = json.load(f)
    if not profile:
        return {"ok": False, "error": "没有已解析的简历，请先上传简历"}

    keywords = extract_keywords(profile)
    if not keywords:
        return {"ok": False, "error": "无法从简历中提取搜索关键词"}

    scraper_status = {"running": True, "progress": "启动中", "jobs_count": 0, "last_run": ""}
    add_log(f"开始岗位采集，关键词: {keywords}", "info")
    add_log(f"使用简历: {profile.get('name', '未知')}", "info")

    # 后台运行采集任务
    import concurrent.futures
    loop = asyncio.get_event_loop()
    plat_list = [p.strip() for p in platforms.split(",") if p.strip()]
    add_log(f"目标平台: {plat_list}", "info")
    loop.run_in_executor(None, _run_scrape_sync, profile, keywords, plat_list, salary_range)
    
    return {"ok": True, "message": "采集任务已启动", "keywords": keywords}



def _auto_batch_score(profile, jobs_filepath):
    import json, os
    from modules.jd_matcher import match_resume_to_jd

    data_dir = DATA_DIR

    with open(jobs_filepath, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)

    jobs_list = jobs_data.get("jobs", [])
    if not jobs_list:
        return

    total = len(jobs_list)
    add_log(f"JD?? {total} ??? (??/??/??????)...", "info")

    scored_jobs = []
    for i, job in enumerate(jobs_list):
        jd_parts = [job.get("title", "")]
        if job.get("tags"):
            jd_parts.extend(job.get("tags", [])[:5])
        jd_text = " ".join([p for p in jd_parts if p])

        if len(jd_text) < 5:
            job["match_score"] = 50
            job["match_brief"] = "????"
            job["skill_match"] = 50
            job["experience_match"] = 50
            job["education_match"] = 50
            scored_jobs.append(job)
            continue

        try:
            result = match_resume_to_jd(profile, jd_text)
            if result.get("ok"):
                job["match_score"] = result.get("overall_score", 50)
                job["skill_match"] = result.get("skill_match", 50)
                job["experience_match"] = result.get("experience_match", 50)
                job["education_match"] = result.get("education_match", 50)
                job["match_brief"] = result.get("verdict", "")
                job["strengths"] = result.get("strengths", [])
                job["weaknesses"] = result.get("weaknesses", [])
                job["suggestions"] = result.get("suggestions", [])
            else:
                job["match_score"] = 50
                job["match_brief"] = result.get("error", "????")
                job["skill_match"] = 50
                job["experience_match"] = 50
                job["education_match"] = 50
        except Exception as e:
            job["match_score"] = 50
            job["match_brief"] = f"{str(e)[:50]}"
            job["skill_match"] = 50
            job["experience_match"] = 50
            job["education_match"] = 50

        scored_jobs.append(job)

        if (i + 1) % 10 == 0:
            add_log(f"  ????: {i+1}/{total}", "info")

    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    jobs_data["jobs"] = scored_jobs
    jobs_data["resume_name"] = profile.get("name", "")
    jobs_data["auto_scored"] = True
    jobs_data["scored_at"] = datetime.now().isoformat()

    with open(jobs_filepath, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, ensure_ascii=False, indent=2)

    high = sum(1 for j in scored_jobs if j.get("match_score", 0) >= 70)
    add_log(f"????: {high}/{len(scored_jobs)} ? >= 70?", "success")

    all_files = sorted(
        [x for x in os.listdir(data_dir) if x.startswith("jobs_") and x.endswith(".json")],
        key=lambda x: os.path.getmtime(os.path.join(data_dir, x)),
        reverse=True
    )
    for old_f in all_files[5:]:
        try:
            os.remove(os.path.join(data_dir, old_f))
        except:
            pass



def _run_scrape_sync(profile, keywords, platforms, salary_range=""):
    """后台执行岗位采集（异步）"""
    global scraper_status
    scraper = JobScraper(headless=False)
    scraper.set_profile(profile)
    if salary_range:
        # 前端传入的薪资，使用 infer_salary_range 做±3k扩展
        from modules.job_scraper import infer_salary_range
        scraper.salary_range = infer_salary_range({"desired_salary": salary_range})
        add_log(f"自定义薪资: {salary_range} -> 过滤范围 {scraper.salary_range}", "info")
    # 注意: 如果前端没传薪资，不预设置 scaper.salary_range
    # search_all() 会自动从 profile.desired_salary 调用 infer_salary_range
    try:
        scraper_status["progress"] = "正在打开浏览器"
        scraper._launch_browser()
        
        scraper_status["progress"] = "正在搜索51前程无忧"
        add_log(f">>> 收到采集请求 - 平台: {platforms}, 简历: {profile.get("name","?")}, 地点: 广州, 关键词: {keywords}", "info")
        jobs = scraper.search_all(platforms=platforms, pages=2)
        
        scraper_status["jobs_count"] = len(jobs)
        
        if jobs:
            # 严格城市过滤：只保留匹配目标城市的岗位
            target_city = scraper.location
            if target_city:
                city_core = target_city.replace("市", "").replace("省", "")
                before = len(jobs)
                jobs = [j for j in jobs if city_core in (j.get("location", "") or "")]
                add_log(f"城市过滤: {before} -> {len(jobs)} 个岗位 (仅保留{target_city})", "info")
            scraper.jobs = jobs  # 用过滤后的结果覆盖
            filepath = scraper.save_jobs()
            scraper_status["progress"] = f"完成，共 {len(jobs)} 个岗位"
            add_log(f"采集完成: {len(jobs)} 个岗位", "success")
            STATS["jobs_found"] += len(jobs)
            # 自动运行批量JD匹配
            try:
                scraper_status["progress"] = "正在自动JD匹配..."
                add_log("开始自动JD匹配评分", "info")
                _auto_batch_score(profile, filepath)
                add_log("自动JD匹配完成", "success")
            except Exception as e2:
                add_log(f"自动匹配失败: {e2}", "warning")
        else:
            scraper_status["progress"] = "未找到岗位"
            add_log("未采集到岗位", "warning")
    except Exception as e:
        scraper_status["progress"] = f"出错: {str(e)[:60]}"
        add_log(f"采集失败: {e}", "error")
    finally:
        scraper.close()
        scraper_status["running"] = False
        scraper_status["last_run"] = datetime.now().strftime("%H:%M:%S")


@app.get("/api/jobs/scrape/status")
async def get_scrape_status():
    """查询采集任务状态"""
    return scraper_status


# ============================================================
# JD 匹配度评分 API（步骤6）
# ============================================================

@app.post("/api/jd/match")
async def match_jd(resume_file: str = Form(""), jd_text: str = Form("")):
    """
    JD匹配度评分
    大白话：上传一份JD文本，选择一份简历，AI告诉你匹配度
    """
    if not jd_text or len(jd_text.strip()) < 10:
        return {"ok": False, "error": "JD文本太短，请粘贴完整的岗位描述"}
    
    # 选择简历
    data_dir = DATA_DIR
    if resume_file:
        filepath = os.path.join(data_dir, resume_file)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = load_profile()
    else:
        profile = load_profile()
    
    if not profile:
        return {"ok": False, "error": "没有已解析的简历，请先上传简历"}
    
    add_log(f"开始JD匹配: {profile.get('name', '未知')}", "info")
    
    # 调用AI匹配
    result = match_resume_to_jd(profile, jd_text.strip())
    
    if result.get("ok"):
        add_log(f"匹配完成，综合评分: {result.get('overall_score', '?')}/100", "success")
    else:
        add_log(f"匹配失败: {result.get('error', '')}", "error")
    
    return result



@app.post("/api/jobs/batch-score")
async def batch_score_jobs(jobs_file: str = Form(""), resume_file: str = Form(""), threshold: int = Form(70)):
    """
    对一批采集的岗位进行批量JD匹配评分
    大白话：把采集到的岗位列表拿去跟简历一一匹配，返回评分排序
    """
    data_dir = DATA_DIR
    
    # 加载岗位数据
    if not jobs_file:
        return {"ok": False, "error": "请指定岗位文件"}
    filepath = os.path.join(data_dir, jobs_file)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "岗位文件不存在"}
    
    with open(filepath, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)
    
    jobs_list = jobs_data.get("jobs", [])
    if not jobs_list:
        return {"ok": False, "error": "岗位列表为空"}
    
    # 加载简历
    if resume_file:
        rp = os.path.join(data_dir, resume_file)
        if os.path.exists(rp):
            with open(rp, "r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = load_profile()
    else:
        profile = load_profile()
    
    if not profile:
        return {"ok": False, "error": "没有已解析的简历"}
    
    add_log(f"开始批量匹配: {len(jobs_list)} 个岗位 vs {profile.get('name', '未知')}", "info")
    
    # 逐岗位匹配
    scored_jobs = []
    for i, job in enumerate(jobs_list):  # ????  # 最多30个，防止token消耗过大
        # 构造JD文本：岗位名+薪资+公司+标签
        jd_parts = [job.get("title", "")]
        if job.get("tags"):
            jd_parts.extend(job.get("tags", [])[:8])
        jd_text = " ".join([p for p in jd_parts if p])
        
        if len(jd_text) < 5:
            # JD信息太少，跳过或用默认分
            job["match_score"] = 50
            job["match_brief"] = "信息不足"
            scored_jobs.append(job)
            continue
        
        try:
            result = quick_match(profile, jd_text)
            job["match_score"] = result.get("score", 50) if result.get("ok") else 50
            job["match_brief"] = result.get("brief", "") if result.get("ok") else "匹配失败"
            job["match_reasons"] = result.get("reasons", []) if result.get("ok") else []
        except Exception as e:
            job["match_score"] = 50
            job["match_brief"] = f"错误: {str(e)[:30]}"
        
        scored_jobs.append(job)
        
        if (i + 1) % 5 == 0:
            add_log(f"匹配进度: {i+1}/{min(len(jobs_list), 30)}", "info")
    
    # 按评分排序
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    # 统计
    high_score = [j for j in scored_jobs if j.get("match_score", 0) >= threshold]
    add_log(f"批量匹配完成: {len(high_score)} 个 >= {threshold}分", "success")
    
    # Save results back to file for deliver list
    jobs_data["jobs"] = scored_jobs
    jobs_data["resume_name"] = profile.get("name", "")
    jobs_data["auto_scored"] = True
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, ensure_ascii=False, indent=2)
    
    return {
        "ok": True,
        "total": len(scored_jobs),
        "high_score_count": len(high_score),
        "threshold": threshold,
        "resume_name": profile.get("name", ""),
        "jobs": scored_jobs
    }


@app.post("/api/jobs/batch-score")


@app.post("/api/jobs/batch-score-json")
async def batch_score_jobs_json(data: dict):
    from modules.jd_matcher import match_resume_to_jd
    """
    批量JD匹配（JSON版，更可靠）
    """
    jobs_file = data.get("jobs_file", "")
    resume_file = data.get("resume_file", "")
    threshold = data.get("threshold", 70)

    data_dir = DATA_DIR
    
    if not jobs_file:
        return {"ok": False, "error": "请指定岗位文件"}
    filepath = os.path.join(data_dir, jobs_file)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "岗位文件不存在"}
    
    with open(filepath, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)
    
    jobs_list = jobs_data.get("jobs", [])
    if not jobs_list:
        return {"ok": False, "error": "岗位列表为空"}
    
    if resume_file:
        rp = os.path.join(data_dir, resume_file)
        if os.path.exists(rp):
            with open(rp, "r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = load_profile()
    else:
        profile = load_profile()
    
    if not profile:
        return {"ok": False, "error": "没有已解析的简历"}
    
    add_log(f"开始批量匹配(JSON): {len(jobs_list)} 个岗位 vs {profile.get('name', '未知')}", "info")
    
    scored_jobs = []
    for i, job in enumerate(jobs_list):  # ????
        jd_parts = [job.get("title", "")]
        if job.get("tags"):
            jd_parts.extend(job.get("tags", [])[:8])
        jd_text = " ".join([p for p in jd_parts if p])
        
        if len(jd_text) < 5:
            job["match_score"] = 50
            job["match_brief"] = "信息不足"
            scored_jobs.append(job)
            continue
        
        try:
            result = quick_match(profile, jd_text)
            job["match_score"] = result.get("score", 50) if result.get("ok") else 50
            job["match_brief"] = result.get("brief", "") if result.get("ok") else "匹配失败"
            job["match_reasons"] = result.get("reasons", []) if result.get("ok") else []
        except Exception as e:
            job["match_score"] = 50
            job["match_brief"] = f"错误: {str(e)[:30]}"
        
        scored_jobs.append(job)
        
        if (i + 1) % 5 == 0:
            add_log(f"匹配进度: {i+1}/{min(len(jobs_list), 30)}", "info")
    
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    high_score = [j for j in scored_jobs if j.get("match_score", 0) >= threshold]
    add_log(f"批量匹配完成: {len(high_score)} 个 >= {threshold}分", "success")
    
    # Save results back to file for deliver list
    jobs_data["jobs"] = scored_jobs
    jobs_data["resume_name"] = profile.get("name", "")
    jobs_data["auto_scored"] = True
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, ensure_ascii=False, indent=2)
    
    return {
        "ok": True,
        "total": len(scored_jobs),
        "high_score_count": len(high_score),
        "threshold": threshold,
        "resume_name": profile.get("name", ""),
        "jobs": scored_jobs
    }


@app.post("/api/jobs/batch-score")
async def batch_score_jobs(jobs_file: str = Form(""), resume_file: str = Form(""), threshold: int = Form(70)):
    """
    对一批采集的岗位进行批量JD匹配评分
    大白话：把采集到的岗位列表拿去跟简历一一匹配，返回评分排序
    """
    data_dir = DATA_DIR
    
    # 加载岗位数据
    if not jobs_file:
        return {"ok": False, "error": "请指定岗位文件"}
    filepath = os.path.join(data_dir, jobs_file)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "岗位文件不存在"}
    
    with open(filepath, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)
    
    jobs_list = jobs_data.get("jobs", [])
    if not jobs_list:
        return {"ok": False, "error": "岗位列表为空"}
    
    # 加载简历
    if resume_file:
        rp = os.path.join(data_dir, resume_file)
        if os.path.exists(rp):
            with open(rp, "r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = load_profile()
    else:
        profile = load_profile()
    
    if not profile:
        return {"ok": False, "error": "没有已解析的简历"}
    
    add_log(f"开始批量匹配: {len(jobs_list)} 个岗位 vs {profile.get('name', '未知')}", "info")
    
    # 逐岗位匹配
    scored_jobs = []
    for i, job in enumerate(jobs_list):  # ????  # 最多30个，防止token消耗过大
        # 构造JD文本：岗位名+薪资+公司+标签
        jd_parts = [job.get("title", "")]
        if job.get("tags"):
            jd_parts.extend(job.get("tags", [])[:8])
        jd_text = " ".join([p for p in jd_parts if p])
        
        if len(jd_text) < 5:
            # JD信息太少，跳过或用默认分
            job["match_score"] = 50
            job["match_brief"] = "信息不足"
            scored_jobs.append(job)
            continue
        
        try:
            result = quick_match(profile, jd_text)
            job["match_score"] = result.get("score", 50) if result.get("ok") else 50
            job["match_brief"] = result.get("brief", "") if result.get("ok") else "匹配失败"
            job["match_reasons"] = result.get("reasons", []) if result.get("ok") else []
        except Exception as e:
            job["match_score"] = 50
            job["match_brief"] = f"错误: {str(e)[:30]}"
        
        scored_jobs.append(job)
        
        if (i + 1) % 5 == 0:
            add_log(f"匹配进度: {i+1}/{min(len(jobs_list), 30)}", "info")
    
    # 按评分排序
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    # 统计
    high_score = [j for j in scored_jobs if j.get("match_score", 0) >= threshold]
    add_log(f"批量匹配完成: {len(high_score)} 个 >= {threshold}分", "success")
    
    # Save results back to file for deliver list
    jobs_data["jobs"] = scored_jobs
    jobs_data["resume_name"] = profile.get("name", "")
    jobs_data["auto_scored"] = True
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, ensure_ascii=False, indent=2)
    
    return {
        "ok": True,
        "total": len(scored_jobs),
        "high_score_count": len(high_score),
        "threshold": threshold,
        "resume_name": profile.get("name", ""),
        "jobs": scored_jobs
    }


@app.post("/api/jobs/batch-score")

@app.post("/api/jd/batch-match")
async def batch_match_jd(resume_file: str = Form(""), jd_text: str = Form("")):
    """
    快速匹配（精简版）
    """
    if not jd_text or len(jd_text.strip()) < 10:
        return {"ok": False, "error": "JD文本太短"}
    
    data_dir = DATA_DIR
    if resume_file:
        filepath = os.path.join(data_dir, resume_file)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = load_profile()
    else:
        profile = load_profile()
    
    if not profile:
        return {"ok": False, "error": "没有已解析的简历"}
    
    result = quick_match(profile, jd_text.strip())
    return result



# ============================================================
# 步骤8：自动打招呼 & 投递简历 API
# ============================================================

deliver_status = {"running": False, "progress": "", "total": 0, "done": 0, "last_run": ""}

def _fix_job_url(url, location=""):
    """Convert old 51前程无忧 URL formats to jobs.51job.com server-rendered format"""
    import re
    m = re.search(r"jobId=(\d+)", url)
    if m:
        job_id = m.group(1)
        city_map = {"广州": "guangzhou", "深圳": "shenzhen", "北京": "beijing", "上海": "shanghai"}
        city_clean = location.strip().split("·")[0].strip()
        city_slug = city_map.get(city_clean, "guangzhou")
        return f"https://jobs.51job.com/{city_slug}/{job_id}.html"
    return url

DELIVER_HISTORY_FILE = os.path.join(DATA_DIR, "deliver_history.json")

def _load_deliver_history():
    if os.path.exists(DELIVER_HISTORY_FILE):
        with open(DELIVER_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_deliver_history(history):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DELIVER_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

@app.get("/api/deliver/status")
async def get_deliver_status():
    return deliver_status

@app.get("/api/deliver/history")
async def get_deliver_history():
    history = _load_deliver_history()
    return {"ok": True, "history": history[-50:], "total": len(history)}


@app.post("/api/deliver/greeting")
async def generate_greeting(
    resume_file: str = Form(""),
    direction: str = Form(""),
    jobs_file: str = Form("")
):
    """AI生成打招呼开场白 - 基于简历+岗位+用户指令"""
    if not resume_file:
        return {"ok": False, "error": "请先选择简历"}
    data_dir = DATA_DIR
    filepath = os.path.join(data_dir, resume_file)
    if not os.path.exists(filepath):
        return {"ok": False, "error": "简历文件不存在"}
    with open(filepath, "r", encoding="utf-8") as f:
        profile = json.load(f)
    
    name = profile.get("name", "求职者")
    position = profile.get("desired_position", "相关岗位")
    skills = profile.get("skills", [])[:5]
    skills_str = "、".join(skills) if skills else "相关技能"
    summary = profile.get("summary", "")[:200]
    
    # Load jobs data if provided
    jobs_context = ""
    if jobs_file:
        jobs_path = os.path.join(data_dir, jobs_file)
        if os.path.exists(jobs_path):
            with open(jobs_path, "r", encoding="utf-8") as jf:
                jobs_data = json.load(jf)
            jobs_list = jobs_data.get("jobs", [])[:8]
            if jobs_list:
                job_lines = []
                for j in jobs_list:
                    title = j.get("title", "")
                    company = j.get("company", "")
                    salary = j.get("salary", "")
                    if title:
                        job_lines.append(f"- {title} | {company} | {salary}")
                if job_lines:
                    jobs_context = "\n".join(job_lines)
    
    # Build prompt with clear priority
    direction_section = ""
    if direction:
        direction_section = f"""[最优先指令 - 必须100%遵守]
用户要求：{direction}
你需要严格按照这个方向来写开场白，这是最高优先级的要求。
例如用户说"前端开发"，你就写前端相关；说"广州"，就写广州求职相关。
"""
    else:
        direction_section = "[用户未填写方向，请根据简历和岗位信息自动生成]\n"
    
    resume_section = f"""[求职者信息]
姓名：{name}
求职意向：{position}
核心技能：{skills_str}
个人亮点：{summary}
"""
    
    jobs_section = ""
    if jobs_context:
        jobs_section = f"""[采集到的岗位信息 - 供参考]
{ jobs_context }
"""
    
    user_msg = f"""请为求职者生成一段简短的打招呼开场白，用于招聘平台发给HR。

{direction_section}
{resume_section}
{jobs_section}

要求：
1. 【最重要】用户写的投递方向/要求是最高优先级，必须严格按照用户的要求来写开场白内容
2. 语气真诚、专业但不生硬，像真人写的消息
3. 80-120字，简短有力
4. 突出求职者与岗位的匹配点
5. 最后用"期待进一步沟通"或类似自然收尾
6. 不要用"尊敬的HR"，用"您好"即可
7. 岗位信息仅作参考，不能偏离用户的方向要求"""

    try:
        client = DeepSeekClient()
        result = client.chat(
            system_prompt="你是一个专业的求职顾问，擅长写简洁有力的求职打招呼语。注意：用户写的投递方向/要求是你必须遵守的最高指令，绝对不能忽略或偏离。只返回开场白文字，不要JSON，不要引号。",
            user_message=user_msg,
            temperature=0.7
        )
        greeting = result.strip().strip('"').strip("'")
        return {"ok": True, "greeting": greeting, "position": position}
    except Exception as e:
        return {"ok": False, "error": f"生成失败: {str(e)}"}
@app.post("/api/deliver/list")
async def list_deliver_candidates(
    jobs_file: str = Form(""),
    resume_file: str = Form(""),
    threshold: int = Form(70)
):
    import glob
    data_dir = DATA_DIR
    jobs_path = os.path.join(data_dir, jobs_file)
    if not jobs_file or not os.path.exists(jobs_path):
        candidates = sorted(glob.glob(os.path.join(data_dir, "jobs_*.json")), reverse=True)
        if not candidates:
            return {"ok": False, "error": "没有找到岗位采集文件"}
        jobs_path = candidates[0]
    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)
    jobs_list = jobs_data.get("jobs", [])
    if resume_file:
        resume_path = os.path.join(data_dir, resume_file)
        if os.path.exists(resume_path):
            with open(resume_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = load_profile()
    else:
        profile = load_profile()
    if not profile:
        return {"ok": False, "error": "没有已解析的简历"}
    
    # 检查岗位文件的评分是否针对当前简历
    scored_resume = jobs_data.get("resume_name", "")
    current_resume = profile.get("name", "")
    if scored_resume and scored_resume != current_resume:
        return {"ok": False, "error": f"⚠️ 该岗位文件的评分对象是 【{scored_resume}】，而非当前选择的简历 【{current_resume}】。请先在步骤5用当前简历重新进行批量评分。"}
    
    history = _load_deliver_history()
    delivered_urls = {_fix_job_url(h.get("url", ""), h.get("location", "")) for h in history}
    candidates_list = []
    for job in jobs_list:
        score = job.get("match_score", 0)
        url = _fix_job_url(job.get("url", ""), job.get("location", ""))
        job["url"] = url
        if score >= threshold and url and url not in delivered_urls:
            job["match_score"] = score
            candidates_list.append(job)
    candidates_list.sort(key=lambda j: j.get("match_score", 0), reverse=True)
    return {
        "ok": True,
        "resume_name": profile.get("name", ""),
        "resume_file": os.path.basename(resume_path) if resume_file else "",
        "jobs_file": os.path.basename(jobs_path),
        "threshold": threshold,
        "total_jobs": len(jobs_list),
        "candidates": len(candidates_list),
        "already_delivered": len(delivered_urls),
        "jobs": candidates_list
    }

# ============================================
# 精准简历优化 - 针对高分岗位定向优化
# ============================================
def _fetch_jd_detail(job_url):
    import urllib.request, urllib.error, re
    L = chr(10)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        req = urllib.request.Request(job_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("gbk", errors="ignore")
        tag_re = re.compile(r"<[^>]+>")
        patterns = [
            re.compile(r'<div[^>]*class="[^"]*bmsg[^"]*"[^>]*>(.*?)</div>', re.DOTALL),
            re.compile(r'<div[^>]*class="[^"]*job_msg[^"]*"[^>]*>(.*?)</div>', re.DOTALL),
            re.compile(r'<div[^>]*class="[^"]*job-detail[^"]*"[^>]*>(.*?)</div>', re.DOTALL),
        ]
        for pat in patterns:
            m = pat.search(html)
            if m:
                text = tag_re.sub(L, m.group(1))
                text = re.sub(L + "{3,}", L + L, text)
                text = re.sub(r"\s{2,}", " ", text)
                text = text.strip()
                if len(text) > 50:
                    return text[:3000]
        text = tag_re.sub(L, html)
        text = re.sub(L + "{3,}", L, text)
        lines = [l.strip() for l in text.split(L) if len(l.strip()) > 20]
        if lines:
            return L.join(lines[:50])
        return ""
    except Exception as e:
        print("JD fetch err: " + str(e))
        return ""


@app.post("/api/resume/precision-optimize")
async def precision_optimize(
    resume_file: str = Form(""),
    jobs_file: str = Form(""),
    job_indices: str = Form("")
):
    if not resume_file or not job_indices:
        return {"ok": False, "error": "缺少参数"}
    data_dir = DATA_DIR
    resume_path = os.path.join(data_dir, resume_file)
    if not os.path.exists(resume_path):
        return {"ok": False, "error": "简历文件不存在"}
    jobs_path = os.path.join(data_dir, jobs_file)
    if not os.path.exists(jobs_path):
        return {"ok": False, "error": "岗位文件不存在"}
    with open(resume_path, "r", encoding="utf-8") as f:
        profile = json.load(f)
    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)
    jobs_list = jobs_data.get("jobs", [])
    indices = [int(x.strip()) for x in job_indices.split(",") if x.strip().isdigit()]
    selected_jobs = []
    for idx in indices:
        if 0 <= idx < len(jobs_list):
            job = jobs_list[idx]
            jd_text = _fetch_jd_detail(job.get("url", ""))
            selected_jobs.append({
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "salary": job.get("salary", ""),
                "location": job.get("location", ""),
                "tags": job.get("tags", []),
                "match_score": job.get("match_score", 0),
                "strengths": job.get("strengths", []),
                "weaknesses": job.get("weaknesses", []),
                "suggestions": job.get("suggestions", []),
                "jd_full": jd_text,
            })
    if not selected_jobs:
        return {"ok": False, "error": "没有找到有效的岗位"}
    name = profile.get("name", "")
    desired = profile.get("desired_position", "")
    summary = profile.get("summary", "")
    skills = profile.get("skills", [])
    work_exp = profile.get("work_experience", [])
    edu = profile.get("education", [])
    L = chr(10)
    exp_lines = []
    for w in work_exp:
        p = str(w.get("position","")); c2 = str(w.get("company",""))
        d = str(w.get("duration","")); de = str(w.get("description",""))
        exp_lines.append("- " + p + " @ " + c2 + " (" + d + "): " + de)
    exp_text = L.join(exp_lines)
    edu_lines = []
    for e in edu:
        s = str(e.get("school","")); m = str(e.get("major",""))
        dg = str(e.get("degree","")); y = str(e.get("year",""))
        edu_lines.append("- " + s + " | " + m + " | " + dg + " | " + y)
    edu_text = L.join(edu_lines)
    jd_texts = []
    for j in selected_jobs:
        jb = ""
        jb += "【岗位" + str(j["title"]) + "@" + str(j["company"]) + " | " + str(j["salary"]) + " | 匹配度" + str(j["match_score"]) + "分】" + L
        if j["jd_full"]:
            jb += "JD原文:" + L + j["jd_full"] + L
        tl = j["tags"] if isinstance(j["tags"], list) else []
        jb += "关键词: " + ", ".join(tl[:10]) + L
        jb += "优势: " + ", ".join(j["strengths"]) + L
        jb += "短板: " + ", ".join(j["weaknesses"]) + L
        jb += "建议: " + ", ".join(j["suggestions"])
        jd_texts.append(jb)
    all_jds = (L + "---" + L).join(jd_texts)
    system_prompt = (
        "你是一位资深简历优化专家。根据目标岗位JD对候选人简历进行精准定向优化。" + L + L +
        "原则：" + L +
        "1.自我评价重写，植入JD关键词" + L +
        "2.经历用行业术语重描述，量化成果" + L +
        "3.技能优先列出JD要求的" + L +
        "4.贴合行业真实情况" + L +
        "5.差距大时可合理杜撰补充经历" + L + L +
        "返回JSON:{\"target_position\":\"\",\"optimized_summary\":\"\",\"optimized_projects\":[{\"name\":\"\",\"role\":\"\",\"description\":\"\"}],\"enhanced_skills\":[],\"optimization_notes\":\"\"}"
    )
    user_msg = (
        "简历：" + L +
        "姓名:" + name + " 意向:" + desired + L +
        "自我评价:" + summary + L +
        "技能:" + ", ".join(skills) + L +
        "经历:" + L + exp_text + L +
        "教育:" + L + edu_text + L + L +
        "目标岗位:" + L + all_jds + L + L +
        "请精准优化，贴合行业实际"
    )
    try:
        client = DeepSeekClient()
        result = client.chat_json(system_prompt, user_msg)
        result["ok"] = True
        result["resume_file"] = resume_file
        result["jobs_count"] = len(selected_jobs)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}
@app.post("/api/deliver/mark")
async def mark_delivered(
    url: str = Form(""),
    title: str = Form(""),
    company: str = Form(""),
    salary: str = Form(""),
    score: int = Form(0),
    notes: str = Form("")
):
    if not url:
        return {"ok": False, "error": "缺少URL"}
    history = _load_deliver_history()
    for h in history:
        if h.get("url") == url:
            return {"ok": False, "error": "该岗位已投递过"}
    entry = {
        "url": url, "title": title, "company": company,
        "salary": salary, "score": score, "notes": notes,
        "delivered_at": datetime.now().isoformat(),
        "delivered_at_display": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history.append(entry)
    _save_deliver_history(history)
    STATS["deliveries"] = len(history)
    add_log(f"已投递: {title} @ {company}", "success")
    return {"ok": True, "total_delivered": len(history), "entry": entry}

@app.post("/api/deliver/undo")
async def undo_deliver(url: str = Form("")):
    history = _load_deliver_history()
    history = [h for h in history if h.get("url") != url]
    _save_deliver_history(history)
    STATS["deliveries"] = len(history)
    return {"ok": True, "total_delivered": len(history)}


if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*50}")
    print(f"  AI 智能简历助手 Web 控制台")
    print(f"  打开浏览器访问: http://localhost:5000")
    print(f"{'='*50}\n")
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=False)


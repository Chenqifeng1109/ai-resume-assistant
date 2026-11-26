import json
import os

from config import DATA_DIR
from core.workspace_context import get_active_data_dir
from core.file_security import resolve_file_in_directory
from core.input_validation import (
    validate_choice,
    validate_http_url,
    validate_integer,
    validate_text,
)
from core.runtime_state import STATS, add_log
from modules.deepseek_client import DeepSeekClient
from modules.job_repository import list_job_batches, load_job_batch
from modules.job_scraper import load_profile

deliver_status = {"running": False, "progress": "", "total": 0, "done": 0, "last_run": ""}

DELIVERY_STATUSES = {
    "pending",
    "delivered",
    "replied",
    "interview",
    "offer",
    "rejected",
}



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

    from modules.deliver_manager import DeliverManager

    return DeliverManager().get_history()



def _save_deliver_history(history):

    # 已弃用，由 DeliverManager 负责保存

    pass



def get_deliver_status():

    return deliver_status



def get_deliver_history():

    history = _load_deliver_history()

    return {"ok": True, "history": history[-50:], "total": len(history)}





def generate_greeting(

    resume_file: str = "",

    direction: str = "",

    jobs_file: str = "",

    scene: str = "greeting",

    tone: str = "professional",

    target_job_json: str = "",

    data_dir: str | None = None,

    db_path: str | None = None,

):

    """AI生成打招呼开场白 - 基于简历+岗位+用户指令"""

    if not resume_file:

        return {"ok": False, "error": "请先选择简历"}

    direction, error = validate_text(
        direction,
        "direction",
        max_length=2000,
    )
    if error:

        return error

    data_dir = data_dir or get_active_data_dir(DATA_DIR)
    resolved_resume = resolve_file_in_directory(data_dir, resume_file, {".json"})
    if resolved_resume is None:

        return {"ok": False, "error": "简历文件名不安全"}

    _, filepath = resolved_resume

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

        resolved_jobs = resolve_file_in_directory(data_dir, jobs_file, {".json"})
        if resolved_jobs is None:

            return {"ok": False, "error": "岗位文件名不安全"}

        batch_id, _ = resolved_jobs
        jobs_data = load_job_batch(batch_id, db_path)

        if jobs_data is not None:

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

你需要严格按照这个方向来写文案，这是最高优先级的要求。

如果用户没有在上面明确写出具体公司名，请统一称呼「贵司」，绝不要自行套用简历历史意向或其他公司名。

"""

    else:

        direction_section = "[用户未填写方向，请根据简历和岗位信息自动生成]\n"

    display_position = (
        position.split("@", 1)[0].strip()
        if direction and isinstance(position, str) and "@" in position
        else position
    )

    resume_section = f"""[求职者信息]

姓名：{name}

求职意向：{display_position}

核心技能：{skills_str}

个人亮点：{summary}

"""

    

    target_job_section = ""
    if target_job_json and str(target_job_json).strip():
        try:
            tj = json.loads(str(target_job_json))
            if isinstance(tj, dict) and (tj.get("title") or tj.get("company")):
                tj_title = str(tj.get("title") or "").strip()
                tj_company = str(tj.get("company") or "").strip()
                tj_salary = str(tj.get("salary") or "面议").strip()
                tj_loc = str(tj.get("location") or "").strip()
                tj_tags = "、".join(str(t) for t in (tj.get("tags") or [])[:10] if t)
                tj_desc = str(tj.get("description") or "").strip()[:1500]
                target_job_section = (
                    "[已锁定目标岗位 JD - 请高度针对此具体岗位和公司专项撰写]\n"
                    f"- 目标公司：{tj_company}\n"
                    f"- 目标岗位：{tj_title}\n"
                    f"- 薪资地点：{tj_salary} | {tj_loc}\n"
                    + (f"- 岗位标签：{tj_tags}\n" if tj_tags else "")
                    + (f"- 岗位描述：\n{tj_desc}\n" if tj_desc else "")
                )
        except Exception:
            pass

    jobs_section = ""

    if target_job_section:
        jobs_section = target_job_section
    elif jobs_context:

        jobs_section = f"""[采集到的岗位信息 - 供参考]

{ jobs_context }

"""

    

    clean_scene = str(scene or "greeting").strip().lower()
    if clean_scene not in {"greeting", "cover_letter", "referral", "followup"}:
        clean_scene = "greeting"
    clean_tone = str(tone or "professional").strip().lower()
    tone_desc = {
        "professional": "专业精炼、逻辑清晰、不卑不亢",
        "warm": "热情真诚、有亲和力、积极主动",
        "concise": "大厂干练风、直击亮点、极简高效",
    }.get(clean_tone, "专业精炼、逻辑清晰")

    scene_prompts = {
        "greeting": f"""请为求职者生成一段简短的招聘平台打招呼开场白（发给 HR 或业务负责人）。
要求：
1. 【最重要】用户写的投递方向/要求是最高优先级，绝不能偏离
2. 语气风格：{tone_desc}
3. 字数控制在 75~120 字，用「您好」开头，自然收尾，突出 2 个真实匹配亮点
4. 只返回纯正文，不要 JSON、不要引号、不要标题。""",
        "cover_letter": f"""请为求职者生成一封可直接发送给 HR 邮箱的求职自荐信（Cover Letter）。
要求：
1. 【最重要】用户写的投递方向/要求是最高优先级
2. 语气风格：{tone_desc}
3. 首行写「邮件主题：应聘{position or '目标岗位'} - {profile.get('name', '求职者')}」，空一行后写正文（220~320字，分3小段：应聘意向、真实经历佐证、礼貌致谢）
4. 严禁虚构简历里不存在的公司或数字，只返回纯文本，不要 JSON。""",
        "referral": f"""请为求职者生成一段发给校友、脉脉前辈或目标公司员工的「高情商求内推话术」。
要求：
1. 【最重要】用户写的投递方向/要求是最高优先级
2. 语气风格：{tone_desc}
3. 字数控制在 90~150 字，礼貌不打扰、信息密度高（简短背景 + 目标岗位 + 方便对方转交的核心亮点 + 客气收尾）
4. 只返回纯文本，不要 JSON、不要引号。""",
        "followup": f"""请为求职者生成一段「面试后感谢信 / 进度礼貌跟进话术」。
要求：
1. 【最重要】用户写的投递方向/要求是最高优先级
2. 语气风格：{tone_desc}
3. 字数控制在 100~160 字，感谢面试官时间、呼应自身与岗位契合点、礼貌询问后续流程进度
4. 只返回纯文本，不要 JSON、不要引号。""",
    }

    user_msg = f"""{scene_prompts[clean_scene]}

{direction_section}

{resume_section}

{jobs_section}"""



    try:

        client = DeepSeekClient()

        result = client.chat(

            system_prompt="你是一个专业的求职沟通文案顾问。注意：用户写的投递方向/要求是你必须遵守的最高指令，绝不能编造简历里没有的经历。只返回最终可复制的纯文本，严禁返回 JSON 或 Markdown 代码块。",

            user_message=user_msg,

            temperature=0.7,
            raise_on_error=True,

        )

        if not isinstance(result, str) or not result.strip():
            return {
                "ok": False,
                "error": "AI未返回有效开场白，请稍后重试",
                "error_code": "UPSTREAM_ERROR",
            }
        cleaned_raw = result.strip()
        if cleaned_raw.startswith("```"):
            lines = cleaned_raw.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned_raw = "\n".join(lines).strip()
        if cleaned_raw.startswith("{") and cleaned_raw.endswith("}"):
            try:
                parsed_obj = json.loads(cleaned_raw)
                if isinstance(parsed_obj, dict):
                    for key in ("greeting", "answer", "content", "text", "message"):
                        val = parsed_obj.get(key)
                        if isinstance(val, str) and val.strip():
                            cleaned_raw = val.strip()
                            break
                    else:
                        first_str = next((v.strip() for v in parsed_obj.values() if isinstance(v, str) and v.strip()), "")
                        if first_str:
                            cleaned_raw = first_str
            except Exception:
                pass
        greeting = cleaned_raw.strip().strip('"').strip("'").strip()
        if not greeting:
            return {
                "ok": False,
                "error": "AI未返回有效开场白，请稍后重试",
                "error_code": "UPSTREAM_ERROR",
            }

        return {"ok": True, "greeting": greeting, "position": position}

    except Exception:

        return {
            "ok": False,
            "error": "AI开场白生成失败，请稍后重试或检查模型配置",
            "error_code": "UPSTREAM_ERROR",
        }



def list_deliver_candidates(

    jobs_file: str = "",

    resume_file: str = "",

    threshold: int = 70,

    data_dir: str | None = None,

    db_path: str | None = None,

):

    threshold, error = validate_integer(
        threshold,
        "threshold",
        minimum=0,
        maximum=100,
    )
    if error:

        return error

    data_dir = data_dir or get_active_data_dir(DATA_DIR)

    batch_id = ""
    jobs_data = None
    if jobs_file:

        resolved_jobs = resolve_file_in_directory(data_dir, jobs_file, {".json"})
        if resolved_jobs is None:

            return {"ok": False, "error": "岗位文件名不安全"}

        batch_id, _ = resolved_jobs
        jobs_data = load_job_batch(batch_id, db_path)

    if jobs_data is None:

        batches = list_job_batches(db_path)

        if not batches:

            return {"ok": False, "error": "没有找到岗位采集文件"}

        batch_id = batches[0]["batch_id"]
        jobs_data = load_job_batch(batch_id, db_path)

    if jobs_data is None:

        return {"ok": False, "error": "岗位文件不存在"}

    jobs_list = jobs_data.get("jobs", [])

    if resume_file:

        resolved_resume = resolve_file_in_directory(data_dir, resume_file, {".json"})
        if resolved_resume is None:

            return {"ok": False, "error": "简历文件名不安全"}

        _, resume_path = resolved_resume

        if os.path.exists(resume_path):

            with open(resume_path, "r", encoding="utf-8") as f:

                profile = json.load(f)

        else:

            profile = load_profile()

    else:

        profile = load_profile()

    if not profile:

        return {"ok": False, "error": "没有已解析的简历"}

    

    # 检查岗位文件是否做过JD匹配评分

    scored_resume = jobs_data.get("resume_name", "")

    if not scored_resume:

        return {"ok": False, "error": "该岗位文件还未进行JD匹配评分，请先在步骤5用当前简历进行批量评分。"}

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

        "jobs_file": batch_id,

        "threshold": threshold,

        "total_jobs": len(jobs_list),

        "candidates": len(candidates_list),

        "already_delivered": len(delivered_urls),

        "jobs": candidates_list

    }





def mark_delivered(

    url: str = "",

    title: str = "",

    company: str = "",

    salary: str = "",

    score: int = 0,

    notes: str = ""

):

    url, error = validate_http_url(url)
    if error:

        return error

    normalized_values = {}
    for field, value, maximum in (
        ("title", title, 200),
        ("company", company, 200),
        ("salary", salary, 100),
        ("notes", notes, 2000),
    ):
        normalized, error = validate_text(value, field, max_length=maximum)
        if error:
            return error
        normalized_values[field] = normalized

    score, error = validate_integer(score, "score", minimum=0, maximum=100)
    if error:
        return error

    title = normalized_values["title"]
    company = normalized_values["company"]
    salary = normalized_values["salary"]
    notes = normalized_values["notes"]

        

    from modules.deliver_manager import DeliverManager

    manager = DeliverManager()

    

    result = manager.mark_delivered(url, title, company, salary, score, notes)

    if not result["ok"]:

        return result

        

    history = manager.get_history()

    STATS["deliveries"] = len(history)

    add_log(f"已投递: {title} @ {company}", "success")

    return {"ok": True, "total_delivered": len(history)}



def undo_deliver(url: str = ""):

    url, error = validate_http_url(url)
    if error:

        return error

    from modules.deliver_manager import DeliverManager

    manager = DeliverManager()

    manager.undo_deliver(url)

    

    history = manager.get_history()

    STATS["deliveries"] = len(history)

    return {"ok": True, "total_delivered": len(history)}





def api_update_deliver_status(delivery_id: int, status: str):
    delivery_id, error = validate_integer(
        delivery_id,
        "delivery_id",
        minimum=1,
        maximum=2_147_483_647,
    )
    if error:
        return error

    status, error = validate_choice(status, "status", DELIVERY_STATUSES)
    if error:
        return error

    from modules.deliver_manager import DeliverManager
    success = DeliverManager().update_status(delivery_id, status)
    if success:
        return {"ok": True, "msg": "状态更新成功"}
    return {"ok": False, "error": "更新失败，找不到该记录"}

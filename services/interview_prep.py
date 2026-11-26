"""AI 模拟面试官业务：针对「当前简历 × 目标 JD」生成高频追问、STAR 参考答法与反问清单。

严格遵守事实护栏：
- 所有 STAR 参考答法必须立足于候选人简历中的真实经历与技能；
- 简历未写明的具体数据/指标绝不虚构，而是用【请补充你的真实数据】占位提醒。
"""

from __future__ import annotations

import json
import os

from config import DATA_DIR
from core.file_security import resolve_file_in_directory
from core.runtime_state import add_log
from core.workspace_context import get_active_data_dir
from modules.db_client import get_connection, init_db
from modules.deepseek_client import DeepSeekClient
from modules.job_repository import load_job_batch
from modules.restriction_checker import (
    evaluate_restrictions_against_jd,
    normalize_restrictions,
)


def _load_resume_for_interview(
    resume_file: str,
    data_dir: str,
    db_path: str | None = None,
) -> tuple[dict | None, str | None]:
    resolved = resolve_file_in_directory(data_dir, resume_file, {".json"})
    if resolved is None:
        return None, "简历文件名不安全"
    safe_name, filepath = resolved
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    try:
        init_db(db_path)
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT parsed_data FROM resumes WHERE filename = ?", (safe_name,)
        ).fetchone()
        conn.close()
        if row and row["parsed_data"]:
            return json.loads(row["parsed_data"]), None
    except Exception:
        pass
    return None, "简历文件不存在"


def _summarize_profile_for_prompt(profile: dict) -> str:
    sections = [
        f"姓名：{profile.get('name', '候选人')}",
        f"求职意向：{profile.get('desired_position', '')}",
        f"技能：{', '.join(str(s) for s in (profile.get('skills') or [])[:25])}",
        f"自我介绍：{str(profile.get('summary') or '')[:600]}",
    ]
    for label, key, p_key, s_key in (
        ("工作/实习经历", "work_experience", "position", "company"),
        ("项目经历", "project_experience", "name", "role"),
        ("个人实践", "practical_experience", "role", "organization"),
        ("校园经历", "campus_experience", "role", "organization"),
        ("科研经历", "research_experience", "name", "role"),
    ):
        items = profile.get(key) or []
        if not items:
            continue
        lines = []
        for idx, item in enumerate(items[:5]):
            if not isinstance(item, dict):
                continue
            title = str(item.get(p_key) or "").strip()
            org = str(item.get(s_key) or "").strip()
            dur = str(item.get("duration") or "").strip()
            desc = str(item.get("description") or "").strip()[:450]
            lines.append(f"  {idx + 1}. {title} @ {org} ({dur})：{desc}")
        if lines:
            sections.append(f"{label}：\n" + "\n".join(lines))
    return "\n".join(sections)


def generate_interview_prep(
    resume_file: str = "",
    jd_text: str = "",
    jobs_file: str = "",
    job_index: int = -1,
    target_position: str = "",
    restrictions: str | list[str] = "",
    db_path: str | None = None,
    avoid_questions: list[str] | str = "",
    temperature: float = 0.72,
    question_count: int = 5,
) -> dict:
    """根据当前简历与目标 JD（或批次岗位）生成结构化模拟面试追问与 STAR 参考答法。"""
    if not str(resume_file or "").strip():
        return {"ok": False, "error": "请先选择一份简历", "error_code": "INVALID_INPUT", "field": "resume_file"}

    data_dir = get_active_data_dir(DATA_DIR)
    profile, load_err = _load_resume_for_interview(resume_file.strip(), data_dir, db_path)
    if load_err or not isinstance(profile, dict):
        return {
            "ok": False,
            "error": load_err or "简历不存在",
            "error_code": "NOT_FOUND" if load_err == "简历文件不存在" else "INVALID_INPUT",
        }

    resolved_jd = str(jd_text or "").strip()
    resolved_position = str(target_position or "").strip()
    resolved_company = ""
    batch_restrictions: list[str] = []

    if jobs_file and str(jobs_file).strip():
        resolved_batch = resolve_file_in_directory(data_dir, str(jobs_file).strip(), {".json"})
        if resolved_batch is None:
            return {"ok": False, "error": "岗位批次文件名不安全", "error_code": "INVALID_INPUT", "field": "jobs_file"}
        batch_data = load_job_batch(resolved_batch[0], db_path)
        if batch_data is None:
            return {"ok": False, "error": "目标岗位批次不存在", "error_code": "NOT_FOUND"}
        batch_restrictions = normalize_restrictions(batch_data.get("restrictions") or [])
        jobs_list = batch_data.get("jobs") or []
        if isinstance(jobs_list, list) and jobs_list:
            idx = job_index if 0 <= job_index < len(jobs_list) else 0
            target_job = jobs_list[idx]
            if isinstance(target_job, dict):
                resolved_position = resolved_position or str(target_job.get("title") or "").strip()
                resolved_company = str(target_job.get("company") or "").strip()
                if not resolved_jd:
                    parts = [
                        f"岗位名称：{target_job.get('title', '')}",
                        f"公司：{target_job.get('company', '')}",
                        f"薪资：{target_job.get('salary', '')} | 地点：{target_job.get('location', '')}",
                    ]
                    tags = target_job.get("tags") or []
                    if tags:
                        parts.append("标签：" + "、".join(str(t) for t in tags[:10]))
                    desc = str(target_job.get("description") or "").strip()
                    if desc:
                        parts.append("岗位描述：\n" + desc)
                    resolved_jd = "\n".join(parts)

    if len(resolved_jd) < 10:
        return {
            "ok": False,
            "error": "请提供至少 10 字的目标岗位 JD 或指定有效岗位批次",
            "error_code": "INVALID_INPUT",
            "field": "jd_text",
        }

    effective_restrictions = normalize_restrictions(restrictions) or batch_restrictions
    restriction_report = (
        evaluate_restrictions_against_jd(effective_restrictions, resolved_jd)
        if effective_restrictions
        else {"items": [], "summary": {"total": 0, "green": 0, "yellow": 0, "red": 0}}
    )
    unconfirmed_restrictions = [
        item["restriction"]
        for item in restriction_report["items"]
        if item["status"] in ("yellow", "red")
    ]

    try:
        effective_temp = max(0.3, min(float(temperature or 0.72), 0.95))
    except (TypeError, ValueError):
        effective_temp = 0.72
    try:
        effective_count = max(3, min(int(question_count or 5), 8))
    except (TypeError, ValueError):
        effective_count = 5

    avoid_list: list[str] = []
    if isinstance(avoid_questions, str) and avoid_questions.strip():
        try:
            parsed_avoid = json.loads(avoid_questions)
            if isinstance(parsed_avoid, list):
                avoid_list = [str(x).strip() for x in parsed_avoid if str(x).strip()][:16]
        except Exception:
            avoid_list = [x.strip() for x in avoid_questions.splitlines() if x.strip()][:16]
    elif isinstance(avoid_questions, list):
        avoid_list = [str(x).strip() for x in avoid_questions if str(x).strip()][:16]

    system_prompt = f"""你是一位资深技术/业务招聘面试官与求职教练。
请根据候选人的真实简历和目标岗位 JD，输出严格 JSON 格式的模拟面试追问清单：
{{
  "target_role": "目标岗位名称",
  "overall_strategy": "一句话面试核心策略与重点提醒",
  "questions": [
    {{
      "category": "项目深挖 | 岗位能力考察 | 短板压力追问 | 场景实战 | 架构与取舍",
      "question": "真实面试官口吻的具体提问",
      "intent": "面试官真正想考察的核心能力或风险点",
      "standard_answer": "可直接开口说的第一人称示范标准口语答案（约150-250字，自然流畅、有条理，立足候选人真实简历，简历缺数字时用【请补充你的真实数据】占位，严禁编造）",
      "star_answer": {{
        "situation": "背景（立足简历真实经历）",
        "task": "你的核心任务",
        "action": "具体做法与方法论",
        "result": "可量化结果（简历未写数字时必须写【请补充你的真实数据】，严禁编造虚假业绩）"
      }},
      "follow_ups": ["可能继续深挖的追问1", "追问2"]
    }}
  ],
  "reverse_questions": ["建议候选人反问面试官的问题1（可自然融入待确认的底线条件）", "问题2", "问题3"]
}}
要求：
1. 生成 {effective_count} 道高价值、紧贴该简历与该 JD 的差异化面试题（覆盖项目深挖、业务/架构取舍、短板压力追问与场景实战；避免每次都从同一个常规切入点发问）。
2. 严守真实性底线：绝不为候选人编造简历中不存在的公司、项目、头衔或百分比数字。
3. 仅返回合法 JSON，不要输出 Markdown 代码块以外的解释文字。"""

    user_message = (
        f"【目标岗位】{resolved_position or '目标岗位'}"
        + (f" @ {resolved_company}" if resolved_company else "")
        + f"\n\n【目标 JD 原文】\n{resolved_jd[:4000]}\n\n"
        + f"【候选人当前简历】\n{_summarize_profile_for_prompt(profile)}\n"
    )
    if avoid_list:
        user_message += (
            "\n【本轮为“换一批题库”模式 — 请从全新维度出题（如方案权衡、异常处理、业务闭环、跨团队推进、边界场景），严禁与以下已出过的题目重复或雷同】\n"
            + "\n".join(f"- {q}" for q in avoid_list)
        )
    if unconfirmed_restrictions:
        user_message += (
            "\n【候选人待确认或有风险的个人底线（请在 reverse_questions 中提供礼貌高情商的反问方式）】\n"
            + "、".join(unconfirmed_restrictions)
        )

    add_log(f"开始生成 AI 模拟面试追问: {resolved_position or '目标岗位'}（温度 {effective_temp}，题数 {effective_count}）", "info")
    try:
        client = DeepSeekClient()
        try:
            ai_data = client.chat_json(system_prompt, user_message, temperature=effective_temp)
        except TypeError:
            ai_data = client.chat_json(system_prompt, user_message)
    except Exception as error:
        add_log(f"模拟面试生成失败: {error}", "error")
        return {"ok": False, "error": f"模拟面试生成失败: {str(error)}", "error_code": "UPSTREAM_ERROR"}

    if not isinstance(ai_data, dict):
        return {"ok": False, "error": "AI 返回格式异常，请重试", "error_code": "UPSTREAM_ERROR"}

    raw_questions = ai_data.get("questions") if isinstance(ai_data.get("questions"), list) else []
    cleaned_questions = []
    for item in raw_questions[:8]:
        if not isinstance(item, dict) or not str(item.get("question") or "").strip():
            continue
        star = item.get("star_answer") if isinstance(item.get("star_answer"), dict) else {}
        follow_ups = [
            str(q).strip()
            for q in (item.get("follow_ups") if isinstance(item.get("follow_ups"), list) else [])
            if str(q).strip()
        ][:3]
        star_clean = {
            "situation": str(star.get("situation") or "").strip(),
            "task": str(star.get("task") or "").strip(),
            "action": str(star.get("action") or "").strip(),
            "result": str(star.get("result") or "").strip(),
        }
        std_answer = str(item.get("standard_answer") or "").strip()
        if not std_answer:
            std_parts = [v for v in (star_clean["situation"], star_clean["task"], star_clean["action"], star_clean["result"]) if v]
            std_answer = " ".join(std_parts)
        cleaned_questions.append(
            {
                "category": str(item.get("category") or "综合考察").strip(),
                "question": str(item.get("question") or "").strip(),
                "intent": str(item.get("intent") or "").strip(),
                "standard_answer": std_answer,
                "star_answer": star_clean,
                "follow_ups": follow_ups,
            }
        )

    reverse_questions = [
        str(q).strip()
        for q in (ai_data.get("reverse_questions") if isinstance(ai_data.get("reverse_questions"), list) else [])
        if str(q).strip()
    ][:5]

    if not cleaned_questions:
        return {"ok": False, "error": "AI 未能生成有效面试题，请重试", "error_code": "UPSTREAM_ERROR"}

    add_log(f"模拟面试追问生成完成: 共 {len(cleaned_questions)} 题", "success")
    return {
        "ok": True,
        "target_role": str(ai_data.get("target_role") or resolved_position or "目标岗位").strip(),
        "company": resolved_company,
        "overall_strategy": str(ai_data.get("overall_strategy") or "").strip(),
        "questions": cleaned_questions,
        "reverse_questions": reverse_questions,
        "restriction_report": restriction_report if effective_restrictions else None,
    }

"""针对目标岗位的精准简历优化与覆盖后复测对比业务。"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os

from config import DATA_DIR, WRITE_LEGACY_JOB_JSON
from core.workspace_context import get_active_data_dir
from core.file_security import resolve_file_in_directory
from core.input_validation import parse_index_list
from core.runtime_state import add_log
from modules.db_client import get_connection, init_db
from modules.deepseek_client import DeepSeekClient
from modules.jd_matcher import match_resume_to_jd
from modules.job_repository import load_job_batch, save_job_batch
from modules.resume_optimization_guard import (
    merge_grounded_optimization,
    optimization_source,
)


def _resume_content_fingerprint(profile: dict) -> str:
    """计算简历核心正文的稳定指纹，用于判定覆盖后是否需要失效旧评分缓存。"""
    payload = {
        key: profile.get(key)
        for key in (
            "desired_position",
            "summary",
            "skills",
            "work_experience",
            "project_experience",
            "practical_experience",
            "campus_experience",
            "research_experience",
        )
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _load_resume_profile(resume_file: str, data_dir: str, db_path: str | None = None) -> tuple[dict | None, str | None]:
    resolved_resume = resolve_file_in_directory(data_dir, resume_file, {".json"})
    if resolved_resume is None:
        return None, "简历文件名不安全"

    safe_name, resume_path = resolved_resume
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            return json.load(f), None

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


def _format_exp_section(items: list, primary_key: str, secondary_key: str) -> str:
    lines = []
    for idx, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        p = str(item.get(primary_key, "") or "").strip()
        s = str(item.get(secondary_key, "") or "").strip()
        d = str(item.get("duration", "") or "").strip()
        desc = str(item.get("description", "") or "").strip()
        lines.append(f"[{idx}] {p} @ {s} ({d}): {desc}")
    return "\n".join(lines)


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


def precision_optimize(

    resume_file: str = "",

    jobs_file: str = "",

    job_indices: str = "",

    data_dir: str | None = None,

    db_path: str | None = None,

    custom_jd: str = "",

    custom_target: str = "",

    intensity: str = "balanced",

):

    if not resume_file:

        return {"ok": False, "error": "缺少参数"}

    clean_custom_jd = str(custom_jd or "").strip()
    clean_custom_target = str(custom_target or "").strip()

    data_dir = data_dir or get_active_data_dir(DATA_DIR)

    stored_profile, load_err = _load_resume_profile(resume_file, data_dir, db_path)
    if load_err:
        return {"ok": False, "error": load_err}

    profile, _ = optimization_source(stored_profile)

    batch_id = ""
    selected_jobs = []

    if clean_custom_jd:
        if len(clean_custom_jd) < 20:
            return {"ok": False, "error": "粘贴的岗位 JD 内容过短（至少 20 字）", "error_code": "INVALID_INPUT"}
        selected_jobs.append({
            "index": 0,
            "job_id": "custom-jd",
            "title": clean_custom_target or profile.get("desired_position") or "目标岗位",
            "company": "自定义目标岗位",
            "salary": "",
            "location": "",
            "tags": [],
            "match_score": 0,
            "match_brief": "",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "jd_full": clean_custom_jd[:12000],
        })
    else:
        indices, error = parse_index_list(job_indices)
        if error:
            return error

        resolved_jobs = resolve_file_in_directory(data_dir, jobs_file, {".json"})
        if resolved_jobs is None:
            return {"ok": False, "error": "岗位文件名不安全"}

        batch_id, _ = resolved_jobs

        jobs_data = load_job_batch(batch_id, db_path)
        if jobs_data is None:
            return {"ok": False, "error": "岗位文件不存在"}

        jobs_list = jobs_data.get("jobs", [])

        for idx in indices:
            if 0 <= idx < len(jobs_list):
                job = jobs_list[idx]
                stored_desc = str(job.get("description") or "").strip()
                jd_text = stored_desc if len(stored_desc) >= 30 else _fetch_jd_detail(job.get("url", ""))
                selected_jobs.append({
                    "index": idx,
                    "job_id": job.get("job_id", ""),
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "salary": job.get("salary", ""),
                    "location": job.get("location", ""),
                    "tags": job.get("tags", []),
                    "match_score": job.get("match_score", 0),
                    "match_brief": job.get("match_brief", ""),
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

    proj_exp = profile.get("project_experience", [])

    prac_exp = profile.get("practical_experience", [])

    campus_exp = profile.get("campus_experience", [])

    research_exp = profile.get("research_experience", [])

    edu = profile.get("education", [])

    L = chr(10)

    work_text = _format_exp_section(work_exp, "position", "company")
    proj_text = _format_exp_section(proj_exp, "name", "role")
    prac_text = _format_exp_section(prac_exp, "role", "organization")
    campus_text = _format_exp_section(campus_exp, "role", "organization")
    research_text = _format_exp_section(research_exp, "name", "role")

    edu_lines = []

    for e in edu:

        s = str(e.get("school", "")); m = str(e.get("major", ""))

        dg = str(e.get("degree", "")); y = str(e.get("year", ""))

        edu_lines.append("- " + s + " | " + m + " | " + dg + " | " + y)

    edu_text = L.join(edu_lines)

    jd_texts = []

    for j in selected_jobs:

        jb = ""

        jb += "【岗位" + str(j["title"]) + "@" + str(j["company"]) + " | " + str(j["salary"]) + " | 匹配度" + str(j["match_score"]) + "分】" + L

        if j["jd_full"]:

            jb += "JD原文:" + L + j["jd_full"] + L

        tl = j["tags"] if isinstance(j["tags"], list) else []

        jb += "关键词: " + ", ".join(str(t) for t in tl[:10]) + L

        jb += "优势: " + ", ".join(str(x) for x in j["strengths"]) + L

        jb += "短板: " + ", ".join(str(x) for x in j["weaknesses"]) + L

        jb += "建议: " + ", ".join(str(x) for x in j["suggestions"])

        jd_texts.append(jb)

    all_jds = (L + "---" + L).join(jd_texts)

    system_prompt = (

        "你是一位资深简历优化专家。根据目标岗位JD对候选人简历进行精准定向优化。" + L + L +

        "严格原则：" + L +

        "1. 自我评价重写，紧扣目标岗位JD核心关键词与胜任力，不允许出现学历信息和原简历未出现的新数字" + L +

        "2. 工作经历(optimized_work_experience)与项目经历(optimized_project_experience)必须与原简历条目数量、顺序完全一致，只重写description以贴合JD，严禁新增或删减条目，严禁编造原文不存在的数字/百分比/年份" + L +

        "3. enhanced_skills 只能从候选人原简历已有 skills 列表中挑选并按与目标JD相关度从高到低重排，原词一字不改；缺少的技能写入 optimization_notes 建议" + L +

        "4. 严禁杜撰公司、项目、时间、技能、数字和成果" + L + L +

        '返回合法JSON：{"target_position":"","optimized_summary":"","optimized_work_experience":[{"company":"","position":"","duration":"","description":""}],"optimized_project_experience":[{"name":"","role":"","duration":"","description":""}],"enhanced_skills":[],"optimization_notes":""}'

    )

    exp_blocks = []
    if work_text:
        exp_blocks.append(f"工作/实习经历(共{len(work_exp)}条):\n{work_text}")
    if proj_text:
        exp_blocks.append(f"项目经历(共{len(proj_exp)}条):\n{proj_text}")
    if prac_text:
        exp_blocks.append(f"个人实践(共{len(prac_exp)}条):\n{prac_text}")
    if campus_text:
        exp_blocks.append(f"校园经历(共{len(campus_exp)}条):\n{campus_text}")
    if research_text:
        exp_blocks.append(f"科研经历(共{len(research_exp)}条):\n{research_text}")

    from modules.resume_optimization_guard import resolve_intensity_config
    intensity_key, intensity_cfg = resolve_intensity_config(intensity)
    llm_temperature = float(intensity_cfg["temperature"])

    user_msg = (
        "简历：" + L +
        "姓名:" + name + " 意向:" + desired + L +
        "自我评价:" + summary + L +
        "技能:" + ", ".join(str(sk) for sk in skills) + L +
        (L.join(exp_blocks) if exp_blocks else "经历: 无") + L +
        "教育:" + L + edu_text + L + L +
        "目标岗位:" + L + all_jds + L + L +
        f"改写力度与温度要求：{intensity_cfg['prompt_rule']}" + L +
        "请严格保持工作经历与项目经历条目数量与原文一致，并对自我评价和每段经历 description 按目标 JD 做实质性重构升级，避免原样照抄。"
    )

    try:

        client = DeepSeekClient()

        prompt_with_intensity = f"{system_prompt}\n\n{intensity_cfg['prompt_rule']}"
        try:
            result = client.chat_json(
                prompt_with_intensity,
                user_msg,
                temperature=llm_temperature,
            )
        except TypeError:
            result = client.chat_json(prompt_with_intensity, user_msg)

        if not isinstance(result, dict) or result.get("error"):
            return {
                "ok": False,
                "error": (result.get("error") if isinstance(result, dict) else "精准优化返回格式异常"),
                "raw": (result.get("raw", "") if isinstance(result, dict) else ""),
                "resume_file": resume_file,
                "jobs_count": len(selected_jobs),
            }

        final_target = str(result.get("target_position") or desired or selected_jobs[0].get("title") or "").strip()
        for _at_sep in ("@", "＠"):
            if _at_sep in final_target:
                final_target = final_target.split(_at_sep, 1)[0].strip()
        candidate_data = {
            "optimized_summary": result.get("optimized_summary", ""),
            "optimized_work_experience": result.get("optimized_work_experience"),
            "optimized_project_experience": (
                result.get("optimized_project_experience")
                if result.get("optimized_project_experience") is not None
                else result.get("optimized_projects")
            ),
            "optimized_practical_experience": result.get("optimized_practical_experience"),
            "optimized_campus_experience": result.get("optimized_campus_experience"),
            "optimized_research_experience": result.get("optimized_research_experience"),
            "enhanced_skills": result.get("enhanced_skills", []),
        }
        merged_profile, optimization_warnings = merge_grounded_optimization(
            profile,
            candidate_data,
            final_target,
            require_evidence=False,
            intensity=intensity_key,
        )
        merged_profile["_optimization_meta"] = {
            "source": "precision_optimize",
            "target": final_target,
            "job_description": all_jds[:4000],
        }

        result["ok"] = True
        result["resume_file"] = resume_file
        result["jobs_file"] = batch_id
        result["jobs_count"] = len(selected_jobs)
        result["target_position"] = final_target
        # 让前端预览内容与后续点击「覆盖简历」写入 SQLite 的最终内容 100% 一致（所见即所存）
        result["optimized_resume"] = merged_profile
        result["optimized_summary"] = merged_profile.get("summary", "")
        result["optimized_work_experience"] = merged_profile.get("work_experience", [])
        result["optimized_projects"] = merged_profile.get("project_experience", [])
        result["enhanced_skills"] = merged_profile.get("skills", [])
        result["optimization_warnings"] = optimization_warnings
        result["selected_jobs"] = [
            {
                "index": j["index"],
                "job_id": j["job_id"],
                "title": j["title"],
                "company": j["company"],
                "salary": j["salary"],
                "location": j["location"],
                "before_score": j["match_score"],
                "before_brief": j["match_brief"],
            }
            for j in selected_jobs
        ]

        return result

    except Exception as e:

        return {"ok": False, "error": str(e)}


def precision_recheck(
    resume_file: str = "",
    jobs_file: str = "",
    job_indices: str = "",
    before_scores: str = "{}",
    data_dir: str | None = None,
    db_path: str | None = None,
    write_legacy_json: bool = WRITE_LEGACY_JOB_JSON,
) -> dict:
    """用覆盖后的最新简历重新检测与已选目标 JD 的匹配度和关联性，输出覆盖前后对比。"""
    if not resume_file or not jobs_file:
        return {"ok": False, "error": "缺少简历或岗位批次参数"}

    indices, error = parse_index_list(job_indices)
    if error:
        return error

    data_dir = data_dir or get_active_data_dir(DATA_DIR)
    profile, load_err = _load_resume_profile(resume_file, data_dir, db_path)
    if load_err or not isinstance(profile, dict):
        return {"ok": False, "error": load_err or "简历加载失败"}

    resolved_jobs = resolve_file_in_directory(data_dir, jobs_file, {".json"})
    if resolved_jobs is None:
        return {"ok": False, "error": "岗位文件名不安全"}

    batch_id, jobs_filepath = resolved_jobs
    jobs_data = load_job_batch(batch_id, db_path)
    if jobs_data is None:
        return {"ok": False, "error": "岗位文件不存在"}

    jobs_list = jobs_data.get("jobs", [])
    if not jobs_list:
        return {"ok": False, "error": "岗位列表为空"}

    before_map: dict = {}
    if before_scores:
        try:
            parsed_before = json.loads(before_scores) if isinstance(before_scores, str) else before_scores
            if isinstance(parsed_before, dict):
                before_map = parsed_before
        except Exception:
            before_map = {}

    target_pairs: list[tuple[int, dict]] = []
    seen_idx = set()
    for idx in indices:
        if 0 <= idx < len(jobs_list) and idx not in seen_idx:
            seen_idx.add(idx)
            target_pairs.append((idx, jobs_list[idx]))

    if not target_pairs:
        return {"ok": False, "error": "没有找到可复测的目标岗位"}

    def _eval_one(pair: tuple[int, dict]) -> dict:
        idx, job = pair
        before_entry = before_map.get(str(idx)) or before_map.get(str(job.get("job_id") or "")) or {}
        if isinstance(before_entry, (int, float)):
            before_score = int(before_entry)
            before_brief = str(job.get("match_brief") or "")
        elif isinstance(before_entry, dict):
            before_score = int(before_entry.get("before_score", before_entry.get("match_score", job.get("match_score") or 0)))
            before_brief = str(before_entry.get("before_brief", before_entry.get("match_brief", job.get("match_brief") or "")))
        else:
            before_score = int(job.get("match_score") or 0)
            before_brief = str(job.get("match_brief") or "")

        jd_parts = [job.get("title", ""), job.get("company", "")]
        if job.get("tags"):
            jd_parts.extend(str(t) for t in job.get("tags", [])[:8] if t)
        desc = str(job.get("description") or "").strip()
        if desc:
            jd_parts.append(desc[:1200])
        jd_text = "\n".join([str(p) for p in jd_parts if p]).strip()

        match_res = match_resume_to_jd(profile, jd_text)
        if match_res.get("ok"):
            after_score = int(match_res.get("overall_score", 50))
            skill_match = int(match_res.get("skill_match", 50))
            experience_match = int(match_res.get("experience_match", 50))
            education_match = int(match_res.get("education_match", 50))
            after_brief = str(match_res.get("verdict") or "")
            strengths = list(match_res.get("strengths") or [])
            weaknesses = list(match_res.get("weaknesses") or [])
            suggestions = list(match_res.get("suggestions") or [])
        else:
            after_score = before_score
            skill_match = int(job.get("skill_match") or 50)
            experience_match = int(job.get("experience_match") or 50)
            education_match = int(job.get("education_match") or 50)
            after_brief = str(match_res.get("error") or "复测失败")
            strengths = list(job.get("strengths") or [])
            weaknesses = list(job.get("weaknesses") or [])
            suggestions = list(job.get("suggestions") or [])

        # 同步写回该岗位在批次里的最新评分
        job["match_score"] = after_score
        job["skill_match"] = skill_match
        job["experience_match"] = experience_match
        job["education_match"] = education_match
        job["match_brief"] = after_brief
        job["strengths"] = strengths
        job["weaknesses"] = weaknesses
        job["suggestions"] = suggestions

        delta = after_score - before_score
        return {
            "index": idx,
            "job_id": job.get("job_id", ""),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "salary": job.get("salary", ""),
            "location": job.get("location", ""),
            "before_score": before_score,
            "after_score": after_score,
            "score_delta": delta,
            "skill_match": skill_match,
            "experience_match": experience_match,
            "education_match": education_match,
            "before_brief": before_brief,
            "after_brief": after_brief,
            "strengths": strengths[:4],
            "weaknesses": weaknesses[:4],
            "suggestions": suggestions[:3],
        }

    workers = min(4, len(target_pairs))
    if workers <= 1:
        items = [_eval_one(p) for p in target_pairs]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            items = list(pool.map(_eval_one, target_pairs))

    jobs_data["jobs"] = jobs_list
    jobs_data["resume_name"] = str(profile.get("name", "") or "")
    jobs_data["scored_resume_file"] = resume_file
    jobs_data["scored_resume_fingerprint"] = _resume_content_fingerprint(profile)
    jobs_data["scored_resume_parsed_at"] = str(profile.get("parsed_at", "") or "")
    save_job_batch(batch_id, jobs_data, db_path)
    if write_legacy_json:
        with open(jobs_filepath, "w", encoding="utf-8") as fh:
            json.dump(jobs_data, fh, ensure_ascii=False, indent=2)

    avg_before = round(sum(x["before_score"] for x in items) / len(items), 1)
    avg_after = round(sum(x["after_score"] for x in items) / len(items), 1)
    avg_delta = round(avg_after - avg_before, 1)
    improved_count = sum(1 for x in items if x["score_delta"] > 0)

    add_log(
        f"精准覆盖后复测完成: {len(items)} 岗平均分 {avg_before} -> {avg_after} ({'+' if avg_delta >= 0 else ''}{avg_delta})",
        "success",
    )

    return {
        "ok": True,
        "resume_file": resume_file,
        "jobs_file": batch_id,
        "resume_updated_at": str(profile.get("parsed_at", "") or ""),
        "count": len(items),
        "avg_before": avg_before,
        "avg_after": avg_after,
        "avg_delta": avg_delta,
        "improved_count": improved_count,
        "items": items,
    }

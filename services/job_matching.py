import hashlib
import json
import os

from config import DATA_DIR, WRITE_LEGACY_JOB_JSON
from core.workspace_context import get_active_data_dir
from core.file_security import resolve_file_in_directory
from core.input_validation import validate_integer, validate_text
from core.runtime_state import add_log
from modules.db_client import get_connection, init_db
from modules.jd_analysis import analyze_jd
from modules.job_repository import load_job_batch, save_job_batch
from modules.job_scraper import load_profile
from modules.jd_matcher import match_resume_to_jd, quick_match
from modules.restriction_checker import (
    evaluate_restrictions_against_jd,
    normalize_restrictions,
)


def _resume_content_fingerprint(profile: dict) -> str:
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


def _load_resume_with_db_fallback(resume_file: str, data_dir: str, db_path: str | None = None):
    if not resume_file:
        return load_profile(), None
    resolved_resume = resolve_file_in_directory(data_dir, resume_file, {".json"})
    if resolved_resume is None:
        return None, {"ok": False, "error": "简历文件名不安全"}
    safe_name, rp = resolved_resume
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as f:
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
    return load_profile(), None


def _load_jobs_data(jobs_file: str, data_dir: str, db_path: str | None):
    resolved_jobs = resolve_file_in_directory(data_dir, jobs_file, {".json"})
    if resolved_jobs is None:
        return None, None, {"ok": False, "error": "岗位文件名不安全"}

    _, filepath = resolved_jobs
    jobs_data = load_job_batch(jobs_file, db_path)
    if jobs_data is None:
        return None, filepath, {"ok": False, "error": "岗位文件不存在"}
    return jobs_data, filepath, None


def _save_jobs_data(
    jobs_file: str,
    jobs_data: dict,
    filepath: str,
    db_path: str | None,
    write_legacy_json: bool,
) -> None:
    save_job_batch(jobs_file, jobs_data, db_path)
    if write_legacy_json:
        with open(filepath, "w", encoding="utf-8") as target:
            json.dump(jobs_data, target, ensure_ascii=False, indent=2)

def match_jd(resume_file: str = "", jd_text: str = "", restrictions: str = ""):

    """

    JD匹配度评分（含个人限制条件避坑红绿灯核查）

    大白话：上传一份JD文本，选择一份简历，AI告诉你匹配度与底线风险

    """

    jd_text, error = validate_text(
        jd_text,
        "jd_text",
        required=True,
        min_length=10,
        max_length=20000,
    )
    if error:

        return error

    

    # 选择简历

    data_dir = get_active_data_dir(DATA_DIR)

    if resume_file:

        resolved_resume = resolve_file_in_directory(data_dir, resume_file, {".json"})
        if resolved_resume is None:

            return {"ok": False, "error": "简历文件名不安全"}

        _, filepath = resolved_resume

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

    

    # 先把JD拆成可核对的结构化要求，再进行简历匹配

    analysis_result = analyze_jd(jd_text)

    if not analysis_result.get("ok"):

        add_log(f"JD分析失败: {analysis_result.get('error', '')}", "error")

        return analysis_result

    jd_analysis = analysis_result["analysis"]

    result = match_resume_to_jd(profile, jd_text, jd_analysis)

    

    if result.get("ok"):

        result["jd_analysis"] = jd_analysis
        restriction_list = normalize_restrictions(restrictions)
        if restriction_list:
            result["restriction_report"] = evaluate_restrictions_against_jd(
                restriction_list, jd_text
            )

        add_log(f"匹配完成，综合评分: {result.get('overall_score', '?')}/100", "success")

    else:

        add_log(f"匹配失败: {result.get('error', '')}", "error")

    

    return result







def batch_score_jobs(
    jobs_file: str = "",
    resume_file: str = "",
    threshold: int = 70,
    data_dir: str | None = None,
    db_path: str | None = None,
    write_legacy_json: bool = WRITE_LEGACY_JOB_JSON,
):

    """

    对一批采集的岗位进行批量JD匹配评分

    大白话：把采集到的岗位列表拿去跟简历一一匹配，返回评分排序

    """

    threshold, error = validate_integer(
        threshold,
        "threshold",
        minimum=0,
        maximum=100,
    )
    if error:

        return error

    data_dir = data_dir or get_active_data_dir(DATA_DIR)

    

    # 加载岗位数据

    if not jobs_file:

        return {"ok": False, "error": "请指定岗位文件"}

    jobs_data, filepath, error = _load_jobs_data(jobs_file, data_dir, db_path)
    if error:

        return error

    

    jobs_list = jobs_data.get("jobs", [])

    if not jobs_list:

        return {"ok": False, "error": "岗位列表为空"}

    

    # 加载简历

    if resume_file:

        resolved_resume = resolve_file_in_directory(data_dir, resume_file, {".json"})
        if resolved_resume is None:

            return {"ok": False, "error": "简历文件名不安全"}

        _, rp = resolved_resume

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

    _save_jobs_data(
        jobs_file,
        jobs_data,
        filepath,
        db_path,
        write_legacy_json,
    )

    

    return {

        "ok": True,

        "total": len(scored_jobs),

        "high_score_count": len(high_score),

        "threshold": threshold,

        "resume_name": profile.get("name", ""),

        "jobs": scored_jobs

    }





def batch_score_jobs_json(
    data: dict,
    data_dir: str | None = None,
    db_path: str | None = None,
    write_legacy_json: bool = WRITE_LEGACY_JOB_JSON,
):

    from modules.jd_matcher import match_resume_to_jd

    """

    批量JD匹配（JSON版，更可靠）

    """

    if not isinstance(data, dict):

        return {
            "ok": False,
            "error": "data必须是对象",
            "error_code": "INVALID_INPUT",
            "field": "data",
        }

    jobs_file = data.get("jobs_file", "")

    resume_file = data.get("resume_file", "")

    threshold = data.get("threshold", 70)

    threshold, error = validate_integer(
        threshold,
        "threshold",
        minimum=0,
        maximum=100,
    )
    if error:

        return error



    data_dir = data_dir or get_active_data_dir(DATA_DIR)

    

    if not jobs_file:

        return {"ok": False, "error": "请指定岗位文件"}

    jobs_data, filepath, error = _load_jobs_data(jobs_file, data_dir, db_path)
    if error:

        return error

    

    jobs_list = jobs_data.get("jobs", [])

    if not jobs_list:

        return {"ok": False, "error": "岗位列表为空"}

    

    profile, resume_err = _load_resume_with_db_fallback(resume_file, data_dir, db_path)
    if resume_err:
        return resume_err

    if not profile:

        return {"ok": False, "error": "没有已解析的简历"}

    

    from concurrent.futures import ThreadPoolExecutor

    force_rescore = bool(data.get("force_rescore", False))
    current_resume_name = str(profile.get("name", "") or "").strip()
    current_fingerprint = _resume_content_fingerprint(profile)
    current_parsed_at = str(profile.get("parsed_at", "") or "").strip()
    stored_resume_name = str(jobs_data.get("resume_name", "") or "").strip()
    stored_resume_file = str(jobs_data.get("scored_resume_file", "") or "").strip()
    stored_fingerprint = str(jobs_data.get("scored_resume_fingerprint", "") or "").strip()
    stored_parsed_at = str(jobs_data.get("scored_resume_parsed_at", "") or "").strip()
    content_unchanged = (
        (not stored_fingerprint or stored_fingerprint == current_fingerprint)
        and (not stored_parsed_at or not current_parsed_at or stored_parsed_at == current_parsed_at)
    )
    resume_identity_matches = (
        bool(current_resume_name)
        and stored_resume_name == current_resume_name
        and (not resume_file or not stored_resume_file or stored_resume_file == resume_file)
        and content_unchanged
    )
    has_cached_scores = any(
        isinstance(j.get("match_score"), (int, float)) for j in jobs_list
    )

    effective_restrictions = normalize_restrictions(
        data.get("restrictions") or jobs_data.get("restrictions") or []
    )

    def _apply_restriction_reports(items: list[dict]) -> None:
        if not effective_restrictions:
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            combined_jd = " ".join(
                str(part)
                for part in (
                    item.get("title", ""),
                    item.get("company", ""),
                    " ".join(str(t) for t in (item.get("tags") or []) if t),
                    item.get("description", ""),
                )
                if part
            )
            item["restriction_report"] = evaluate_restrictions_against_jd(
                effective_restrictions, combined_jd
            )

    if not force_rescore and jobs_data.get("auto_scored") and resume_identity_matches and has_cached_scores:
        cached_jobs = sorted(
            jobs_list,
            key=lambda x: x.get("match_score", -1) if isinstance(x.get("match_score"), (int, float)) else -1,
            reverse=True,
        )
        _apply_restriction_reports(cached_jobs)
        high_score = [
            j for j in cached_jobs
            if isinstance(j.get("match_score"), (int, float)) and j.get("match_score", 0) >= threshold
        ]
        add_log(
            f"命中同简历缓存评分: 直接返回 {len(cached_jobs)} 个岗位 ({len(high_score)} 个 >= {threshold}分)",
            "info",
        )
        return {
            "ok": True,
            "cached": True,
            "total": len(cached_jobs),
            "high_score_count": len(high_score),
            "threshold": threshold,
            "resume_name": current_resume_name,
            "restrictions": effective_restrictions,
            "jobs": cached_jobs,
        }

    raw_max_jobs = data.get("max_jobs", 10)
    try:
        score_limit = min(len(jobs_list), max(1, min(int(raw_max_jobs), 30)))
    except (TypeError, ValueError):
        score_limit = min(len(jobs_list), 10)

    head_jobs = list(jobs_list[:score_limit])
    tail_jobs = list(jobs_list[score_limit:])
    add_log(
        f"开始批量匹配(JSON): 优先并发评估前 {score_limit}/{len(jobs_list)} 个岗位 vs {current_resume_name or '未知'}",
        "info",
    )

    def _score_job_fast(job: dict) -> dict:
        jd_parts = [job.get("title", ""), job.get("company", "")]
        if job.get("tags"):
            jd_parts.extend(str(t) for t in job.get("tags", [])[:8] if t)
        desc = str(job.get("description") or "").strip()
        if desc:
            jd_parts.append(desc[:500])
        jd_text = " ".join([p for p in jd_parts if p]).strip()

        if len(jd_text) < 5:
            job["match_score"] = 50
            job["match_brief"] = "信息不足"
            return job

        try:
            result = quick_match(profile, jd_text)
            job["match_score"] = result.get("score", 50) if result.get("ok") else 50
            job["match_brief"] = result.get("brief", "") if result.get("ok") else "匹配失败"
            job["match_reasons"] = result.get("reasons", []) if result.get("ok") else []
        except Exception as e:
            job["match_score"] = 50
            job["match_brief"] = f"错误: {str(e)[:30]}"
        return job

    workers = min(4, len(head_jobs))
    if workers <= 1:
        scored_head = [_score_job_fast(j) for j in head_jobs]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            scored_head = list(pool.map(_score_job_fast, head_jobs))

    scored_head.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    scored_jobs = scored_head + tail_jobs
    high_score = [
        j for j in scored_jobs
        if isinstance(j.get("match_score"), (int, float)) and j.get("match_score", 0) >= threshold
    ]
    add_log(f"批量匹配完成: {len(high_score)} 个 >= {threshold}分（已评估 {len(scored_head)}/{len(scored_jobs)}）", "success")

    # Save results back to file for deliver list
    jobs_data["jobs"] = scored_jobs
    jobs_data["resume_name"] = current_resume_name
    if resume_file:
        jobs_data["scored_resume_file"] = resume_file
    jobs_data["scored_resume_fingerprint"] = current_fingerprint
    jobs_data["scored_resume_parsed_at"] = current_parsed_at
    jobs_data["auto_scored"] = True
    jobs_data["scored_count"] = len(scored_head)

    _apply_restriction_reports(scored_jobs)
    _save_jobs_data(
        jobs_file,
        jobs_data,
        filepath,
        db_path,
        write_legacy_json,
    )

    return {
        "ok": True,
        "cached": False,
        "total": len(scored_jobs),
        "high_score_count": len(high_score),
        "threshold": threshold,
        "resume_name": current_resume_name,
        "restrictions": effective_restrictions,
        "jobs": scored_jobs,
    }










def batch_match_jd(resume_file: str = "", jd_text: str = ""):

    """

    快速匹配（精简版）

    """

    jd_text, error = validate_text(
        jd_text,
        "jd_text",
        required=True,
        min_length=10,
        max_length=20000,
    )
    if error:

        return error

    

    data_dir = get_active_data_dir(DATA_DIR)

    if resume_file:

        resolved_resume = resolve_file_in_directory(data_dir, resume_file, {".json"})
        if resolved_resume is None:

            return {"ok": False, "error": "简历文件名不安全"}

        _, filepath = resolved_resume

        if os.path.exists(filepath):

            with open(filepath, "r", encoding="utf-8") as f:

                profile = json.load(f)

        else:

            profile = load_profile()

    else:

        profile = load_profile()

    

    if not profile:

        return {"ok": False, "error": "没有已解析的简历"}

    

    result = quick_match(profile, jd_text)

    return result

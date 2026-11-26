import asyncio
import contextvars
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from config import DATA_DIR, WRITE_LEGACY_JOB_JSON
from core.file_security import resolve_file_in_directory
from core.input_validation import validate_text
from core.runtime_state import SCRAPER_STATUS, STATS, add_log, get_scraper_status
from core.security_middleware import is_public_mode
from core.workspace_context import get_active_data_dir, get_active_db_path
from modules.job_repository import save_job_batch
from modules.job_collection_tasks import (
    create_task,
    get_stop_reason,
    get_task,
    latest_task,
    public_status,
    request_cancel,
    update_task,
)
from modules.job_scraper import (
    CollectionStopped,
    JobScraper,
    extract_keywords,
    get_metro_code,
    normalize_city_name,
)
from modules.job_sources import resolve_sources
from modules.browser_use_job_collector import (
    BrowserUseCollectionError,
    collect_jobs as collect_browser_use_jobs,
)
from modules.official_job_sources import (
    OfficialSourceError,
    collect_official_jobs,
    expand_search_keywords,
    is_province_level_match,
    list_official_source_codes,
    official_location_matches_city,
    rank_and_filter_jobs_by_relevance,
)
from services.job_login import login_manager

async def start_scrape(
    platforms: str = "51job",
    resume_file: str = "",
    salary_range: str = "",
    target_position: str = "",
    target_city: str = "",
    restrictions: str = "",
    related_keywords: str = "",
):

    """启动岗位采集。resume_file: 必须指定简历文件名"""

    """

    启动岗位采集（后台运行）

    大白话：点击后自动打开浏览器抓取51前程无忧岗位，完成后保存

    """

    scraper_status = get_scraper_status(SCRAPER_STATUS)
    if scraper_status["running"]:

        return {"ok": False, "error": "岗位采集任务正在进行中", "error_code": "CONFLICT"}

    if login_manager.active():

        return {
            "ok": False,
            "error": "网站登录窗口正在等待操作，请先在会话管理中保存或取消登录，再启动采集",
            "error_code": "CONFLICT",
        }

    try:
        if not isinstance(platforms, str) or len(platforms) > 200:
            raise ValueError("招聘来源格式不正确")
        plat_list = [item.code for item in resolve_sources(platforms.split(","))]
    except ValueError as error:
        return {"ok": False, "error": str(error), "error_code": "INVALID_INPUT", "field": "platforms"}

    if is_public_mode() and any(code in {"51job", "liepin"} for code in plat_list):
        return {
            "ok": False,
            "error": "公网演示模式已禁用本机浏览器采集（51job / 猎聘），请使用 15 个纯 HTTP 官方开放源",
            "error_code": "PUBLIC_MODE_RESTRICTED",
            "field": "platforms",
        }

    salary_range, error = validate_text(
        salary_range,
        "salary_range",
        max_length=100,
    )
    if error:

        return error

    target_position, error = validate_text(
        target_position,
        "target_position",
        max_length=100,
    )
    if error:
        return error

    selected_related = []
    if related_keywords:
        try:
            decoded_related = json.loads(related_keywords)
        except (TypeError, json.JSONDecodeError):
            return {
                "ok": False,
                "error": "关联岗位格式不正确",
                "error_code": "INVALID_INPUT",
                "field": "related_keywords",
            }
        if not isinstance(decoded_related, list) or len(decoded_related) > 4:
            return {
                "ok": False,
                "error": "关联岗位必须是最多4项的列表",
                "error_code": "INVALID_INPUT",
                "field": "related_keywords",
            }
        for item in decoded_related:
            if not isinstance(item, str) or not 2 <= len(item.strip()) <= 50:
                return {
                    "ok": False,
                    "error": "关联岗位每项必须是2至50个字符的文字",
                    "error_code": "INVALID_INPUT",
                    "field": "related_keywords",
                }
            query = item.strip()
            if query != target_position and query not in selected_related:
                selected_related.append(query)

    target_city, error = validate_text(
        target_city,
        "target_city",
        max_length=30,
    )
    if error:
        return error

    if target_city:
        normalized_city = normalize_city_name(target_city)
        if not normalized_city or get_metro_code(normalized_city) == "000000":
            return {
                "ok": False,
                "error": f"当前51前程无忧采集尚未配置城市：{target_city}",
                "error_code": "INVALID_INPUT",
                "field": "target_city",
            }
        target_city = normalized_city

    restrictions, error = validate_text(
        restrictions,
        "restrictions",
        max_length=500,
    )
    if error:
        return error



    # 选择简历

    if not resume_file:

        return {"ok": False, "error": "请先选择一份简历，系统需要根据求职意向精准采集"}

    active_data_dir = get_active_data_dir(DATA_DIR)
    resolved_resume = resolve_file_in_directory(active_data_dir, resume_file, {".json"})
    if resolved_resume is None:

        return {"ok": False, "error": "简历文件名不安全"}

    _, filepath = resolved_resume

    if not os.path.exists(filepath):

        return {"ok": False, "error": f"简历文件不存在: {resume_file}"}

    with open(filepath, "r", encoding="utf-8") as f:

        profile = json.load(f)

    if not profile:

        return {"ok": False, "error": "没有已解析的简历，请先上传简历"}

    if target_position:
        profile["desired_position"] = target_position
    if target_city:
        profile["target_city"] = target_city
    if salary_range:
        profile["desired_salary"] = salary_range
    if restrictions:
        profile["job_restrictions"] = [
            item.strip()
            for item in restrictions.replace("；", "\n").replace(";", "\n").splitlines()
            if item.strip()
        ]



    keywords = extract_keywords(profile)
    for query in selected_related:
        if query not in keywords:
            keywords.append(query)
    keywords = keywords[:5]

    if not keywords:

        return {"ok": False, "error": "无法从简历中提取搜索关键词"}



    task = create_task({
        "platforms": plat_list,
        "resume_file": resume_file,
        "salary_range": salary_range,
        "target_position": target_position,
        "target_city": target_city,
        "restrictions": profile.get("job_restrictions", []),
        "keywords": keywords,
    })
    task_id = task["task_id"]

    scraper_status.update({
        "task_id": task_id,
        "status": "queued",
        "stage": "queued",
        "running": True,
        "progress": "等待后台开始采集",
        "progress_percent": 0,
        "jobs_count": 0,
        "last_run": task["updated_at"],
    })

    add_log(f"开始岗位采集，关键词: {keywords}", "info")

    add_log(f"使用简历: {profile.get('name', '未知')}", "info")



    # 后台运行采集任务（显式复制 ContextVar 确保写入当前访客的独立工作区）

    loop = asyncio.get_event_loop()

    add_log(f"目标平台: {plat_list}", "info")

    ctx = contextvars.copy_context()
    loop.run_in_executor(None, ctx.run, _run_scrape_sync, profile, keywords, plat_list, salary_range, task_id)

    

    return {
        "ok": True,
        "message": "采集任务已启动",
        "task_id": task_id,
        "keywords": keywords,
    }







AUTO_SCORE_MAX_JOBS = 8
AUTO_SCORE_CONCURRENCY = 4


def _auto_batch_score(
    profile,
    jobs_filepath,
    jobs_data,
    data_dir=None,
    db_path=None,
    write_legacy_json=WRITE_LEGACY_JOB_JSON,
    stop_check=None,
    max_jobs=AUTO_SCORE_MAX_JOBS,
    resume_file="",
):
    from concurrent.futures import ThreadPoolExecutor
    from modules.jd_matcher import match_resume_to_jd

    data_dir = data_dir or get_active_data_dir(DATA_DIR)
    jobs_list = jobs_data.get("jobs", [])
    if not jobs_list:
        return

    total = len(jobs_list)
    score_limit = min(total, max(1, int(max_jobs or AUTO_SCORE_MAX_JOBS)))
    head_jobs = list(jobs_list[:score_limit])
    tail_jobs = list(jobs_list[score_limit:])
    add_log(
        f"开始自动JD匹配：总计 {total} 个岗位，优先并发评估前 {score_limit} 个（其余岗位完整保留）",
        "info",
    )

    def _score_one(job: dict) -> dict:
        if callable(stop_check):
            stop_check()
        jd_parts = [job.get("title", ""), job.get("company", "")]
        if job.get("tags"):
            jd_parts.extend(str(t) for t in job.get("tags", [])[:5] if t)
        desc = str(job.get("description") or "").strip()
        if desc:
            jd_parts.append(desc[:400])
        jd_text = " ".join([p for p in jd_parts if p]).strip()

        if len(jd_text) < 5:
            job["match_score"] = 50
            job["match_brief"] = "信息不足"
            job["skill_match"] = 50
            job["experience_match"] = 50
            job["education_match"] = 50
            return job

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
                job["match_brief"] = result.get("error", "匹配失败")
                job["skill_match"] = 50
                job["experience_match"] = 50
                job["education_match"] = 50
        except Exception as e:
            job["match_score"] = 50
            job["match_brief"] = f"{str(e)[:50]}"
            job["skill_match"] = 50
            job["experience_match"] = 50
            job["education_match"] = 50
        return job

    workers = min(AUTO_SCORE_CONCURRENCY, len(head_jobs))
    if workers <= 1:
        scored_head = [_score_one(j) for j in head_jobs]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            scored_head = list(pool.map(_score_one, head_jobs))

    scored_head.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    scored_jobs = scored_head + tail_jobs

    jobs_data["jobs"] = scored_jobs
    jobs_data["resume_name"] = profile.get("name", "")
    if resume_file:
        jobs_data["scored_resume_file"] = resume_file
    jobs_data["auto_scored"] = True
    jobs_data["scored_count"] = len(scored_head)
    jobs_data["scored_at"] = datetime.now().isoformat()



    save_job_batch(os.path.basename(jobs_filepath), jobs_data, db_path)

    if write_legacy_json:

        with open(jobs_filepath, "w", encoding="utf-8") as f:

            json.dump(jobs_data, f, ensure_ascii=False, indent=2)



    high = sum(1 for j in scored_jobs if j.get("match_score", 0) >= 70)

    add_log(f"????: {high}/{len(scored_jobs)} ? >= 70?", "success")



    if write_legacy_json:

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







def _set_scrape_task(task_id, stage, message, percent, jobs_count=None, **changes):
    status = changes.pop("status", "running")
    scraper_status = get_scraper_status(SCRAPER_STATUS)
    memory_changes = {
        "task_id": task_id,
        "status": status,
        "stage": stage,
        "running": status in {"queued", "running"},
        "progress": message,
        "progress_percent": percent,
    }
    if jobs_count is not None:
        memory_changes["jobs_count"] = jobs_count
    scraper_status.update(memory_changes)
    if task_id:
        update_task(
            task_id,
            status=status,
            stage=stage,
            progress_message=message,
            progress_percent=percent,
            jobs_count=scraper_status.get("jobs_count", 0),
            **changes,
        )


def _run_scrape_sync(profile, keywords, platforms, salary_range="", task_id=""):

    """后台执行岗位采集（异步）"""

    platform_codes = [source.code for source in resolve_sources(platforms)]
    scraper = JobScraper(headless=False)

    scraper.set_profile(profile)
    scraper.keywords = list(keywords)
    scraper.primary_keyword = scraper.keywords[0] if scraper.keywords else ""
    active_db_path = get_active_db_path()
    scraper.stop_check = (lambda: get_stop_reason(task_id, active_db_path)) if task_id else None

    if salary_range:

        # 前端传入的薪资，使用 infer_salary_range 做±3k扩展

        from modules.job_scraper import infer_salary_range

        scraper.salary_range = infer_salary_range({"desired_salary": salary_range})

        add_log(f"自定义薪资: {salary_range} -> 过滤范围 {scraper.salary_range}", "info")

    # 注意: 如果前端没传薪资，不预设置 scaper.salary_range

    # search_all() 会自动从 profile.desired_salary 调用 infer_salary_range

    try:

        official_codes = [c for c in platform_codes if c in list_official_source_codes()]
        needs_browser = any(c in ("51job", "liepin") for c in platform_codes)
        _set_scrape_task(
            task_id,
            "opening_browser" if needs_browser else "collecting",
            "正在准备岗位采集浏览器" if needs_browser else "正在连接权威官方开放招聘源",
            10,
        )

        add_log(f">>> 收到采集请求 - 平台: {platforms}, 地点: {scraper.location}, 关键词: {keywords}", "info")
        jobs = []
        official_errors = []
        raw_source_counts: dict[str, int] = {}
        final_source_stats: dict[str, int] = {}
        per_source_limit = 30
        expanded_official_keywords = expand_search_keywords(list(keywords), max_queries=3)
        if len(expanded_official_keywords) > len(list(keywords)):
            add_log(f"智能同义扩词已启用: {list(keywords)} -> {expanded_official_keywords}", "info")
        if len(official_codes) > 1:
            _set_scrape_task(
                task_id,
                "collecting",
                f"正在并发直连 {len(official_codes)} 个权威官方招聘源（单源上限 {per_source_limit} 岗）",
                25,
                0,
            )
            with ThreadPoolExecutor(max_workers=min(6, len(official_codes))) as pool:
                future_map = {
                    pool.submit(
                        contextvars.copy_context().run,
                        collect_official_jobs,
                        code,
                        expanded_official_keywords,
                        scraper.location,
                        max_pages=3,
                        max_jobs=per_source_limit,
                        stop_check=scraper.stop_check,
                    ): code
                    for code in official_codes
                }
                completed_sources = 0
                for fut in as_completed(future_map):
                    code = future_map[fut]
                    completed_sources += 1
                    try:
                        batch_items = fut.result() or []
                        raw_source_counts[code] = len(batch_items)
                        jobs.extend(batch_items)
                    except OfficialSourceError as official_exc:
                        if official_exc.code in ("cancelled", "timed_out"):
                            raise CollectionStopped(official_exc.code, official_exc.message) from official_exc
                        official_errors.append(official_exc.message)
                        raw_source_counts[code] = 0
                        add_log(f"官方开放源[{code}]采集异常: {official_exc.message}", "warning")
                    except Exception as exc_other:
                        official_errors.append(f"{code}: {exc_other}")
                        raw_source_counts[code] = 0
                        add_log(f"官方开放源[{code}]采集异常: {exc_other}", "warning")
                    pct = 25 + int((completed_sources / len(official_codes)) * 35)
                    _set_scrape_task(
                        task_id,
                        "collecting",
                        f"已完成 {completed_sources}/{len(official_codes)} 个官方源直采",
                        pct,
                        len(jobs),
                    )
        else:
            for official_code in official_codes:
                try:
                    batch_items = collect_official_jobs(
                        official_code,
                        expanded_official_keywords,
                        scraper.location,
                        max_pages=3,
                        max_jobs=per_source_limit,
                        stop_check=scraper.stop_check,
                        progress_callback=lambda stage, message, percent: _set_scrape_task(
                            task_id, stage, message, percent, len(jobs)
                        ),
                    )
                    raw_source_counts[official_code] = len(batch_items)
                    jobs.extend(batch_items)
                except OfficialSourceError as official_exc:
                    if official_exc.code in ("cancelled", "timed_out"):
                        raise CollectionStopped(official_exc.code, official_exc.message) from official_exc
                    official_errors.append(official_exc.message)
                    raw_source_counts[official_code] = 0
                    add_log(f"官方开放源[{official_code}]采集异常: {official_exc.message}", "warning")
        if "51job" in platform_codes:
            _set_scrape_task(task_id, "collecting", "正在多页搜索51前程无忧（最多30岗）", 25)
            try:
                scraper._launch_browser()
                items_51 = scraper.search_all(platforms=["51job"], pages=3)
                raw_source_counts["51job"] = len(items_51)
                jobs.extend(items_51)
            except CollectionStopped:
                raise
            except Exception as err_51:
                if len(platform_codes) == 1:
                    raise
                official_errors.append(f"51job: {err_51}")
                raw_source_counts["51job"] = 0
                add_log(f"51job 采集异常（已保留其它渠道结果）: {err_51}", "warning")
        if "liepin" in platform_codes:
            _set_scrape_task(task_id, "collecting", "正在多页搜索猎聘（最多30岗）", 45, len(jobs))
            try:
                items_lp = collect_browser_use_jobs(
                    "liepin",
                    list(keywords),
                    scraper.location,
                    max_jobs=30,
                    stop_check=scraper.stop_check,
                    progress_callback=lambda stage, message, percent: _set_scrape_task(
                        task_id, stage, message, percent, len(jobs)
                    ),
                )
                raw_source_counts["liepin"] = len(items_lp)
                jobs.extend(items_lp)
            except Exception as err_lp:
                err_code = getattr(err_lp, "code", "")
                if err_code in {"USER_CANCELLED", "COLLECTION_TIMEOUT"} or len(platform_codes) == 1:
                    raise
                official_errors.append(f"猎聘: {str(err_lp)}")
                raw_source_counts["liepin"] = 0
                add_log(f"猎聘采集异常（已保留其它渠道结果）: {str(err_lp)}", "warning")
        if not jobs and official_errors:
            raise RuntimeError("；".join(official_errors))
        jobs = scraper._deduplicate_and_rank(jobs)

        

        _set_scrape_task(task_id, "filtering", "正在核对岗位城市与重复项", 65, len(jobs))

        

        if jobs:

            # 严格城市过滤：只保留匹配目标城市的岗位

            target_city = scraper.location

            if target_city:

                before = len(jobs)

                official_set = set(list_official_source_codes())
                jobs = [
                    j for j in jobs
                    if scraper._city_matches(j.get("location", ""))
                    or (j.get("source") == "sasac" and str(j.get("location", "")).strip() == "全国")
                    or (
                        j.get("source") in official_set
                        and official_location_matches_city(j.get("location", ""), target_city)
                    )
                    or is_province_level_match(j.get("location", ""), target_city)
                ]
                if before and not jobs:
                    raise RuntimeError("城市筛选未生效，已停止保存岗位，请检查目标城市")

                add_log(f"城市过滤: {before} -> {len(jobs)} 个岗位 (仅保留{target_city})", "info")

            before_rel = len(jobs)
            jobs = rank_and_filter_jobs_by_relevance(jobs, list(keywords))
            if before_rel != len(jobs):
                add_log(f"相关性筛选与排序: {before_rel} -> {len(jobs)} 个高相关岗位", "info")

            if scraper.salary_range and jobs:
                before_sal = len(jobs)
                negotiable_jobs = []
                priced_jobs = []
                for item in jobs:
                    sal_text = str(item.get("salary") or "").strip()
                    if not sal_text or "面议" in sal_text or not any(ch.isdigit() for ch in sal_text):
                        negotiable_jobs.append(item)
                    else:
                        priced_jobs.append(item)
                matched_priced = [
                    item for item in priced_jobs
                    if scraper._match_salary_exact(item.get("salary", ""))
                ]
                if not matched_priced and priced_jobs:
                    matched_priced = [
                        item for item in priced_jobs
                        if scraper._match_salary_widen(item.get("salary", ""), widen=2)
                    ]
                filtered_by_sal = matched_priced + negotiable_jobs
                if filtered_by_sal:
                    # 保持原有的相关性排序顺序
                    kept_ids = {id(item) for item in filtered_by_sal}
                    jobs = [item for item in jobs if id(item) in kept_ids]
                    if len(jobs) != before_sal:
                        add_log(
                            f"薪资区间过滤 [{scraper.salary_range}]: {before_sal} -> {len(jobs)} 个岗位（过滤掉超出范围的明码薪资岗，保留面议岗）",
                            "info",
                        )

            for j in jobs:
                src_key = str(j.get("source") or "unknown").strip() or "unknown"
                final_source_stats[src_key] = final_source_stats.get(src_key, 0) + 1

            scraper.jobs = jobs  # 用过滤后的结果覆盖

            scraper._check_stop()
            filepath, jobs_data = scraper.save_jobs(include_payload=True)
            jobs_data["source_stats"] = dict(final_source_stats)
            jobs_data["source_raw_counts"] = dict(raw_source_counts)
            jobs_data["target_city"] = target_city or ""
            jobs_data["salary_range"] = salary_range or ""
            jobs_data["restrictions"] = list(profile.get("job_restrictions") or [])
            save_job_batch(os.path.basename(filepath), jobs_data)
            if WRITE_LEGACY_JOB_JSON:
                with open(filepath, "w", encoding="utf-8") as fh:
                    json.dump(jobs_data, fh, ensure_ascii=False, indent=2)

            summary_parts = ", ".join(f"{k}={v}" for k, v in sorted(final_source_stats.items(), key=lambda kv: -kv[1]))
            add_log(f"采集完成: {len(jobs)} 个岗位（各渠道分布: {summary_parts}）", "success")

            STATS["jobs_found"] += len(jobs)

            # 自动运行批量JD匹配

            try:

                _set_scrape_task(task_id, "matching", "正在自动JD匹配...", 85, len(jobs))

                add_log("开始自动JD匹配评分", "info")

                _auto_batch_score(
                    profile,
                    filepath,
                    jobs_data,
                    stop_check=scraper._check_stop,
                )

                add_log("自动JD匹配完成", "success")

            except Exception as e2:

                add_log(f"自动匹配失败: {e2}", "warning")

        else:

            _set_scrape_task(
                task_id,
                "completed",
                "未找到岗位",
                100,
                0,
                status="completed",
                result_data={"jobs_count": 0},
            )

            add_log("未采集到岗位", "warning")

    except BrowserUseCollectionError as error:
        scraper_status = get_scraper_status(SCRAPER_STATUS)
        if error.code in {"USER_CANCELLED", "COLLECTION_TIMEOUT"}:
            final_status = "timed_out" if error.code == "COLLECTION_TIMEOUT" else "cancelled"
            final_message = "岗位采集已超过时限并安全停止" if final_status == "timed_out" else "岗位采集已由用户取消"
        else:
            final_status = "failed"
            final_message = str(error)
        _set_scrape_task(
            task_id,
            final_status,
            final_message,
            scraper_status.get("progress_percent", 0),
            status=final_status,
            error_code=error.code,
            error_message=str(error),
        )
        add_log(f"智能浏览器采集停止 [{error.code}]: {error}", "warning")

    except CollectionStopped as stopped:
        scraper_status = get_scraper_status(SCRAPER_STATUS)
        timed_out = stopped.reason == "timed_out"
        final_status = "timed_out" if timed_out else "cancelled"
        final_message = "岗位采集已超过10分钟并安全停止" if timed_out else "岗位采集已由用户取消"
        _set_scrape_task(
            task_id,
            final_status,
            final_message,
            scraper_status.get("progress_percent", 0),
            status=final_status,
            error_code="COLLECTION_TIMEOUT" if timed_out else "USER_CANCELLED",
            error_message=str(stopped),
        )
        add_log(final_message, "warning")

    except Exception as e:
        scraper_status = get_scraper_status(SCRAPER_STATUS)
        error_message = str(e)[:200]
        _set_scrape_task(
            task_id,
            "failed",
            f"出错: {error_message[:60]}",
            scraper_status.get("progress_percent", 0),
            status="failed",
            error_code="COLLECTION_FAILED",
            error_message=error_message,
        )

        add_log(f"采集失败: {e}", "error")

    finally:
        scraper_status = get_scraper_status(SCRAPER_STATUS)
        try:
            scraper.close()
        except Exception as close_error:
            add_log(f"采集浏览器关闭失败: {close_error}", "warning")

        if scraper_status.get("status") == "running":
            final_count = scraper_status.get("jobs_count", 0)
            _set_scrape_task(
                task_id,
                "completed",
                f"完成，共 {final_count} 个岗位",
                100,
                final_count,
                status="completed",
                result_data={
                    "jobs_count": final_count,
                    "source_stats": dict(locals().get("final_source_stats") or {}),
                },
            )
        scraper_status["running"] = False
        scraper_status["last_run"] = datetime.now().isoformat()





async def get_scrape_status(task_id=""):

    """查询采集任务状态"""

    scraper_status = get_scraper_status(SCRAPER_STATUS)
    if task_id:
        task = get_task(task_id)
        if task is None:
            return {
                "ok": False,
                "error": "岗位采集任务不存在",
                "error_code": "NOT_FOUND",
                "field": "task_id",
            }
        return public_status(task)
    current_task_id = scraper_status.get("task_id")
    task = get_task(current_task_id) if current_task_id else latest_task()
    return public_status(task) if task else dict(scraper_status)


async def cancel_scrape(task_id, confirmed=False):
    if confirmed is not True:
        return {
            "ok": False,
            "error": "取消岗位采集前需要明确确认",
            "error_code": "INVALID_INPUT",
            "field": "confirmed",
        }
    task = request_cancel(task_id)
    if task is None:
        return {
            "ok": False,
            "error": "岗位采集任务不存在",
            "error_code": "NOT_FOUND",
            "field": "task_id",
        }
    if task["status"] not in {"queued", "running", "cancelling"}:
        return {
            "ok": False,
            "error": "岗位采集任务已经结束，不能重复取消",
            "error_code": "CONFLICT",
            "field": "task_id",
        }
    return {"ok": True, **public_status(task)}





# ============================================================

# JD 匹配度评分 API（步骤6）


def parse_wechat_recruitment_post(
    text: str,
    article_url: str = "",
    resume_file: str = "",
) -> dict:
    """将用户粘贴的微信公众号官方招聘推文/公告，通过 AI 拆解为结构化岗位批次并入库。"""
    cleaned_text = (text or "").strip()
    if len(cleaned_text) < 20:
        return {"ok": False, "error": "请粘贴至少 20 字以上的微信公众号招聘正文或公告内容", "error_code": "INVALID_INPUT"}

    safe_url = (article_url or "").strip()
    if safe_url and not safe_url.startswith(("http://", "https://")):
        safe_url = ""
    final_url = safe_url or "https://mp.weixin.qq.com/"

    from modules.deepseek_client import DeepSeekClient
    from modules.job_repository import save_job_batch

    system_prompt = (
        "你是专业的招聘公告结构化提取助手。请从用户粘贴的微信公众号官方招聘文章中提取所有招聘岗位，"
        "严格忠于原文，不得编造原文未提及的薪资或公司名。只返回合法 JSON 对象："
        '{"company": "招聘单位名称", "jobs": [{"title": "岗位名称", "company": "招聘单位", '
        '"location": "工作城市(未知填全国)", "salary": "薪资范围(未标明填面议)", '
        '"description": "岗位职责与任职要求摘要", "tags": ["标签1", "标签2"]}]}'
    )
    client = DeepSeekClient()
    parsed = client.chat_json(system_prompt, cleaned_text[:8000])
    if not isinstance(parsed, dict) or parsed.get("error"):
        return {
            "ok": False,
            "error": f"AI 解析微信推文失败：{parsed.get('error', '返回格式异常') if isinstance(parsed, dict) else '未知错误'}",
            "error_code": "UPSTREAM_ERROR",
        }

    raw_jobs = parsed.get("jobs") or []
    default_company = str(parsed.get("company") or "微信公众号官方发布").strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch_id = f"jobs_wechat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    structured_jobs = []
    for idx, item in enumerate(raw_jobs[:15]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        comp = str(item.get("company") or default_company).strip() or default_company
        loc = str(item.get("location") or "全国").strip() or "全国"
        sal = str(item.get("salary") or "面议").strip() or "面议"
        desc = str(item.get("description") or cleaned_text[:400]).strip()
        tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()][:5]
        if "微信公众号" not in tags:
            tags.insert(0, "微信公众号")
        structured_jobs.append(
            {
                "job_id": f"wechat_{datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}",
                "platform": "wechat",
                "source": "wechat",
                "title": title,
                "company": comp,
                "location": loc,
                "salary": sal,
                "description": desc,
                "url": final_url,
                "tags": tags,
                "relation_type": "primary",
                "keyword_tier": "primary",
                "scraped_at": now_str,
            }
        )

    if not structured_jobs:
        return {"ok": False, "error": "未能从该推文中识别出具体岗位名称，请粘贴包含岗位列表的正文", "error_code": "INVALID_INPUT"}

    payload = {
        "scraped_at": now_str,
        "count": len(structured_jobs),
        "keywords": [f"微信推文:{default_company}"],
        "platforms": ["wechat"],
        "jobs": structured_jobs,
    }
    save_job_batch(batch_id, payload)
    active_data_dir = get_active_data_dir(DATA_DIR)
    filepath = os.path.join(active_data_dir, batch_id)
    if WRITE_LEGACY_JOB_JSON:
        os.makedirs(active_data_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    if resume_file:
        resolved = resolve_file_in_directory(active_data_dir, resume_file, {".json"})
        if resolved and os.path.exists(resolved[1]):
            try:
                with open(resolved[1], "r", encoding="utf-8") as fh:
                    profile = json.load(fh)
                _auto_batch_score(profile, filepath, payload)
            except Exception:
                pass

    add_log(f"微信公众号推文拆解入库成功: {len(structured_jobs)} 个岗位 ({batch_id})", "success")
    return {
        "ok": True,
        "jobs_file": batch_id,
        "count": len(structured_jobs),
        "jobs": payload["jobs"],
        "message": f"已从微信公众号推文拆解出 {len(structured_jobs)} 个岗位并存入岗位库",
    }

"""简历文件、模板、照片和导出业务。"""

import html
import json
import inspect
import io
import os
import uuid
import warnings
from urllib.parse import quote

from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image, UnidentifiedImageError

from config import DATA_DIR
from core.workspace_context import get_active_data_dir, get_active_photos_dir
from core.file_security import resolve_file_in_directory
from core.input_validation import validation_error, validate_choice, validate_text
from core.runtime_state import add_log
from modules.db_client import get_connection, init_db
from modules.resume_optimization_guard import (
    build_optimization_version,
    merge_grounded_optimization,
    normalize_capability_decisions,
    optimization_source,
    original_profile_snapshot,
)
from modules.resume_schema import _build_quality_warnings
from modules.resume_version_repository import (
    save_optimized_version,
    save_original_version,
)


MAX_PHOTO_SIZE = 5 * 1024 * 1024
MAX_PHOTO_PIXELS = 20_000_000
PHOTO_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
}


def overwrite_resume(

    resume_file: str = "",

    optimized_summary: str = "",

    optimized_projects: str = "[]",

    optimized_internships: str = "[]",

    enhanced_skills: str = "[]",

    target: str = "",

    optimized_resume: str = "{}",

    db_path: str = None,

):

    """用AI优化结果覆盖简历文件，同时更新求职意向"""

    if not resume_file:

        return {"ok": False, "error": "缺少简历文件名"}

    normalized_values = {}
    for field, value, maximum in (
        ("optimized_summary", optimized_summary, 10000),
        ("optimized_projects", optimized_projects, 100000),
        ("optimized_internships", optimized_internships, 100000),
        ("enhanced_skills", enhanced_skills, 50000),
        ("target", target, 100),
        ("optimized_resume", optimized_resume, 400000),
    ):
        normalized, error = validate_text(value, field, max_length=maximum)
        if error:
            return error
        normalized_values[field] = normalized

    optimized_summary = normalized_values["optimized_summary"]
    optimized_projects = normalized_values["optimized_projects"]
    optimized_internships = normalized_values["optimized_internships"]
    enhanced_skills = normalized_values["enhanced_skills"]
    target = normalized_values["target"]
    optimized_resume = normalized_values["optimized_resume"]

    active_data_dir = get_active_data_dir(DATA_DIR)
    resolved_resume = resolve_file_in_directory(active_data_dir, resume_file, {".json"})
    if resolved_resume is None:

        return {"ok": False, "error": "文件名不安全"}

    _, filepath = resolved_resume

    stored_profile = None
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            stored_profile = json.load(f)
    else:
        try:
            init_db(db_path)
            conn_check = get_connection(db_path)
            row = conn_check.execute(
                "SELECT parsed_data FROM resumes WHERE filename = ?", (resume_file,)
            ).fetchone()
            conn_check.close()
            if row and row["parsed_data"]:
                stored_profile = json.loads(row["parsed_data"])
        except Exception:
            stored_profile = None

    if not isinstance(stored_profile, dict):

        return {"ok": False, "error": "简历文件不存在"}

    

    try:

        # Read current resume

        original_content = json.dumps(stored_profile, ensure_ascii=False, indent=2)
        source_profile, has_original_snapshot = optimization_source(stored_profile)

        

        candidate_data = {}
        candidate_meta = {}
        if optimized_resume and optimized_resume != "{}":
            parsed_candidate = json.loads(optimized_resume)
            if not isinstance(parsed_candidate, dict):
                return {"ok": False, "error": "优化结果必须是结构化对象"}
            candidate_meta = parsed_candidate.get("_optimization_meta", {})
            if not isinstance(candidate_meta, dict):
                candidate_meta = {}
            candidate_data = {
                "optimized_summary": parsed_candidate.get("summary", ""),
                "optimized_work_experience": parsed_candidate.get("work_experience", []),
                "optimized_project_experience": parsed_candidate.get("project_experience", []),
                "optimized_practical_experience": parsed_candidate.get("practical_experience", []),
                "optimized_campus_experience": parsed_candidate.get("campus_experience", []),
                "optimized_research_experience": parsed_candidate.get("research_experience", []),
                "enhanced_skills": parsed_candidate.get("skills", []),
            }
        else:
            candidate_data = {
                "optimized_summary": optimized_summary,
                "optimized_projects": json.loads(optimized_projects or "[]"),
                "optimized_internships": json.loads(optimized_internships or "[]"),
                "enhanced_skills": json.loads(enhanced_skills or "[]"),
            }

        profile, optimization_warnings = merge_grounded_optimization(
            source_profile,
            candidate_data,
            target or source_profile.get("desired_position", ""),
            require_evidence=False,
        )
        if not has_original_snapshot:
            optimization_warnings.insert(
                0,
                {
                    "code": "SOURCE_SNAPSHOT_CREATED_FROM_LEGACY",
                    "field": "original_profile",
                    "message": "旧简历没有原始快照，已从覆盖前版本建立底稿；如旧版本曾被AI改写，请重新上传原文件核对。",
                },
            )

        

        # Update parse timestamp

        from datetime import datetime as _dt

        profile["parsed_at"] = _dt.now().strftime("%Y-%m-%d %H:%M:%S")

        profile["optimized"] = True

        if target:

            profile["desired_position"] = target

        capability_analysis = candidate_meta.get("capability_analysis", {})
        if not isinstance(capability_analysis, dict):
            capability_analysis = {}
        capability_analysis, decision_error = normalize_capability_decisions(
            capability_analysis
        )
        if decision_error:
            return {
                "ok": False,
                "error": decision_error,
                "error_code": "CONFIRMATION_REQUIRED",
                "field": "capability_analysis.gaps",
            }
        version = build_optimization_version(
            profile,
            target or profile.get("desired_position", ""),
            str(candidate_meta.get("job_description", "")),
            capability_analysis,
        )
        if candidate_meta.get("version_id"):
            version["version_id"] = str(candidate_meta["version_id"])
        if candidate_meta.get("created_at"):
            version["created_at"] = str(candidate_meta["created_at"])

        history = stored_profile.get("optimization_history", [])
        if not isinstance(history, list):
            history = []
        history = [item for item in history if isinstance(item, dict)][-4:]
        history.append(version)
        profile["original_profile"] = original_profile_snapshot(source_profile)
        profile["optimization_history"] = history
        profile["active_optimization"] = {
            key: value for key, value in version.items() if key != "profile"
        }

        tracked_fields = (
            "summary",
            "desired_position",
            "skills",
            "work_experience",
            "project_experience",
            "practical_experience",
            "campus_experience",
            "research_experience",
        )
        list_tracked_fields = {
            "skills",
            "work_experience",
            "project_experience",
            "practical_experience",
            "campus_experience",
            "research_experience",
        }
        changed_fields = [
            field_name
            for field_name in tracked_fields
            if (
                (stored_profile.get(field_name) or []) != (profile.get(field_name) or [])
                if field_name in list_tracked_fields
                else (stored_profile.get(field_name) or "") != (profile.get(field_name) or "")
            )
        ]

        

        serialized_profile = json.dumps(profile, ensure_ascii=False, indent=2)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        temp_path = f"{filepath}.{uuid.uuid4().hex}.tmp"
        connection = None
        file_replaced = False
        try:
            with open(temp_path, "w", encoding="utf-8") as output_file:
                output_file.write(serialized_profile)

            init_db(db_path)
            connection = get_connection(db_path)
            connection.execute("BEGIN")
            connection.execute(
                """
                INSERT INTO resumes (filename, name, phone, email, parsed_data)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    name = excluded.name,
                    phone = excluded.phone,
                    email = excluded.email,
                    parsed_data = excluded.parsed_data
                """,
                (
                    resume_file,
                    profile.get("name", ""),
                    profile.get("phone", ""),
                    profile.get("email", ""),
                    serialized_profile,
                ),
            )
            save_original_version(
                resume_file,
                source_profile,
                created_at=str(source_profile.get("parsed_at", "")),
                is_current=False,
                connection=connection,
            )
            saved_version = save_optimized_version(
                resume_file,
                version,
                connection=connection,
            )
            os.replace(temp_path, filepath)
            file_replaced = True
            connection.commit()
        except Exception:
            if connection is not None:
                connection.rollback()
            if file_replaced:
                restore_path = f"{filepath}.{uuid.uuid4().hex}.restore"
                with open(restore_path, "w", encoding="utf-8") as restore_file:
                    restore_file.write(original_content)
                os.replace(restore_path, filepath)
            elif os.path.exists(temp_path):
                os.remove(temp_path)
            raise
        finally:
            if connection is not None:
                connection.close()

        add_log(
            f"已保存简历优化版本: {profile.get('name', '')}（变更字段: {', '.join(changed_fields) if changed_fields else '无正文变化'}）",
            "success",
        )

        return {
            "ok": True,
            "message": "优化版本已保存" if changed_fields else "已保存版本记录，但正文内容未发生变化",
            "changed_fields": changed_fields,
            "optimization_warnings": optimization_warnings,
            "profile_summary": {
                "name": profile.get("name", ""),
                "desired_position": profile.get("desired_position", ""),
                "summary": profile.get("summary", ""),
                "skills": profile.get("skills", []),
                "parsed_at": profile.get("parsed_at", ""),
            },
            "version": {
                key: value for key, value in saved_version.items() if key != "content"
            },
        }

    except Exception as e:

        return {"ok": False, "error": f"覆盖失败: {str(e)}"}


_MANUAL_SCALAR_LIMITS = {
    "name": (1, 80),
    "desired_position": (0, 120),
    "desired_salary": (0, 80),
    "phone": (0, 60),
    "email": (0, 120),
    "summary": (0, 6000),
}

_MANUAL_LIST_SCHEMAS = {
    "education": ("school", "major", "degree", "year"),
    "work_experience": ("company", "position", "duration", "description"),
    "project_experience": ("name", "role", "duration", "description"),
    "practical_experience": ("organization", "role", "duration", "description"),
    "campus_experience": ("organization", "role", "duration", "description"),
    "research_experience": ("name", "role", "duration", "description"),
}


def update_resume_manual(
    resume_file: str,
    updates: dict,
    db_path: str | None = None,
) -> dict:
    """用户人工微调简历并原子写回 SQLite、版本历史表与兼容 JSON。"""
    if not resume_file:
        return {"ok": False, "error": "缺少简历文件名", "error_code": "INVALID_INPUT", "field": "filename"}
    if not isinstance(updates, dict):
        return {"ok": False, "error": "修改内容必须是结构化对象", "error_code": "INVALID_INPUT"}

    active_data_dir = get_active_data_dir(DATA_DIR)
    resolved_resume = resolve_file_in_directory(active_data_dir, resume_file, {".json"})
    if resolved_resume is None:
        return {"ok": False, "error": "文件名不安全", "error_code": "INVALID_INPUT", "field": "filename"}
    safe_name, filepath = resolved_resume

    stored_profile = None
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as handle:
            stored_profile = json.load(handle)
    else:
        try:
            init_db(db_path)
            conn_check = get_connection(db_path)
            row = conn_check.execute(
                "SELECT parsed_data FROM resumes WHERE filename = ?", (safe_name,)
            ).fetchone()
            conn_check.close()
            if row and row["parsed_data"]:
                stored_profile = json.loads(row["parsed_data"])
        except Exception:
            stored_profile = None

    if not isinstance(stored_profile, dict):
        return {"ok": False, "error": "简历文件不存在", "error_code": "NOT_FOUND"}

    original_content = json.dumps(stored_profile, ensure_ascii=False, indent=2)
    source_profile, _ = optimization_source(stored_profile)
    profile = json.loads(json.dumps(stored_profile, ensure_ascii=False))
    changed_fields = []

    for field_name, (min_len, max_len) in _MANUAL_SCALAR_LIMITS.items():
        if field_name not in updates or updates[field_name] is None:
            continue
        raw_val = updates[field_name]
        if not isinstance(raw_val, str):
            return {"ok": False, "error": f"{field_name} 必须是文本", "error_code": "INVALID_INPUT", "field": field_name}
        clean_val = raw_val.strip()
        if len(clean_val) < min_len:
            return {"ok": False, "error": f"{field_name} 不能为空", "error_code": "INVALID_INPUT", "field": field_name}
        if len(clean_val) > max_len:
            return {"ok": False, "error": f"{field_name} 最多 {max_len} 个字符", "error_code": "INVALID_INPUT", "field": field_name}
        if (profile.get(field_name) or "") != clean_val:
            profile[field_name] = clean_val
            changed_fields.append(field_name)

    if "skills" in updates and updates["skills"] is not None:
        raw_skills = updates["skills"]
        if not isinstance(raw_skills, list):
            return {"ok": False, "error": "skills 必须是数组", "error_code": "INVALID_INPUT", "field": "skills"}
        clean_skills = []
        seen_skills = set()
        for item in raw_skills[:80]:
            if not isinstance(item, str):
                continue
            token = item.strip()
            if not token:
                continue
            if len(token) > 80:
                return {"ok": False, "error": "单个技能标签最多 80 个字符", "error_code": "INVALID_INPUT", "field": "skills"}
            if token not in seen_skills:
                seen_skills.add(token)
                clean_skills.append(token)
        if (profile.get("skills") or []) != clean_skills:
            profile["skills"] = clean_skills
            changed_fields.append("skills")

    for section_key, allowed_cols in _MANUAL_LIST_SCHEMAS.items():
        if section_key not in updates or updates[section_key] is None:
            continue
        raw_items = updates[section_key]
        if not isinstance(raw_items, list):
            return {"ok": False, "error": f"{section_key} 必须是列表", "error_code": "INVALID_INPUT", "field": section_key}
        if len(raw_items) > 30:
            return {"ok": False, "error": f"{section_key} 最多支持 30 条记录", "error_code": "INVALID_INPUT", "field": section_key}
        existing_items = profile.get(section_key) if isinstance(profile.get(section_key), list) else []
        cleaned_items = []
        for idx, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                return {"ok": False, "error": f"{section_key} 第 {idx + 1} 项格式无效", "error_code": "INVALID_INPUT", "field": section_key}
            base_item = dict(existing_items[idx]) if idx < len(existing_items) and isinstance(existing_items[idx], dict) else {}
            for col in allowed_cols:
                if col in raw_item and raw_item[col] is not None:
                    val_str = str(raw_item[col]).strip()
                    max_col_len = 4000 if col == "description" else 200
                    if len(val_str) > max_col_len:
                        return {"ok": False, "error": f"{section_key}.{col} 长度超出限制", "error_code": "INVALID_INPUT", "field": section_key}
                    base_item[col] = val_str
            if any(str(base_item.get(col) or "").strip() for col in allowed_cols):
                cleaned_items.append(base_item)
        if (profile.get(section_key) or []) != cleaned_items:
            profile[section_key] = cleaned_items
            changed_fields.append(section_key)

    from datetime import datetime as _dt

    now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    profile["parsed_at"] = now_str
    profile["original_profile"] = original_profile_snapshot(source_profile)

    # 根据人工微调后的最新字段实时刷新质量检查警告（补齐字段后自动消除对应旧提示）
    _missing_codes = {"MISSING_NAME", "MISSING_CONTACT", "MISSING_DESIRED_POSITION", "MISSING_SKILLS"}
    preserved_warnings = [
        item
        for item in (profile.get("quality_warnings") or [])
        if isinstance(item, dict) and item.get("code") not in _missing_codes
    ]
    refreshed_warnings = _build_quality_warnings(profile, preserved_warnings)
    profile["quality_warnings"] = refreshed_warnings
    profile["quality_status"] = "needs_review" if refreshed_warnings else "complete"

    version = build_optimization_version(
        profile,
        (profile.get("desired_position") or "人工微调") + "（人工微调）",
        "",
        {},
    )
    version["version_id"] = f"manual-{uuid.uuid4().hex[:10]}"
    version["created_at"] = now_str

    history = stored_profile.get("optimization_history", [])
    if not isinstance(history, list):
        history = []
    history = [item for item in history if isinstance(item, dict)][-4:]
    history.append(version)
    profile["optimization_history"] = history
    profile["active_optimization"] = {
        key: value for key, value in version.items() if key != "profile"
    }

    serialized_profile = json.dumps(profile, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    temp_path = f"{filepath}.{uuid.uuid4().hex}.tmp"
    connection = None
    file_replaced = False
    try:
        with open(temp_path, "w", encoding="utf-8") as output_file:
            output_file.write(serialized_profile)

        init_db(db_path)
        connection = get_connection(db_path)
        connection.execute("BEGIN")
        connection.execute(
            """
            INSERT INTO resumes (filename, name, phone, email, parsed_data)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                name = excluded.name,
                phone = excluded.phone,
                email = excluded.email,
                parsed_data = excluded.parsed_data
            """,
            (
                safe_name,
                profile.get("name", ""),
                profile.get("phone", ""),
                profile.get("email", ""),
                serialized_profile,
            ),
        )
        save_original_version(
            safe_name,
            source_profile,
            created_at=str(source_profile.get("parsed_at", "")),
            is_current=False,
            connection=connection,
        )
        saved_version = save_optimized_version(
            safe_name,
            version,
            connection=connection,
        )
        os.replace(temp_path, filepath)
        file_replaced = True
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        if file_replaced:
            restore_path = f"{filepath}.{uuid.uuid4().hex}.restore"
            with open(restore_path, "w", encoding="utf-8") as restore_file:
                restore_file.write(original_content)
            os.replace(restore_path, filepath)
        elif os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    finally:
        if connection is not None:
            connection.close()

    add_log(
        f"人工微调简历已保存: {profile.get('name', '')}（变更字段: {', '.join(changed_fields) if changed_fields else '无变化'}）",
        "success",
    )
    return {
        "ok": True,
        "filename": safe_name,
        "changed_fields": changed_fields,
        "version_id": saved_version.get("version_id", version["version_id"]),
        "data": profile,
    }


def _safe_html(value) -> str:
    return html.escape(str(value or "").strip(), quote=True)


def _experience_items_html(items, primary_fields, secondary_fields, desc_field="description") -> str:
    if not items or not isinstance(items, list):
        return ""
    rendered = []
    for item in items:
        if not isinstance(item, dict):
            continue
        primary = next(
            (_safe_html(item.get(field)) for field in primary_fields if item.get(field)),
            "",
        )
        secondary_parts = [
            _safe_html(item.get(field))
            for field in secondary_fields
            if item.get(field)
        ]
        secondary = " | ".join(secondary_parts)
        description = _safe_html(item.get(desc_field, ""))
        if not any((primary, secondary, description)):
            continue
        item_html = '<div class="exp-item">'
        if primary:
            item_html += f'<div class="exp-title">{primary}</div>'
        if secondary:
            item_html += f'<div class="exp-sub">{secondary}</div>'
        if description:
            item_html += f'<div class="exp-desc">{description}</div>'
        item_html += "</div>"
        rendered.append(item_html)
    return "".join(rendered)


def _simple_items_html(items, title_fields, detail_fields) -> str:
    if not items or not isinstance(items, list):
        return ""
    rendered = []
    for item in items:
        if isinstance(item, str):
            title = _safe_html(item)
            details = ""
        elif isinstance(item, dict):
            title = next(
                (_safe_html(item.get(field)) for field in title_fields if item.get(field)),
                "",
            )
            detail_parts = [
                _safe_html(item.get(field))
                for field in detail_fields
                if item.get(field)
            ]
            details = " | ".join(detail_parts)
        else:
            continue
        if not title and not details:
            continue
        item_html = '<div class="exp-item">'
        if title:
            item_html += f'<div class="exp-title">{title}</div>'
        if details:
            item_html += f'<div class="exp-sub">{details}</div>'
        item_html += "</div>"
        rendered.append(item_html)
    return "".join(rendered)


def _render_tags_html(items) -> str:
    if not items or not isinstance(items, list):
        return ""
    tags = []
    for item in items:
        if isinstance(item, str) and item.strip():
            tags.append(f'<span class="skill-tag">{_safe_html(item)}</span>')
        elif isinstance(item, dict):
            text = " · ".join(
                _safe_html(item.get(f))
                for f in ("language", "level", "certificate", "name")
                if item.get(f)
            )
            if text:
                tags.append(f'<span class="skill-tag">{text}</span>')
    return "".join(tags)


def _render_section(title: str, content: str, heading_tag: str = "h2", section_class: str = "section") -> str:
    if not content or not content.strip():
        return ""
    if not section_class:
        return f'<{heading_tag}>{title}</{heading_tag}>{content}'
    return f'<div class="{section_class}"><{heading_tag}>{title}</{heading_tag}>{content}</div>'


def _render_additional_sections(profile: dict, heading_tag: str = "h2") -> str:
    sections = []

    salary = _safe_html(profile.get("desired_salary", ""))
    if salary:
        sections.append(f'<div class="section"><{heading_tag}>期望薪资</{heading_tag}><div class="exp-desc">{salary}</div></div>')

    proj_html = _experience_items_html(profile.get("project_experience", []), ("name",), ("role", "duration"))
    if proj_html:
        sections.append(f'<div class="section"><{heading_tag}>项目经历</{heading_tag}>{proj_html}</div>')

    prac_html = _experience_items_html(profile.get("practical_experience", []), ("organization", "role", "name"), ("role", "duration"))
    if prac_html:
        sections.append(f'<div class="section"><{heading_tag}>个人实践</{heading_tag}>{prac_html}</div>')

    camp_html = _experience_items_html(profile.get("campus_experience", []), ("organization", "role"), ("role", "duration"))
    if camp_html:
        sections.append(f'<div class="section"><{heading_tag}>校园经历</{heading_tag}>{camp_html}</div>')

    res_html = _experience_items_html(profile.get("research_experience", []), ("name",), ("role", "duration"))
    if res_html:
        sections.append(f'<div class="section"><{heading_tag}>科研经历</{heading_tag}>{res_html}</div>')

    award_html = _simple_items_html(profile.get("awards", []), ("name",), ("level", "year", "description"))
    if award_html:
        sections.append(f'<div class="section"><{heading_tag}>获奖荣誉</{heading_tag}>{award_html}</div>')

    cert_html = _simple_items_html(profile.get("certificates", []), ("name",), ("level", "issuer", "year"))
    if cert_html:
        sections.append(f'<div class="section"><{heading_tag}>证书资质</{heading_tag}>{cert_html}</div>')

    lang_html = _simple_items_html(profile.get("language_skills", []), ("language",), ("level", "certificate"))
    if lang_html:
        sections.append(f'<div class="section"><{heading_tag}>语言能力</{heading_tag}>{lang_html}</div>')

    interests = profile.get("interests", [])
    interest_tags = _render_tags_html(interests)
    if interest_tags:
        sections.append(f'<div class="section"><{heading_tag}>兴趣爱好</{heading_tag}>{interest_tags}</div>')

    return "".join(sections)


def resume_template(
    resume_file: str = "",
    template_style: str = "classic",
):
    template_style, error = validate_choice(
        template_style,
        "template_style",
        {
            "classic",
            "modern",
            "dual",
            "magazine",
            "minimal",
            "timeline",
            "elegant",
            "tech",
            "finance",
            "mint",
            "gov",
            "obsidian",
        },
    )
    if error:
        return JSONResponse(error, status_code=400)

    active_data_dir = get_active_data_dir(DATA_DIR)
    resolved_resume = resolve_file_in_directory(active_data_dir, resume_file, {".json"})
    if resolved_resume is None:
        return JSONResponse(
            {"ok": False, "error": "文件名不安全"},
            status_code=400,
        )

    resume_file, filepath = resolved_resume
    data_dir = active_data_dir

    if not os.path.exists(filepath):
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)

    # 1. 优先读取 SQLite 中当前激活版本 (is_current=1)，若无则读取本地文件
    p = None
    conn = None
    try:
        target_db = os.path.join(data_dir, "offerforge.db")
        if os.path.exists(target_db):
            conn = get_connection(target_db)
            row = conn.execute(
                "SELECT content_json FROM resume_versions WHERE resume_filename = ? AND is_current = 1",
                (resume_file,),
            ).fetchone()
            if row and row["content_json"]:
                p = json.loads(row["content_json"])
    except Exception:
        pass
    finally:
        if conn is not None:
            conn.close()

    if p is None or not isinstance(p, dict):
        with open(filepath, "r", encoding="utf-8") as f:
            p = json.load(f)

    name = _safe_html(p.get("name", ""))
    desired = _safe_html(p.get("desired_position", ""))
    desired_salary = _safe_html(p.get("desired_salary", ""))
    phone = _safe_html(p.get("phone", ""))
    email = _safe_html(p.get("email", ""))
    summary = _safe_html(p.get("summary", ""))

    # 照片加载
    photo_html = ""
    photo_dir = get_active_photos_dir(data_dir)
    photo_base = os.path.splitext(resume_file)[0]
    for photo_type, photo_extension in PHOTO_FORMATS.values():
        resolved_photo = resolve_file_in_directory(
            photo_dir,
            f"{photo_base}.photo{photo_extension}",
            {photo_extension},
        )
        if not resolved_photo or not os.path.exists(resolved_photo[1]):
            continue

        import base64
        with open(resolved_photo[1], "rb") as pf:
            b64 = base64.b64encode(pf.read()).decode()
        photo_html = f'<img src="data:{photo_type};base64,{b64}" class="photo" alt="photo">'
        break

    # 2. 动态模块渲染器（有数据则渲染对应组件，无数据彻底返回空字符串）
    summary_html = f'<div class="summary">{summary}</div>' if summary else ""
    
    work_html = _experience_items_html(p.get("work_experience", []), ("position",), ("company", "duration"))
    work_sec = _render_section("工作经历", work_html)

    proj_html = _experience_items_html(p.get("project_experience", []), ("name",), ("role", "duration"))
    proj_sec = _render_section("项目经历", proj_html)

    prac_html = _experience_items_html(p.get("practical_experience", []), ("organization", "role", "name"), ("role", "duration"))
    prac_sec = _render_section("个人实践", prac_html)

    camp_html = _experience_items_html(p.get("campus_experience", []), ("organization", "role"), ("role", "duration"))
    camp_sec = _render_section("校园经历", camp_html)

    res_html = _experience_items_html(p.get("research_experience", []), ("name",), ("role", "duration"))
    res_sec = _render_section("科研经历", res_html)

    edu_html = _experience_items_html(p.get("education", []), ("school",), ("major", "degree", "year"))
    edu_sec = _render_section("教育背景", edu_html)

    skills_tags = _render_tags_html(p.get("skills", []))
    skills_sec = _render_section("专业技能", f'<div class="skills-wrap">{skills_tags}</div>' if skills_tags else "")

    award_html = _simple_items_html(p.get("awards", []), ("name",), ("level", "year", "description"))
    award_sec = _render_section("获奖荣誉", award_html)

    cert_html = _simple_items_html(p.get("certificates", []), ("name",), ("level", "issuer", "year"))
    cert_sec = _render_section("证书资质", cert_html)

    lang_tags = _render_tags_html(p.get("language_skills", []))
    lang_sec = _render_section("语言能力", f'<div class="skills-wrap">{lang_tags}</div>' if lang_tags else "")

    interest_tags = _render_tags_html(p.get("interests", []))
    interest_sec = _render_section("兴趣爱好", f'<div class="skills-wrap">{interest_tags}</div>' if interest_tags else "")

    # 头部意向与薪资展示（无薪资自动隐藏薪资）
    job_parts = []
    if desired:
        job_parts.append(desired)
    if desired_salary:
        job_parts.append(f"期望薪资：{desired_salary}")
    job_display = " | ".join(job_parts)

    css_map = {
        "classic": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f7fafc;padding:40px 20px;color:#1a202c}
.page{max-width:800px;margin:0 auto;background:#fff;padding:48px 56px;box-shadow:0 1px 3px rgba(0,0,0,0.1);border-radius:4px}
.header{text-align:center;border-bottom:2px solid #1a56db;padding-bottom:20px;margin-bottom:24px;position:relative}
h1{font-size:28px;color:#1a202c;margin-bottom:4px}
.job{font-size:15px;color:#4a5568;margin-bottom:8px;font-weight:500}
.contact{font-size:13px;color:#718096;display:flex;justify-content:center;gap:24px;flex-wrap:wrap}
.photo{width:90px;height:120px;object-fit:cover;border:1px solid #e2e8f0;float:right;margin-left:16px;margin-bottom:8px;border-radius:4px}
.section{margin-bottom:24px}
.section h2{font-size:15px;color:#1a56db;border-bottom:2px solid #1a56db;padding-bottom:6px;margin-bottom:12px;letter-spacing:1px;text-transform:uppercase}
.summary{font-size:14px;color:#2d3748;line-height:1.7;margin-bottom:8px;white-space:pre-wrap}
.exp-item{margin-bottom:14px;padding-left:14px;border-left:2px solid #cbd5e0}
.exp-title{font-size:15px;font-weight:700;color:#1a202c}
.exp-sub{font-size:12px;color:#718096;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#4a5568;line-height:1.6;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.skill-tag{display:inline-block;background:#ebf4ff;color:#1a56db;padding:4px 12px;border-radius:16px;font-size:12px;border:1px solid #bee3f8}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}}""",

        "modern": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#0f172a;padding:30px;color:#e2e8f0}
.page{max-width:780px;margin:0 auto;background:#1e293b;border-radius:12px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.5)}
.header{background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:36px 40px;color:#fff;position:relative}
.header h1{font-size:30px;font-weight:700;margin-bottom:4px}
.header .job{font-size:15px;opacity:0.95;margin-bottom:12px}
.header .contact{font-size:13px;opacity:0.85;display:flex;gap:24px;flex-wrap:wrap}
.photo{width:80px;height:80px;border-radius:50%;object-fit:cover;border:3px solid rgba(255,255,255,0.4);float:right;margin-top:-10px}
.body{padding:32px 40px}
.section{margin-bottom:28px}
.section h2{font-size:15px;color:#a78bfa;border-bottom:2px solid #334155;padding-bottom:8px;margin-bottom:14px;letter-spacing:1px;text-transform:uppercase}
.summary{font-size:14px;color:#cbd5e1;line-height:1.8;margin-bottom:4px;white-space:pre-wrap}
.exp-item{margin-bottom:16px;padding-left:16px;border-left:3px solid #6366f1}
.exp-title{font-size:15px;font-weight:700;color:#f1f5f9}
.exp-sub{font-size:12px;color:#94a3b8;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#cbd5e1;line-height:1.6;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.skill-tag{display:inline-block;background:rgba(99,102,241,0.18);color:#a5b4fc;padding:4px 12px;border-radius:20px;font-size:12px;border:1px solid rgba(99,102,241,0.35)}
@media print{body{background:#fff;padding:0;color:#000}.page{box-shadow:none;border-radius:0}}""",

        "dual": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f8fafc;padding:24px;color:#1e293b}
.page{max-width:820px;margin:0 auto;display:flex;min-height:100vh;box-shadow:0 4px 24px rgba(0,0,0,0.08);border-radius:8px;overflow:hidden}
.left{width:280px;background:#1e293b;color:#e2e8f0;padding:32px 22px;flex-shrink:0}
.left .name{font-size:22px;font-weight:700;margin-bottom:4px;color:#fff}
.left .job{font-size:13px;color:#a5b4fc;margin-bottom:16px}
.left .photo{width:100px;height:100px;border-radius:50%;object-fit:cover;border:3px solid #6366f1;margin:0 auto 16px;display:block}
.left .info{font-size:12px;color:#94a3b8;margin-bottom:12px;line-height:1.6}
.left h3{font-size:13px;color:#a78bfa;border-bottom:1px solid #334155;padding-bottom:6px;margin:20px 0 10px;letter-spacing:1px}
.left .skills-wrap{display:flex;flex-direction:column;gap:6px}
.left .skill-tag{display:block;background:rgba(99,102,241,0.18);color:#a5b4fc;padding:5px 10px;border-radius:4px;font-size:12px;word-break:break-all}
.left .exp-item{margin-bottom:10px}
.left .exp-title{font-size:13px;font-weight:600;color:#f1f5f9}
.left .exp-sub{font-size:11px;color:#94a3b8}
.right{flex:1;padding:32px 36px;background:#fff}
.right .section{margin-bottom:24px}
.right h2{font-size:15px;color:#6366f1;border-bottom:2px solid #e2e8f0;padding-bottom:8px;margin-bottom:14px;letter-spacing:1px}
.right .summary{font-size:14px;color:#475569;line-height:1.8;white-space:pre-wrap}
.right .exp-item{margin-bottom:14px;padding-left:12px;border-left:2px solid #e2e8f0}
.right .exp-title{font-size:15px;font-weight:700;color:#1e293b}
.right .exp-sub{font-size:12px;color:#64748b;margin:2px 0 4px}
.right .exp-desc{font-size:13px;color:#475569;line-height:1.6;white-space:pre-wrap}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}}""",

        "magazine": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f0eb;padding:32px;color:#2c2c2c}
.page{max-width:800px;margin:0 auto;background:#fff;box-shadow:0 4px 24px rgba(0,0,0,0.08)}
.top-bar{background:#1a1a2e;color:#fff;padding:36px 48px 24px;position:relative}
.top-bar h1{font-size:34px;font-weight:300;letter-spacing:4px;margin-bottom:4px}
.top-bar .job{font-size:15px;color:#a0a0b8;font-weight:300}
.top-bar .contact{font-size:12px;color:#888;margin-top:14px;display:flex;gap:20px;flex-wrap:wrap}
.photo{width:80px;height:80px;border-radius:50%;object-fit:cover;float:right;margin-top:-10px;border:2px solid #fff}
.content{padding:32px 48px 40px}
.section{margin-bottom:28px}
.section h2{font-size:13px;color:#1a1a2e;border-bottom:1px solid #1a1a2e;padding-bottom:8px;margin-bottom:16px;letter-spacing:4px;text-transform:uppercase;font-weight:600}
.summary{font-size:14px;color:#555;line-height:1.9;margin-bottom:6px;white-space:pre-wrap}
.exp-item{margin-bottom:16px;padding-left:12px;border-left:2px solid #1a1a2e}
.exp-title{font-size:15px;font-weight:600;color:#1a1a2e}
.exp-sub{font-size:12px;color:#777;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#666;line-height:1.7;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;border:1px solid #d0d0d0;color:#555;padding:4px 12px;font-size:12px}
@media print{body{background:#fff;padding:0}.page{box-shadow:none}}""",

        "minimal": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#fff;padding:36px;color:#333}
.page{max-width:760px;margin:0 auto}
.header{padding-bottom:20px;margin-bottom:24px;border-bottom:1px solid #e0e0e0;position:relative}
.header h1{font-size:26px;font-weight:600;color:#111;margin-bottom:4px}
.header .job{font-size:14px;color:#777;font-weight:400;margin-bottom:8px}
.header .contact{font-size:12px;color:#999;display:flex;gap:18px;flex-wrap:wrap}
.photo{width:70px;height:70px;border-radius:4px;object-fit:cover;float:right;margin-top:-10px}
.section{margin-bottom:24px}
.section h2{font-size:12px;color:#888;font-weight:600;margin-bottom:12px;letter-spacing:3px;text-transform:uppercase}
.summary{font-size:13px;color:#555;line-height:1.8;white-space:pre-wrap}
.exp-item{margin-bottom:14px}
.exp-title{font-size:14px;font-weight:600;color:#222}
.exp-sub{font-size:12px;color:#888;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#666;line-height:1.7;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;color:#666;padding:3px 10px;font-size:12px;border:1px solid #e5e5e5;border-radius:2px}
@media print{body{padding:0}}""",

        "timeline": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#fafafa;padding:32px;color:#1a1a1a}
.page{max-width:780px;margin:0 auto;background:#fff;padding:44px 52px;box-shadow:0 2px 12px rgba(0,0,0,0.06);border-radius:6px}
.header{text-align:center;margin-bottom:28px;position:relative}
.header h1{font-size:26px;font-weight:600;color:#1a1a1a}
.header .job{font-size:14px;color:#666;margin:6px 0 8px}
.header .contact{font-size:12px;color:#999;display:flex;justify-content:center;gap:20px;flex-wrap:wrap}
.photo{width:72px;height:72px;border-radius:50%;object-fit:cover;margin:0 auto 12px;display:block;border:3px solid #0891b2}
.section{margin-bottom:26px}
.section h2{font-size:14px;color:#0891b2;display:flex;align-items:center;gap:12px;margin-bottom:14px}
.section h2:after{content:"";flex:1;height:1px;background:#e5e5e5}
.summary{font-size:14px;color:#555;line-height:1.8;white-space:pre-wrap}
.exp-item{position:relative;padding-left:20px;margin-bottom:14px;border-left:2px solid #0891b2}
.exp-title{font-size:15px;font-weight:600;color:#1a1a1a}
.exp-sub{font-size:12px;color:#888;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#666;line-height:1.6;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;background:#ecfeff;color:#0891b2;padding:4px 12px;border-radius:16px;font-size:12px;font-weight:500}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}}""",

        "elegant": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Noto Serif SC","PingFang SC","Source Han Serif CN",serif;background:#d4c5a9;padding:40px 20px;color:#2c1810}
.page{max-width:780px;margin:0 auto;background:#faf6ee;padding:56px 60px;box-shadow:0 4px 40px rgba(44,24,16,0.12);border:1px solid #e8ddcc}
.header{text-align:center;border-bottom:1px solid #d4c5a9;padding-bottom:20px;margin-bottom:32px;position:relative}
.header h1{font-size:32px;font-weight:500;color:#2c1810;letter-spacing:4px;margin-bottom:6px}
.header .job{font-size:14px;color:#6b5b4e;letter-spacing:2px;font-style:italic;margin-bottom:6px}
.header .contact{font-size:12px;color:#8b7d72;display:flex;justify-content:center;gap:24px;flex-wrap:wrap}
.photo{width:76px;height:96px;object-fit:cover;border-radius:2px;border:1px solid #c4b49a;margin:0 auto 12px;display:block}
.section{margin-bottom:28px}
.section h2{font-size:14px;color:#5c3a2a;font-weight:600;letter-spacing:3px;text-transform:uppercase;margin-bottom:14px;border-bottom:1px solid #e0d5c5;padding-bottom:6px}
.summary{font-size:13px;color:#4a3d36;line-height:1.9;white-space:pre-wrap}
.exp-item{margin-bottom:16px;padding-left:14px;border-left:2px solid #d4c5a9}
.exp-title{font-size:15px;font-weight:600;color:#2c1810}
.exp-sub{font-size:12px;color:#7d6e62;margin:2px 0 4px;font-style:italic}
.exp-desc{font-size:13px;color:#4a3d36;line-height:1.7;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;border:1px solid #d4c5a9;color:#6b5b4e;background:rgba(139,111,71,0.06);padding:4px 12px;font-size:12px}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border:none}}""",

        "tech": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#0a1628;padding:30px;color:#c8d6e5}
.page{max-width:780px;margin:0 auto;background:#0f2247;border-radius:8px;overflow:hidden;box-shadow:0 8px 40px rgba(0,100,255,0.15)}
.header{background:linear-gradient(135deg,#0d3b7a,#1a56db);padding:36px 40px;color:#fff;display:flex;align-items:center;gap:24px;position:relative}
.header h1{font-size:28px;font-weight:700;letter-spacing:1px}
.header .job{font-size:14px;opacity:0.9;margin-top:4px}
.header .contact{font-size:12px;opacity:0.8;display:flex;gap:18px;margin-top:8px;flex-wrap:wrap}
.photo{width:75px;height:95px;object-fit:cover;border-radius:6px;border:2px solid #4dabf7;margin-left:auto}
.body{padding:32px 40px}
.section{margin-bottom:28px}
.section h2{font-size:14px;color:#4dabf7;font-weight:600;letter-spacing:2px;text-transform:uppercase;border-bottom:2px solid #1a3a5c;padding-bottom:8px;margin-bottom:14px}
.summary{font-size:14px;color:#94aec5;line-height:1.9;white-space:pre-wrap}
.exp-item{margin-bottom:16px;padding-left:14px;border-left:3px solid #1a56db}
.exp-title{font-size:15px;font-weight:600;color:#e8f0f8}
.exp-sub{font-size:12px;color:#5a7a9a;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#7d9db9;line-height:1.7;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;background:rgba(26,86,219,0.18);color:#4dabf7;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:500;border:1px solid rgba(77,171,247,0.25)}
@media print{body{background:#fff;padding:0;color:#000}.page{background:#fff;box-shadow:none}.header{background:#1a56db;-webkit-print-color-adjust:exact}}""",
        "finance": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Georgia","Songti SC","SimSun",serif;background:#eef0f3;padding:28px;color:#111827}
.page{max-width:780px;margin:0 auto;background:#fff;padding:40px 48px;border:1px solid #d1d5db;box-shadow:0 4px 20px rgba(0,0,0,0.06)}
.header{border-bottom:2px solid #111827;padding-bottom:14px;margin-bottom:20px;display:flex;align-items:center;gap:20px}
.header h1{font-size:26px;font-weight:700;letter-spacing:1.5px;color:#111827}
.header .job{font-size:13.5px;color:#374151;margin-top:4px;font-weight:600}
.header .contact{font-size:12px;color:#4b5563;display:flex;gap:16px;margin-top:6px;flex-wrap:wrap;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
.photo{width:70px;height:90px;object-fit:cover;border:1px solid #111827;margin-left:auto}
.section{margin-bottom:20px}
.section h2{font-size:13px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#111827;border-bottom:1px solid #9ca3af;padding-bottom:4px;margin-bottom:10px}
.summary{font-size:13px;color:#1f2937;line-height:1.75;white-space:pre-wrap;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
.exp-item{margin-bottom:13px}
.exp-title{font-size:14px;font-weight:700;color:#111827;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
.exp-sub{font-size:12px;color:#6b7280;margin:2px 0 4px;font-style:italic}
.exp-desc{font-size:12.5px;color:#374151;line-height:1.68;white-space:pre-wrap;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;background:#f3f4f6;color:#111827;padding:3px 10px;border:1px solid #d1d5db;border-radius:2px;font-size:12px;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
@media print{body{background:#fff;padding:0}.page{border:none;box-shadow:none;padding:24px 32px}}""",
        "mint": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#ecf9f4;padding:28px;color:#1e293b}
.page{max-width:780px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 10px 32px rgba(16,185,129,0.12)}
.header{background:linear-gradient(135deg,#059669,#10b981,#34d399);padding:34px 40px;color:#fff;display:flex;align-items:center;gap:22px}
.header h1{font-size:28px;font-weight:700}
.header .job{font-size:14px;opacity:0.95;margin-top:5px}
.header .contact{font-size:12px;opacity:0.9;display:flex;gap:16px;margin-top:8px;flex-wrap:wrap}
.photo{width:76px;height:96px;object-fit:cover;border-radius:10px;border:3px solid rgba(255,255,255,0.85);margin-left:auto}
.body{padding:30px 40px}
.section{margin-bottom:24px}
.section h2{font-size:15px;font-weight:700;color:#047857;display:flex;align-items:center;gap:8px;padding-bottom:6px;margin-bottom:12px;border-bottom:2px solid #d1fae5}
.summary{font-size:13.5px;color:#334155;line-height:1.85;white-space:pre-wrap}
.exp-item{margin-bottom:14px;padding:10px 14px;background:#f8fafc;border-left:3px solid #10b981;border-radius:0 8px 8px 0}
.exp-title{font-size:14.5px;font-weight:600;color:#0f172a}
.exp-sub{font-size:12px;color:#64748b;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#475569;line-height:1.7;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:500}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}.header{-webkit-print-color-adjust:exact;print-color-adjust:exact}}""",
        "gov": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f1f4f8;padding:28px;color:#1f2937}
.page{max-width:780px;margin:0 auto;background:#fff;border-top:5px solid #b91c1c;box-shadow:0 6px 24px rgba(15,23,42,0.08)}
.header{background:#1e3a5f;padding:30px 40px;color:#fff;display:flex;align-items:center;gap:22px}
.header h1{font-size:27px;font-weight:700;letter-spacing:2px}
.header .job{font-size:14px;color:#fde68a;margin-top:5px;font-weight:500}
.header .contact{font-size:12px;color:#e2e8f0;display:flex;gap:18px;margin-top:8px;flex-wrap:wrap}
.photo{width:76px;height:98px;object-fit:cover;border:2px solid #fff;margin-left:auto}
.body{padding:30px 40px}
.section{margin-bottom:22px}
.section h2{font-size:15px;font-weight:700;color:#1e3a5f;border-left:4px solid #b91c1c;padding-left:10px;border-bottom:1px solid #e5e7eb;padding-bottom:6px;margin-bottom:12px}
.summary{font-size:13.5px;color:#374151;line-height:1.85;white-space:pre-wrap}
.exp-item{margin-bottom:14px;padding-bottom:10px;border-bottom:1px dashed #e5e7eb}
.exp-title{font-size:14.5px;font-weight:700;color:#111827}
.exp-sub{font-size:12px;color:#6b7280;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#4b5563;line-height:1.72;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;background:#eff6ff;color:#1e3a5f;border:1px solid #bfdbfe;padding:4px 11px;border-radius:4px;font-size:12px;font-weight:500}
@media print{body{background:#fff;padding:0}.page{box-shadow:none}.header{-webkit-print-color-adjust:exact;print-color-adjust:exact}}""",
        "obsidian": """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#e5e7eb;padding:28px;color:#18181b}
.page{max-width:780px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 12px 36px rgba(0,0,0,0.14)}
.header{background:linear-gradient(135deg,#18181b,#27272a);padding:36px 42px;color:#fafafa;display:flex;align-items:center;gap:24px;border-bottom:3px solid #f59e0b}
.header h1{font-size:29px;font-weight:800;letter-spacing:1px}
.header .job{font-size:14px;color:#fbbf24;margin-top:5px;font-weight:600}
.header .contact{font-size:12px;color:#d4d4d8;display:flex;gap:18px;margin-top:8px;flex-wrap:wrap}
.photo{width:76px;height:96px;object-fit:cover;border-radius:8px;border:2px solid #f59e0b;margin-left:auto}
.body{padding:32px 42px}
.section{margin-bottom:24px}
.section h2{font-size:14px;font-weight:700;color:#18181b;letter-spacing:1.5px;text-transform:uppercase;border-bottom:2px solid #18181b;padding-bottom:6px;margin-bottom:13px}
.summary{font-size:13.5px;color:#3f3f46;line-height:1.85;white-space:pre-wrap}
.exp-item{margin-bottom:15px;padding-left:14px;border-left:2px solid #f59e0b}
.exp-title{font-size:14.5px;font-weight:700;color:#18181b}
.exp-sub{font-size:12px;color:#71717a;margin:2px 0 4px}
.exp-desc{font-size:13px;color:#3f3f46;line-height:1.72;white-space:pre-wrap}
.skills-wrap{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{display:inline-block;background:#18181b;color:#fef3c7;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:500}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;border-radius:0}.header{-webkit-print-color-adjust:exact;print-color-adjust:exact}.skill-tag{-webkit-print-color-adjust:exact;print-color-adjust:exact}}"""
    }

    css = css_map.get(template_style, css_map["classic"])

    if template_style == "dual":
        # 双栏左侧：短属性聚合（有数据才挂载）
        left_parts = []
        if photo_html:
            left_parts.append(photo_html)
        if name:
            left_parts.append(f'<div class="name">{name}</div>')
        
        info_lines = []
        if phone:
            info_lines.append(f'<p>📱 {phone}</p>')
        if email:
            info_lines.append(f'<p>📧 {email}</p>')
        if info_lines:
            left_parts.append(f'<div class="info">{"".join(info_lines)}</div>')

        if job_display:
            left_parts.append(f'<div class="job"><h3>🎯 求职意向</h3><p>{job_display}</p></div>')
        if skills_tags:
            left_parts.append(f'<h3>🛠 专业技能</h3><div class="skills-wrap">{skills_tags}</div>')
        if lang_tags:
            left_parts.append(f'<h3>🌐 语言能力</h3><div class="skills-wrap">{lang_tags}</div>')
        if cert_sec:
            left_parts.append(f'<h3>📜 证书资质</h3>{cert_html}')
        if interest_tags:
            left_parts.append(f'<h3>🎨 兴趣爱好</h3><div class="skills-wrap">{interest_tags}</div>')
        
        # 双栏右侧：长叙述经历（有数据才挂载）
        right_parts = []
        if summary_html:
            right_parts.append(f'<div class="section"><h2>📝 个人总结</h2>{summary_html}</div>')
        if work_sec:
            right_parts.append(work_sec)
        if proj_sec:
            right_parts.append(proj_sec)
        if prac_sec:
            right_parts.append(prac_sec)
        if camp_sec:
            right_parts.append(camp_sec)
        if res_sec:
            right_parts.append(res_sec)
        if edu_sec:
            right_parts.append(edu_sec)
        if award_sec:
            right_parts.append(award_sec)
        
        body = f'<div class="left">{"".join(left_parts)}</div><div class="right">{"".join(right_parts)}</div>'

    else:
        # 单栏头部
        contact_spans = []
        if phone:
            contact_spans.append(f'<span>📱 {phone}</span>')
        if email:
            contact_spans.append(f'<span>📧 {email}</span>')
        contact_html = f'<div class="contact">{"".join(contact_spans)}</div>' if contact_spans else ""
        job_html = f'<div class="job">{job_display}</div>' if job_display else ""
        
        if template_style == "magazine":
            header_html = f'<div class="top-bar">{photo_html}<h1>{name}</h1>{job_html}{contact_html}</div>'
        else:
            header_html = f'<div class="header">{photo_html}<h1>{name}</h1>{job_html}{contact_html}</div>'

        # 单栏主体列表（全量 10 大模块动态挂载）
        main_parts = []
        if summary_html:
            main_parts.append(f'<div class="section"><h2>📝 个人总结</h2>{summary_html}</div>')
        if work_sec:
            main_parts.append(work_sec)
        if proj_sec:
            main_parts.append(proj_sec)
        if prac_sec:
            main_parts.append(prac_sec)
        if camp_sec:
            main_parts.append(camp_sec)
        if res_sec:
            main_parts.append(res_sec)
        if edu_sec:
            main_parts.append(edu_sec)
        if skills_sec:
            main_parts.append(skills_sec)
        if award_sec:
            main_parts.append(award_sec)
        if cert_sec:
            main_parts.append(cert_sec)
        if lang_sec:
            main_parts.append(lang_sec)
        if interest_sec:
            main_parts.append(interest_sec)
        
        body_content = "".join(main_parts)

        if template_style in ("modern", "tech", "mint", "gov", "obsidian"):
            body = f'{header_html}<div class="body">{body_content}</div>'
        elif template_style == "magazine":
            body = f'{header_html}<div class="content">{body_content}</div>'
        else:
            body = f'{header_html}{body_content}'

    html = f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>{name} - 简历</title><style>{css}</style></head><body><div class="page">{body}</div></body></html>'
    return HTMLResponse(content=html, status_code=200, headers={"X-Template-Style": template_style})


def _inspect_photo_content(content: bytes, declared_type: str):
    """验证照片体积、真实格式、像素数量及声明的MIME类型。"""
    if not isinstance(content, (bytes, bytearray)):
        return None, None, validation_error("photo", "照片内容必须是二进制文件")
    if not content:
        return None, None, validation_error("photo", "照片文件不能为空")
    if len(content) > MAX_PHOTO_SIZE:
        return None, None, validation_error("photo", "照片文件不能超过5MB")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
    ):
        return None, None, validation_error("photo", "照片内容不是有效图片")

    photo_info = PHOTO_FORMATS.get(image_format)
    if photo_info is None:
        return None, None, validation_error("photo", "照片仅支持JPEG或PNG格式")
    if width * height > MAX_PHOTO_PIXELS:
        return None, None, validation_error("photo", "照片像素不能超过2000万")

    expected_type, extension = photo_info
    if (declared_type or "").lower().strip() != expected_type:
        return None, None, validation_error("photo", "照片类型声明与真实内容不一致")
    return extension, expected_type, None


async def upload_photo(resume_file: str = "", photo=None):

    if not photo:

        return {"ok": False, "error": "missing photo"}

    active_data_dir = get_active_data_dir(DATA_DIR)
    resolved_resume = resolve_file_in_directory(active_data_dir, resume_file, {".json"})
    if resolved_resume is None:

        return {"ok": False, "error": "文件名不安全"}

    resume_file, _ = resolved_resume
    content = await photo.read()
    close_photo = getattr(photo, "close", None)
    if close_photo is not None:
        close_result = close_photo()
        if inspect.isawaitable(close_result):
            await close_result

    extension, content_type, error = _inspect_photo_content(
        content,
        getattr(photo, "content_type", ""),
    )
    if error:

        return error

    photo_dir = get_active_photos_dir(active_data_dir)
    os.makedirs(photo_dir, exist_ok=True)
    safe_name = os.path.splitext(resume_file)[0]
    photo_filename = f"{safe_name}.photo{extension}"
    resolved_photo = resolve_file_in_directory(
        photo_dir,
        photo_filename,
        {extension},
    )
    if resolved_photo is None:

        return {"ok": False, "error": "照片路径不安全"}

    _, filepath = resolved_photo

    with open(filepath, "wb") as f:

        f.write(content)

    for _, old_extension in PHOTO_FORMATS.values():
        if old_extension == extension:
            continue
        old_photo = resolve_file_in_directory(
            photo_dir,
            f"{safe_name}.photo{old_extension}",
            {old_extension},
        )
        if old_photo and os.path.exists(old_photo[1]):
            os.remove(old_photo[1])

    add_log(f"photo uploaded for {resume_file}: {len(content)} bytes", "success")

    return {
        "ok": True,
        "message": "ok",
        "filename": photo_filename,
        "content_type": content_type,
    }


def _build_export_response(profile: dict):
    name = _safe_html(profile.get("name", ""))
    desired = _safe_html(profile.get("desired_position", ""))
    phone = _safe_html(profile.get("phone", ""))
    email = _safe_html(profile.get("email", ""))
    summary = _safe_html(profile.get("summary", ""))
    skills_html = "".join(
        f'<span class="skill-tag">{_safe_html(skill)}</span>'
        for skill in profile.get("skills", [])
        if isinstance(skill, str) and skill.strip()
    )
    work_html = _experience_items_html(
        profile.get("work_experience", []),
        ("position",),
        ("company", "duration"),
    )
    education_html = _experience_items_html(
        profile.get("education", []),
        ("school",),
        ("major", "degree", "year"),
    )
    additional_sections_html = _render_additional_sections(profile, heading_tag="h3")

    sections = []
    if summary:
        sections.append(f'<div class="summary">{summary}</div>')
    if work_html:
        sections.append(f'<div class="section"><h3>工作经验</h3>{work_html}</div>')
    if education_html:
        sections.append(f'<div class="section"><h3>教育背景</h3>{education_html}</div>')
    sections.append(additional_sections_html)
    if skills_html:
        sections.append(f'<div class="section"><h3>技能</h3>{skills_html}</div>')

    page_content = "".join(sections)
    document_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{name} - 简历</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f7fafc;padding:40px 20px}}
.page{{max-width:800px;margin:0 auto;background:#fff;padding:48px 56px;box-shadow:0 1px 3px rgba(0,0,0,.1);border-radius:4px}}
h1{{font-size:28px;color:#1a202c;margin-bottom:4px}}
h2{{font-size:16px;color:#4a5568;font-weight:400;margin-bottom:8px}}
h3{{font-size:15px;color:#1a56db;border-bottom:2px solid #1a56db;padding-bottom:6px;margin:28px 0 14px;letter-spacing:1px}}
.contact{{font-size:13px;color:#718096;margin-bottom:20px}} .contact span{{margin-right:20px}}
.summary{{font-size:14px;color:#2d3748;line-height:1.7;margin-bottom:8px}}
.exp-item{{margin-bottom:14px;padding-left:14px;border-left:2px solid #cbd5e0}}
.exp-title{{font-size:15px;font-weight:700;color:#1a202c}}
.exp-sub{{font-size:12px;color:#718096;margin:2px 0 4px}}
.exp-desc{{font-size:13px;color:#4a5568;line-height:1.6}}
.skill-tag{{display:inline-block;background:#f0f4ff;color:#1a56db;padding:4px 12px;margin:4px;border-radius:16px;font-size:13px}}
@media print{{body{{background:#fff;padding:0}}.page{{box-shadow:none;border-radius:0}}}}
</style></head>
<body><div class="page">
<h1>{name}</h1><h2>{desired}</h2>
<div class="contact"><span>tel {phone}</span><span>email {email}</span></div>
{page_content}
</div></body></html>"""

    safe_name = quote(f"{profile.get('name', '')}_简历.html")
    return HTMLResponse(
        content=document_html,
        status_code=200,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}"},
    )


def export_resume(filename: str):
    resolved_resume = resolve_file_in_directory(get_active_data_dir(DATA_DIR), filename, {".json"})
    if resolved_resume is None:
        return JSONResponse({"ok": False, "error": "文件名不安全"}, status_code=400)

    _, filepath = resolved_resume
    if not os.path.exists(filepath):
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)

    with open(filepath, "r", encoding="utf-8") as resume_file:
        profile = json.load(resume_file)
    return _build_export_response(profile)


def export_optimized_resume(filename: str, optimized_resume: str = "{}"):
    resolved_resume = resolve_file_in_directory(get_active_data_dir(DATA_DIR), filename, {".json"})
    if resolved_resume is None:
        return JSONResponse({"ok": False, "error": "文件名不安全"}, status_code=400)

    _, filepath = resolved_resume
    if not os.path.exists(filepath):
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)

    try:
        with open(filepath, "r", encoding="utf-8") as resume_file:
            stored_profile = json.load(resume_file)
        source_profile, _ = optimization_source(stored_profile)
        candidate_profile = json.loads(optimized_resume)
        if not isinstance(candidate_profile, dict):
            raise ValueError("优化结果必须是结构化对象")
        candidate_data = {
            "optimized_summary": candidate_profile.get("summary", ""),
            "optimized_work_experience": candidate_profile.get("work_experience", []),
            "optimized_project_experience": candidate_profile.get("project_experience", []),
            "optimized_practical_experience": candidate_profile.get("practical_experience", []),
            "optimized_campus_experience": candidate_profile.get("campus_experience", []),
            "optimized_research_experience": candidate_profile.get("research_experience", []),
            "enhanced_skills": candidate_profile.get("skills", []),
        }
        safe_profile, _ = merge_grounded_optimization(
            source_profile,
            candidate_data,
            candidate_profile.get("desired_position") or source_profile.get("desired_position", ""),
            require_evidence=False,
        )
        return _build_export_response(safe_profile)
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=400)

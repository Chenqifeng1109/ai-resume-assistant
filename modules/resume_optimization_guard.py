import copy
import hashlib
import json
import re
from datetime import datetime
from typing import Any


EXPERIENCE_SPECS = {
    "work_experience": {
        "response_key": "optimized_work_experience",
        "identity_fields": ("company", "position", "duration"),
    },
    "project_experience": {
        "response_key": "optimized_project_experience",
        "identity_fields": ("name", "role", "duration"),
    },
    "practical_experience": {
        "response_key": "optimized_practical_experience",
        "identity_fields": ("organization", "role", "duration"),
    },
    "campus_experience": {
        "response_key": "optimized_campus_experience",
        "identity_fields": ("organization", "role", "duration"),
    },
    "research_experience": {
        "response_key": "optimized_research_experience",
        "identity_fields": ("name", "role", "duration"),
    },
}

PROMPT_PROFILE_FIELDS = (
    "name",
    "phone",
    "email",
    "desired_position",
    "desired_salary",
    "summary",
    "education",
    "work_experience",
    "practical_experience",
    "project_experience",
    "campus_experience",
    "research_experience",
    "skills",
    "awards",
    "certificates",
    "language_skills",
    "interests",
    "raw_text",
)

LIST_PROFILE_FIELDS = {
    "education",
    "work_experience",
    "practical_experience",
    "project_experience",
    "campus_experience",
    "research_experience",
    "skills",
    "awards",
    "certificates",
    "language_skills",
    "interests",
}

RESUME_OPTIMIZATION_PROMPT_VERSION = "resume-grounded-70-30-v3"


INTENSITY_PRESETS = {
    "mild": {
        "label": "微调档",
        "temperature": 0.3,
        "require_evidence": True,
        "allow_new_skills": False,
        "relax_numbers": False,
        "allow_rewrite_numbers": False,
        "prompt_rule": "【微调档 · 温度0.3】以原简历句式为底稿，仅优化语病、动词与专业表达，严格保留全部原有数字与事实结构。",
    },
    "balanced": {
        "label": "均衡档",
        "temperature": 0.55,
        "require_evidence": False,
        "allow_new_skills": True,
        "relax_numbers": True,
        "allow_rewrite_numbers": False,
        "prompt_rule": "【均衡档 · 温度0.55】保留真实的姓名、公司、学校、岗位、项目名与时间段；大胆运用目标岗位专业术语与 STAR 法则重构个人总结与每段经历描述，让改写后明显更契合目标 JD（可使用1/2/3分点与行业术语，不虚构假公司或夸张假业绩数字）。",
    },
    "aggressive": {
        "label": "激进档",
        "temperature": 0.85,
        "require_evidence": False,
        "allow_new_skills": True,
        "relax_numbers": True,
        "allow_rewrite_numbers": True,
        "prompt_rule": "【激进档 · 温度0.85】严守不编造假公司、假学校、假学历和假时间段底线；在此前提下，以大厂资深面试官标准深度重写个人总结与每段工作/项目经历，强力对齐目标 JD 高频关键词、拆解业务动作与业务价值产出，最大化提升匹配度与说服力。",
    },
}


def resolve_intensity_config(intensity: str | None) -> tuple[str, dict]:
    key = str(intensity or "mild").strip().lower()
    if key not in INTENSITY_PRESETS:
        key = "balanced"
    return key, INTENSITY_PRESETS[key]


def _numbers(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    return set(re.findall(r"\d+(?:\.\d+)?%?", text))


def _metric_numbers(text: Any) -> set[str]:
    """剔除分点序号（1./2、）、常见非业绩术语（0到1/B2B/GPT-4/2.0/3.0）后再提取业绩数字。"""
    if not isinstance(text, str):
        return set()
    cleaned = re.sub(r"(?:^|[；;。\n\r])\s*\d{1,2}[\.\、\)\）]\s*", " ", text)
    cleaned = re.sub(r"(?i)(?:b2b|b2c|c2c|o2o|gpt-?\d+(?:\.\d+)?|glm-?\d+(?:\.\d+)?|v\d+(?:\.\d+)?|web\d+\.\d+|top\s*\d+)", " ", cleaned)
    cleaned = re.sub(r"0\s*[到\-~→]\s*1", " ", cleaned)
    cleaned = re.sub(r"\d+\.\d+(?=\s*(?:版本|版|时代))", " ", cleaned)
    return set(re.findall(r"\d+(?:\.\d+)?%?", cleaned))


def _supported_text(candidate: Any, source_text: str, relax_numbers: bool = False, allow_rewrite_numbers: bool = False) -> bool:
    if not isinstance(candidate, str) or not candidate.strip():
        return False
    if allow_rewrite_numbers:
        return True
    if relax_numbers:
        return _metric_numbers(candidate).issubset(_numbers(source_text))
    return _numbers(candidate).issubset(_numbers(source_text))


def _normalized_evidence(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def capability_gap_id(capability: str, jd_evidence: str) -> str:
    """Build a stable identifier for one capability-gap suggestion."""
    source = f"{capability.strip()}\n{jd_evidence.strip()}".encode("utf-8")
    return hashlib.sha256(source).hexdigest()[:16]


def normalize_capability_decisions(capability_analysis: Any) -> tuple[dict, str | None]:
    """Validate user decisions without allowing unconfirmed text into a version."""
    if not isinstance(capability_analysis, dict):
        return {"direct_matches": [], "transferable_matches": [], "gaps": []}, None

    normalized = copy.deepcopy(capability_analysis)
    gaps = normalized.get("gaps", [])
    if not isinstance(gaps, list):
        gaps = []

    normalized_gaps = []
    for item in gaps[:10]:
        if not isinstance(item, dict):
            continue
        gap = copy.deepcopy(item)
        capability = str(gap.get("capability", "")).strip()
        jd_evidence = str(gap.get("jd_evidence", "")).strip()
        suggestion_id = str(gap.get("suggestion_id", "")).strip()
        gap["suggestion_id"] = suggestion_id or capability_gap_id(
            capability,
            jd_evidence,
        )

        decision = str(gap.get("decision", "pending")).strip().lower()
        if decision not in {"pending", "accepted", "rejected"}:
            return {}, f"能力建议“{capability or gap['suggestion_id']}”的确认状态无效"

        confirmed_content = str(gap.get("confirmed_content", "")).strip()
        if decision == "accepted" and not confirmed_content:
            return {}, f"已接受的能力建议“{capability or gap['suggestion_id']}”缺少真实经历说明"

        gap["decision"] = decision
        gap["confirmed_content"] = confirmed_content if decision == "accepted" else ""
        gap["decided_at"] = (
            str(gap.get("decided_at", "")).strip()
            or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if decision in {"accepted", "rejected"}
            else ""
        )
        normalized_gaps.append(gap)

    normalized["gaps"] = normalized_gaps
    return normalized, None


def confirmed_content_for_resume_writer(capability_analysis: Any) -> list[dict]:
    """Return only user-confirmed facts that a later resume writer may consume."""
    normalized, error = normalize_capability_decisions(capability_analysis)
    if error:
        return []
    return [
        {
            "suggestion_id": gap["suggestion_id"],
            "capability": str(gap.get("capability", "")).strip(),
            "confirmed_content": gap["confirmed_content"],
        }
        for gap in normalized.get("gaps", [])
        if gap.get("decision") == "accepted" and gap.get("confirmed_content")
    ]


def _evidence_supported(evidence: Any, source_text: str) -> bool:
    items = evidence if isinstance(evidence, list) else [evidence]
    valid_items = [item for item in items if isinstance(item, str) and item.strip()]
    normalized_source = _normalized_evidence(source_text)
    return bool(valid_items) and all(
        _normalized_evidence(item) in normalized_source for item in valid_items
    )


def original_profile_snapshot(profile: dict) -> dict:
    snapshot = copy.deepcopy(profile if isinstance(profile, dict) else {})
    for field in (
        "original_profile",
        "optimization_history",
        "active_optimization",
        "_optimization_meta",
    ):
        snapshot.pop(field, None)
    return snapshot


def optimization_source(profile: dict) -> tuple[dict, bool]:
    original = profile.get("original_profile") if isinstance(profile, dict) else None
    if isinstance(original, dict) and original:
        return original_profile_snapshot(original), True
    return original_profile_snapshot(profile), False


def build_grounded_prompt(
    profile: dict,
    target: str,
    extra: str = "",
    job_description: str = "",
) -> str:
    source_profile = {
        field: profile.get(field, [] if field in LIST_PROFILE_FIELDS else "")
        for field in PROMPT_PROFILE_FIELDS
    }
    source_json = json.dumps(source_profile, ensure_ascii=False, indent=2)
    extra_text = extra.strip() if isinstance(extra, str) else ""
    jd_text = job_description.strip() if isinstance(job_description, str) else ""

    return f"""你是一位严谨的跨行业简历优化师。你的任务不是简单换同义词，而是基于原文证据，把候选人的真实经历重新组织成目标岗位更容易理解的表达。

目标岗位：{target}
目标岗位JD：{jd_text or '用户未提供JD，只能根据具体岗位名称分析，不得猜测某家公司的特殊要求'}
用户额外要求：{extra_text or '无'}

【原始简历，唯一事实来源】
{source_json}

必须遵守（70%忠于原文核心事实 + 30%合理润色与添砖加瓦原则）：
1. 【70%核心事实底线】不得修改姓名、联系方式、公司名、学校名、项目名、角色、职位和时间；不得凭空新增原文不存在的公司、项目、证书、奖项或虚构新数字；每类经历的项目数量与原始简历保持一致（原始为空则返回[]）。
2. 【30%合理自由发挥与添砖加瓦】在不违背核心事实与已有数字的前提下，允许并鼓励基于候选人真实经历进行约30%的合理专业润色、STAR（情境-任务-行动-价值）结构展开、行业标准术语升级与业务场景细节补全，避免几乎原样照抄导致优化无感知。
3. 可以在summary和各经历的description中更积极地用目标岗位视角提炼可迁移能力与专业动作方法，使表达更具竞争力，但不得冒充从未工作过的行业履历或捏造虚假数字指标。
4. 技能只能从原始skills中筛选和按目标岗位相关性重排，不能直接塞入原文没有的新技能；缺少的关键能力请放入gaps能力缺口中建议用户补充。
5. 每一条改写后的summary或description都必须返回原文证据evidence；evidence必须逐字摘自原始简历，证明改写骨架源于真实经历。
6. 先区分direct_matches直接匹配、transferable_matches可迁移和gaps能力缺口。能力缺口只能作为建议，不能写入正式简历。
9. 如果提供了JD，岗位分析和能力映射以JD为准；没有JD时以具体岗位名称为准。
10. 原文没有对应经历时，在suggestions中建议用户补充，不得写入正式简历。
11. Kimi、Claude、ChatGPT、DeepSeek等专有名词保持原样，不得翻译。
12. 只返回JSON，不要返回解释文字。

返回格式：
{{
  "job_analysis": "目标岗位的核心职责、能力要求和行业特点",
  "capability_analysis": {{
    "direct_matches": [{{"capability":"直接匹配能力","source_evidence":"逐字引用原文","target_relevance":"为什么匹配"}}],
    "transferable_matches": [{{"capability":"可迁移能力","source_evidence":"逐字引用原文","target_relevance":"如何迁移到目标岗位但不冒充行业经验"}}],
    "gaps": [{{"capability":"简历未体现的能力","jd_evidence":"逐字引用JD；未提供JD时留空","action":"真实可执行的补充建议","priority":"high/medium/low"}}]
  }},
  "optimized_summary": "根据直接匹配和可迁移能力重写的个人总结",
  "summary_evidence": ["支撑个人总结的原文片段"],
  "optimized_work_experience": [{{"company":"保持原值","position":"保持原值","duration":"保持原值","description":"面向目标岗位重写原描述","evidence":["支撑改写的原文片段"],"transfer_focus":"突出的可迁移能力"}}],
  "optimized_project_experience": [{{"name":"保持原值","role":"保持原值","duration":"保持原值","description":"面向目标岗位重写原描述","evidence":["支撑改写的原文片段"],"transfer_focus":"突出的可迁移能力"}}],
  "optimized_practical_experience": [{{"organization":"保持原值","role":"保持原值","duration":"保持原值","description":"面向目标岗位重写原描述","evidence":["支撑改写的原文片段"],"transfer_focus":"突出的可迁移能力"}}],
  "optimized_campus_experience": [{{"organization":"保持原值","role":"保持原值","duration":"保持原值","description":"面向目标岗位重写原描述","evidence":["支撑改写的原文片段"],"transfer_focus":"突出的可迁移能力"}}],
  "optimized_research_experience": [{{"name":"保持原值","role":"保持原值","duration":"保持原值","description":"面向目标岗位重写原描述","evidence":["支撑改写的原文片段"],"transfer_focus":"突出的可迁移能力"}}],
  "enhanced_skills": ["只能从原始skills中选择并按目标岗位相关性排序"],
  "suggestions": ["原文缺少的能力只能作为建议"]
}}
"""


def _merge_experience_field(
    source_items: Any,
    proposed_items: Any,
    field: str,
    source_evidence: str,
    warnings: list[dict],
    require_evidence: bool,
    relax_numbers: bool = False,
    allow_rewrite_numbers: bool = False,
) -> list[dict]:
    if not isinstance(source_items, list):
        return []
    if not isinstance(proposed_items, list) or len(proposed_items) != len(source_items):
        if proposed_items not in (None, []):
            warnings.append(
                {
                    "code": "OPTIMIZATION_COUNT_MISMATCH",
                    "field": field,
                    "message": "AI返回的经历数量与原简历不一致，已保留原内容。",
                }
            )
        return copy.deepcopy(source_items)

    merged_items = []
    for index, source_item in enumerate(source_items):
        if not isinstance(source_item, dict):
            merged_items.append(copy.deepcopy(source_item))
            continue

        merged_item = copy.deepcopy(source_item)
        proposed_item = proposed_items[index]
        if not isinstance(proposed_item, dict):
            merged_items.append(merged_item)
            continue

        proposed_description = proposed_item.get("description", "")
        proposed_evidence = proposed_item.get("evidence", [])
        original_description = str(source_item.get("description", ""))
        evidence_ok = not require_evidence or _evidence_supported(
            proposed_evidence,
            source_evidence + "\n" + original_description,
        )
        if evidence_ok and _supported_text(
            proposed_description,
            source_evidence + "\n" + original_description,
            relax_numbers=relax_numbers,
            allow_rewrite_numbers=allow_rewrite_numbers,
        ):
            merged_item["description"] = proposed_description.strip()
        elif (
            require_evidence
            and not evidence_ok
            and isinstance(proposed_description, str)
            and proposed_description.strip()
        ):
            warnings.append(
                {
                    "code": "OPTIMIZATION_EVIDENCE_MISSING",
                    "field": f"{field}.{index}.description",
                    "message": "AI改写没有可核对的原文证据，已保留原描述。",
                }
            )
        elif isinstance(proposed_description, str) and proposed_description.strip():
            warnings.append(
                {
                    "code": "UNSUPPORTED_NUMBER_REMOVED",
                    "field": f"{field}.{index}.description",
                    "message": "AI润色加入了原文没有的数字，已保留原描述。",
                }
            )
        merged_items.append(merged_item)
    return merged_items


def merge_grounded_optimization(
    profile: dict,
    ai_data: dict,
    target: str,
    require_evidence: bool = True,
    intensity: str = "mild",
) -> tuple[dict, list[dict]]:
    _, cfg = resolve_intensity_config(intensity)
    effective_require_evidence = require_evidence and cfg["require_evidence"]
    relax_numbers = cfg["relax_numbers"]
    allow_rewrite_numbers = cfg["allow_rewrite_numbers"]
    allow_new_skills = cfg["allow_new_skills"]

    merged = copy.deepcopy(profile)
    warnings = []
    source_evidence = json.dumps(profile, ensure_ascii=False)

    proposed_summary = ai_data.get("optimized_summary", "")
    summary_evidence = ai_data.get("summary_evidence", [])
    original_summary = str(profile.get("summary", ""))
    summary_evidence_ok = not effective_require_evidence or _evidence_supported(
        summary_evidence,
        source_evidence + "\n" + original_summary,
    )
    if summary_evidence_ok and _supported_text(
        proposed_summary,
        source_evidence + "\n" + original_summary,
        relax_numbers=relax_numbers,
        allow_rewrite_numbers=allow_rewrite_numbers,
    ):
        merged["summary"] = proposed_summary.strip()
    elif (
        effective_require_evidence
        and not summary_evidence_ok
        and isinstance(proposed_summary, str)
        and proposed_summary.strip()
    ):
        warnings.append(
            {
                "code": "SUMMARY_EVIDENCE_MISSING",
                "field": "summary",
                "message": "AI总结没有可核对的原文证据，已保留原总结。",
            }
        )
    elif isinstance(proposed_summary, str) and proposed_summary.strip():
        warnings.append(
            {
                "code": "UNSUPPORTED_SUMMARY_REMOVED",
                "field": "summary",
                "message": "AI总结加入了原文没有的数字，已保留原总结。",
            }
        )

    for field, spec in EXPERIENCE_SPECS.items():
        proposed = ai_data.get(spec["response_key"])
        if proposed is None:
            if field == "work_experience":
                proposed = ai_data.get("optimized_internships")
            elif field == "project_experience":
                proposed = ai_data.get("optimized_projects")
        merged[field] = _merge_experience_field(
            profile.get(field, []),
            proposed,
            field,
            source_evidence,
            warnings,
            effective_require_evidence,
            relax_numbers=relax_numbers,
            allow_rewrite_numbers=allow_rewrite_numbers,
        )

    source_skills = [
        item for item in profile.get("skills", []) if isinstance(item, str) and item.strip()
    ]
    proposed_skills = ai_data.get("enhanced_skills", [])
    supported_proposed_skills = []
    if isinstance(proposed_skills, list):
        if allow_new_skills:
            seen_sk = set()
            for item in proposed_skills:
                clean_sk = str(item or "").strip()
                if clean_sk and clean_sk not in seen_sk and len(clean_sk) <= 40:
                    seen_sk.add(clean_sk)
                    supported_proposed_skills.append(clean_sk)
            supported_proposed_skills = supported_proposed_skills[:18]
        else:
            unsupported_skills = [item for item in proposed_skills if item not in source_skills]
            for item in proposed_skills:
                if item in source_skills and item not in supported_proposed_skills:
                    supported_proposed_skills.append(item)
            if unsupported_skills:
                warnings.append(
                    {
                        "code": "UNSUPPORTED_SKILLS_REMOVED",
                        "field": "skills",
                        "message": "AI建议了原简历没有的技能，未写入正式简历。",
                    }
                )
    merged["skills"] = supported_proposed_skills + [
        item for item in source_skills if item not in supported_proposed_skills
    ]
    merged["desired_position"] = target

    warnings.append(
        {
            "code": "HUMAN_REVIEW_REQUIRED",
            "field": "optimized_resume",
            "message": "AI润色结果仍需用户确认后再覆盖原简历。",
        }
    )
    return merged, warnings


def validated_capability_analysis(
    ai_data: dict,
    profile: dict,
    job_description: str = "",
) -> dict:
    analysis = ai_data.get("capability_analysis", {})
    if not isinstance(analysis, dict):
        return {"direct_matches": [], "transferable_matches": [], "gaps": []}

    source_text = json.dumps(profile, ensure_ascii=False)
    result = {"direct_matches": [], "transferable_matches": [], "gaps": []}
    for category in ("direct_matches", "transferable_matches"):
        items = analysis.get(category, [])
        if not isinstance(items, list):
            continue
        for item in items[:10]:
            if isinstance(item, dict) and _evidence_supported(
                item.get("source_evidence"),
                source_text,
            ):
                result[category].append(
                    {
                        "capability": str(item.get("capability", "")).strip(),
                        "source_evidence": str(item.get("source_evidence", "")).strip(),
                        "target_relevance": str(item.get("target_relevance", "")).strip(),
                    }
                )

    gaps = analysis.get("gaps", [])
    jd_text = job_description.strip() if isinstance(job_description, str) else ""
    if isinstance(gaps, list):
        for item in gaps[:10]:
            capability = str(item.get("capability", "")).strip() if isinstance(item, dict) else ""
            action = str(item.get("action", "")).strip() if isinstance(item, dict) else ""
            if capability and action:
                jd_evidence = str(item.get("jd_evidence", "")).strip()
                if jd_text and not _evidence_supported(jd_evidence, jd_text):
                    continue
                result["gaps"].append(
                    {
                        "suggestion_id": capability_gap_id(capability, jd_evidence),
                        "capability": capability,
                        "jd_evidence": jd_evidence if jd_text else "未提供JD，建议仅基于目标岗位名称生成。",
                        "resume_status": "简历未体现该能力，不代表你不具备。",
                        "action": action,
                        "write_condition": "仅在用户确认真实经历后，才允许写入正式简历。",
                        "priority": item.get("priority") if item.get("priority") in {"high", "medium", "low"} else "medium",
                        "decision": "pending",
                        "confirmed_content": "",
                        "decided_at": "",
                    }
                )
    return result


def build_optimization_version(
    optimized_profile: dict,
    target: str,
    job_description: str,
    capability_analysis: dict,
) -> dict:
    now = datetime.now()
    return {
        "version_id": now.strftime("%Y%m%d_%H%M%S_%f"),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "optimization_mode": (
            "jd_targeted" if str(job_description or "").strip() else "role_targeted"
        ),
        "prompt_version": RESUME_OPTIMIZATION_PROMPT_VERSION,
        "target": target,
        "job_description": job_description,
        "capability_analysis": copy.deepcopy(capability_analysis),
        "resume_writer_inputs": confirmed_content_for_resume_writer(
            capability_analysis
        ),
        "profile": original_profile_snapshot(optimized_profile),
    }


def optimization_response_sections(profile: dict) -> dict:
    return {
        "optimized_projects": profile.get("project_experience", []),
        "optimized_internships": profile.get("work_experience", []),
        "enhanced_skills": profile.get("skills", []),
        "section_counts": {
            field: len(profile.get(field, []))
            for field in (
                "education",
                "work_experience",
                "practical_experience",
                "project_experience",
                "campus_experience",
                "research_experience",
                "awards",
                "certificates",
                "language_skills",
                "interests",
            )
        },
    }

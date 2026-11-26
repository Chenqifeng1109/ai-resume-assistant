import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from modules.deepseek_client import (
    build_chat_completion_kwargs,
    create_chat_completion_with_fallback,
    get_active_llm_model,
)
from modules.jd_matcher import client


class JDEvidenceCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str
    evidence: str


class JDRequirementCandidate(JDEvidenceCandidate):
    required: bool


class JDAnalysisCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_title: JDEvidenceCandidate | None = None
    responsibilities: list[JDEvidenceCandidate] = Field(default_factory=list)
    hard_skills: list[JDEvidenceCandidate] = Field(default_factory=list)
    soft_skills: list[JDEvidenceCandidate] = Field(default_factory=list)
    keywords: list[JDEvidenceCandidate] = Field(default_factory=list)
    hard_thresholds: list[JDRequirementCandidate] = Field(default_factory=list)
    preferred_qualifications: list[JDRequirementCandidate] = Field(default_factory=list)


PREFERRED_MARKERS = (
    "优先",
    "加分",
    "优先考虑",
    "更佳",
    "preferred",
    "plus",
    "bonus",
)

QUANTIFIED_CLAIM_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十两]+)(?:年|个月|月|天|岁|%|万|千|k)",
    re.IGNORECASE,
)


SYSTEM_PROMPT = """你是OfferForge的JD结构化分析助手。

任务：只根据用户提供的JD原文提取岗位名称、岗位职责、硬技能、软技能、关键词、硬性门槛和加分项。

必须遵守：
1. value必须忠实保留原意，Kimi、Claude、SQL等专有名词不得翻译或改写。
2. evidence必须逐字复制JD原文中的单行证据，不得概括、拼接或编造。
3. 原文没有的内容不得输出；单值缺失返回null，多值缺失返回[]。
4. 只有“必须、要求、至少、以上、需具备”等明确强制条件才能进入hard_thresholds，required必须为true。
5. “优先、加分、更佳”等条件必须进入preferred_qualifications，required必须为false。
6. hard_skills只放可学习、可验证的专业能力；soft_skills只放沟通、协作等通用能力。
7. 只返回JSON对象，不要Markdown代码块或额外说明。

输出结构：
{
  "job_title": {"value": "岗位名称", "evidence": "原文证据"} 或 null,
  "responsibilities": [{"value": "结构化职责", "evidence": "原文证据"}],
  "hard_skills": [{"value": "硬技能", "evidence": "原文证据"}],
  "soft_skills": [{"value": "软技能", "evidence": "原文证据"}],
  "keywords": [{"value": "关键词", "evidence": "原文证据"}],
  "hard_thresholds": [{"value": "硬性门槛", "evidence": "原文证据", "required": true}],
  "preferred_qualifications": [{"value": "加分项", "evidence": "原文证据", "required": false}]
}

示例：原文“有RAG项目经验者优先”必须进入preferred_qualifications，不得改成必须具备RAG项目经验。"""


def _clean_json_text(result_text: str) -> str:
    cleaned = result_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _find_evidence_line(lines: list[str], evidence: str) -> tuple[str, int] | None:
    normalized_evidence = _normalize_for_match(evidence)
    if not normalized_evidence:
        return None

    for line_number, source_line in enumerate(lines, start=1):
        if normalized_evidence in _normalize_for_match(source_line):
            return source_line.strip(), line_number
    return None


def _build_evidence_items(
    candidates: list[JDEvidenceCandidate],
    lines: list[str],
    field: str,
    warnings: list[dict],
) -> list[dict]:
    items = []
    seen = set()
    for candidate in candidates:
        value = candidate.value.strip()
        if not value:
            continue
        dedupe_key = value.casefold()
        if dedupe_key in seen:
            continue

        source = _find_evidence_line(lines, candidate.evidence)
        if source is None:
            warnings.append(
                {
                    "code": "JD_EVIDENCE_NOT_FOUND",
                    "field": field,
                    "value": value,
                    "message": f"{value}没有找到对应JD原文证据，已从分析结果中移除。",
                }
            )
            continue

        evidence, line_number = source
        items.append(
            {
                "value": value,
                "evidence": evidence,
                "line_number": line_number,
            }
        )
        seen.add(dedupe_key)
    return items


def _is_preferred(evidence: str) -> bool:
    lowered = evidence.casefold()
    return any(marker in lowered for marker in PREFERRED_MARKERS)


def _has_unsupported_quantified_claim(value: str, evidence: str) -> bool:
    value_claims = {
        claim.casefold() for claim in QUANTIFIED_CLAIM_PATTERN.findall(value)
    }
    evidence_claims = {
        claim.casefold() for claim in QUANTIFIED_CLAIM_PATTERN.findall(evidence)
    }
    return bool(value_claims - evidence_claims)


def _build_requirements(
    hard_candidates: list[JDRequirementCandidate],
    preferred_candidates: list[JDRequirementCandidate],
    lines: list[str],
    warnings: list[dict],
) -> tuple[list[dict], list[dict]]:
    hard_thresholds = []
    preferred_qualifications = []
    seen = set()

    for candidate in [*hard_candidates, *preferred_candidates]:
        value = candidate.value.strip()
        if not value or value.casefold() in seen:
            continue

        source = _find_evidence_line(lines, candidate.evidence)
        if source is None:
            warnings.append(
                {
                    "code": "JD_EVIDENCE_NOT_FOUND",
                    "field": "requirements",
                    "value": value,
                    "message": f"{value}没有找到对应JD原文证据，已从分析结果中移除。",
                }
            )
            continue

        evidence, line_number = source
        if _has_unsupported_quantified_claim(value, evidence):
            warnings.append(
                {
                    "code": "JD_VALUE_NOT_SUPPORTED",
                    "field": "requirements",
                    "value": value,
                    "message": f"{value}包含原文证据没有的数量或年限，已从分析结果中移除。",
                }
            )
            continue

        preferred = _is_preferred(evidence)
        item = {
            "value": value,
            "evidence": evidence,
            "line_number": line_number,
            "required": not preferred,
        }
        if preferred:
            preferred_qualifications.append(item)
        else:
            hard_thresholds.append(item)
        seen.add(value.casefold())

    return hard_thresholds, preferred_qualifications


def _normalize_analysis(candidate: JDAnalysisCandidate, jd_text: str) -> dict:
    lines = jd_text.splitlines()
    warnings: list[dict] = []
    job_title = None

    if candidate.job_title is not None:
        title_items = _build_evidence_items(
            [candidate.job_title],
            lines,
            "job_title",
            warnings,
        )
        job_title = title_items[0] if title_items else None

    hard_thresholds, preferred_qualifications = _build_requirements(
        candidate.hard_thresholds,
        candidate.preferred_qualifications,
        lines,
        warnings,
    )

    analysis = {
        "job_title": job_title,
        "responsibilities": _build_evidence_items(
            candidate.responsibilities, lines, "responsibilities", warnings
        ),
        "hard_skills": _build_evidence_items(
            candidate.hard_skills, lines, "hard_skills", warnings
        ),
        "soft_skills": _build_evidence_items(
            candidate.soft_skills, lines, "soft_skills", warnings
        ),
        "keywords": _build_evidence_items(
            candidate.keywords, lines, "keywords", warnings
        ),
        "hard_thresholds": hard_thresholds,
        "preferred_qualifications": preferred_qualifications,
        "quality_status": "needs_review" if warnings else "evidence_checked",
        "quality_warnings": warnings,
    }
    return analysis


def analyze_jd(jd_text: str) -> dict[str, Any]:
    try:
        response = create_chat_completion_with_fallback(
            client,
            model=get_active_llm_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请分析以下JD原文：\n\n{jd_text}"},
            ],
            temperature=0.1,
            max_tokens=2200,
        )
        content = response.choices[0].message.content or ""
        raw_payload = json.loads(_clean_json_text(content))
        candidate = JDAnalysisCandidate.model_validate(raw_payload)
        return {
            "ok": True,
            "analysis": _normalize_analysis(candidate, jd_text),
        }
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "AI响应解析失败：JD分析结果不是有效JSON。",
            "error_code": "UPSTREAM_ERROR",
        }
    except ValidationError:
        return {
            "ok": False,
            "error": "AI响应解析失败：JD分析结果不符合数据结构。",
            "error_code": "UPSTREAM_ERROR",
        }
    except Exception as error:
        return {
            "ok": False,
            "error": f"AI调用失败：{str(error)[:160]}",
            "error_code": "UPSTREAM_ERROR",
        }

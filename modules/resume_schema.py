from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ResumeSectionModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class EducationItem(ResumeSectionModel):
    school: str = ""
    degree: str = ""
    major: str = ""
    year: str = ""


class WorkExperienceItem(ResumeSectionModel):
    company: str = ""
    position: str = ""
    duration: str = ""
    description: str = ""


class PracticalExperienceItem(ResumeSectionModel):
    organization: str = ""
    role: str = ""
    duration: str = ""
    description: str = ""


class ProjectExperienceItem(ResumeSectionModel):
    name: str = ""
    role: str = ""
    duration: str = ""
    description: str = ""


class CampusExperienceItem(ResumeSectionModel):
    organization: str = ""
    role: str = ""
    duration: str = ""
    description: str = ""


class ResearchExperienceItem(ResumeSectionModel):
    name: str = ""
    role: str = ""
    duration: str = ""
    description: str = ""


class AwardItem(ResumeSectionModel):
    name: str = ""
    level: str = ""
    year: str = ""
    description: str = ""


class CertificateItem(ResumeSectionModel):
    name: str = ""
    level: str = ""
    year: str = ""
    issuer: str = ""


class LanguageSkillItem(ResumeSectionModel):
    language: str = ""
    level: str = ""
    certificate: str = ""


class ResumeParseModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    phone: str = ""
    email: str = ""
    desired_position: str = ""
    desired_salary: str = ""
    summary: str = ""
    education: list[EducationItem] = Field(default_factory=list)
    work_experience: list[WorkExperienceItem] = Field(default_factory=list)
    practical_experience: list[PracticalExperienceItem] = Field(default_factory=list)
    project_experience: list[ProjectExperienceItem] = Field(default_factory=list)
    campus_experience: list[CampusExperienceItem] = Field(default_factory=list)
    research_experience: list[ResearchExperienceItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    awards: list[AwardItem] = Field(default_factory=list)
    certificates: list[CertificateItem] = Field(default_factory=list)
    language_skills: list[LanguageSkillItem] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)


RESUME_LIST_FIELDS = (
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
)

RESUME_TEXT_FIELDS = (
    "name",
    "phone",
    "email",
    "desired_position",
    "desired_salary",
    "summary",
)

FIELD_LABELS = {
    "name": "姓名",
    "phone": "电话",
    "email": "邮箱",
    "desired_position": "求职意向",
    "desired_salary": "期望薪资",
    "summary": "自我介绍",
    "education": "教育经历",
    "work_experience": "工作/实习经历",
    "practical_experience": "个人实践",
    "project_experience": "项目经历",
    "campus_experience": "校园经历",
    "research_experience": "科研经历",
    "skills": "技能",
    "awards": "获奖荣誉",
    "certificates": "证书",
    "language_skills": "语言能力",
    "interests": "兴趣爱好",
    "school": "学校",
    "degree": "学历",
    "major": "专业",
    "year": "时间",
    "company": "公司名称",
    "position": "职位",
    "duration": "起止时间",
    "description": "内容描述",
    "organization": "单位或组织",
    "role": "角色或职责",
    "level": "等级",
    "issuer": "颁发机构",
    "language": "语言",
    "certificate": "相关证书",
}

ERROR_MESSAGES = {
    "missing": "缺少必要内容",
    "string_type": "必须是文本格式",
    "list_type": "必须是列表格式",
    "model_type": "必须是结构化对象",
    "dict_type": "必须是结构化对象",
    "string_too_short": "内容长度不足",
    "too_short": "内容或项目数量不足",
}


def _format_location(location: tuple[Any, ...]) -> str:
    parts = []
    for item in location:
        if isinstance(item, int):
            parts.append(f"第{item + 1}项")
        else:
            parts.append(FIELD_LABELS.get(str(item), str(item)))
    return " > ".join(parts) or "解析结果"


def _format_validation_errors(error: ValidationError) -> list[dict]:
    details = []
    for item in error.errors():
        field = _format_location(item.get("loc", ()))
        error_type = item.get("type", "unknown")
        message = ERROR_MESSAGES.get(error_type, "数据格式不正确")
        details.append(
            {
                "field": field,
                "message": f"{field}{message}",
                "type": error_type,
            }
        )
    return details


def _build_quality_warnings(data: dict, normalized_warnings: list[dict]) -> list[dict]:
    warnings = list(normalized_warnings)

    if not data.get("name", "").strip():
        warnings.append(
            {
                "code": "MISSING_NAME",
                "field": "name",
                "message": "未识别到姓名，请检查简历内容。",
            }
        )
    if not data.get("phone", "").strip() and not data.get("email", "").strip():
        warnings.append(
            {
                "code": "MISSING_CONTACT",
                "field": "contact",
                "message": "未识别到电话或邮箱，请检查联系方式。",
            }
        )
    if not data.get("desired_position", "").strip():
        warnings.append(
            {
                "code": "MISSING_DESIRED_POSITION",
                "field": "desired_position",
                "message": "未识别到求职意向，请检查或补充目标岗位。",
            }
        )
    if not any(item.strip() for item in data.get("skills", [])):
        warnings.append(
            {
                "code": "MISSING_SKILLS",
                "field": "skills",
                "message": "未识别到技能，请检查简历中的技能信息。",
            }
        )

    return warnings


def validate_resume_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        return {
            "error": "AI简历解析结果格式异常：最外层必须是结构化对象。",
            "error_code": "RESUME_SCHEMA_INVALID",
            "validation_errors": [
                {
                    "field": "解析结果",
                    "message": "解析结果必须是结构化对象",
                    "type": "dict_type",
                }
            ],
        }

    normalized = dict(payload)
    normalized_warnings = []

    for field in RESUME_LIST_FIELDS:
        value = normalized.get(field)
        if value is None:
            normalized[field] = []
        elif not isinstance(value, list):
            normalized[field] = []
            normalized_warnings.append(
                {
                    "code": "AI_FIELD_TYPE_NORMALIZED",
                    "field": field,
                    "message": (
                        f"{FIELD_LABELS.get(field, field)}返回格式异常，"
                        "已按空内容处理，请检查解析结果。"
                    ),
                }
            )

    for field in RESUME_TEXT_FIELDS:
        if normalized.get(field) is None:
            normalized[field] = ""

    try:
        validated = ResumeParseModel.model_validate(normalized).model_dump()
    except ValidationError as error:
        details = _format_validation_errors(error)
        first_message = details[0]["message"] if details else "数据格式不正确"
        return {
            "error": f"AI简历解析结果格式异常：{first_message}。",
            "error_code": "RESUME_SCHEMA_INVALID",
            "validation_errors": details,
        }

    quality_warnings = _build_quality_warnings(validated, normalized_warnings)
    validated["quality_status"] = (
        "needs_review" if quality_warnings else "complete"
    )
    validated["quality_warnings"] = quality_warnings
    return validated

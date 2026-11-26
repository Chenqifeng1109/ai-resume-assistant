"""简历 AI 优化业务逻辑。"""

import json
import os
import re
import time

from config import DATA_DIR
from core.workspace_context import get_active_data_dir
from core.file_security import resolve_file_in_directory
from core.input_validation import validate_text
from modules.deepseek_client import DeepSeekClient
from modules.resume_optimization_guard import (
    build_optimization_version,
    build_grounded_prompt,
    merge_grounded_optimization,
    optimization_source,
    optimization_response_sections,
    validated_capability_analysis,
)
from modules.resume_version_diff import build_resume_diff


def _target_is_too_broad(target: str) -> bool:
    compact = target.strip().replace(" ", "")
    broad_targets = {
        "金融",
        "金融行业",
        "互联网",
        "互联网行业",
        "教育",
        "教育行业",
        "医疗",
        "医疗行业",
        "传媒",
        "传媒行业",
    }
    return compact in broad_targets or (compact.endswith("行业") and len(compact) <= 8)


def _notify(progress_callback, stage: str, progress: int, **details) -> None:
    if progress_callback:
        progress_callback(stage, progress, **details)


def _extract_ai_json(raw_response: str) -> dict:
    """只修复 JSON 外壳（含尾逗号、裸换行、字符串内未转义双引号），不改写简历事实。"""
    from modules.deepseek_client import parse_llm_json_robust

    return parse_llm_json_robust(raw_response)


def _ai_error_details(exception: Exception) -> tuple[str, str, bool]:
    status_code = getattr(exception, "status_code", None)
    lowered = str(exception).lower()
    if status_code in {401, 403} or "api key" in lowered or "authentication" in lowered:
        return "AI_AUTH_ERROR", "AI服务配置或权限错误，请检查API Key", False
    if status_code == 429 or "rate limit" in lowered:
        return "AI_RATE_LIMIT", "AI服务当前请求过多", True
    if status_code in {502, 503, 504}:
        return "UPSTREAM_ERROR", "AI服务暂时不可用", True
    if "timeout" in lowered or "timed out" in lowered:
        return "AI_TIMEOUT", "AI服务响应超时", True
    return "UPSTREAM_ERROR", "AI服务调用失败", False


def optimize_resume(
    resume_file: str,
    target: str,
    extra: str = "",
    job_description: str = "",
    progress_callback=None,
    raw_response_callback=None,
    retry_delay: float = 1.0,
    intensity: str = "mild",
):

    """AI智能优化简历 - 三维度优化：项目经验/实习经验/技能能力"""

    if not resume_file:

        return {"ok": False, "error": "缺少简历文件或求职意向"}

    target, error = validate_text(
        target,
        "target",
        required=True,
        max_length=100,
    )
    if error:
        return error

    extra, error = validate_text(extra, "extra", max_length=2000)
    if error:
        return error

    job_description, error = validate_text(
        job_description,
        "job_description",
        max_length=12000,
    )
    if error:
        return error
    if _target_is_too_broad(target) and len(job_description.strip()) < 20:
        return {
            "ok": False,
            "error": "求职目标过于宽泛，请填写具体岗位（如金融产品运营）或粘贴完整JD",
            "error_code": "INVALID_INPUT",
        }

    _notify(progress_callback, "validating_input", 10)

    resolved_resume = resolve_file_in_directory(get_active_data_dir(DATA_DIR), resume_file, {".json"})
    if resolved_resume is None:

        return {"ok": False, "error": "文件名不安全"}

    _, filepath = resolved_resume

    if not os.path.exists(filepath):

        return {"ok": False, "error": "简历文件不存在"}

    with open(filepath, "r", encoding="utf-8") as f:

        stored_profile = json.load(f)

    _notify(progress_callback, "reading_resume", 25)

    profile, has_original_snapshot = optimization_source(stored_profile)

    

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



### 2. 严禁杜撰经历

- 原始简历没有的公司、项目、岗位、时间、数字、技能和成果一律不得生成

- 原文缺少相关经历时，只能在建议中提醒用户补充，不得写入正式简历

- “协助、参与、可能、约、待确认”等限定词必须保留，不得升级为确定事实



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



1. **项目经验**：只润色原简历已有项目，不得增加项目、工具、数字或成果。

2. **实习经验**：只润色原简历已有实习，不得增加公司、岗位、时间、数字或工作内容。

3. **技能能力**：正式简历只允许保留原简历已有技能；缺少的技能只能放入建议。



### 第三步：输出格式

严格按照以下JSON格式返回（不要包含任何其他文字）：

{{

  "job_analysis": "对{target}的深度分析(80-120字)：真实工作内容、核心技能、行业特点",

  "optimized_summary": "个人总结(150-250字)，语气真实不浮夸，突出与岗位的匹配点，不允许出现学历信息",

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

    

    from modules.resume_optimization_guard import resolve_intensity_config
    intensity_key, intensity_cfg = resolve_intensity_config(intensity)
    llm_temperature = float(intensity_cfg["temperature"])

    prompt = build_grounded_prompt(
        profile,
        target,
        extra,
        job_description,
    ) + f"\n\n改写力度与温度指令：{intensity_cfg['prompt_rule']}\n注意：请对个人总结和每条工作/项目经历的 description 进行实质性重写升级，避免原封不动照抄原文。"

    client = DeepSeekClient()
    result = None
    for attempt_number in range(1, 3):
        _notify(
            progress_callback,
            "calling_ai",
            40,
            attempts=attempt_number,
        )
        try:
            result = client.chat(
                system_prompt=f"你是资深简历优化专家。{intensity_cfg['prompt_rule']} 请严格返回合法JSON格式，中文引号使用「」或“”。",
                user_message=prompt,
                temperature=llm_temperature,
                raise_on_error=True,
            )
            break
        except Exception as exception:
            error_code, message, retryable = _ai_error_details(exception)
            if not retryable or attempt_number == 2:
                return {
                    "ok": False,
                    "error": message,
                    "error_code": "UPSTREAM_ERROR",
                    "failure_code": error_code,
                    "attempts": attempt_number,
                }
            _notify(
                progress_callback,
                "retry_wait",
                45,
                attempts=attempt_number,
            )
            if retry_delay > 0:
                time.sleep(retry_delay)

    if raw_response_callback:
        raw_response_callback(result)

    _notify(progress_callback, "parsing_response", 65)
    try:
        data = _extract_ai_json(result)
    except (json.JSONDecodeError, ValueError):
        # JSON 经本地修复仍破损时，自动以更低温度静默重试 1 次
        try:
            attempt_number += 1
            _notify(progress_callback, "calling_ai", 52, attempts=attempt_number)
            retry_result = client.chat(
                system_prompt=(
                    "你是专业简历优化师，遵循70%忠于原文核心事实+30%合理润色添砖加瓦原则。"
                    "上一次输出存在JSON语法错误，请严格返回合法JSON对象；中文引号一律使用「」或“”，"
                    "严禁在JSON字符串值内出现未转义的英文双引号。"
                ),
                user_message=prompt,
                temperature=0.1,
                raise_on_error=True,
            )
            if raw_response_callback:
                raw_response_callback(retry_result)
            _notify(progress_callback, "parsing_response", 68)
            data = _extract_ai_json(retry_result)
        except Exception as retry_exc:
            return {
                "ok": False,
                "error": f"AI响应解析失败：{retry_exc}",
                "error_code": "UPSTREAM_ERROR",
                "failure_code": "AI_RESPONSE_INVALID",
                "attempts": attempt_number,
            }

    _notify(progress_callback, "validating_result", 80)

    try:

            optimized_resume, optimization_warnings = merge_grounded_optimization(
                profile,
                data,
                target,
                intensity=intensity_key,
            )
            capability_analysis = validated_capability_analysis(
                data,
                profile,
                job_description,
            )
            optimization_version = build_optimization_version(
                optimized_resume,
                target,
                job_description,
                capability_analysis,
            )
            optimized_resume["_optimization_meta"] = {
                key: value
                for key, value in optimization_version.items()
                if key != "profile"
            }
            if not has_original_snapshot:
                optimization_warnings.insert(
                    0,
                    {
                        "code": "SOURCE_SNAPSHOT_MISSING",
                        "field": "original_profile",
                        "message": "这份旧简历没有原始底稿快照；本次只能依据当前版本优化，建议重新上传原文件后再做正式优化。",
                    },
                )
            response_sections = optimization_response_sections(optimized_resume)
            resume_diff = build_resume_diff(profile, optimized_resume)

            response = {

                "ok": True,

                "target": target,

                "job_analysis": data.get("job_analysis", ""),

                "capability_analysis": capability_analysis,

                "optimized_summary": optimized_resume.get("summary", ""),

                "optimized_projects": response_sections["optimized_projects"],

                "optimized_internships": response_sections["optimized_internships"],

                "enhanced_skills": response_sections["enhanced_skills"],

                "suggestions": data.get("suggestions", []),

                "optimized_resume": optimized_resume,

                "resume_diff": resume_diff,

                "optimization_warnings": optimization_warnings,

                "section_counts": response_sections["section_counts"],

                "source_snapshot_available": has_original_snapshot,

                "resume_file": resume_file,

                "attempts": attempt_number,

            }
            _notify(progress_callback, "completed", 100)
            return response

    except Exception as exception:
        return {
            "ok": False,
            "error": f"AI结果检查失败：{exception}",
            "error_code": "UPSTREAM_ERROR",
            "failure_code": "AI_RESULT_VALIDATION_FAILED",
            "attempts": attempt_number,
        }

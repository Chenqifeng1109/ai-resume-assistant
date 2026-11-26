"""岗位采集前的求职意向提取、校验与确认。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from modules.deepseek_client import DeepSeekClient


class JobIntentExtractRequest(BaseModel):
    intent_text: str = Field(min_length=2, max_length=1000)


class JobIntentData(BaseModel):
    position: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=30)
    salary_min: int | None = Field(default=None, ge=0, le=1_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=1_000_000)
    restrictions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("position", "city", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return "" if value is None else str(value).strip()

    @field_validator("restrictions", mode="before")
    @classmethod
    def normalize_restrictions(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("限制条件必须是列表")
        return [str(item).strip() for item in value if str(item).strip()]


class JobIntentResult(JobIntentData):
    status: Literal["needs_confirmation", "confirmed"] = "needs_confirmation"
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_text: str = ""
    confirmed_at: str | None = None


class JobIntentConfirmRequest(JobIntentData):
    position: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_salary_range(self):
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("最低薪资不能高于最高薪资")
        return self


class JobIntentResponse(BaseModel):
    ok: bool
    intent: JobIntentResult | None = None
    error: str | None = None
    error_code: str | None = None


INTENT_SYSTEM_PROMPT = """你是OfferForge岗位采集前的求职意向提取助手。

【任务】
从用户输入中提取目标岗位、目标城市、月薪下限、月薪上限和限制条件；只整理意向，不替用户确认，也不启动岗位采集。

【输入】
用户提交的一段求职意向原文。原文可能包含不确定、缺失或相互冲突的信息。

【规则】
1. 只能提取原文明确表达的内容，不得根据简历、常识或市场行情补充。
2. 保留“不确定、考虑、可能、最好”等语义；把它们写进restrictions，不得改成确定事实。
3. 月薪统一换算为人民币元整数；8k表示8000，1万表示10000。
4. 不得替用户确认意向，不得承诺岗位或薪资。

【示例】
输入：想在广州找AI产品助理，月薪8k到10k，不接受长期出差。
输出：{"position":"AI产品助理","city":"广州","salary_min":8000,"salary_max":10000,"restrictions":["不接受长期出差"]}

【输出】
只返回JSON对象，字段固定为position、city、salary_min、salary_max、restrictions。岗位和城市缺失时返回空字符串；薪资缺失时返回null；限制条件缺失时返回空列表；不得增加其他字段。

【失败行为】
信息缺失时保持对应空值；薪资范围冲突时保留原始顺序，由程序提示用户确认；输入与求职无关时所有字段返回空值，禁止猜测。
"""


def _build_draft(payload: dict, source_text: str) -> JobIntentResult:
    data = JobIntentData.model_validate(payload)
    missing_fields = []
    warnings = []

    if not data.position:
        missing_fields.append("position")
    if not data.city:
        missing_fields.append("city")
    if data.salary_min is None or data.salary_max is None:
        missing_fields.append("salary")
    elif data.salary_min > data.salary_max:
        warnings.append("最低薪资高于最高薪资，请确认后修改")

    return JobIntentResult(
        **data.model_dump(),
        status="needs_confirmation",
        missing_fields=missing_fields,
        warnings=warnings,
        source_text=source_text,
    )


def extract_job_intent(
    intent_text: str,
    client_factory=DeepSeekClient,
) -> dict:
    try:
        client = client_factory()
        payload = client.chat_json(INTENT_SYSTEM_PROMPT, intent_text)
        if not isinstance(payload, dict) or "error" in payload:
            return {
                "ok": False,
                "error": "AI求职意向提取失败，请稍后重试或手动填写",
                "error_code": "UPSTREAM_ERROR",
            }
        draft = _build_draft(payload, intent_text)
        return {"ok": True, "intent": draft.model_dump()}
    except ValidationError:
        return {
            "ok": False,
            "error": "AI返回的求职意向格式不正确，请重试或手动填写",
            "error_code": "UPSTREAM_ERROR",
        }
    except Exception:
        return {
            "ok": False,
            "error": "AI求职意向提取失败，请稍后重试或手动填写",
            "error_code": "UPSTREAM_ERROR",
        }


def confirm_job_intent(request: JobIntentConfirmRequest) -> dict:
    confirmed = JobIntentResult(
        **request.model_dump(),
        status="confirmed",
        missing_fields=[],
        warnings=[],
        confirmed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return {"ok": True, "intent": confirmed.model_dump()}

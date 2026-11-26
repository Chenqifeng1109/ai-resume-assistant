"""普通接口参数的公共校验和统一错误格式。"""

import re
from collections.abc import Iterable
from urllib.parse import urlparse


def validation_error(field: str, message: str) -> dict:
    """返回前端兼容的统一参数错误。"""
    return {
        "ok": False,
        "error": message,
        "error_code": "INVALID_INPUT",
        "field": field,
    }


def validate_text(
    value,
    field: str,
    *,
    required: bool = False,
    min_length: int = 0,
    max_length: int = 2000,
) -> tuple[str | None, dict | None]:
    """校验字符串类型和长度，并去掉首尾空白。"""
    if not isinstance(value, str):
        return None, validation_error(field, f"{field}必须是文本")

    normalized = value.strip()
    if required and not normalized:
        return None, validation_error(field, f"{field}不能为空")
    if normalized and len(normalized) < min_length:
        return None, validation_error(
            field,
            f"{field}不能少于{min_length}个字符",
        )
    if len(normalized) > max_length:
        return None, validation_error(
            field,
            f"{field}不能超过{max_length}个字符",
        )
    return normalized, None


def validate_integer(
    value,
    field: str,
    *,
    minimum: int,
    maximum: int,
) -> tuple[int | None, dict | None]:
    """校验整数及其允许范围。"""
    if isinstance(value, bool):
        return None, validation_error(field, f"{field}必须是整数")

    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        parsed = int(value.strip())
    else:
        return None, validation_error(field, f"{field}必须是整数")

    if parsed < minimum or parsed > maximum:
        return None, validation_error(
            field,
            f"{field}必须在{minimum}到{maximum}之间",
        )
    return parsed, None


def validate_choice(
    value,
    field: str,
    allowed_values: Iterable[str],
) -> tuple[str | None, dict | None]:
    """校验一个值是否属于白名单。"""
    normalized, error = validate_text(value, field, required=True, max_length=100)
    if error:
        return None, error

    allowed = set(allowed_values)
    if normalized not in allowed:
        return None, validation_error(
            field,
            f"{field}不是允许的值",
        )
    return normalized, None


def validate_csv_choices(
    value,
    field: str,
    allowed_values: Iterable[str],
) -> tuple[list[str] | None, dict | None]:
    """校验逗号分隔的白名单选项，并拒绝空项和重复项。"""
    normalized, error = validate_text(value, field, required=True, max_length=200)
    if error:
        return None, error

    choices = [item.strip() for item in normalized.split(",")]
    allowed = set(allowed_values)
    if any(not item or item not in allowed for item in choices):
        return None, validation_error(
            field,
            f"{field}包含不支持的选项",
        )
    if len(choices) != len(set(choices)):
        return None, validation_error(
            field,
            f"{field}不能包含重复项",
        )
    return choices, None


def parse_index_list(
    value,
    field: str = "job_indices",
    *,
    maximum_items: int = 20,
) -> tuple[list[int] | None, dict | None]:
    """校验逗号分隔的非负整数索引。"""
    normalized, error = validate_text(value, field, required=True, max_length=200)
    if error:
        return None, error

    parts = [item.strip() for item in normalized.split(",")]
    if any(not item or not item.isdigit() for item in parts):
        return None, validation_error(
            field,
            f"{field}只能包含逗号分隔的非负整数",
        )

    indices = [int(item) for item in parts]
    if len(indices) > maximum_items:
        return None, validation_error(
            field,
            f"{field}一次最多选择{maximum_items}个岗位",
        )
    if len(indices) != len(set(indices)):
        return None, validation_error(
            field,
            f"{field}不能包含重复索引",
        )
    return indices, None


def validate_http_url(
    value,
    field: str = "url",
) -> tuple[str | None, dict | None]:
    """只接受长度合理的HTTP或HTTPS网址。"""
    normalized, error = validate_text(
        value,
        field,
        required=True,
        max_length=2048,
    )
    if error:
        return None, error

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, validation_error(
            field,
            f"{field}必须是有效的HTTP或HTTPS网址",
        )
    return normalized, None

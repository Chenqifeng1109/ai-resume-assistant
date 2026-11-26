"""OfferForge API 的统一错误正文、HTTP 状态码和异常处理。"""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response


LOGGER = logging.getLogger(__name__)

ERROR_STATUS_BY_CODE = {
    "INVALID_INPUT": 400,
    "BAD_REQUEST": 400,
    "CONFIG_MISSING": 400,
    "ACCESS_TOKEN_REQUIRED": 401,
    "INVALID_TOKEN": 401,
    "AUTH_FAILED": 401,
    "INSUFFICIENT_BALANCE": 402,
    "PUBLIC_MODE_RESTRICTED": 403,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "REQUEST_VALIDATION_ERROR": 422,
    "UNPROCESSABLE_CONTENT": 422,
    "RESUME_SCHEMA_INVALID": 422,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
    "UPSTREAM_ERROR": 502,
    "TIMEOUT": 504,
}

NOT_FOUND_MARKERS = (
    "不存在",
    "没有找到",
    "找不到",
    "数据库中没有",
    "file not found",
)
CONFLICT_MARKERS = (
    "正在进行",
    "还未进行",
    "评分对象是",
    "已经投递",
    "已投递",
    "重复",
)
UPSTREAM_MARKERS = (
    "ai调用失败",
    "ai响应解析失败",
    "大模型 api",
    "余额不足",
    "请求过于频繁",
    "响应超时",
    "生成失败",
)
UNPROCESSABLE_MARKERS = (
    "解析失败",
)
BAD_REQUEST_MARKERS = (
    "缺少",
    "未配置",
    "api 密钥",
    "密钥无效",
    "不能为空",
    "必须",
    "不能",
    "不安全",
    "仅支持",
    "请先",
    "请指定",
    "为空",
    "没有已解析",
    "无法从简历",
    "missing photo",
    "不是允许",
    "不支持",
)


def _contains(message: str, markers: tuple[str, ...]) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in markers)


def classify_error(payload: dict, status_hint: int = 200) -> tuple[str, int]:
    """为旧Service错误补上稳定错误码，并映射为HTTP状态。"""
    explicit_code = payload.get("error_code")
    if explicit_code in ERROR_STATUS_BY_CODE:
        return explicit_code, ERROR_STATUS_BY_CODE[explicit_code]

    if status_hint >= 400:
        status_codes = {
            400: "BAD_REQUEST",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "REQUEST_VALIDATION_ERROR",
            500: "INTERNAL_ERROR",
            502: "UPSTREAM_ERROR",
        }
        code = status_codes.get(status_hint, "HTTP_ERROR")
        return code, status_hint

    message = str(payload.get("error", ""))
    if _contains(message, NOT_FOUND_MARKERS):
        return "NOT_FOUND", 404
    if _contains(message, CONFLICT_MARKERS):
        return "CONFLICT", 409
    if _contains(message, UPSTREAM_MARKERS):
        return "UPSTREAM_ERROR", 502
    if _contains(message, UNPROCESSABLE_MARKERS):
        return "UNPROCESSABLE_CONTENT", 422
    if _contains(message, BAD_REQUEST_MARKERS):
        return "BAD_REQUEST", 400
    return "INTERNAL_ERROR", 500


def build_error_response(payload: dict, status_hint: int = 200) -> JSONResponse:
    """保留旧的ok/error字段，同时补齐商业API需要的错误码。"""
    error_code, status_code = classify_error(payload, status_hint)
    normalized = dict(payload)
    normalized["ok"] = False
    normalized["error_code"] = error_code
    if error_code == "INTERNAL_ERROR":
        normalized["error"] = "服务器内部错误"
    elif not normalized.get("error"):
        normalized["error"] = "请求失败"
    return JSONResponse(content=normalized, status_code=status_code)


def normalize_api_response(response: Response) -> Response:
    """只转换JSON错误；成功、HTML、文件下载等响应保持原样。"""
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return response

    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return response

    if not isinstance(payload, dict):
        return response
    if payload.get("ok") is not False and "error" not in payload:
        return response
    return build_error_response(payload, response.status_code)


class UnifiedAPIRoute(APIRoute):
    """让路由自动使用统一错误合同，无需在每个函数重复包装。"""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def unified_handler(request: Request) -> Response:
            response = await original_handler(request)
            return normalize_api_response(response)

        return unified_handler


def register_api_exception_handlers(app: FastAPI) -> None:
    """注册框架校验、HTTP错误和未捕获异常的统一响应。"""

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        details = []
        for item in exception.errors():
            field_parts = [
                str(part)
                for part in item.get("loc", ())
                if part not in {"body", "query", "path", "header", "cookie"}
            ]
            details.append(
                {
                    "field": ".".join(field_parts),
                    "message": item.get("msg", "参数不合法"),
                    "type": item.get("type", "validation_error"),
                }
            )
        field = details[0]["field"] if details else "request"
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error": "请求参数校验失败",
                "error_code": "REQUEST_VALIDATION_ERROR",
                "field": field,
                "details": details,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exception: StarletteHTTPException,
    ) -> JSONResponse:
        message = (
            exception.detail
            if isinstance(exception.detail, str)
            else "HTTP请求失败"
        )
        return build_error_response(
            {"ok": False, "error": message},
            exception.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        LOGGER.exception("Unhandled API error on %s", request.url.path, exc_info=exception)
        return build_error_response(
            {
                "ok": False,
                "error": "服务器内部错误",
                "error_code": "INTERNAL_ERROR",
            }
        )

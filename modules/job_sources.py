"""Explicit source capabilities; registration is not live-site verification."""
from dataclasses import dataclass

from modules.official_job_sources import OFFICIAL_ADAPTERS


@dataclass(frozen=True)
class JobSource:
    code: str
    name: str
    aliases: tuple[str, ...]
    handler: str | None
    implementation_status: str
    verification_status: str = "not_verified"
    session_status: str = "unknown"
    official_entry: str | None = None
    category: str = "browser_legacy"


SOURCES = (
    JobSource("51job", "前程无忧", ("51job", "51前程无忧", "前程无忧"),
              "search_51job", "implemented", "simulation_passed"),
    JobSource("boss", "BOSS直聘", ("boss", "boss直聘", "BOSS直聘"),
              None, "manual_assist", "official_entry_verified",
              official_entry="https://www.zhipin.com/", category="manual_assist"),
    JobSource("zhilian", "智联招聘", ("zhilian", "智联", "智联招聘"),
              None, "manual_assist", "official_entry_verified",
              official_entry="https://sou.zhaopin.com/", category="manual_assist"),
    JobSource("liepin", "猎聘（智能浏览器测试版）", ("liepin", "猎聘"),
              "browser_use", "browser_use_beta", "not_verified"),
    *(
        JobSource(
            adapter.meta.code,
            adapter.meta.name,
            adapter.meta.aliases,
            "official_http",
            "official_http",
            "http_probe_verified",
            "not_required",
            official_entry=adapter.meta.official_entry,
            category=adapter.meta.category,
        )
        for adapter in OFFICIAL_ADAPTERS.values()
    ),
)


OFFICIAL_CITY_ENTRIES = {
    ("boss", "广州"): "https://www.zhipin.com/guangzhou/",
}


def resolve_sources(values):
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("请至少选择一个招聘来源")
    resolved = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("招聘来源必须为字符串")
        source = next((item for item in SOURCES if value.strip().lower() in item.aliases), None)
        if source is None:
            raise ValueError("不支持的招聘来源")
        if source.handler is None:
            if source.implementation_status == "manual_assist":
                raise ValueError(f"{source.name}仅支持人工辅助搜索，不支持自动采集")
            raise ValueError(f"{source.name}尚未实现采集，请选择其他来源")
        if source not in resolved:
            resolved.append(source)
    return resolved


def list_source_capabilities():
    return [{
        "code": item.code,
        "name": item.name,
        "can_attempt_search": item.handler is not None,
        "implementation_status": item.implementation_status,
        "verification_status": item.verification_status,
        "session_status": item.session_status,
        "session_persistence": item.code == "51job",
        "interactive_login": item.code == "51job",
        "access_mode": (
            "official_http" if item.implementation_status == "official_http" else
            "browser_use_beta" if item.implementation_status == "browser_use_beta" else
            "automatic" if item.handler is not None else
            "manual_assist" if item.implementation_status == "manual_assist" else "unavailable"
        ),
        "category": item.category,
        "official_entry": item.official_entry,
        "city_configuration_status": (
            "configured_not_live_verified" if item.code == "51job" else
            "manual_guangzhou_verified" if item.code == "boss" else
            "adapter_validates_result_city" if item.implementation_status == "official_http" else
            "agent_validates_result_city"
        ),
    } for item in SOURCES]


def build_official_search_handoff(source_code, position, city):
    """Return a user-operated official entry; this does not scrape or copy site data."""
    source = next((item for item in SOURCES if item.code == source_code), None)
    if source is None or source.implementation_status != "manual_assist":
        raise ValueError("该来源不支持人工辅助搜索")
    normalized_city = city.strip().removesuffix("市")
    default_entry = source.official_entry or "https://www.zhipin.com/"
    official_url = OFFICIAL_CITY_ENTRIES.get((source.code, normalized_city), default_entry)
    city_verified = (source.code, normalized_city) in OFFICIAL_CITY_ENTRIES
    return {
        "source": source.code,
        "source_name": source.name,
        "official_url": official_url,
        "search_term": position.strip(),
        "target_city": normalized_city,
        "city_entry_verified": city_verified,
        "message": (
            f"已生成{normalized_city}官方入口，请在{source.name}页面搜索“{position.strip()}”"
            if city_verified else
            f"尚未核实{normalized_city}独立入口，请在{source.name}首页手动选城市后搜索“{position.strip()}”"
        ),
    }

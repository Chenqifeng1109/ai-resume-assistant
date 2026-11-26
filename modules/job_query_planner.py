"""Bounded, explainable query suggestions. It never launches a scraper."""

ROLE_GROUPS = (
    (("AI产品", "人工智能产品", "AIGC产品"), ("AI产品助理", "AI产品专员", "AI产品运营")),
    (("新媒体", "内容运营"), ("新媒体运营", "内容运营", "社媒运营")),
    (("数据分析", "数据运营"), ("数据分析助理", "数据运营", "商业分析助理")),
    (("电商运营", "电商"), ("电商运营", "平台运营", "商品运营")),
)

JD_ROLE_HINTS = (
    (("用户研究", "需求分析", "产品原型"), "产品助理"),
    (("内容策划", "账号运营", "短视频"), "内容运营"),
    (("SQL", "数据看板", "指标体系"), "数据运营"),
)


def suggest_related_queries(position, jd_text="", max_related=4):
    primary = str(position or "").strip()
    limit = max(0, min(int(max_related), 4))
    suggestions = []

    def add(query, reason):
        query = str(query).strip()
        if query and query != primary and all(item["query"] != query for item in suggestions):
            suggestions.append({"query": query, "reason": reason})

    for triggers, roles in ROLE_GROUPS:
        if any(trigger in primary for trigger in triggers):
            for role in roles:
                add(role, f"与目标岗位“{primary}”属于同一岗位族")

    jd = str(jd_text or "")
    for evidence_terms, role in JD_ROLE_HINTS:
        matched = [term for term in evidence_terms if term.lower() in jd.lower()]
        if matched:
            add(role, f"JD出现：{'、'.join(matched)}")

    return {"primary": primary, "related": suggestions[:limit], "max_related": 4}

"""求职限制条件「避坑红绿灯」核查引擎（纯确定性 + 原文证据溯源，零幻觉、零额外 Token）。

将用户在步骤 4 / 步骤 5 填写的个人底线（如：双休、五险一金、不接受外包、不接受长期出差）
与目标岗位 JD 原文逐条比对，输出：
- green  : 明确满足（命中正向原文证据）
- red    : 疑似踩雷（命中反向/冲突原文证据）
- yellow : JD 未提及（建议面试反问确认）
"""

from __future__ import annotations

import re


_RULE_DEFINITIONS = [
    {
        "triggers": ("双休", "周末双休", "不接受单休", "不接受大小周", "拒绝大小周", "拒绝单休"),
        "green": ("双休", "周末双休", "做五休二", "五天八小时", "5天8小时", "周六日双休", "标准工时"),
        "red": ("大小周", "单休", "单双休", "月休4天", "月休四天", "月休2天", "排班倒休", "轮休", "六天工作制"),
    },
    {
        "triggers": ("五险一金", "六险一金", "社保", "公积金", "全额公积金"),
        "green": ("五险一金", "六险一金", "七险一金", "六险二金", "足额公积金", "全额五险一金", "缴纳社保公积金", "入职即缴"),
        "red": ("无公积金", "不缴公积金", "无五险", "不买社保", "仅五险", "试用期不交社保", "试用期不缴社保"),
    },
    {
        "triggers": ("不接受外包", "不要外包", "拒绝外包", "非外包", "不外包", "正式编制", "直签"),
        "green": ("正式员工", "公司直签", "非外包", "自研岗位", "正式编制", "事业编", "国企直签"),
        "red": ("外包", "驻场", "劳务派遣", "人力外包", "第三方签约", "外派驻场", "OD岗位", "德科"),
    },
    {
        "triggers": ("不接受出差", "不接受长期出差", "不出差", "不要出差", "拒绝出差", "少出差"),
        "green": ("无需出差", "不出差", "无出差", "不用出差"),
        "red": ("长期出差", "频繁出差", "经常出差", "能接受出差", "适应出差", "全国出差", "驻外", "短期出差"),
    },
    {
        "triggers": ("不加班", "不接受加班", "拒绝加班", "不接受996", "拒绝996", "朝九晚五"),
        "green": ("不加班", "极少加班", "准点下班", "朝九晚五", "朝九晚六", "弹性打卡", "弹性工作", "拒绝内卷"),
        "red": ("996", "995", "高强度加班", "能接受加班", "接受弹性加班", "抗压加班", "通宵"),
    },
    {
        "triggers": ("不接受夜班", "不上夜班", "不要夜班", "不倒班", "不接受倒班", "白班"),
        "green": ("纯白班", "无夜班", "不倒班", "常白班"),
        "red": ("夜班", "两班倒", "三班倒", "轮班", "通宵班", "晚班"),
    },
    {
        "triggers": ("不接受销售", "不做销售", "拒绝销售", "不接受电销", "不要电销", "纯技术"),
        "green": ("非销售", "无销售性质", "不做电销"),
        "red": ("电话销售", "电销", "陌拜", "地推", "业绩指标", "拉新业绩", "外呼销售"),
    },
    {
        "triggers": ("远程", "居家办公", "可远程", "混合办公"),
        "green": ("远程办公", "居家办公", "混合办公", "可远程", "wfh", "remote"),
        "red": ("全职坐班", "必须坐班", "不支持远程", "线下坐班"),
    },
    {
        "triggers": ("弹性", "弹性打卡", "不打卡"),
        "green": ("弹性工作", "弹性打卡", "不打卡", "弹性上下班"),
        "red": ("严格考勤", "军事化管理"),
    },
    {
        "triggers": ("包吃", "包住", "包吃住", "餐补", "房补", "交通补贴"),
        "green": ("包吃", "包住", "包吃住", "免费三餐", "员工食堂", "餐补", "房补", "住宿补贴", "提供宿舍", "交通补贴"),
        "red": ("不包吃住", "无餐补", "无住宿"),
    },
]

_NEGATIVE_PREFIXES = ("不接受", "不要", "拒绝", "不能接受", "非", "不希望", "避免", "不做", "不上", "不出")


def normalize_restrictions(raw) -> list[str]:
    """把换行/逗号字符串或列表清洗为去重后的限制条件数组。"""
    if not raw:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[\r\n,，;；、]+", raw)
    elif isinstance(raw, list):
        parts = [str(item) for item in raw]
    else:
        return []
    cleaned = []
    seen = set()
    for part in parts:
        token = str(part or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token[:80])
        if len(cleaned) >= 20:
            break
    return cleaned


def _extract_snippet(text: str, keyword: str, window: int = 24) -> str:
    lower_text = text.lower()
    idx = lower_text.find(keyword.lower())
    if idx < 0:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end].replace("\n", " ").replace("\r", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def _first_hit(text: str, keywords: tuple[str, ...]) -> tuple[str, str]:
    lower_text = text.lower()
    for kw in keywords:
        if kw.lower() in lower_text:
            return kw, _extract_snippet(text, kw)
    return "", ""


def evaluate_restrictions_against_jd(restrictions, jd_text: str) -> dict:
    """逐条核查个人限制条件与 JD 原文，返回红绿灯明细与汇总统计。"""
    clean_list = normalize_restrictions(restrictions)
    text = str(jd_text or "").strip()
    items = []

    for rule_text in clean_list:
        matched_rule = None
        for rule in _RULE_DEFINITIONS:
            if any(trigger in rule_text for trigger in rule["triggers"]):
                matched_rule = rule
                break

        status = "yellow"
        label = "未提及（建议面试确认）"
        evidence = ""

        if matched_rule:
            red_kw, red_snip = _first_hit(text, matched_rule["red"])
            green_kw, green_snip = _first_hit(text, matched_rule["green"])
            if red_kw and not (green_kw and ("无" + red_kw in green_kw or "不" + red_kw in green_kw or "非" + red_kw in green_kw)):
                status = "red"
                label = f"疑似踩雷（命中「{red_kw}」）"
                evidence = red_snip
            elif green_kw:
                status = "green"
                label = f"明确满足（命中「{green_kw}」）"
                evidence = green_snip
        else:
            # 通用兜底匹配：处理“不接受XX”反向词与普通正向关键词
            neg_core = ""
            for prefix in _NEGATIVE_PREFIXES:
                if rule_text.startswith(prefix) and len(rule_text) > len(prefix):
                    neg_core = rule_text[len(prefix):].strip()
                    break
            if neg_core and len(neg_core) >= 2:
                if f"无{neg_core}" in text or f"不{neg_core}" in text or f"非{neg_core}" in text:
                    status = "green"
                    label = f"明确满足（不含「{neg_core}」）"
                    evidence = _extract_snippet(text, neg_core)
                elif neg_core.lower() in text.lower():
                    status = "red"
                    label = f"疑似踩雷（原文出现「{neg_core}」）"
                    evidence = _extract_snippet(text, neg_core)
            elif len(rule_text) >= 2 and rule_text.lower() in text.lower():
                status = "green"
                label = f"明确满足（原文命中「{rule_text}」）"
                evidence = _extract_snippet(text, rule_text)

        items.append(
            {
                "restriction": rule_text,
                "status": status,
                "label": label,
                "evidence": evidence,
            }
        )

    green_count = sum(1 for item in items if item["status"] == "green")
    yellow_count = sum(1 for item in items if item["status"] == "yellow")
    red_count = sum(1 for item in items if item["status"] == "red")

    return {
        "items": items,
        "summary": {
            "total": len(items),
            "green": green_count,
            "yellow": yellow_count,
            "red": red_count,
        },
    }

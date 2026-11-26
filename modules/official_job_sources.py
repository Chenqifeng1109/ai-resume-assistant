"""可扩展的权威官方/公共招聘开放源统一适配器引擎（纯 HTTP，无登录无验证码）。

新增权威官方源只需继承 OfficialJobAdapter 并注册到 OFFICIAL_ADAPTERS，
即可自动接入任务调度、进度回报、去重排序与 SQLite 入库。
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 12.0


class OfficialSourceError(RuntimeError):
    """开放官方招聘源拉取失败异常。"""

    def __init__(self, source: str, code: str, message: str):
        super().__init__(message)
        self.source = source
        self.code = code
        self.message = message


def _build_direct_opener() -> urllib.request.OpenerDirector:
    """显式绕过本机代理的 HTTPS opener，避免本机代理造成 502 假异常。"""
    ctx = ssl.create_default_context()
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ctx),
    )


def _strip_html(raw: Any) -> str:
    text = str(raw or "")
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _normalize_city(city: str) -> str:
    return (city or "").strip().removesuffix("市")


# 全国主要城市 GB/T 2260 行政区划与所属省份映射：(6位市码, 6位省码, 省级简称)
CITY_GEO_TABLE: dict[str, tuple[str, str, str]] = {
    "北京": ("110100", "110000", "北京"),
    "天津": ("120100", "120000", "天津"),
    "上海": ("310100", "310000", "上海"),
    "重庆": ("500100", "500000", "重庆"),
    "石家庄": ("130100", "130000", "河北"),
    "唐山": ("130200", "130000", "河北"),
    "保定": ("130600", "130000", "河北"),
    "太原": ("140100", "140000", "山西"),
    "呼和浩特": ("150100", "150000", "内蒙古"),
    "沈阳": ("210100", "210000", "辽宁"),
    "大连": ("210200", "210000", "辽宁"),
    "长春": ("220100", "220000", "吉林"),
    "哈尔滨": ("230100", "230000", "黑龙江"),
    "南京": ("320100", "320000", "江苏"),
    "无锡": ("320200", "320000", "江苏"),
    "徐州": ("320300", "320000", "江苏"),
    "常州": ("320400", "320000", "江苏"),
    "苏州": ("320500", "320000", "江苏"),
    "南通": ("320600", "320000", "江苏"),
    "盐城": ("320900", "320000", "江苏"),
    "扬州": ("321000", "320000", "江苏"),
    "镇江": ("321100", "320000", "江苏"),
    "杭州": ("330100", "330000", "浙江"),
    "宁波": ("330200", "330000", "浙江"),
    "温州": ("330300", "330000", "浙江"),
    "嘉兴": ("330400", "330000", "浙江"),
    "湖州": ("330500", "330000", "浙江"),
    "绍兴": ("330600", "330000", "浙江"),
    "金华": ("330700", "330000", "浙江"),
    "台州": ("331000", "330000", "浙江"),
    "合肥": ("340100", "340000", "安徽"),
    "芜湖": ("340200", "340000", "安徽"),
    "福州": ("350100", "350000", "福建"),
    "厦门": ("350200", "350000", "福建"),
    "泉州": ("350500", "350000", "福建"),
    "漳州": ("350600", "350000", "福建"),
    "南昌": ("360100", "360000", "江西"),
    "济南": ("370100", "370000", "山东"),
    "青岛": ("370200", "370000", "山东"),
    "淄博": ("370300", "370000", "山东"),
    "烟台": ("370600", "370000", "山东"),
    "潍坊": ("370700", "370000", "山东"),
    "临沂": ("371300", "370000", "山东"),
    "郑州": ("410100", "410000", "河南"),
    "洛阳": ("410300", "410000", "河南"),
    "南阳": ("411300", "410000", "河南"),
    "武汉": ("420100", "420000", "湖北"),
    "宜昌": ("420500", "420000", "湖北"),
    "襄阳": ("420600", "420000", "湖北"),
    "长沙": ("430100", "430000", "湖南"),
    "株洲": ("430200", "430000", "湖南"),
    "湘潭": ("430300", "430000", "湖南"),
    "衡阳": ("430400", "430000", "湖南"),
    "岳阳": ("430600", "430000", "湖南"),
    "广州": ("440100", "440000", "广东"),
    "深圳": ("440300", "440000", "广东"),
    "珠海": ("440400", "440000", "广东"),
    "佛山": ("440600", "440000", "广东"),
    "惠州": ("441300", "440000", "广东"),
    "东莞": ("441900", "440000", "广东"),
    "中山": ("442000", "440000", "广东"),
    "南宁": ("450100", "450000", "广西"),
    "柳州": ("450200", "450000", "广西"),
    "桂林": ("450300", "450000", "广西"),
    "海口": ("460100", "460000", "海南"),
    "三亚": ("460200", "460000", "海南"),
    "成都": ("510100", "510000", "四川"),
    "绵阳": ("510700", "510000", "四川"),
    "宜宾": ("511500", "510000", "四川"),
    "贵阳": ("520100", "520000", "贵州"),
    "昆明": ("530100", "530000", "云南"),
    "拉萨": ("540100", "540000", "西藏"),
    "西安": ("610100", "610000", "陕西"),
    "兰州": ("620100", "620000", "甘肃"),
    "西宁": ("630100", "630000", "青海"),
    "银川": ("640100", "640000", "宁夏"),
    "乌鲁木齐": ("650100", "650000", "新疆"),
}


def get_city_geo(city: str) -> tuple[str, str, str] | None:
    """查询目标城市对应的 (6位市码, 6位省码, 省级简称)。"""
    return CITY_GEO_TABLE.get(_normalize_city(city))


def is_province_level_match(location_text: str, target_city: str) -> bool:
    """当官方接口仅返回省级名称（如 '广东'、'广东省'）时，核验其是否与目标城市同省。"""
    geo = get_city_geo(target_city)
    if not geo:
        return False
    _, _, prov_short = geo
    cleaned = (location_text or "").strip()
    for suffix in ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "省", "市"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return bool(cleaned) and cleaned == prov_short


def _city_hit(location_text: str, target_city: str) -> bool:
    """严格核验岗位地点是否命中目标城市，拒绝跨城岗位。"""
    target = _normalize_city(target_city)
    if not target:
        return True
    loc = (location_text or "").strip()
    if not loc:
        return False
    return target in loc


def official_location_matches_city(location_text: str, target_city: str) -> bool:
    """核验官方开放源的岗位地点（兼容多城市拼接、省·市格式及同省省级标注）。"""
    target = _normalize_city(target_city)
    if not target:
        return True
    loc = str(location_text or "").strip()
    if not loc:
        return False
    parts = [p.strip() for p in re.split(r"[/、,，;；|]+", loc) if p.strip()]
    for part in parts:
        if target in part or is_province_level_match(part, target):
            return True
    return False


def _stable_job_id(source: str, raw_id: Any, title: str, company: str, location: str) -> str:
    if raw_id is not None and str(raw_id).strip():
        return f"{source}_{str(raw_id).strip()}"
    seed = f"{source}|{title}|{company}|{location}".encode("utf-8")
    return f"{source}_{hashlib.sha1(seed).hexdigest()[:12]}"


@dataclass(frozen=True)
class OfficialSourceMeta:
    code: str
    name: str
    aliases: tuple[str, ...]
    official_entry: str
    coverage: str
    category: str = "public_open"


class OfficialJobAdapter:
    """权威官方招聘源适配器基类。"""

    meta: OfficialSourceMeta

    def fetch_raw_items(
        self,
        keyword: str,
        city: str,
        page: int,
        page_size: int,
        opener: urllib.request.OpenerDirector,
        timeout: float,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def parse_item(
        self,
        item: dict[str, Any],
        keyword: str,
        target_city: str,
        relation_type: str,
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def _request_json(
        self,
        opener: urllib.request.OpenerDirector,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        referer: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        }
        if referer:
            headers["Referer"] = referer
        data_bytes = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except TimeoutError as exc:
            raise OfficialSourceError(
                self.meta.code, "TIMEOUT", f"{self.meta.name}接口响应超时"
            ) from exc
        except Exception as exc:
            raise OfficialSourceError(
                self.meta.code,
                "REQUEST_FAILED",
                f"{self.meta.name}接口请求失败: {str(exc)[:120]}",
            ) from exc


class IguopinAdapter(OfficialJobAdapter):
    """国聘网（央视频/国投人力主办，央企国企与全行业权威综合平台）。"""

    meta = OfficialSourceMeta(
        code="iguopin",
        name="国聘网（央企/全行业）",
        aliases=("iguopin", "国聘", "国聘网"),
        official_entry="https://www.iguopin.com/job",
        coverage="央企、国企、科研院所、制造、金融、运营、技术全行业",
        category="job_platform",
    )

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        payload: dict[str, Any] = {
            "page": page,
            "page_size": max(page_size, 20),
            "keyword": keyword,
        }
        geo = get_city_geo(city)
        if geo:
            city_code, prov_code, _ = geo
            payload["district"] = [f"000000.{prov_code}.{city_code}"]
        data = self._request_json(
            opener,
            "POST",
            "https://gp-api.iguopin.com/api/jobs/v1/list",
            payload=payload,
            referer="https://www.iguopin.com/job",
            timeout=timeout,
        )
        if not isinstance(data, dict):
            return []
        return list((data.get("data") or {}).get("list") or [])

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("job_name") or "").strip()
        company = str(item.get("company_name") or "").strip()
        if not title or not company:
            return None

        districts = item.get("district_list") or []
        city_names = []
        for dist in districts:
            if isinstance(dist, dict):
                area = str(dist.get("area_cn") or "").strip()
                if area and area not in city_names:
                    city_names.append(area)
        location = " / ".join(city_names) if city_names else ""
        if target_city and not _city_hit(location, target_city):
            return None

        min_w = item.get("min_wage") or 0
        max_w = item.get("max_wage") or 0
        if min_w or max_w:
            low_k = round(float(min_w) / 1000, 1) if float(min_w) >= 1000 else min_w
            high_k = round(float(max_w) / 1000, 1) if float(max_w) >= 1000 else max_w
            salary = f"{low_k}k-{high_k}k"
        else:
            salary = "面议"

        desc_text = _strip_html(item.get("contents"))
        tags = [
            str(v).strip()
            for v in (
                item.get("recruitment_type_cn"),
                item.get("education_cn"),
                item.get("experience_cn"),
                item.get("category_cn"),
            )
            if v and str(v).strip()
        ]
        job_id_raw = item.get("job_id")
        url = (
            f"https://www.iguopin.com/job/detail?id={job_id_raw}"
            if job_id_raw
            else self.meta.official_entry
        )
        return {
            "job_id": _stable_job_id(self.meta.code, job_id_raw, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": salary,
            "description": desc_text or f"{title} - {company}（详见国聘网官方岗位页）",
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("refresh_time") or item.get("update_time") or ""),
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class NcssAdapter(OfficialJobAdapter):
    """国家大学生就业服务平台 / 24365（教育部主办，全专业全行业权威平台）。"""

    meta = OfficialSourceMeta(
        code="ncss",
        name="国家24365平台（全行业）",
        aliases=("ncss", "24365", "国家24365", "国家大学生就业服务平台"),
        official_entry="https://www.ncss.cn/student/jobs/index.html",
        coverage="金融、教育、消费、运营、管理、研发等全专业全行业",
        category="gov_official",
    )

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        params: dict[str, Any] = {
            "jobName": keyword,
            "limit": max(page_size, 20),
            "offset": page,
        }
        geo = get_city_geo(city)
        if geo:
            params["areaCode"] = geo[0]
        qs = urllib.parse.urlencode(params)
        url = f"https://www.ncss.cn/student/jobs/jobslist/ajax/?{qs}"
        data = self._request_json(
            opener,
            "GET",
            url,
            referer="https://www.ncss.cn/student/jobs/index.html",
            timeout=timeout,
        )
        if not isinstance(data, dict):
            return []
        return list((data.get("data") or {}).get("list") or [])

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("jobName") or "").strip()
        company = str(item.get("recName") or "").strip()
        if not title or not company:
            return None

        location = str(item.get("areaCodeName") or "").strip()
        if target_city:
            if _city_hit(location, target_city):
                pass
            elif is_province_level_match(location, target_city):
                location = f"{location}·{_normalize_city(target_city)}"
            else:
                return None

        low = item.get("lowMonthPay")
        high = item.get("highMonthPay")
        if low and high:
            salary = f"{int(low) if float(low).is_integer() else low}k-{int(high) if float(high).is_integer() else high}k"
        elif low:
            salary = f"{low}k以上"
        else:
            salary = "面议"

        parts = []
        if item.get("degreeName"):
            parts.append(f"学历要求：{item['degreeName']}")
        if item.get("major"):
            parts.append(f"专业方向：{item['major']}")
        if item.get("recProperty"):
            parts.append(f"单位性质：{item['recProperty']}")
        if item.get("recScale"):
            parts.append(f"企业规模：{item['recScale']}")
        if item.get("sourcesNameCh"):
            parts.append(f"发布渠道：{item['sourcesNameCh']}")
        description = "；".join(parts) or f"{title} - {company}"

        tags = [
            str(v).strip()
            for v in (item.get("degreeName"), item.get("recProperty"), item.get("recScale"))
            if v and str(v).strip()
        ]
        job_id_raw = item.get("jobId")
        url = (
            f"https://www.ncss.cn/student/jobs/{job_id_raw}/detail.html"
            if job_id_raw
            else self.meta.official_entry
        )
        return {
            "job_id": _stable_job_id(self.meta.code, job_id_raw, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": salary,
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("publishDate") or item.get("updateDate") or ""),
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class MeituanAdapter(OfficialJobAdapter):
    """美团官方招聘（覆盖技术、产品、运营、零售、采购、职能等多领域全职业）。"""

    meta = OfficialSourceMeta(
        code="meituan",
        name="美团官方招聘（全职业）",
        aliases=("meituan", "美团", "美团招聘", "美团官方招聘"),
        official_entry="https://zhaopin.meituan.com/web/social",
        coverage="技术、产品、运营、零售、采购、供应链、职能全职业",
        category="company_official",
    )

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        payload = {
            "page": {"pageNo": page, "pageSize": max(page_size, 40)},
            "keywords": keyword,
            "jobShareType": "1",
        }
        data = self._request_json(
            opener,
            "POST",
            "https://zhaopin.meituan.com/api/official/job/getJobList",
            payload=payload,
            referer="https://zhaopin.meituan.com/web/social",
            timeout=timeout,
        )
        if not isinstance(data, dict):
            return []
        return list((data.get("data") or {}).get("list") or [])

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("name") or "").strip()
        if not title:
            return None

        dept_list = item.get("department") or []
        dept_names = [
            str(d.get("name")).strip()
            for d in dept_list
            if isinstance(d, dict) and d.get("name")
        ]
        company = f"美团 · {dept_names[0]}" if dept_names else "美团"

        cities = [
            str(c.get("name")).strip()
            for c in (item.get("cityList") or [])
            if isinstance(c, dict) and c.get("name")
        ]
        location = " / ".join(cities)
        if target_city and not _city_hit(location, target_city):
            return None

        duty = _strip_html(item.get("jobDuty"))
        req = _strip_html(item.get("jobRequirement"))
        desc_parts = []
        if duty:
            desc_parts.append(f"【岗位职责】\n{duty}")
        if req:
            desc_parts.append(f"【任职要求】\n{req}")
        description = "\n\n".join(desc_parts) or f"{title} - {company}"

        tags = [
            str(v).strip()
            for v in (item.get("jobFamily"), item.get("jobFamilyGroup"))
            if v and str(v).strip()
        ]
        job_id_raw = item.get("jobUnionId")
        url = (
            f"https://zhaopin.meituan.com/web/position/detail?jobUnionId={job_id_raw}"
            if job_id_raw
            else self.meta.official_entry
        )
        return {
            "job_id": _stable_job_id(self.meta.code, job_id_raw, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": "面议",
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("refreshTime") or item.get("firstPostTime") or ""),
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class TencentAdapter(OfficialJobAdapter):
    """腾讯官方招聘（careers.tencent.com）：技术/产品/运营/设计/职能社招公开 JSON 接口。"""

    meta = OfficialSourceMeta(
        code="tencent",
        name="腾讯官方招聘",
        aliases=("tencent", "腾讯", "腾讯官方", "腾讯招聘"),
        official_entry="https://careers.tencent.com/search.html",
        coverage="技术、产品、运营、设计、市场、职能等大厂社招",
        category="company_official",
    )

    ENDPOINT = "https://careers.tencent.com/tencentcareer/api/post/Query"
    CITY_IDS = {
        "深圳": "1",
        "北京": "2",
        "广州": "5",
        "上海": "3",
        "成都": "4",
        "杭州": "6",
        "武汉": "11",
        "重庆": "9",
        "西安": "10",
        "南京": "7",
        "苏州": "12",
        "厦门": "14",
        "天津": "8",
        "长沙": "13",
    }

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        city_key = _normalize_city(city)
        city_id = self.CITY_IDS.get(city_key, "")
        params = urllib.parse.urlencode(
            {
                "timestamp": str(int(datetime.now().timestamp() * 1000)),
                "countryId": "",
                "cityId": city_id,
                "bgIds": "",
                "productId": "",
                "categoryId": "",
                "parentCategoryId": "",
                "attrId": "",
                "keyword": keyword,
                "pageIndex": str(page),
                "pageSize": str(max(page_size, 20) if not city_id else page_size),
                "language": "zh-cn",
                "area": "cn",
            }
        )
        req = urllib.request.Request(
            f"{self.ENDPOINT}?{params}",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Referer": self.meta.official_entry,
            },
            method="GET",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"腾讯官方接口请求失败: {exc}") from exc

        if data.get("Code") != 200:
            raise OfficialSourceError(self.meta.code, "api_error", f"腾讯官方返回异常状态: {data.get('Code')}")
        return ((data.get("Data") or {}).get("Posts") or [])

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("RecruitPostName") or "").strip()
        if not title:
            return None
        location = str(item.get("LocationName") or "").strip()
        if not _city_hit(location, target_city):
            return None

        bg = str(item.get("BGName") or "").strip()
        product = str(item.get("ProductName") or "").strip()
        company = f"腾讯（{bg}）" if bg else "腾讯"
        duty = _strip_html(item.get("Responsibility"))
        years = str(item.get("RequireWorkYearsName") or "").strip()
        desc_parts = []
        if product:
            desc_parts.append(f"【所属产品/业务】{product}")
        if years:
            desc_parts.append(f"【经验要求】{years}")
        if duty:
            desc_parts.append(f"【岗位职责】\n{duty}")
        description = "\n\n".join(desc_parts) or f"{title} - {company}"

        tags = [v for v in (bg, str(item.get("CategoryName") or "").strip(), years) if v]
        post_id = str(item.get("PostId") or item.get("RecruitPostId") or "").strip()
        raw_url = str(item.get("PostURL") or "").strip()
        if raw_url.startswith("http://"):
            raw_url = "https://" + raw_url[len("http://"):]
        url = raw_url if raw_url.startswith("https://") else (
            f"https://careers.tencent.com/jobdesc.html?postId={post_id}"
            if post_id
            else self.meta.official_entry
        )
        return {
            "job_id": _stable_job_id(self.meta.code, post_id, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": "面议",
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("LastUpdateTime") or ""),
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class NetEaseAdapter(OfficialJobAdapter):
    """网易官方招聘（hr.163.com）：技术/产品/运营/设计/游戏/音乐全岗位公开 JSON 接口。"""

    meta = OfficialSourceMeta(
        code="netease",
        name="网易官方招聘",
        aliases=("netease", "163", "网易", "网易官方", "网易招聘"),
        official_entry="https://hr.163.com/job-list.html",
        coverage="游戏、云音乐、有道、传媒、技术、产品、运营全岗位",
        category="company_official",
    )

    ENDPOINT = "https://hr.163.com/api/hr163/position/queryPage"

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        city_key = _normalize_city(city)
        payload = {
            "currentPage": page,
            "pageSize": max(page_size, 25),
            "keyword": keyword,
            "workPlaceNameList": [f"{city_key}市"] if city_key else [],
        }
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Referer": self.meta.official_entry,
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"网易官方接口请求失败: {exc}") from exc

        if data.get("code") != 200:
            raise OfficialSourceError(self.meta.code, "api_error", f"网易官方返回异常: {data.get('msg')}")
        return ((data.get("data") or {}).get("list") or [])

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("name") or "").strip()
        if not title:
            return None
        places = item.get("workPlaceNameList") or []
        if isinstance(places, list):
            location = "、".join(str(p).strip() for p in places if str(p).strip())
        else:
            location = str(places or "").strip()
        if not _city_hit(location, target_city):
            return None

        dep = str(item.get("firstDepName") or "").strip()
        company = f"网易（{dep}）" if dep else "网易"
        duty = _strip_html(item.get("description"))
        req_text = _strip_html(item.get("requirement"))
        desc_parts = []
        if duty:
            desc_parts.append(f"【岗位描述】\n{duty}")
        if req_text:
            desc_parts.append(f"【任职要求】\n{req_text}")
        description = "\n\n".join(desc_parts) or f"{title} - {company}"

        tags = [
            str(v).strip()
            for v in (
                item.get("firstPostTypeName"),
                item.get("reqEducationName"),
                item.get("reqWorkYearsName"),
                dep,
            )
            if v and str(v).strip()
        ]
        job_id_raw = item.get("id")
        bee_url = str(item.get("beeUrl") or "").strip()
        url = bee_url if bee_url.startswith(("http://", "https://")) else (
            f"https://hr.163.com/job-detail.html?id={job_id_raw}"
            if job_id_raw
            else self.meta.official_entry
        )
        return {
            "job_id": _stable_job_id(self.meta.code, job_id_raw, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": "面议",
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("updateTime") or ""),
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class JdAdapter(OfficialJobAdapter):
    """京东官方招聘（zhaopin.jd.com）：电商/物流/科技/健康/运营/产研全职业公开接口。"""

    meta = OfficialSourceMeta(
        code="jd",
        name="京东官方招聘",
        aliases=("jd", "京东", "京东官方", "京东招聘"),
        official_entry="https://zhaopin.jd.com/web/job/job_info_list/3",
        coverage="技术、产品、运营、供应链、物流、健康、采销全职业",
        category="company_official",
    )

    ENDPOINT = "https://zhaopin.jd.com/web/job/job_list"

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        geo = get_city_geo(city)
        work_city_json = json.dumps([geo[1][:2]]) if geo else "[]"
        body = urllib.parse.urlencode(
            {
                "pageIndex": str(page),
                "pageSize": str(max(page_size, 25)),
                "jobSearch": keyword,
                "workCityJson": work_city_json,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.ENDPOINT,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Referer": self.meta.official_entry,
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"京东官方接口请求失败: {exc}") from exc

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data") or data.get("list") or []
        return []

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("positionName") or "").strip()
        if not title:
            return None
        location = str(item.get("workCity") or "").strip()
        if target_city:
            if _city_hit(location, target_city):
                pass
            elif is_province_level_match(location, target_city):
                location = f"{location}（{_normalize_city(target_city)}同省）"
            else:
                return None

        dept = str(item.get("positionDeptName") or "").strip()
        company = f"京东（{dept}）" if dept else "京东"
        duty = _strip_html(item.get("workContent"))
        qual = _strip_html(item.get("qualification"))
        desc_parts = []
        if duty:
            desc_parts.append(f"【工作内容】\n{duty}")
        if qual:
            desc_parts.append(f"【任职资格】\n{qual}")
        description = "\n\n".join(desc_parts) or f"{title} - {company}"

        tags = [
            str(v).strip()
            for v in (item.get("jobType"), dept)
            if v and str(v).strip()
        ]
        pos_id = item.get("positionId") or item.get("id")
        url = (
            f"https://zhaopin.jd.com/web/job/job_info_list/3?positionId={pos_id}"
            if pos_id
            else self.meta.official_entry
        )
        return {
            "job_id": _stable_job_id(self.meta.code, pos_id, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": "面议",
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("formatPublishTime") or ""),
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class SasacAdapter(OfficialJobAdapter):
    """国务院国资委人事招聘专栏（sasac.gov.cn）：央企及委属单位最新官方招聘公告。"""

    meta = OfficialSourceMeta(
        code="sasac",
        name="国务院国资委",
        aliases=("sasac", "国资委", "国务院国资委"),
        official_entry="http://www.sasac.gov.cn/n2588035/n2588325/n2588350/index.html",
        coverage="中央企业及国资委委属单位官方公开招聘公告",
        category="gov_official",
    )

    ENDPOINT = "http://www.sasac.gov.cn/n2588035/n2588325/n2588350/index.html"

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        if page > 1:
            return []
        req = urllib.request.Request(
            self.ENDPOINT,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
            method="GET",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                raw_html = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"国务院国资委招聘专栏请求失败: {exc}") from exc

        rows = []
        pattern = re.compile(
            r'<li[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*(?:<span[^>]*>(.*?)</span>)?',
            re.S | re.I,
        )
        for href, raw_title, raw_date in pattern.findall(raw_html):
            title = re.sub(r"\s+", " ", _strip_html(raw_title)).strip()
            if not title or len(title) < 6:
                continue
            if not any(w in title for w in ("招聘", "录用", "人才", "央企", "校园", "岗位")):
                continue
            full_url = urllib.parse.urljoin(self.ENDPOINT, href.strip())
            posted = re.sub(r"[\[\]\s]", "", _strip_html(raw_date or ""))
            rows.append({"title": title, "url": full_url, "posted_at": posted})
            if len(rows) >= max(page_size, 15):
                break
        return rows

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        url = str(item.get("url") or self.meta.official_entry).strip()
        company = "国务院国资委 / 中央企业"
        posted = str(item.get("posted_at") or "").strip()
        description = (
            f"【官方发布】{title}\n"
            f"来源：国务院国资委官网人事招聘专栏（央企及委属单位面向社会/校园公开招聘公告，点击原网页查看完整职位表与报名方式）。"
        )
        return {
            "job_id": _stable_job_id(self.meta.code, url, title, company, "全国"),
            "title": title,
            "company": company,
            "location": "全国",
            "salary": "面议",
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": ["国家发布", "央企招聘", "官方公告"],
            "posted_at": posted,
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 0.9 if keyword.lower() in title.lower() else 0.65,
        }


class NowcoderAdapter(OfficialJobAdapter):
    """牛客网招聘广场（nowcoder.com）：覆盖全网互联网/金融/国企/独角兽，带真实薪资区间。"""

    meta = OfficialSourceMeta(
        code="nowcoder",
        name="牛客招聘",
        aliases=("nowcoder", "牛客", "牛客网", "牛客招聘"),
        official_entry="https://www.nowcoder.com/jobs/fulltime/center",
        coverage="全网互联网、AI、金融、国企与成长型企业，含真实薪资区间",
        category="job_platform",
    )

    ENDPOINT = "https://www.nowcoder.com/np-api/u/job/square-search"

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        city_key = _normalize_city(city)
        payload: dict[str, Any] = {
            "page": page,
            "pageSize": max(page_size, 25),
            "query": keyword,
            "recruitType": 3,
            "order": 0,
        }
        if city_key:
            payload["jobCity"] = [city_key]
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Referer": self.meta.official_entry,
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"牛客招聘接口请求失败: {exc}") from exc

        if data.get("code") != 0:
            raise OfficialSourceError(self.meta.code, "api_error", f"牛客招聘返回异常: {data.get('msg')}")
        return ((data.get("data") or {}).get("datas") or [])

    def parse_item(self, item, keyword, target_city, relation_type):
        row = item.get("data") if isinstance(item.get("data"), dict) else item
        title = str(row.get("jobName") or "").strip()
        if not title:
            return None
        city_list = row.get("jobCityList") or []
        location = "、".join(str(c).strip() for c in city_list if str(c).strip()) or str(row.get("jobCity") or "").strip()
        if not _city_hit(location, target_city):
            return None

        comp_obj = row.get("recommendInternCompany") or {}
        company = str(comp_obj.get("companyName") or comp_obj.get("companyShortName") or "牛客认证企业").strip()

        sal_min = row.get("salaryMin")
        sal_max = row.get("salaryMax")
        sal_month = row.get("salaryMonth")
        if sal_min and sal_max:
            salary = f"{sal_min}-{sal_max}K" + (f"·{sal_month}薪" if sal_month and int(sal_month) > 12 else "")
        else:
            salary = str(row.get("salaryShow") or "面议").strip() or "面议"

        ext_obj = {}
        raw_ext = row.get("ext")
        if isinstance(raw_ext, str) and raw_ext.strip().startswith("{"):
            try:
                ext_obj = json.loads(raw_ext)
            except Exception:
                ext_obj = {}
        elif isinstance(raw_ext, dict):
            ext_obj = raw_ext

        desc_parts = []
        if ext_obj.get("infos"):
            desc_parts.append(f"【岗位职责】\n{_strip_html(ext_obj.get('infos'))}")
        if ext_obj.get("requirements"):
            desc_parts.append(f"【任职要求】\n{_strip_html(ext_obj.get('requirements'))}")
        description = "\n\n".join(desc_parts) or f"{title} - {company}"

        tags = [str(t).strip() for t in (comp_obj.get("industryTagNameList") or []) if str(t).strip()]
        if comp_obj.get("scaleTagName"):
            tags.append(str(comp_obj.get("scaleTagName")).strip())
        job_id_raw = row.get("id")
        url = f"https://www.nowcoder.com/jobs/detail/{job_id_raw}" if job_id_raw else self.meta.official_entry
        return {
            "job_id": _stable_job_id(self.meta.code, job_id_raw, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": salary,
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": "",
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class BaiduAdapter(OfficialJobAdapter):
    """百度官方招聘（talent.baidu.com）：AI大模型/搜索/云/自动驾驶/产品/运营全社招。"""

    meta = OfficialSourceMeta(
        code="baidu",
        name="百度官方招聘",
        aliases=("baidu", "百度", "百度官方", "百度招聘"),
        official_entry="https://talent.baidu.com/jobs/social-list",
        coverage="大模型、搜索、云智能、自动驾驶、产品与运营全社招",
        category="company_official",
    )

    ENDPOINT = "https://talent.baidu.com/httservice/getPostListNew"

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        city_key = _normalize_city(city)
        query_word = f"{city_key} {keyword}".strip() if city_key else keyword
        body = urllib.parse.urlencode(
            {
                "recruitType": "SOCIAL",
                "pageSize": "10",
                "curPage": str(page),
                "keyWord": query_word,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.ENDPOINT,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Referer": self.meta.official_entry,
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"百度官方接口请求失败: {exc}") from exc

        if data.get("status") != "ok":
            raise OfficialSourceError(self.meta.code, "api_error", f"百度官方返回异常: {data.get('message')}")
        items = (data.get("data") or {}).get("list") or []
        if not items and city_key and page == 1:
            fallback_body = urllib.parse.urlencode(
                {
                    "recruitType": "SOCIAL",
                    "pageSize": "30",
                    "curPage": "1",
                    "keyWord": keyword,
                }
            ).encode("utf-8")
            fallback_req = urllib.request.Request(
                self.ENDPOINT,
                data=fallback_body,
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": self.meta.official_entry,
                },
                method="POST",
            )
            try:
                with opener.open(fallback_req, timeout=timeout) as resp:
                    fb_data = json.loads(resp.read().decode("utf-8", errors="replace"))
                if fb_data.get("status") == "ok":
                    items = (fb_data.get("data") or {}).get("list") or []
            except Exception:
                pass
        return items

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("name") or "").strip()
        if not title:
            return None
        location = str(item.get("workPlace") or "").strip()
        if not _city_hit(location, target_city):
            return None

        bg = str(item.get("bgShortName") or "").strip()
        company = f"百度（{bg}）" if bg else "百度"
        duty = _strip_html(item.get("workContent"))
        req_text = _strip_html(item.get("serviceCondition"))
        desc_parts = []
        if duty:
            desc_parts.append(f"【工作职责】\n{duty}")
        if req_text:
            desc_parts.append(f"【任职资格】\n{req_text}")
        description = "\n\n".join(desc_parts) or f"{title} - {company}"

        tags = [str(v).strip() for v in (item.get("postType"), bg, item.get("education")) if v and str(v).strip()]
        post_id = str(item.get("postId") or item.get("jobId") or "").strip()
        url = f"https://talent.baidu.com/jobs/detail/SOCIAL/{post_id}" if post_id else self.meta.official_entry
        return {
            "job_id": _stable_job_id(self.meta.code, post_id, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": "面议",
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("updateDate") or item.get("publishDate") or ""),
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class MihoyoAdapter(OfficialJobAdapter):
    """米哈游官方招聘（jobs.mihoyo.com）：研发/产品/运营/美术/国际化社招。"""

    meta = OfficialSourceMeta(
        code="mihoyo",
        name="米哈游官方",
        aliases=("mihoyo", "米哈游", "米哈游官方"),
        official_entry="https://jobs.mihoyo.com/",
        coverage="研发、技术、产品、运营、美术与国际化岗位",
        category="company_official",
    )

    ENDPOINT = "https://ats.openout.mihoyo.com/ats-portal/v1/job/list"

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        payload = {
            "pageNo": page,
            "pageSize": max(page_size, 30),
            "hireType": 0,
            "keyword": keyword,
            "channelDetailIds": [1],
        }
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Referer": self.meta.official_entry,
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"米哈游官方接口请求失败: {exc}") from exc

        if data.get("code") != 0:
            raise OfficialSourceError(self.meta.code, "api_error", f"米哈游官方返回异常: {data.get('message')}")
        return ((data.get("data") or {}).get("list") or [])

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        addr_list = item.get("addressDetailList") or []
        location = "、".join(
            str(a.get("addressDetail") or "").strip()
            for a in addr_list
            if isinstance(a, dict) and str(a.get("addressDetail") or "").strip()
        )
        if not _city_hit(location, target_city):
            return None

        company = "米哈游"
        summary = _strip_html(item.get("jobSummary"))
        comp_type = str(item.get("competencyType") or "").strip()
        proj_name = str(item.get("projectName") or "").strip()
        description = summary or f"【岗位类别】{comp_type or '综合'} · {proj_name or '社会招聘'}\n岗位：{title}（米哈游官方直招，点击原网页查看完整职责要求）"
        job_id_raw = str(item.get("id") or "").strip()
        url = f"https://jobs.mihoyo.com/#/position/{job_id_raw}" if job_id_raw else self.meta.official_entry
        tags = [v for v in (comp_type, str(item.get("jobNature") or "").strip(), proj_name) if v]
        return {
            "job_id": _stable_job_id(self.meta.code, job_id_raw, title, company, location),
            "title": title,
            "company": company,
            "location": location or target_city,
            "salary": "面议",
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": "",
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


class BeisenZhiyeAdapter(OfficialJobAdapter):
    """北森（*.zhiye.com）通用企业官方直招适配器：一套逻辑复用多家跨行业龙头官网。"""

    host: str = ""
    company_display: str = ""

    def __init__(self, meta: OfficialSourceMeta, host: str, company_display: str):
        self.meta = meta
        self.host = host
        self.company_display = company_display

    def fetch_raw_items(self, keyword, city, page, page_size, opener, timeout):
        payload = {
            "PageIndex": max(0, page - 1),
            "PageSize": max(page_size, 30),
            "KeyWords": keyword,
            "SpecialType": 0,
            "PortalBrand": "",
        }
        req = urllib.request.Request(
            f"https://{self.host}/api/Jobad/GetJobAdPageList",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Referer": f"https://{self.host}/",
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise OfficialSourceError(self.meta.code, "network_error", f"{self.company_display}官网接口请求失败: {exc}") from exc

        if data.get("Code") != 200:
            raise OfficialSourceError(self.meta.code, "api_error", f"{self.company_display}官网返回异常: {data.get('Message')}")
        return data.get("Data") or []

    def parse_item(self, item, keyword, target_city, relation_type):
        title = str(item.get("JobAdNameWithoutJobCode") or item.get("JobAdName") or "").strip()
        if not title:
            return None
        loc_names = item.get("LocNames") or []
        loc_parts = [str(v).strip() for v in loc_names if str(v).strip()] if isinstance(loc_names, list) else []
        detail_addr = str(item.get("DetailAddress") or "").strip()
        if detail_addr and detail_addr not in loc_parts:
            loc_parts.append(detail_addr)
        location_text = "、".join(loc_parts)
        # 北森部分岗位把工作城市写在标题后缀或职责中，综合校验城市
        city_probe = f"{location_text} {title}"
        if not _city_hit(city_probe, target_city):
            return None
        display_loc = location_text or (_normalize_city(target_city) if _city_hit(title, target_city) else target_city)

        duty = _strip_html(item.get("Duty"))
        req_text = _strip_html(item.get("Require"))
        desc_parts = []
        if duty:
            desc_parts.append(f"【岗位职责】\n{duty}")
        if req_text:
            desc_parts.append(f"【任职要求】\n{req_text}")
        description = "\n\n".join(desc_parts) or f"{title} - {self.company_display}"

        salary = str(item.get("Salary") or "面议").strip() or "面议"
        job_ad_id = item.get("JobAdId") or item.get("Id")
        url = f"https://{self.host}/zpdetail/{job_ad_id}" if job_ad_id else self.meta.official_entry
        tags = [
            str(v).strip()
            for v in (item.get("Category"), item.get("Degree"), item.get("YearsOfWorking"))
            if v and str(v).strip()
        ]
        return {
            "job_id": _stable_job_id(self.meta.code, job_ad_id, title, self.company_display, display_loc),
            "title": title,
            "company": self.company_display,
            "location": display_loc,
            "salary": salary,
            "description": description,
            "url": url,
            "source": self.meta.code,
            "tags": tags[:6],
            "posted_at": str(item.get("ChangeDate") or "")[:10],
            "match_keyword": keyword,
            "relation_type": relation_type,
            "relevance_score": 1.0 if relation_type == "primary" else 0.75,
        }


def _make_beisen_adapters() -> tuple[BeisenZhiyeAdapter, ...]:
    specs = (
        ("iflytek", "科大讯飞官方", ("iflytek", "科大讯飞", "讯飞"), "iflytek.zhiye.com", "科大讯飞", "AI大模型、语音算法、产研与行业解决方案"),
        ("wuxiapptec", "药明康德官方", ("wuxiapptec", "药明康德", "药明"), "wuxiapptec.zhiye.com", "药明康德", "生物医药、研发、临床、供应链与职能"),
        ("mindray", "迈瑞医疗官方", ("mindray", "迈瑞", "迈瑞医疗"), "mindray.zhiye.com", "迈瑞医疗", "医疗器械、硬件研发、算法与国际营销"),
        ("mengniu", "蒙牛集团官方", ("mengniu", "蒙牛", "蒙牛集团"), "mengniu.zhiye.com", "蒙牛集团", "快消品、市场营销、供应链、品控与财务"),
        ("vivo", "vivo官方招聘", ("vivo", "vivo官方"), "vivo.zhiye.com", "vivo", "智能硬件、通信芯片、产研设计与零售"),
    )
    return tuple(
        BeisenZhiyeAdapter(
            OfficialSourceMeta(
                code=code,
                name=name,
                aliases=aliases,
                official_entry=f"https://{host}/",
                coverage=cov,
                category="company_official",
            ),
            host=host,
            company_display=comp,
        )
        for code, name, aliases, host, comp, cov in specs
    )


# 统一官方开放源注册表（15 个实测可用免登录直连源）
OFFICIAL_ADAPTERS: dict[str, OfficialJobAdapter] = {
    adapter.meta.code: adapter
    for adapter in (
        SasacAdapter(),
        NcssAdapter(),
        IguopinAdapter(),
        NowcoderAdapter(),
        MeituanAdapter(),
        TencentAdapter(),
        NetEaseAdapter(),
        JdAdapter(),
        BaiduAdapter(),
        MihoyoAdapter(),
        *_make_beisen_adapters(),
    )
}


def list_official_source_codes() -> tuple[str, ...]:
    return tuple(OFFICIAL_ADAPTERS.keys())


_RELEVANCE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "后端": ("后端", "服务端", "后台", "java", "python", "golang", "go", "研发", "开发工程师"),
    "前端": ("前端", "web", "react", "vue", "typescript", "javascript", "h5", "客户端"),
    "产品": ("产品", "pm", "策略", "需求", "规划", "商业化"),
    "运营": ("运营", "增长", "活动", "用户", "内容", "社群", "推广"),
    "数据": ("数据", "分析", "bi", "sql", "数仓", "商业分析", "算法"),
    "ai": ("ai", "大模型", "llm", "算法", "rag", "智能", "机器学习", "nlp"),
    "测试": ("测试", "qa", "测开", "质量保障", "自动化测试"),
    "设计": ("设计", "ui", "ux", "交互", "视觉", "平面"),
    "金融": ("金融", "财务", "风控", "合规", "投研", "审计", "会计"),
    "市场": ("市场", "营销", "品牌", "公关", "商务", "bd", "渠道"),
    "人事": ("人事", "hr", "招聘", "薪酬", "培训", "行政"),
}


_GENERIC_ROLE_STOPWORDS = {
    "专员", "经理", "助理", "主管", "工程师", "实习", "实习生", "总监", "顾问",
    "管培生", "校招", "社招", "人员", "岗位", "方向", "招聘", "工作", "专家",
    "架构", "研发", "开发", "中心", "部门", "总部", "公司", "集团", "有限",
}

_SEARCH_EXPANSION_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("ai", "产品"), ("AI产品", "AI产品经理", "大模型产品")),
    (("大模型", "产品"), ("AI产品", "大模型产品", "AI产品经理")),
    (("aigc", "产品"), ("AI产品", "AIGC产品", "AI产品经理")),
    (("人工智能", "产品"), ("AI产品", "AI产品经理", "大模型产品")),
    (("ai", "运营"), ("AI运营", "AI产品运营", "大模型运营")),
    (("ai", "算法"), ("大模型算法", "算法工程师", "AI算法")),
    (("ai", "开发"), ("AI工程师", "大模型开发", "AI应用开发")),
    (("ai", "工程"), ("AI工程师", "大模型", "AI应用")),
    (("python",), ("Python", "Python开发", "后端开发")),
    (("java",), ("Java", "Java开发", "后端开发")),
    (("后端",), ("后端开发", "服务端开发")),
    (("前端",), ("前端开发", "Web前端")),
    (("数据", "分析"), ("数据分析", "数据分析师", "商业分析")),
    (("产品",), ("产品经理", "产品助理", "产品运营")),
    (("测试",), ("测试开发", "软件测试")),
    (("运营",), ("产品运营", "用户运营", "内容运营")),
)


def expand_search_keywords(keywords: list[str], *, max_queries: int = 3) -> list[str]:
    """为官方企业接口自动扩展高命中同义主干词（例如「AI产品专员」->「AI产品」「AI产品经理」）。"""
    cleaned = [k.strip() for k in (keywords or []) if isinstance(k, str) and k.strip()]
    if not cleaned:
        return []
    expanded: list[str] = []

    def _add(term: str) -> None:
        t = term.strip()
        if t and t.lower() not in {x.lower() for x in expanded}:
            expanded.append(t)

    primary = cleaned[0]
    _add(primary)
    for extra in cleaned[1:]:
        _add(extra)

    low_primary = primary.lower()
    # 1) 剥离泛化职级后缀（如 专员/助理/实习生/岗）得到核心主干词
    stem = re.sub(r"(实习生|实习|专员|助理|主管|管培生|方向|岗位|岗)$", "", primary).strip()
    if len(stem) >= 2 and stem != primary:
        _add(stem)

    # 2) 匹配高频行业同义检索词
    for must_terms, candidates in _SEARCH_EXPANSION_RULES:
        if all(tok in low_primary for tok in must_terms):
            for cand in candidates:
                _add(cand)
            break

    return expanded[: max(1, max_queries)]


def _extract_relevance_tokens(keywords: list[str]) -> tuple[list[str], list[str], set[str]]:
    cleaned = [k.strip() for k in (keywords or []) if isinstance(k, str) and k.strip()]
    primary_list = [cleaned[0].lower()] if cleaned else []
    related_list = [k.lower() for k in cleaned[1:]]
    sub_tokens: set[str] = set()

    for kw in cleaned:
        low = kw.lower()
        sub_tokens.add(low)
        # Split on spaces / punctuation
        for part in re.split(r"[\s/、,，;；|·\-]+", low):
            if len(part) >= 2 and part not in _GENERIC_ROLE_STOPWORDS:
                sub_tokens.add(part)
        # Extract 2-char Chinese segments for compound titles, excluding generic role suffixes
        cn_parts = re.findall(r"[\u4e00-\u9fff]{2,}", low)
        for cn in cn_parts:
            if len(cn) <= 4 and cn not in _GENERIC_ROLE_STOPWORDS:
                sub_tokens.add(cn)
            if len(cn) >= 4:
                head, tail = cn[:2], cn[-2:]
                if head not in _GENERIC_ROLE_STOPWORDS:
                    sub_tokens.add(head)
                if tail not in _GENERIC_ROLE_STOPWORDS:
                    sub_tokens.add(tail)
        # Extract English tech/domain acronyms like ai, llm, aigc, nlp, java, python
        for en in re.findall(r"[a-z]{2,}", low):
            if en not in _GENERIC_ROLE_STOPWORDS:
                sub_tokens.add(en)
        # Add domain synonyms when trigger appears
        for trigger, syns in _RELEVANCE_SYNONYMS.items():
            if trigger in low:
                for syn in syns:
                    if syn not in _GENERIC_ROLE_STOPWORDS:
                        sub_tokens.add(syn)

    sub_tokens -= _GENERIC_ROLE_STOPWORDS
    return primary_list, related_list, sub_tokens


def rank_and_filter_jobs_by_relevance(
    jobs: list[dict[str, Any]],
    keywords: list[str],
    *,
    min_keep: int = 8,
) -> list[dict[str, Any]]:
    """按岗位标题与正文相关性严格排序与过滤，彻底剔除零相关噪音岗（如无关央企综合公告）。"""
    if not jobs or not keywords:
        return list(jobs or [])

    primary_list, related_list, sub_tokens = _extract_relevance_tokens(keywords)
    scored_pairs: list[tuple[int, int, dict[str, Any]]] = []

    for idx, job in enumerate(jobs):
        item = dict(job)
        title = str(item.get("title") or "").lower()
        desc = str(item.get("description") or "")[:400].lower()

        score = 0
        matched_primary = any(p and p in title for p in primary_list)
        matched_related = any(r and r in title for r in related_list)

        if matched_primary:
            score += 100
            item["relation_type"] = "primary"
            item["keyword_tier"] = "primary"
        elif matched_related:
            score += 75

        token_hits = 0
        for tok in sub_tokens:
            if tok and tok in title:
                token_hits += 1
        score += min(60, token_hits * 25)

        if score == 0:
            desc_hits = sum(1 for tok in sub_tokens if tok and tok in desc)
            if any(p and p in desc for p in primary_list) or desc_hits >= 2:
                score += 20
            elif desc_hits == 1:
                score += 12

        item["relevance_score"] = score
        item["relevance_level"] = "high" if score >= 70 else ("medium" if score >= 25 else "low")
        scored_pairs.append((score, idx, item))

    scored_pairs.sort(key=lambda pair: (-pair[0], pair[1]))
    ranked = [pair[2] for pair in scored_pairs]

    # 严格门控：优先保留标题命中的强相关岗（>=25分）；数量不足时仅用正文确实命中关键词的岗（>=12分）补足，绝不保留 0 分无关噪音
    strong = [j for j in ranked if j.get("relevance_score", 0) >= 25]
    desc_matched = [j for j in ranked if 12 <= j.get("relevance_score", 0) < 25]

    if len(strong) >= min_keep:
        return strong
    need = max(0, min_keep - len(strong))
    return strong + desc_matched[:need]


def collect_official_jobs(
    source_code: str,
    keywords: list[str],
    target_city: str,
    *,
    max_pages: int = 2,
    page_size: int = 15,
    max_jobs: int = 20,
    timeout: float = DEFAULT_TIMEOUT,
    stop_check: Callable[[], str | None] | None = None,
    progress_callback: Callable[[str, str, int], None] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
) -> list[dict[str, Any]]:
    """从指定权威官方开放源采集岗位，执行严格城市校验与跨页去重。"""
    adapter = OFFICIAL_ADAPTERS.get(source_code)
    if adapter is None:
        raise ValueError(f"未注册的开放官方招聘源: {source_code}")

    http_opener = opener or _build_direct_opener()
    cleaned_keywords = [kw.strip() for kw in (keywords or []) if isinstance(kw, str) and kw.strip()]
    if not cleaned_keywords:
        return []

    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for kw_index, keyword in enumerate(cleaned_keywords):
        relation_type = "primary" if kw_index == 0 else "related"
        for page in range(1, max_pages + 1):
            if stop_check:
                reason = stop_check()
                if reason:
                    raise OfficialSourceError(source_code, reason, f"采集已中止: {reason}")
            if progress_callback:
                progress_callback(
                    "collecting",
                    f"正在从{adapter.meta.name}检索「{keyword}」（第{page}页）",
                    min(55, 20 + kw_index * 10 + page * 5),
                )
            raw_items = adapter.fetch_raw_items(
                keyword, target_city, page, page_size, http_opener, timeout
            )
            if not raw_items:
                break
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                parsed = adapter.parse_item(item, keyword, target_city, relation_type)
                if not parsed:
                    continue
                if parsed["job_id"] in seen_ids:
                    continue
                seen_ids.add(parsed["job_id"])
                parsed["scraped_at"] = scraped_at
                collected.append(parsed)
                if len(collected) >= max_jobs:
                    return collected
            if len(raw_items) < page_size:
                break

    return collected

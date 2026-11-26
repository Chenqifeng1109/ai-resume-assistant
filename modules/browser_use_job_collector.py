"""Browser Use adapter for bounded, source-specific job collection."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse


PROJECT_DIR = Path(__file__).resolve().parent.parent
BROWSER_USE_DIR = PROJECT_DIR / "external" / "browser-use"
BROWSER_USE_PYTHON = BROWSER_USE_DIR / ".venv" / "Scripts" / "python.exe"
SOURCE_CONFIG = {
    "liepin": {
        "name": "猎聘",
        "entry_url": "https://www.liepin.com/",
        "allowed_hosts": ("liepin.com", "www.liepin.com"),
        "city_codes": {
            "北京": "010",
            "上海": "020",
            "天津": "030",
            "重庆": "040",
            "广州": "050020",
            "深圳": "050090",
            "南京": "060020",
            "苏州": "060080",
            "杭州": "070020",
            "郑州": "150020",
            "武汉": "170020",
            "长沙": "180020",
            "大连": "210040",
            "西安": "270020",
            "成都": "280020",
        },
    },
}


class BrowserUseCollectionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _extract_json(text: str) -> dict:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("智能浏览器没有返回岗位JSON")
    payload = json.loads(value[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("智能浏览器返回格式不正确")
    return payload


def _agent_failure_message(errors: list) -> str | None:
    combined = "\n".join(str(error) for error in errors if error)
    if "Insufficient Balance" in combined or "余额不足" in combined:
        return "AI API余额不足，智能浏览器已停止；充值或更换可用模型后重试"
    if "429" in combined or "rate limit" in combined.lower():
        return "模型请求过于频繁，智能浏览器已停止，请稍后重试"
    return None


def _classify_failure(message: str) -> tuple[str, str]:
    text = str(message or "")
    lowered = text.lower()
    if "insufficient balance" in lowered or "余额不足" in text:
        return "MODEL_BALANCE_INSUFFICIENT", "AI API余额不足，智能浏览器已停止；充值或更换可用模型后重试"
    if "429" in text or "rate limit" in lowered:
        return "MODEL_RATE_LIMITED", "模型请求过于频繁，智能浏览器已停止，请稍后重试"
    if "验证码" in text or "captcha" in lowered:
        return "CAPTCHA_REQUIRED", "网站要求完成验证码，自动采集已暂停，请人工处理后重试"
    if "登录墙" in text or "需要登录" in text or "login required" in lowered:
        return "LOGIN_REQUIRED", "网站要求登录，自动采集已暂停，请先通过独立会话完成登录"
    if any(value in lowered for value in ("access denied", "forbidden", "blocked")) or "拒绝访问" in text:
        return "ACCESS_RESTRICTED", "网站拒绝当前访问，自动采集已停止"
    return "BROWSER_AGENT_FAILED", text[:200] or "智能浏览器采集失败"


def _write_progress(path: Path, stage: str, message: str, percent: int) -> None:
    path.write_text(json.dumps({
        "stage": stage, "message": message, "percent": max(0, min(int(percent), 100)),
    }, ensure_ascii=False), encoding="utf-8")


async def _extract_liepin_cards(browser, max_jobs: int) -> list[dict]:
    """Read visible public Liepin cards through CDP before spending model calls."""
    cdp_session = await browser.get_or_create_cdp_session(target_id=None, focus=False)
    expression = r"""
(() => {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const firstText = (root, selectors) => {
    for (const selector of selectors) {
      const node = root.querySelector(selector);
      const value = clean(node && node.textContent);
      if (value) return value;
    }
    return '';
  };
  const links = [...document.querySelectorAll('a[href*="/job/"]')];
  const jobs = [];
  const seen = new Set();
  for (const link of links) {
    const url = link.href || '';
    if (!url || seen.has(url)) continue;
    const card = link.closest('[class*="job-card"], [class*="job-list-item"], article, li') || link.parentElement?.parentElement || link.parentElement;
    if (!card) continue;
    const linkText = clean(link.innerText || link.textContent);
    const locMatch = linkText.match(/【\s*([^】]+?)\s*】/);
    let title = firstText(card, ['[class*="job-title"]', '[class*="job-name"]', 'h3', 'h2']);
    let location = firstText(card, ['[class*="job-dq"]', '[class*="job-area"]', '[class*="location"]', '[class*="area"]']);
    let salary = firstText(card, ['[class*="job-salary"]', '[class*="salary"]']);
    let company = firstText(card, ['[class*="company-name"]', '[class*="company-title"]', 'a[href*="/company/"]', '[class*="company"]']);
    let tags = [...card.querySelectorAll('[class*="tag"], [class*="label"]')]
      .map(node => clean(node.textContent)).filter(Boolean).slice(0, 10);

    // 新版猎聘采用混淆类名（如 _40108veEPX），按卡片文本结构兜底解析
    if (locMatch) {
      if (!location) location = clean(locMatch[1]);
      if (!title) title = clean(linkText.slice(0, locMatch.index));
      const afterLoc = clean(linkText.slice(locMatch.index + locMatch[0].length));
      if (!salary) {
        const salMatch = afterLoc.match(/(\d+(?:\.\d+)?-\d+(?:\.\d+)?[kK万](?:·\d+薪)?|面议)/);
        if (salMatch) salary = salMatch[1];
      }
      if (!tags.length && afterLoc) {
        tags = afterLoc.split(/\s+/).filter(t => t && t !== salary).slice(0, 6);
      }
    } else if (!title) {
      title = linkText;
    }
    if (!company) {
      const cardText = clean(card.innerText || card.textContent);
      const tail = linkText && cardText.includes(linkText)
        ? clean(cardText.slice(cardText.indexOf(linkText) + linkText.length))
        : '';
      if (tail) {
        const parts = tail.split(/\s+/).filter(Boolean);
        company = parts[0] || '';
        if (parts.length > 1 && tags.length < 8) {
          tags.push(parts[1]);
        }
      }
    }
    if (!title || !company || !location) continue;
    const cleanUrl = url.split('?')[0] || url;
    if (seen.has(cleanUrl)) continue;
    seen.add(cleanUrl);
    jobs.push({title, company, location, salary, url: cleanUrl, description: '', tags: tags.slice(0, 10)});
  }
  return jobs.slice(0, MAX_JOBS);
})()
""".replace("MAX_JOBS", str(max(1, min(int(max_jobs), 20))))
    result = await cdp_session.cdp_client.send.Runtime.evaluate(
        params={"expression": expression, "returnByValue": True},
        session_id=cdp_session.session_id,
    )
    value = result.get("result", {}).get("value", [])
    return value if isinstance(value, list) else []


def _host_allowed(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def normalize_jobs(payload: dict, source_code: str, city: str, keywords: list[str], max_jobs: int) -> list[dict]:
    """Validate untrusted Agent output before it reaches the repository."""
    config = SOURCE_CONFIG.get(source_code)
    if config is None:
        raise ValueError("智能浏览器来源尚未配置")
    raw_jobs = payload.get("jobs", [])
    if not isinstance(raw_jobs, list):
        raise ValueError("智能浏览器岗位结果必须是列表")
    normalized_city = city.strip().removesuffix("市")
    accepted = []
    seen = set()
    for item in raw_jobs[: max_jobs * 2]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        company = str(item.get("company", "")).strip()
        location = str(item.get("location", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not company or not location or not url:
            continue
        if normalized_city not in location.removesuffix("市"):
            continue
        if not _host_allowed(url, config["allowed_hosts"]):
            continue
        identity = (url, title, company)
        if identity in seen:
            continue
        seen.add(identity)
        keyword = next((value for value in keywords if value and value in title), keywords[0] if keywords else "")
        job_id = str(item.get("job_id", "")).strip() or hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        accepted.append({
            "job_id": f"{source_code}-{job_id}",
            "source": config["name"],
            "title": title[:200],
            "company": company[:200],
            "location": location[:100],
            "salary": str(item.get("salary", "")).strip()[:100],
            "url": url,
            "description": str(item.get("description", "")).strip()[:10000],
            "tags": [str(tag).strip()[:100] for tag in item.get("tags", [])[:10] if str(tag).strip()]
                    if isinstance(item.get("tags", []), list) else [],
            "keyword": keyword,
        })
        if len(accepted) >= max_jobs:
            break
    return accepted


def _stop_process_tree(process: subprocess.Popen) -> None:
    """Stop the worker and its owned Edge children without touching daily Edge."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        process.kill()


_LIEPIN_EXTRACT_JS = r"""
(maxJobs) => {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const firstText = (root, selectors) => {
    for (const selector of selectors) {
      const node = root.querySelector(selector);
      const value = clean(node && node.textContent);
      if (value) return value;
    }
    return '';
  };
  const links = [...document.querySelectorAll('a[href*="/job/"]')];
  const jobs = [];
  const seen = new Set();
  for (const link of links) {
    const url = link.href || '';
    if (!url) continue;
    const card = link.closest('[class*="job-card"], [class*="job-list-item"], article, li') || link.parentElement?.parentElement || link.parentElement;
    if (!card) continue;
    const linkText = clean(link.innerText || link.textContent);
    const locMatch = linkText.match(/【\s*([^】]+?)\s*】/);
    let title = firstText(card, ['[class*="job-title"]', '[class*="job-name"]', 'h3', 'h2']);
    let location = firstText(card, ['[class*="job-dq"]', '[class*="job-area"]', '[class*="location"]', '[class*="area"]']);
    let salary = firstText(card, ['[class*="job-salary"]', '[class*="salary"]']);
    let company = firstText(card, ['[class*="company-name"]', '[class*="company-title"]', 'a[href*="/company/"]', '[class*="company"]']);
    let tags = [...card.querySelectorAll('[class*="tag"], [class*="label"]')]
      .map(node => clean(node.textContent)).filter(Boolean).slice(0, 10);

    if (locMatch) {
      if (!location) location = clean(locMatch[1]);
      if (!title) title = clean(linkText.slice(0, locMatch.index));
      const afterLoc = clean(linkText.slice(locMatch.index + locMatch[0].length));
      if (!salary) {
        const salMatch = afterLoc.match(/(\d+(?:\.\d+)?-\d+(?:\.\d+)?[kK万](?:·\d+薪)?|面议)/);
        if (salMatch) salary = salMatch[1];
      }
      if (!tags.length && afterLoc) {
        tags = afterLoc.split(/\s+/).filter(t => t && t !== salary).slice(0, 6);
      }
    } else if (!title) {
      title = linkText;
    }
    if (!company) {
      const cardText = clean(card.innerText || card.textContent);
      const tail = linkText && cardText.includes(linkText)
        ? clean(cardText.slice(cardText.indexOf(linkText) + linkText.length))
        : '';
      if (tail) {
        const parts = tail.split(/\s+/).filter(Boolean);
        company = parts[0] || '';
        if (parts.length > 1 && tags.length < 8) {
          tags.push(parts[1]);
        }
      }
    }
    if (!title || !company || !location) continue;
    const cleanUrl = url.split('?')[0] || url;
    if (seen.has(cleanUrl)) continue;
    seen.add(cleanUrl);
    jobs.push({title, company, location, salary, url: cleanUrl, description: '', tags: tags.slice(0, 10)});
  }
  return jobs.slice(0, maxJobs);
}
"""


def _collect_liepin_with_playwright(
    keywords: list[str],
    city: str,
    max_jobs: int = 30,
    stop_check=None,
    progress_callback=None,
    max_pages: int = 3,
) -> list[dict]:
    """内置 Playwright 猎聘多页直采（4 级浏览器探测链，单源最多 30 岗，零外部虚拟环境依赖）。"""
    from playwright.sync_api import sync_playwright
    from modules.browser_runtime import launch_best_chromium_browser

    config = SOURCE_CONFIG["liepin"]
    city_name = str(city or "").strip().removesuffix("市")
    city_code = config["city_codes"].get(city_name)
    if not city_code:
        raise BrowserUseCollectionError("UNSUPPORTED_CITY", f"猎聘暂未配置城市：{city_name or '未知'}")

    kw = (keywords[0] if keywords else "").strip()
    if not kw:
        raise BrowserUseCollectionError("INVALID_INPUT", "缺少猎聘搜索关键词")

    target_limit = max(1, min(int(max_jobs or 30), 30))
    if callable(progress_callback):
        progress_callback("browser_starting", f"正在启动内置浏览器采集猎聘（{city_name}）", 45)

    pw = sync_playwright().start()
    browser = None
    try:
        browser, browser_label = launch_best_chromium_browser(pw, headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 860},
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        all_raw_cards: list[dict] = []
        seen_urls: set[str] = set()
        pages_to_scan = max(1, min(int(max_pages or 3), 3))
        for page_idx in range(pages_to_scan):
            if len(all_raw_cards) >= target_limit:
                break
            search_url = "https://www.liepin.com/zhaopin/?" + urlencode({
                "dq": city_code,
                "city": city_code,
                "currentPage": page_idx,
                "pageSize": 40,
                "key": kw,
            })
            if callable(progress_callback):
                progress_callback(
                    "browser_navigating",
                    f"已使用 {browser_label} 采集猎聘{city_name}第 {page_idx + 1} 页",
                    min(59, 48 + page_idx * 4),
                )
            page.goto(search_url, wait_until="domcontentloaded", timeout=25000)

            for _ in range(5):
                if callable(stop_check):
                    reason = stop_check()
                    if reason:
                        code = "COLLECTION_TIMEOUT" if reason == "timed_out" else "USER_CANCELLED"
                        raise BrowserUseCollectionError(code, "岗位采集已安全停止")
                page.wait_for_timeout(1000)
                if page.locator('a[href*="/job/"]').count() > 0:
                    break

            raw_cards = page.evaluate(_LIEPIN_EXTRACT_JS, target_limit)
            if not isinstance(raw_cards, list) or not raw_cards:
                break
            added = 0
            for card in raw_cards:
                u = str(card.get("url") or "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    all_raw_cards.append(card)
                    added += 1
                    if len(all_raw_cards) >= target_limit:
                        break
            if added == 0:
                break

        jobs = normalize_jobs({"jobs": all_raw_cards}, "liepin", city, keywords, target_limit)
        if not jobs:
            raise BrowserUseCollectionError("EMPTY_EXACT_RESULTS", f"猎聘在{city_name}暂未找到匹配岗位")
        if callable(progress_callback):
            progress_callback("browser_validating", f"猎聘多页直采完成（{len(jobs)} 岗）", 62)
        return jobs
    finally:
        try:
            if browser is not None:
                browser.close()
        finally:
            pw.stop()


def collect_jobs(source_code: str, keywords: list[str], city: str, max_jobs: int = 30,
                 timeout_seconds: int = 300, stop_check=None, progress_callback=None) -> list[dict]:
    """Run bounded source-specific job collection (built-in Playwright first, external worker optional)."""
    if source_code not in SOURCE_CONFIG:
        raise ValueError("智能浏览器来源尚未配置")
    if source_code == "liepin":
        try:
            return _collect_liepin_with_playwright(
                keywords=keywords,
                city=city,
                max_jobs=max_jobs,
                stop_check=stop_check,
                progress_callback=progress_callback,
            )
        except BrowserUseCollectionError as err:
            if err.code in {"USER_CANCELLED", "COLLECTION_TIMEOUT"} or not BROWSER_USE_PYTHON.exists():
                raise
        except Exception as exc:
            if not BROWSER_USE_PYTHON.exists():
                raise BrowserUseCollectionError("BROWSER_AGENT_FAILED", str(exc)[:200]) from exc
    if not BROWSER_USE_PYTHON.exists():
        raise BrowserUseCollectionError("BROWSER_ENV_MISSING", "未检测到可用浏览器内核，已跳过该渠道")
    request_data = {
        "source": source_code,
        "city": city,
        "keywords": keywords[:5],
        "max_jobs": max(1, min(int(max_jobs), 20)),
    }
    with tempfile.TemporaryDirectory(prefix="offerforge_browser_use_") as temp_dir:
        request_path = Path(temp_dir) / "request.json"
        result_path = Path(temp_dir) / "result.json"
        progress_path = Path(temp_dir) / "progress.json"
        request_path.write_text(json.dumps(request_data, ensure_ascii=False), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_DIR)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_PROXY"] = "127.0.0.1,localhost,::1"
        env["no_proxy"] = env["NO_PROXY"]
        env["ANONYMIZED_TELEMETRY"] = "false"
        process = subprocess.Popen(
            [str(BROWSER_USE_PYTHON), "-m", "modules.browser_use_job_collector",
             "--worker", str(request_path), str(result_path), str(progress_path)],
            cwd=str(PROJECT_DIR), env=env,
        )
        deadline = time.monotonic() + max(30, min(timeout_seconds, 600))
        last_progress = ""
        if callable(progress_callback):
            progress_callback("browser_starting", "正在启动猎聘独立Edge", 35)
        try:
            while process.poll() is None:
                if progress_path.exists():
                    current_progress = progress_path.read_text(encoding="utf-8")
                    if current_progress != last_progress:
                        last_progress = current_progress
                        progress = json.loads(current_progress)
                        if callable(progress_callback):
                            progress_callback(progress["stage"], progress["message"], progress["percent"])
                stop_reason = stop_check() if callable(stop_check) else None
                if stop_reason:
                    _stop_process_tree(process)
                    code = "COLLECTION_TIMEOUT" if stop_reason == "timed_out" else "USER_CANCELLED"
                    raise BrowserUseCollectionError(code, "岗位采集已安全停止")
                if time.monotonic() >= deadline:
                    _stop_process_tree(process)
                    raise BrowserUseCollectionError("BROWSER_TIMEOUT", "智能浏览器采集超时，请稍后重试")
                time.sleep(1)
            if process.returncode != 0 or not result_path.exists():
                raise BrowserUseCollectionError("BROWSER_PROCESS_FAILED", "智能浏览器进程异常结束")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if not result.get("ok"):
                raise BrowserUseCollectionError(
                    str(result.get("error_code") or "BROWSER_AGENT_FAILED"),
                    str(result.get("error") or "智能浏览器采集失败"),
                )
            payload = result.get("data", {})
            raw_jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            jobs = normalize_jobs(payload, source_code, city, keywords, request_data["max_jobs"])
            if not raw_jobs:
                raise BrowserUseCollectionError("EMPTY_EXACT_RESULTS", f"{city}暂未找到精确匹配岗位")
            if not jobs:
                locations = [str(item.get("location", "")) for item in raw_jobs if isinstance(item, dict)]
                if any(locations):
                    raise BrowserUseCollectionError("CITY_RESULT_MISMATCH", f"页面返回了非{city}岗位，已全部拦截且未保存")
                raise BrowserUseCollectionError("BROWSER_RESULT_INVALID", "岗位结果缺少必要字段，已停止保存")
            if callable(progress_callback):
                progress_callback("browser_validating", "正在核对猎聘岗位城市、来源与重复项", 62)
            return jobs
        finally:
            if process.poll() is None:
                _stop_process_tree(process)


async def _worker(request_path: Path, result_path: Path, progress_path: Path) -> None:
    import asyncio

    from browser_use import Agent, Browser, ChatOpenAI
    from dotenv import load_dotenv

    load_dotenv(PROJECT_DIR / ".env", override=False)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    config = SOURCE_CONFIG[request["source"]]
    city_name = str(request["city"]).strip().removesuffix("市")
    city_code = config["city_codes"].get(city_name)
    if not city_code:
        raise RuntimeError(f"{config['name']}智能浏览器尚未配置城市：{city_name}")
    search_url = "https://www.liepin.com/zhaopin/?" + urlencode({
        "dq": city_code,
        "city": city_code,
        "currentPage": 0,
        "pageSize": 40,
        "key": request["keywords"][0],
    })
    browser = Browser(
        channel="msedge",
        user_data_dir=BROWSER_USE_DIR / f".offerforge-{request['source']}-profile",
        headless=False,
        keep_alive=False,
    )
    task = f"""直接打开 {search_url}。这是{config['name']}“{city_name}”城市的岗位搜索结果页，关键词为{json.dumps(request['keywords'], ensure_ascii=False)}。
最多读取{request['max_jobs']}个公开可见岗位。只浏览、搜索、翻页和提取，不登录、不绕过验证码、不投递、不发送消息、不修改账号。
遇到登录墙、验证码、拒绝访问或无法确认城市时立即结束并说明原因。
先确认页面城市为“{city_name}”；清除网站自行保留、但用户没有指定的工作经验、学历或其他附加筛选。不要切换成全国或其他城市。
最终只返回合法JSON对象：{{"jobs":[{{"title":"", "company":"", "location":"", "salary":"", "url":"", "description":"", "tags":[]}}]}}。
不得杜撰；缺失字段用空字符串；URL必须来自当前{config['name']}页面。"""
    try:
        _write_progress(progress_path, "browser_navigating", f"正在打开猎聘{city_name}搜索页", 40)
        await browser.start()
        await browser.navigate_to(search_url)
        await asyncio.sleep(3)
        _write_progress(progress_path, "browser_extracting", "正在直接读取猎聘公开岗位卡片", 48)
        deterministic_jobs = await _extract_liepin_cards(browser, request["max_jobs"])
        deterministic_payload = {"jobs": deterministic_jobs}
        if normalize_jobs(
            deterministic_payload,
            request["source"],
            request["city"],
            request["keywords"],
            request["max_jobs"],
        ):
            _write_progress(progress_path, "browser_formatting", "固定规则已读取岗位，正在整理结果", 60)
            result_path.write_text(
                json.dumps({"ok": True, "data": deterministic_payload}, ensure_ascii=False),
                encoding="utf-8",
            )
            return

        _write_progress(progress_path, "browser_collecting", "固定规则未读到精确结果，切换AI浏览器", 50)
        from modules.deepseek_client import resolve_llm_config
        llm_cfg = resolve_llm_config()
        api_key = str(llm_cfg.get("api_key") or "").strip()
        base_url = str(llm_cfg.get("base_url") or "").strip()
        model_name = str(llm_cfg.get("model") or "").strip()
        if not api_key:
            raise RuntimeError("未配置AI API密钥（请在右上角「模型设置」中配置 ZHIPU_API_KEY / DEEPSEEK_API_KEY）")
        llm = ChatOpenAI(
            model=model_name, api_key=api_key,
            base_url=base_url,
            temperature=0.1, max_retries=2, timeout=90,
            add_schema_to_system_prompt=True, dont_force_structured_output=True,
        )
        agent = Agent(
            task=task, llm=llm, browser=browser, use_vision=False,
            max_actions_per_step=3, max_failures=3, directly_open_url=False,
            extend_system_message="未经用户确认不得登录、投递、发送消息、删除数据或绕过访问限制。",
        )

        async def report_step(_browser_state, _agent_output, step_number):
            _write_progress(
                progress_path,
                "browser_collecting",
                f"智能浏览器正在执行第{step_number}步，读取公开岗位",
                min(58, 42 + int(step_number)),
            )

        agent.register_new_step_callback = report_step
        history = await agent.run(max_steps=20)
        _write_progress(progress_path, "browser_formatting", "正在整理智能浏览器返回结果", 60)
        final_result = history.final_result() or ""
        if not final_result:
            failure_message = _agent_failure_message(history.errors())
            if failure_message:
                raise RuntimeError(failure_message)
        payload = _extract_json(final_result)
        result_path.write_text(json.dumps({"ok": True, "data": payload}, ensure_ascii=False), encoding="utf-8")
    finally:
        await browser.stop()


def _worker_main() -> None:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=3, metavar=("REQUEST", "RESULT", "PROGRESS"))
    args = parser.parse_args()
    request_path, result_path, progress_path = map(Path, args.worker)
    try:
        asyncio.run(_worker(request_path, result_path, progress_path))
    except Exception as error:
        error_code, error_message = _classify_failure(str(error))
        result_path.write_text(
            json.dumps({"ok": False, "error_code": error_code, "error": error_message}, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    _worker_main()

# ============================================
# modules/job_scraper.py - 岗位信息采集器 v6（多平台）
# 支持: 51job, 猎聘(liepin)
# ============================================
import os, sys, json, time, random, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DATA_DIR
from datetime import datetime


def load_profile():
    """加载最新的简历（按文件修改时间排序）"""
    profiles = []
    if os.path.exists(DATA_DIR):
        files = [f for f in os.listdir(DATA_DIR) if f.startswith("resume_") and f.endswith(".json")]
        # 按文件修改时间倒序，最新的在前
        files.sort(key=lambda f: os.path.getmtime(os.path.join(DATA_DIR, f)), reverse=True)
        for f in files:
            with open(os.path.join(DATA_DIR, f), "r", encoding="utf-8") as fp:
                profiles.append(json.load(fp))
    if not profiles:
        return None
    return profiles[0]


def extract_keywords(profile):
    """从简历提取搜索关键词：优先使用求职意向，自动拆分行业+职位"""
    keywords = []
    
    # 1. 求职意向（优先级最高）
    desired = profile.get("desired_position", "")
    if desired:
        parts = re.split(r'[|｜/、，,]', desired)
        for p in parts:
            p = p.strip()
            if p and len(p) >= 2:
                keywords.append(p)
                # 智能拆分：如"金融行业"->额外生成"金融"，"餐饮行业"->"餐饮"
                # 去掉常见后缀，生成更精准的短关键词
                for suffix in ["行业", "方向", "领域", "岗位", "职位"]:
                    if p.endswith(suffix) and len(p) > len(suffix):
                        short = p[:-len(suffix)]
                        if len(short) >= 2 and short not in keywords:
                            keywords.append(short)
        # 去重，最多取5个
        seen = set()
        result = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                result.append(k)
        return result[:5]
    
    # 2. 求职意向为空时，才从工作经历中提取关键词
    experiences = profile.get("work_experience", []) + profile.get("internship", [])
    exp_kws = set()
    industry_kws = ["运营", "新媒体", "短视频", "内容", "推广", "营销", "文案",
                    "策划", "电商", "直播", "品牌", "设计", "数据分析", "产品",
                    "销售", "客服", "行政", "人事", "财务", "开发", "测试",
                    "视频", "剪辑", "拍摄", "自媒体", "社区", "用户", "增长",
                    "社群", "私域", "公众号", "小红书", "抖音", "TikTok",
                    "餐饮", "酒店", "旅游", "教育", "医疗", "金融", "房地产",
                    "物流", "制造", "汽车", "游戏", "音乐", "体育", "法律"]
    for exp in experiences:
        combined = exp.get("position", "") + " " + exp.get("description", "")
        for kw in industry_kws:
            if kw in combined and kw not in " ".join(keywords):
                exp_kws.add(kw)
    for kw in list(exp_kws)[:5]:
        keywords.append(kw)
    
    # 去重
    seen = set()
    result = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result[:6]


def infer_salary_range(profile):
    """根据简历期望薪资推断合理薪资范围（±2-3k浮动）"""
    desired = profile.get("desired_salary", "")
    if desired and re.search(r'\d', desired):
        # 简历有期望薪资，以它为中心浮动±2-3k
        nums = re.findall(r'(\d+(?:\.\d+)?)', desired)
        if len(nums) >= 2:
            vals = [float(n) for n in nums[:2]]
            center = sum(vals) / len(vals)
            lower = max(0, int(center) - 3)
            upper = int(center) + 3
            return f"{lower}k-{upper}k"
        elif len(nums) == 1:
            base = float(nums[0])  # 取第一个数字作为基准
            # 返回 ±2-3k 的范围
            lower = max(0, int(base) - 3)
            upper = int(base) + 3
            return f"{lower}k-{upper}k"
        return desired
    
    experiences = profile.get("work_experience", []) + profile.get("internship", [])
    position = profile.get("desired_position", "")
    
    # 计算经验年限
    total_years = 0.0
    for exp in experiences:
        dur = exp.get("duration", "")
        years = re.findall(r'(\d{4})', dur)
        if len(years) >= 2:
            start, end = int(years[0]), int(years[-1])
            if "至今" in dur or "现在" in dur:
                end = 2026
            total_years += max(0, end - start)
    
    is_junior = total_years < 1 or ("实习" in position or "协助" in position or "助理" in position)
    is_entry = total_years < 0.5 or ("应届" in position or "实习" in position or "小白" in position)
    
    if is_entry:
        return "3k-6k"
    elif is_junior:
        return "4k-8k"
    elif total_years < 3:
        return "6k-15k"
    else:
        return "10k-25k"


def extract_location(profile):
    """从简历中提取目标城市 - 支持城市名和省份名"""
    # 城市列表（扩展版）
    cities = [
        "广州", "深圳", "北京", "上海", "杭州", "成都", "武汉", "南京", "东莞", "佛山",
        "珠海", "中山", "惠州", "长沙", "重庆", "天津", "苏州", "西安", "郑州", "厦门",
        "合肥", "济南", "青岛", "福州", "昆明", "贵阳", "南宁", "海口", "南昌", "太原",
        "哈尔滨", "长春", "沈阳", "大连", "无锡", "宁波", "温州", "嘉兴", "绍兴",
        "株洲", "湘潭", "衡阳", "岳阳", "常德", "郴州", "邵阳", "益阳", "永州",
        "江门", "肇庆", "湛江", "茂名", "清远", "揭阳", "汕头", "汕尾", "潮州",
        "绵阳", "宜宾", "南充", "泸州", "德阳",
        "宜昌", "襄阳", "荆州", "黄石", "十堰",
        "洛阳", "开封", "新乡", "南阳", "许昌",
        "烟台", "潍坊", "临沂", "淄博", "济宁",
        "泉州", "漳州", "莆田", "龙岩",
        "唐山", "保定", "邯郸", "廊坊", "秦皇岛",
        "柳州", "桂林", "玉林", "北海",
        "三亚", "儋州",
        "芜湖", "马鞍山", "安庆",
        "镇江", "扬州", "常州", "徐州", "南通", "盐城",
        "金华", "台州", "湖州",
    ]
    
    # 省份→省会映射
    province_to_capital = {
        "湖南": "长沙", "湖北": "武汉", "广东": "广州", "广西": "南宁",
        "浙江": "杭州", "江苏": "南京", "四川": "成都", "山东": "济南",
        "福建": "福州", "江西": "南昌", "安徽": "合肥", "河南": "郑州",
        "河北": "石家庄", "山西": "太原", "陕西": "西安", "甘肃": "兰州",
        "辽宁": "沈阳", "吉林": "长春", "黑龙江": "哈尔滨", "云南": "昆明",
        "贵州": "贵阳", "海南": "海口", "内蒙古": "呼和浩特", "新疆": "乌鲁木齐",
        "西藏": "拉萨", "青海": "西宁", "宁夏": "银川",
    }
    
    text = json.dumps(profile, ensure_ascii=False)
    
    # 1. 先找城市名
    found_cities = []
    for city in cities:
        if city in text:
            found_cities.append(city)
    
    if found_cities:
        from collections import Counter
        top = Counter(found_cities).most_common(1)[0][0]
        print(f"提取地点(城市): {top}")
        return top
    
    # 2. 没找到城市名，尝试从省份推断省会
    for province, capital in province_to_capital.items():
        if province in text:
            print(f"提取地点(省份→省会): {province} → {capital}")
            return capital
    
    return None

# 51job metro 城市码映射
METRO_CODES = {
    "广州": "030200", "深圳": "040000", "北京": "010000", "上海": "020000",
    "杭州": "080200", "成都": "090200", "武汉": "180200", "南京": "070200",
    "东莞": "030800", "佛山": "030500", "珠海": "030400", "中山": "030600",
    "惠州": "030300", "长沙": "190200", "重庆": "060000", "天津": "050000",
    "苏州": "070300", "西安": "200200", "郑州": "170200", "厦门": "110300",
    "合肥": "150200", "济南": "120200", "青岛": "120300", "福州": "110200",
    "昆明": "250200", "贵阳": "240200", "南宁": "230200", "海口": "210200",
    "南昌": "160200", "太原": "260200", "哈尔滨": "220200", "长春": "220100",
    "沈阳": "230100", "大连": "230300", "无锡": "070400", "宁波": "080300",
    "温州": "080400", "嘉兴": "080500", "绍兴": "080700", "台州": "080900",
    "金华": "081000", "湖州": "080600", "兰州": "270200", "石家庄": "130100",
    "株洲": "190300", "湘潭": "190400", "衡阳": "191100", "岳阳": "190600",
    "常州": "070500", "镇江": "070600", "扬州": "070800", "徐州": "071200",
    "南通": "071000", "盐城": "071500", "洛阳": "170400", "南阳": "171300",
    "烟台": "120500", "潍坊": "120700", "临沂": "121600", "淄博": "120400",
    "泉州": "110400", "漳州": "110500", "唐山": "130600", "保定": "130800",
    "柳州": "230400", "桂林": "230500", "宜昌": "180500", "襄阳": "180700",
    "绵阳": "090400", "宜宾": "091600",
}

def get_metro_code(city_name):
    for city, code in METRO_CODES.items():
        if city_name and city in city_name:
            return code
    return "000000"


class JobScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.page = None
        self.playwright = None
        self.jobs = []
        self.profile = None
        self.keywords = []

    def set_profile(self, profile):
        self.profile = profile
        self.keywords = extract_keywords(profile) if profile else []
        print(f"搜索关键词: {self.keywords}")

    def _launch_browser(self):
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(
                channel="msedge", headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            print("使用 Edge 浏览器")
        except:
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            print("使用 Chromium 浏览器")
        self.page = self.browser.new_page()
        self.page.set_viewport_size({"width": 1280, "height": 800})
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

    def random_delay(self, min_sec=1, max_sec=3):
        time.sleep(random.uniform(min_sec, max_sec))

    def close(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()
    def search_all(self, platforms=None, pages=2):
        """????????"""
        if not platforms:
            platforms = ["51job", "liepin"]
        if not self.page:
            self._launch_browser()

        # ???? + ??????
        self.location = "广州"  # Guangzhou
        # ??????app.py???????????????
        if not hasattr(self, "salary_range") or not self.salary_range:
            self.salary_range = infer_salary_range(self.profile) if self.profile else ""
        print(f"????: {self.location} | ????: {self.salary_range}")

        all_jobs = []
        for plat in platforms:
            print(f"\n>>> ????: {plat}")
            if plat == "51job":
                jobs = self.search_51job(pages=pages)
            elif plat == "liepin":
                jobs = self.search_liepin(pages=pages)
            else:
                print(f"  ????: {plat}")
                continue
            print(f"  {plat}: {len(jobs)} ???")
            all_jobs.extend(jobs)

        self.jobs = all_jobs
        print(f"\n?? {len(self.jobs)} ???")
        return self.jobs

    def search_51job(self, pages=3):
        if not self.keywords:
            print("没有搜索关键词")
            return []
        all_jobs = []
        seen_ids = set()
        for kw in self.keywords:
            print(f"  >>> 51job 搜索: {kw}")
            # 51job ?? jobArea ???????metro???????jobArea?
            url = f"https://we.51job.com/pc/search?keyword={kw}&searchType=2&sortType=0&jobArea=030200"
            try:
                self.page.goto(url, wait_until="networkidle", timeout=30000)
                self.random_delay(2, 3)
                
                # ??????????????????????
                try:
                    page_title = self.page.title()
                    if "??" not in page_title:
                        print(f"  ????????: {page_title}?????...")
                        self._click_city_tab("??")
                        self.random_delay(2, 3)
                except:
                    pass
                
                for p in range(pages):
                    self.page.evaluate("window.scrollBy(0, 800)")
                    self.random_delay(1, 2)
                cards = self.page.query_selector_all(".joblist-item")
                print(f"  找到 {len(cards)} 个岗位卡片")
                for card in cards:
                    try:
                        job = self._parse_51job_card(card, kw)
                        if job and job.get("job_id") not in seen_ids:
                            seen_ids.add(job.get("job_id"))
                            # 强地点过滤：必须包含目标城市名
                            job_loc = job.get("location", "") or ""
                            if self.location and self.location not in job_loc:
                                city_core = self.location.replace("市", "").replace("省", "")
                                if city_core not in job_loc:
                                    continue  # 跳过不匹配城市的岗位
                                if self.location not in job_loc:
                                    city_core = self.location.replace("市", "")
                                    if city_core not in job_loc:
                                        continue
                            # 薪资先不过滤，收集所有岗位，后面统一处理
                            all_jobs.append(job)
                    except Exception as e:
                        pass
            except Exception as e:
                print(f"  51job搜索 '{kw}' 出错: {e}")
        
        # 薪资分级过滤：精确匹配 → 放宽2-3k → 返回所有
        if self.salary_range:
            all_jobs = self._filter_by_salary_tiered(all_jobs)
        
        return all_jobs


    def _click_city_tab(self, city_name):
        """在51job页面上点击对应城市选项卡"""
        import re
        core = city_name.replace("市", "").replace("省", "")
        # 尝试多种选择器
        selectors = [
            f'a:has-text("{core}")',
            f'span:has-text("{core}")',
            f'li:has-text("{core}")',
            f'[class*="city"]:has-text("{core}")',
            f'[class*="area"]:has-text("{core}")',
            f'[class*="location"]:has-text("{core}")',
            f'[class*="work"]:has-text("{core}")',

        ]
        for sel in selectors:
            try:
                el = self.page.query_selector(sel)
                if el:
                    el.click()
                    print(f"  已点击城市: {core} (选择器: {sel})")
                    return True
            except:
                pass
        # 备选：用文本匹配点击
        try:
            all_text = self.page.query_selector_all("a, span, li, div[class*='city'], div[class*='area']")
            for el in all_text:
                try:
                    txt = el.inner_text().strip()
                    if txt == core or txt == city_name or (core in txt and len(txt) <= 6):
                        el.click()
                        print(f"  已点击城市选项卡: {txt}")
                        return True
                except:
                    pass
        except:
            pass
        print(f"  未找到城市选项卡: {city_name}")
        
        # JS fallback
        try:
            js_code = f'(function(){{var c="{core}";var a=document.querySelectorAll("a,span,div,li");for(var i=0;i<a.length;i++){{var t=(a[i].innerText||"").trim();if(t===c||(t.indexOf(c)>=0&&t.length<=8)){{a[i].click();return"ok:"+t}}}}return"no"}})()'
            r = self.page.evaluate(js_code)
            if r and r.startswith('ok:'):
                print(f'  JS clicked: {r}')
                return True
        except:
            pass
        return False

    def _filter_by_salary_tiered(self, jobs):
        if not jobs:
            return []
        if not self.salary_range:
            return jobs
        matched = [j for j in jobs if self._match_salary_exact(j.get("salary", ""))]
        print(f"  薪资过滤 [{self.salary_range}]: 匹配{len(matched)}/{len(jobs)}个")
        if not matched:
            print(f"  薪资范围[{self.salary_range}]内无匹配岗位")
        return matched

    def _match_salary_exact(self, job_salary):
        """精确薪资匹配（原_match_salary）"""
        return self._match_salary(job_salary)

    def _match_salary_widen(self, job_salary, widen=2):
        """放宽薪资匹配：在原有范围基础上扩大 widen k"""
        try:
            if not self.salary_range or not job_salary:
                return True
            
            def to_k(text):
                try:
                    t = str(text).lower().replace(" ", "").replace(",", "")
                    nums = re.findall(r'(\d+\.?\d*)', t)
                    if not nums:
                        return None
                    v = [float(n) for n in nums[:2]]
                    if "万" in t or "w" in t:
                        v = [x * 10 for x in v]
                    elif any(x > 100 for x in v if x > 0):
                        v = [x / 1000 for x in v]
                    if "天" in t or "/d" in t.lower() or "日" in t:
                        v = [x * 22 / 1000 for x in v]
                    return (min(v), max(v)) if len(v) > 1 else (v[0], v[0])
                except:
                    return None
            
            jk = to_k(job_salary)
            rk = to_k(self.salary_range)
            if not jk or not rk:
                return True
            
            j_min, j_max = jk
            r_min, r_max = rk
            
            # 放宽范围: r_min - widen 到 r_max + widen
            r_min_widened = max(0, r_min - widen)
            r_max_widened = r_max + widen
            
            return not (j_max < r_min_widened or j_min > r_max_widened)
        except:
            return True

    def _parse_51job_card(self, card, keyword):
        try:
            sensor_div = card.query_selector("[sensorsdata]")
            if not sensor_div:
                return None
            sensors_str = sensor_div.get_attribute("sensorsdata") or ""
            import html as _html
            sensors_str = _html.unescape(sensors_str)
            try:
                sensor_data = json.loads(sensors_str)
            except Exception as _je:
                # Try fixing common JSON issues
                try:
                    import re as _re
                    fixed = _re.sub(r'\\(?!["\\/bfnrtu])', r'\\', sensors_str)
                    sensor_data = json.loads(fixed)
                except:
                    return self._parse_51job_card_text(card, keyword)
            job_title = sensor_data.get("jobTitle", "")
            if not job_title:
                return None
            job_id = sensor_data.get("jobId", "")
            company_name = ""
            company_link = card.query_selector("a")
            if company_link:
                full_company = company_link.inner_text().strip()
                company_name = full_company.split("\n")[0].strip()
            tag_els = card.query_selector_all("[class*=tag], [class*=skill]")
            tags = [t.inner_text().strip() for t in tag_els if t.inner_text().strip()]
            return {
                "job_id": job_id, "title": job_title,
                "salary": sensor_data.get("jobSalary", ""),
                "location": sensor_data.get("jobArea", ""),
                "experience": sensor_data.get("jobYear", ""),
                "education": sensor_data.get("jobDegree", ""),
                "company": company_name,
                "tags": tags,
                "url": f"https://jobs.51job.com/guangzhou/{job_id}.html" if job_id else "",
                "source": "51前程无忧", "keyword": keyword,
                "collected_at": datetime.now().isoformat()
            }
        except:
            return None


    def _parse_51job_card_text(self, card, keyword):
        """?????51job??????"""
        try:
            title_el = card.query_selector("[class*=job], [class*=title], .job-name, .jname")
            title = title_el.inner_text().strip() if title_el else ""
            if not title:
                return None
            salary_el = card.query_selector("[class*=salary], [class*=pay], .job-salary")
            salary = salary_el.inner_text().strip() if salary_el else ""
            loc_el = card.query_selector("[class*=area], [class*=location], .job-area")
            location = loc_el.inner_text().strip() if loc_el else ""
            job_id = str(hash(title + (salary or ""))) 
            return {
                "job_id": job_id, "title": title,
                "salary": salary, "location": location,
                "company": "", "tags": [],
                "url": "", "source": "51前程无忧", "keyword": keyword
            }
        except:
            return None

    def search_liepin(self, pages=2):
        """????????????????????"""
        print(f"  >>> ????: {self.keywords}")
        print("  ?????????????")
        return []

    def _parse_liepin_card(self, card, keyword):
        """????????"""
        return None

    def _match_salary(self, job_salary):
        if not self.salary_range:
            return True
        try:
            ts = str(job_salary).lower().replace(" ", "").replace(",", "")
            nums = re.findall(r"(\d+(?:\.\d+)?)\s*[kKwW万千]?", ts)
            if not nums:
                return True
            nums = [float(n) for n in nums]
            has_k = any(u in ts for u in ["k", "千"])
            has_w = any(u in ts for u in ["w", "万"])
            if has_w:
                nums = [n * 10 for n in nums]
            elif not has_k and any(n >= 100 for n in nums if n > 0):
                nums = [n / 1000 for n in nums]
            j_min, j_max = min(nums), max(nums)
            range_nums = re.findall(r"\d+", str(self.salary_range))
            if len(range_nums) >= 2:
                r_min = float(range_nums[0])
                r_max = float(range_nums[1])
                return not (j_max < r_min or j_min > r_max)
            return True
        except:
            return True

    def save_jobs(self):
        """???????JSON??"""
        os.makedirs(DATA_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.json"
        filepath = os.path.join(DATA_DIR, filename)
        data = {
            "profile": {
                "name": self.profile.get("name", "") if self.profile else "",
                "desired_position": self.profile.get("desired_position", "") if self.profile else ""
            },
            "keywords": self.keywords,
            "count": len(self.jobs),
            "collected_at": datetime.now().isoformat(),
            "jobs": self.jobs
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n???: {filepath}")
        return filepath

def run_test():
    print("=" * 50)
    print("  AI 简历助手 - 岗位采集测试")
    print("=" * 50)
    profile = load_profile()
    if not profile:
        print("没找到已解析的简历！")
        return
    print(f"\n使用简历: {profile.get('name', '未知')}")
    keywords = extract_keywords(profile)
    print(f"关键词: {keywords}")
    scraper = JobScraper(headless=False)
    scraper.set_profile(profile)
    try:
        scraper._launch_browser()
        scraper.search_all(platforms=["51job", "liepin"], pages=2)
        if scraper.jobs:
            scraper.save_jobs()
            for j in scraper.jobs[:10]:
                print(f"  [{j['source']}] {j['title']} | {j['salary']} | {j['company']}")
    finally:
        scraper.close()


if __name__ == "__main__":
    run_test()

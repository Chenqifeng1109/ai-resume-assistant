# ============================================
# modules/resume_parser.py — 简历解析模块
# 大白话：把 Word/PDF/文本 简历转成结构化的数据
# ============================================

import os
import sys
import json
import re
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RESUMES_DIR, LOGS_DIR, DEEPSEEK_MODEL
from modules.deepseek_client import DeepSeekClient
from modules.resume_optimization_guard import original_profile_snapshot
from modules.resume_schema import RESUME_LIST_FIELDS, validate_resume_payload
from modules.resume_version_repository import save_original_version


# 常见简历标题别名：左边是程序里的标准模块，右边是用户可能使用的标题。
# 同一组标题会进入同一个结构化字段，避免“实习经历”因不叫“工作经历”而漏掉。
RESUME_SECTION_ALIASES = {
    "basic_info": ["基本信息", "个人信息", "个人资料", "联系方式"],
    "desired_position": ["求职意向", "求职目标", "应聘方向", "目标岗位", "职业目标"],
    "education": ["教育经历", "教育背景", "学习经历", "学历背景"],
    "work_experience": [
        "工作经历", "工作经验", "职业经历", "任职经历",
        "实习经历", "实习经验",
    ],
    "practical_experience": [
        "个人实践", "实践经历", "实践经验", "社会实践",
        "社会实践经历", "专业实践", "实训经历", "兼职经历", "志愿实践",
    ],
    "project_experience": ["项目经历", "项目经验", "项目实践", "项目案例"],
    "campus_experience": [
        "校园经历", "在校经历", "校内经历", "学生工作",
        "社团经历", "校园活动", "志愿经历", "志愿服务",
    ],
    "research_experience": ["科研经历", "科研项目", "研究经历", "学术经历", "学术研究"],
    "skills": ["专业技能", "技能特长", "个人技能", "核心技能", "技能清单"],
    "awards": [
        "荣誉奖项", "获奖经历", "获奖情况", "奖励荣誉",
        "荣誉奖励", "所获荣誉", "奖项荣誉",
    ],
    "certificates": [
        "技能证书", "资格证书", "专业证书", "各类证书",
        "证书资质", "资质证书", "认证证书",
    ],
    "language_skills": ["语言能力", "外语能力", "语言水平", "英语能力", "外语水平"],
    "interests": ["兴趣爱好", "爱好特长", "个人爱好", "特长爱好"],
    "summary": [
        "自我评价", "个人总结", "个人优势", "自我介绍", "个人简介",
        "关于我", "自我描述", "个人陈述", "职业简介", "职业概述", "核心优势",
    ],
}

RESUME_EVIDENCE_FIELDS = (
    "name",
    "phone",
    "email",
    "desired_position",
    "skills",
)


def _normalize_evidence_text(text) -> str:
    """统一空格、横线和括号，方便匹配不同格式的电话或文本。"""
    return re.sub(r"[\s\-()（）]+", "", str(text)).casefold()


def find_value_source(resume_text: str, value, context_radius: int = 1) -> dict | None:
    """
    在简历原文中寻找一个字段值，并返回它的行号、原文和上下文。
    大白话：AI 说“这个字段是某个值”，Python 再回原文里核对证据。
    """
    target = str(value).strip() if value is not None else ""
    if not target:
        return None

    lines = resume_text.splitlines()
    normalized_target = _normalize_evidence_text(target)

    for line_number, line in enumerate(lines, start=1):
        confidence = None
        if target.casefold() in line.casefold():
            confidence = 1.0
        elif normalized_target and normalized_target in _normalize_evidence_text(line):
            confidence = 0.9

        if confidence is not None:
            line_index = line_number - 1
            start_index = max(0, line_index - context_radius)
            end_index = min(len(lines), line_index + context_radius + 1)
            return {
                "value": target,
                "source_text": line.strip(),
                "line_number": line_number,
                "context": lines[start_index:end_index],
                "confidence": confidence,
            }

    return None


def build_field_evidence(resume_text: str, parsed_data: dict) -> dict:
    """为关键字段建立可追溯证据；找不到原文就不伪造证据。"""
    evidence = {}

    for field in RESUME_EVIDENCE_FIELDS:
        raw_value = parsed_data.get(field)
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        entries = []
        seen = set()

        for value in values:
            if not isinstance(value, (str, int, float)):
                continue
            source = find_value_source(resume_text, value)
            if source is None:
                continue

            identity = (_normalize_evidence_text(value), source["line_number"])
            if identity in seen:
                continue
            seen.add(identity)
            entries.append(source)

        if entries:
            evidence[field] = entries

    return evidence


def normalize_resume_section_headings(resume_text: str) -> str:
    """
    把不同写法的简历标题标记为统一模块，同时保留原标题。
    只处理单独占一行的标题，不替换普通正文，避免误伤。
    """
    alias_to_section = {
        alias: section
        for section, aliases in RESUME_SECTION_ALIASES.items()
        for alias in aliases
    }
    normalized_lines = []

    for original_line in resume_text.splitlines():
        heading = original_line.strip().strip(":：-—|【】[]（）() ")
        section = alias_to_section.get(heading)
        if section:
            normalized_lines.append(f"[简历模块:{section}；原标题:{heading}]")
        else:
            normalized_lines.append(original_line)

    return "\n".join(normalized_lines)


def read_docx(file_path: str) -> str:
    """
    读取 Word 文档（.docx）
    大白话：把 Word 文件的内容全捞出来变成纯文本
    """
    try:
        from docx import Document
        doc = Document(file_path)
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():  # 跳过空行
                text_parts.append(para.text.strip())

        # 简历常把教育、经历、技能放在 Word 表格中，不能只读取普通段落。
        for table in doc.tables:
            for row in table.rows:
                row_parts = []
                seen_cells = set()
                for cell in row.cells:
                    cell_id = id(cell._tc)
                    if cell_id in seen_cells:
                        continue
                    seen_cells.add(cell_id)
                    cell_text = "\n".join(
                        paragraph.text.strip()
                        for paragraph in cell.paragraphs
                        if paragraph.text.strip()
                    )
                    if cell_text:
                        row_parts.append(cell_text)
                if row_parts:
                    text_parts.append(" | ".join(row_parts))
        return "\n".join(text_parts)
    except Exception as e:
        return f"<Word文件读取失败: {e}>"


def read_pdf(file_path: str) -> str:
    """
    读取 PDF 文件
    大白话：一页一页读 PDF，把文字全拼起来
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        return f"<PDF文件读取失败: {e}>"


def read_txt(file_path: str) -> str:
    """
    读取纯文本文件
    大白话：直接打开文件读全部内容
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<TXT文件读取失败: {e}>"

def extract_resume_info(resume_text: str) -> dict:
    """
    核心函数：把简历文字交给 DeepSeek，让它提取出结构化信息
    大白话：把简历文本丢给 AI，AI 会返回一个整理好的字典
    """
    client = DeepSeekClient()

    # ----- 给 AI 的角色设定（System Prompt）-----
    # 告诉 AI："你是一个专业的简历分析师，请严格按照格式回答"
    section_alias_text = json.dumps(RESUME_SECTION_ALIASES, ensure_ascii=False)
    system_prompt = """你是一个专业的简历分析师。请从以下简历中提取关键信息。
只返回 JSON 格式，不要包含任何其他文字。

JSON 结构如下：
{
  "name": "姓名",
  "phone": "电话号码",
  "email": "邮箱",
  "education": [
    {"school": "学校名", "degree": "学历", "major": "专业", "year": "毕业年份"}
  ],
  "work_experience": [
    {"company": "公司名", "position": "职位", "duration": "起止时间", "description": "工作内容摘要"}
  ],
  "practical_experience": [
    {"organization": "单位/组织/活动名称", "role": "角色或职责", "duration": "起止时间", "description": "实践内容和成果"}
  ],
  "project_experience": [
    {"name": "项目名", "role": "你的角色", "duration": "起止时间", "description": "项目描述和你的贡献"}
  ],
  "campus_experience": [
    {"organization": "学校/组织名", "role": "职务或角色", "duration": "起止时间", "description": "主要工作和成果"}
  ],
  "research_experience": [
    {"name": "科研或研究名称", "role": "你的角色", "duration": "起止时间", "description": "研究内容和成果"}
  ],
  "skills": ["技能1", "技能2", "技能3"],
  "awards": [
    {"name": "奖项或荣誉名称", "level": "国家级/省级/校级等", "year": "获奖时间", "description": "补充说明"}
  ],
  "certificates": [
    {"name": "证书名称", "level": "等级或分数", "year": "取得时间", "issuer": "颁发机构"}
  ],
  "language_skills": [
    {"language": "语言", "level": "熟练程度", "certificate": "相关证书或成绩"}
  ],
  "interests": ["兴趣或特长1", "兴趣或特长2"],
  "desired_position": "期望岗位",
  "desired_salary": "期望薪资",
  "summary": "一句话总结这位候选人的核心优势"
}

注意：
- 如果某项信息没找到，用空字符串 "" 或空列表 []
- education、work_experience、practical_experience、project_experience、campus_experience、research_experience 按时间倒序排列
- skills 列出所有提到的技能关键词
- 标记为 work_experience 的工作和实习内容写入 work_experience
- 标记为 practical_experience 的个人实践、社会实践、实训和兼职内容写入 practical_experience
- practical_experience、campus_experience、research_experience、awards、certificates、language_skills、interests 必须独立提取，不要混入 skills 或其他经历
- summary 从自我介绍、个人简介、自我评价等模块提取为一段文字；没有时返回空字符串 ""
- 简历没有对应内容时，该列表必须返回 []，不得编造；空列表由前端隐藏
- 标题写法不同不代表内容可以省略；请根据标准模块和上下文完整提取
""" + f"\n常见标题与标准模块的对应字典：\n{section_alias_text}\n"

    # ----- 调用 AI -----
    analysis_text = normalize_resume_section_headings(resume_text)
    result = client.chat_json(system_prompt, analysis_text)
    if isinstance(result, dict) and "error" not in result:
        result = validate_resume_payload(result)
        if "error" not in result:
            result["field_evidence"] = build_field_evidence(resume_text, result)
    return result

def parse_resume(file_path: str) -> dict:
    """
    主入口：给定简历文件路径，返回结构化数据
    大白话：你只需告诉它简历在哪，它自动识别格式、读取、AI分析、返回结果
    """
    # 1. 判断文件类型，选对应的读取函数
    ext = os.path.splitext(file_path)[1].lower()  # 取文件后缀 .docx / .pdf / .txt

    if ext == ".docx":
        text = read_docx(file_path)
    elif ext == ".pdf":
        text = read_pdf(file_path)
    elif ext == ".txt":
        text = read_txt(file_path)
    else:
        return {"error": f"不支持的文件格式: {ext}，只支持 .docx / .pdf / .txt"}

    # 2. 如果读取失败，返回错误
    if text.startswith("<"):
        return {"error": text}

    if not text.strip():
        return {"error": "简历文件内容为空"}

    # 保留从原文件提取出的完整文字，便于核对 AI 结果和后续检索。
    raw_text = text

    # 3. 记录读到了多少字
    print(f"读取到 {len(raw_text)} 个字符，正在 AI 分析...")

    # 4. 调用 AI 提取信息
    result = extract_resume_info(raw_text)

    # 5. AI 可能没有正确返回 JSON，做个兼容处理
    if "error" in result:
        return result

    # 6. 打上时间戳，方便以后查
    from datetime import datetime
    result["parsed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result["source_file"] = os.path.basename(file_path)
    result["raw_text"] = raw_text
    result["original_profile"] = original_profile_snapshot(result)
    result["optimization_history"] = []

    return result


def save_parsed_result(parsed_data: dict, output_dir: str = None):
    """
    保存到JSON（兼容旧版）并同步写入 SQLite 数据库
    大白话：AI 分析完了，存一份进抽屉，以后直接从抽屉读
    """
    if output_dir is None:
        from config import DATA_DIR
        from core.workspace_context import get_active_data_dir
        output_dir = get_active_data_dir(DATA_DIR)

    os.makedirs(output_dir, exist_ok=True)

    name = parsed_data.get("name", "unknown")
    timestamp = parsed_data.get("parsed_at", "").replace(":", "-").replace(" ", "_")
    filename = f"resume_{name}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    serialized_data = json.dumps(parsed_data, ensure_ascii=False, indent=2)
    temp_path = f"{filepath}.{uuid.uuid4().hex}.tmp"
    previous_content = None
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as existing_file:
            previous_content = existing_file.read()

    from modules.db_client import get_connection

    conn = None
    file_replaced = False
    try:
        with open(temp_path, "w", encoding="utf-8") as output_file:
            output_file.write(serialized_data)

        conn = get_connection()
        conn.execute("BEGIN")
        conn.execute('''
            INSERT INTO resumes (filename, name, phone, email, parsed_data)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                name = excluded.name,
                phone = excluded.phone,
                email = excluded.email,
                parsed_data = excluded.parsed_data
        ''', (
            filename,
            parsed_data.get("name", ""),
            parsed_data.get("phone", ""),
            parsed_data.get("email", ""),
            serialized_data,
        ))
        original_profile = parsed_data.get("original_profile")
        if not isinstance(original_profile, dict) or not original_profile:
            original_profile = original_profile_snapshot(parsed_data)
        save_original_version(
            filename,
            original_profile,
            created_at=str(parsed_data.get("parsed_at", "")),
            is_current=True,
            connection=conn,
        )
        os.replace(temp_path, filepath)
        file_replaced = True
        conn.commit()
    except Exception as error:
        if conn is not None:
            conn.rollback()
        if file_replaced:
            if previous_content is None:
                if os.path.exists(filepath):
                    os.remove(filepath)
            else:
                restore_path = f"{filepath}.{uuid.uuid4().hex}.restore"
                with open(restore_path, "w", encoding="utf-8") as restore_file:
                    restore_file.write(previous_content)
                os.replace(restore_path, filepath)
        elif os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError("简历版本保存失败") from error
    finally:
        if conn is not None:
            conn.close()

    print(f"\n[成功] 简历 {name} 已存入 SQLite 数据库 resumes 表。")
    print(f"旧版JSON暂作保留: {filepath}")
    return filepath


def list_resumes():
    """
    列出 resumes 文件夹里有哪些简历文件
    大白话：看看你放了哪些简历
    """
    from core.workspace_context import get_active_resumes_dir

    target_dir = get_active_resumes_dir(RESUMES_DIR)
    files = []
    if os.path.exists(target_dir):
        for f in os.listdir(target_dir):
            if any(f.lower().endswith(ext) for ext in [".docx", ".pdf", ".txt"]):
                files.append(f)
    return files


# ============================================
# 测试：用一段模拟简历文本验证功能
# ============================================
if __name__ == "__main__":
    print("=" * 50)
    print("测试简历解析引擎")
    print("=" * 50)

    # 一段假的简历文本，用于测试 AI 分析能力
    test_resume = """
    张三
    电话: 13800138000 | 邮箱: zhangsan@example.com

    求职意向: Python开发工程师 | 期望薪资: 15k-20k

    教育背景:
    2018-2021 北京大学 计算机科学与技术 硕士
    2014-2018 武汉大学 软件工程 本科

    工作经历:
    2021-至今 字节跳动 Python后端开发工程师
    - 负责用户服务后端开发，使用Django + MySQL架构
    - 优化数据库查询，将API响应时间降低40%
    - 参与微服务架构设计，用Redis做缓存层

    2019-2021 阿里巴巴 实习Python开发
    - 参与内部工具系统开发
    - 编写自动化测试脚本

    技能:
    Python, Django, Flask, MySQL, Redis, Docker, Git, Linux
    """

    print("\n[测试] 用模拟简历文本解析...")
    result = extract_resume_info(test_resume)

    print("\n" + "=" * 50)
    print("解析结果:")
    print("=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 保存结果
    save_parsed_result(result)

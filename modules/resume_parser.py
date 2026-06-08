# ============================================
# modules/resume_parser.py — 简历解析模块
# 大白话：把 Word/PDF/文本 简历转成结构化的数据
# ============================================

import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RESUMES_DIR, LOGS_DIR, DEEPSEEK_MODEL
from modules.deepseek_client import DeepSeekClient

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
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def extract_resume_info(resume_text: str) -> dict:
    """
    核心函数：把简历文字交给 DeepSeek，让它提取出结构化信息
    大白话：把简历文本丢给 AI，AI 会返回一个整理好的字典
    """
    client = DeepSeekClient()
    
    # ----- 给 AI 的角色设定（System Prompt）-----
    # 告诉 AI："你是一个专业的简历分析师，请严格按照格式回答"
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
  "skills": ["技能1", "技能2", "技能3"],
  "desired_position": "期望岗位",
  "desired_salary": "期望薪资",
  "summary": "一句话总结这位候选人的核心优势"
}

注意：
- 如果某项信息没找到，用空字符串 "" 或空列表 []
- education、work_experience 按时间倒序排列
- skills 列出所有提到的技能关键词
"""

    # ----- 调用 AI -----
    result = client.chat_json(system_prompt, resume_text)
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
    
    # 3. 记录读到了多少字
    print(f"读取到 {len(text)} 个字符，正在 AI 分析...")
    
    # 4. 调用 AI 提取信息
    result = extract_resume_info(text)
    
    # 5. AI 可能没有正确返回 JSON，做个兼容处理
    if "error" in result:
        return result
    
    # 6. 打上时间戳，方便以后查
    from datetime import datetime
    result["parsed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result["source_file"] = os.path.basename(file_path)
    
    return result


def save_parsed_result(parsed_data: dict, output_dir: str = None):
    """
    把解析结果保存成 JSON 文件
    大白话：AI 分析完了，存一份到硬盘，以后直接读不用再分析
    """
    if output_dir is None:
        from config import DATA_DIR
        output_dir = DATA_DIR
    
    os.makedirs(output_dir, exist_ok=True)
    
    name = parsed_data.get("name", "unknown")
    timestamp = parsed_data.get("parsed_at", "").replace(":", "-").replace(" ", "_")
    filename = f"resume_{name}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)
    
    print(f"解析结果已保存到: {filepath}")
    return filepath


def list_resumes():
    """
    列出 resumes 文件夹里有哪些简历文件
    大白话：看看你放了哪些简历
    """
    files = []
    if os.path.exists(RESUMES_DIR):
        for f in os.listdir(RESUMES_DIR):
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

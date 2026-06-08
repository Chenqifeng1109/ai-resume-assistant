# ============================================
# modules/jd_matcher.py - JD匹配度评分
# 使用 DeepSeek API 对简历和岗位描述进行语义匹配打分
# ============================================
import os, json, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DEEPSEEK_API_KEY
from openai import OpenAI

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


def match_resume_to_jd(resume_data: dict, jd_text: str) -> dict:
    """
    将简历与JD进行AI语义匹配，返回评分和详细分析
    大白话：把简历和招聘要求发给AI，让它打分并解释为什么匹配/不匹配
    """
    # 提取简历关键信息
    name = resume_data.get("name", "未知")
    position = resume_data.get("desired_position", "")
    skills = resume_data.get("skills", [])
    summary = resume_data.get("summary", "")
    
    # 整理工作经历
    experiences = resume_data.get("work_experience", []) + resume_data.get("internship", [])
    exp_text = ""
    for exp in experiences:
        exp_text += f"- {exp.get('company','')} | {exp.get('position','')} | {exp.get('duration','')}: {exp.get('description','')}\n"
    
    # 整理教育背景
    edu_text = ""
    for edu in resume_data.get("education", []):
        edu_text += f"- {edu.get('school','')} {edu.get('degree','')} {edu.get('major','')}\n"
    
    # 构建提示词
    prompt = f"""你是一个专业的HR和职业顾问。请根据以下简历和岗位描述(JD)，进行匹配度分析。

## 简历信息
姓名: {name}
求职意向: {position}
技能: {', '.join(skills[:15])}
摘要: {summary}

### 工作/实习经历
{exp_text if exp_text else '无'}

### 教育背景
{edu_text if edu_text else '无'}

## 岗位描述 (JD)
{jd_text[:3000]}

---

请按以下JSON格式返回分析结果（只返回JSON，不要其他内容）：
{{
  "overall_score": 0-100的整数,
  "skill_match": 0-100的整数,
  "experience_match": 0-100的整数,
  "education_match": 0-100的整数,
  "strengths": ["匹配点1", "匹配点2", "匹配点3"],
  "weaknesses": ["不足点1", "不足点2"],
  "suggestions": ["改进建议1", "改进建议2"],
  "verdict": "一句话总结（20字以内）"
}}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )
        result_text = response.choices[0].message.content.strip()
        
        # 清理可能的markdown代码块标记
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else result_text
        
        result = json.loads(result_text)
        result["ok"] = True
        return result
        
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "error": f"AI返回格式异常: {str(e)[:100]}",
            "raw": result_text[:500] if 'result_text' in dir() else ""
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"AI匹配失败: {str(e)[:200]}"
        }


def quick_match(resume_data: dict, jd_text: str) -> dict:
    """
    快速匹配（更短的提示词，适合批量）
    """
    name = resume_data.get("name", "")
    position = resume_data.get("desired_position", "")
    skills = ", ".join(resume_data.get("skills", [])[:10])
    summary = resume_data.get("summary", "")
    
    experiences = resume_data.get("work_experience", []) + resume_data.get("internship", [])
    exp_short = "; ".join([f"{e.get('position','')}@{e.get('company','')}" for e in experiences[:5]])
    
    prompt = f"""简历: {name}, 求职{position}, 技能{skills}, 经历{exp_short}, 摘要{summary}
JD: {jd_text[:2000]}

请评估匹配度，返回纯JSON:
{{"score":0-100,"brief":"一句话点评(15字)","reasons":["理由1","理由2"]}}"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1]) if len(lines) > 2 else result_text
        result = json.loads(result_text)
        result["ok"] = True
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

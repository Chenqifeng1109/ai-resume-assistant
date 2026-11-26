"""D18 暗线动态模板与 Schema 驱动回归测试套件。"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import services.resume_documents as documents
from modules.db_client import init_db
from modules.resume_version_repository import save_optimized_version, save_original_version


class DynamicResumeTemplateTests(unittest.TestCase):
    def setUp(self):
        self.templates = ["classic", "modern", "dual", "magazine", "minimal", "timeline", "elegant", "tech"]

    def test_student_profile_has_no_work_h2_and_no_zanwu(self):
        """应届生简历（无工作经验）在所有模板中绝不生成工作经历标题和'暂无'占位符。"""
        student_profile = {
            "name": "李小萌",
            "desired_position": "前端开发实习生",
            "phone": "13911112222",
            "email": "limeng@student.edu.cn",
            "summary": "计算机系大三学生，热爱开源前端技术。",
            "skills": ["JavaScript", "React", "HTML5", "CSS3"],
            "education": [{"school": "清华大学", "major": "软件工程", "degree": "本科", "year": "2023-2027"}],
            "work_experience": [],
            "campus_experience": [{"organization": "校团委宣传部", "role": "部长", "duration": "2024-2025", "description": "负责设计海报与运营推文"}],
            "project_experience": [{"name": "AI 简历助手", "role": "前端主创", "duration": "2026.01-2026.03", "description": "开发了多风格动态模板与组件映射系统"}]
        }

        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root) / "data"
            data_dir.mkdir()
            filename = "resume_student.json"
            (data_dir / filename).write_text(json.dumps(student_profile, ensure_ascii=False), encoding="utf-8")

            with patch.object(documents, "DATA_DIR", str(data_dir)):
                for style in self.templates:
                    with self.subTest(style=style):
                        response = documents.resume_template(filename, style)
                        self.assertEqual(response.status_code, 200)
                        html_text = response.body.decode("utf-8")

                        # 核心断言 1：严禁出现任何“暂无”字样
                        self.assertNotIn("暂无", html_text, f"模板 [{style}] 出现了'暂无'占位符！")
                        self.assertNotIn("工作经历", html_text if style == "dual" else html_text.replace("AI 简历助手", ""), f"模板 [{style}] 对空工作经历输出了标题！")

                        # 核心断言 2：应届生真实存在的模块必须 100% 完整渲染
                        self.assertIn("李小萌", html_text)
                        self.assertIn("前端开发实习生", html_text)
                        self.assertIn("清华大学", html_text)
                        self.assertIn("AI 简历助手", html_text)
                        self.assertIn("校团委宣传部", html_text)

    def test_senior_veteran_profile_renders_all_advanced_sections_without_campus(self):
        """资深专家简历（无校园经历）在所有模板中完整渲染科研、荣誉与专利，且无校园标题。"""
        senior_profile = {
            "name": "王建国",
            "desired_position": "首席架构师",
            "desired_salary": "60k-80k",
            "phone": "13888889999",
            "email": "jianguo.wang@tech.com",
            "summary": "10年分布式系统与大模型架构经验，曾主导亿级流量系统高可用重构。",
            "skills": ["Python", "Go", "Kubernetes", "LangChain", "LLM", "Distributed Systems"],
            "education": [{"school": "上海交通大学", "major": "计算机系统", "degree": "硕士", "year": "2012-2015"}],
            "work_experience": [
                {"position": "技术总监", "company": "未来科技有限公司", "duration": "2020.03-至今", "description": "全面负责智能简历与大模型平台研发，管理50人团队。"},
                {"position": "资深后端专家", "company": "全球云计算集团", "duration": "2015.07-2020.02", "description": "核心参与服务网格与高并发网关建设。"}
            ],
            "project_experience": [
                {"name": "百万并发 Agent 调度平台", "role": "总设计师", "duration": "2024-2025", "description": "自研低延迟 ReAct 任务路由网关，提升吞吐量 300%。"}
            ],
            "research_experience": [
                {"name": "基于大模型的结构化信息受控提取算法研究", "role": "第一作者", "duration": "2025", "description": "发表于顶级会议，提出防幻觉 Schema 校验范式。"}
            ],
            "awards": [
                {"name": "国家科技进步二等奖", "level": "国家级", "year": "2023", "description": "分布式计算领域核心贡献"}
            ],
            "certificates": [
                {"name": "AWS Certified Solutions Architect - Professional", "level": "专业级", "issuer": "Amazon", "year": "2022"}
            ],
            "language_skills": [
                {"language": "英语", "level": "精通", "certificate": "TEM-8"}
            ],
            "interests": ["马拉松", "开源社区", "科技写作"],
            "campus_experience": []
        }

        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root) / "data"
            data_dir.mkdir()
            filename = "resume_senior.json"
            (data_dir / filename).write_text(json.dumps(senior_profile, ensure_ascii=False), encoding="utf-8")

            with patch.object(documents, "DATA_DIR", str(data_dir)):
                for style in self.templates:
                    with self.subTest(style=style):
                        response = documents.resume_template(filename, style)
                        self.assertEqual(response.status_code, 200)
                        html_text = response.body.decode("utf-8")

                        # 核心断言 1：无校园经历时严禁生成校园标题与暂无
                        self.assertNotIn("暂无", html_text)
                        self.assertNotIn("校园经历", html_text)

                        # 核心断言 2：高价值科研、荣誉、证书、薪资、经历 100% 完整展示
                        self.assertIn("王建国", html_text)
                        self.assertIn("首席架构师", html_text)
                        self.assertIn("60k-80k", html_text)
                        self.assertIn("未来科技有限公司", html_text)
                        self.assertIn("百万并发 Agent 调度平台", html_text)
                        self.assertIn("基于大模型的结构化信息受控提取算法研究", html_text)
                        self.assertIn("国家科技进步二等奖", html_text)
                        self.assertIn("AWS Certified Solutions Architect", html_text)
                        self.assertIn("马拉松", html_text)

    def test_minimal_profile_renders_compactly_without_empty_sections(self):
        """极简简历（仅姓名联系方式）渲染紧凑，无任何空标签。"""
        minimal_profile = {
            "name": "张三",
            "phone": "13000000000",
            "email": "zhangsan@test.com"
        }

        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root) / "data"
            data_dir.mkdir()
            filename = "resume_minimal.json"
            (data_dir / filename).write_text(json.dumps(minimal_profile, ensure_ascii=False), encoding="utf-8")

            with patch.object(documents, "DATA_DIR", str(data_dir)):
                for style in self.templates:
                    with self.subTest(style=style):
                        response = documents.resume_template(filename, style)
                        self.assertEqual(response.status_code, 200)
                        html_text = response.body.decode("utf-8")

                        self.assertIn("张三", html_text)
                        self.assertIn("13000000000", html_text)
                        self.assertNotIn("暂无", html_text)
                        self.assertNotIn("工作经历", html_text)
                        self.assertNotIn("教育背景", html_text)
                        self.assertNotIn("专业技能", html_text)

    def test_version_integration_reads_active_version_from_sqlite(self):
        """模板引擎优先联动读取 SQLite resume_versions 中 is_current=1 的激活版本数据。"""
        original_profile = {
            "name": "赵六",
            "desired_position": "普通开发",
            "work_experience": [{"position": "初级程序员", "company": "旧公司", "duration": "2024", "description": "日常写代码"}]
        }
        optimized_profile = {
            "name": "赵六",
            "desired_position": "资深全栈工程师",
            "work_experience": [{"position": "全栈技术骨干", "company": "旧公司", "duration": "2024", "description": "负责核心全栈微服务重构与性能调优"}],
            "project_experience": [{"name": "高并发即时通信系统", "role": "架构师", "duration": "2025", "description": "基于 WebSocket 架构开发"}],
            "skills": ["Python", "FastAPI", "React", "Redis"]
        }

        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root) / "data"
            data_dir.mkdir()
            db_path = str(data_dir / "offerforge.db")
            filename = "resume_zhaoliu.json"
            (data_dir / filename).write_text(json.dumps(original_profile, ensure_ascii=False), encoding="utf-8")

            init_db(db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute(
                    "INSERT INTO resumes (filename, name, phone, email, parsed_data) VALUES (?, ?, ?, ?, ?)",
                    (filename, "赵六", "", "", json.dumps(original_profile))
                )
                save_original_version(filename, original_profile, connection=conn, is_current=False)
                save_optimized_version(filename, {"version_id": "opt_v2", "profile": optimized_profile}, connection=conn)
                conn.commit()
            finally:
                conn.close()

            with patch.object(documents, "DATA_DIR", str(data_dir)):
                # 调用模板预览
                response = documents.resume_template(filename, "classic")
                self.assertEqual(response.status_code, 200)
                html_text = response.body.decode("utf-8")

                # 必须成功读取到 is_current=1 激活版本里的内容
                self.assertIn("资深全栈工程师", html_text)
                self.assertIn("全栈技术骨干", html_text)
                self.assertIn("高并发即时通信系统", html_text)
                self.assertIn("FastAPI", html_text)


if __name__ == "__main__":
    unittest.main()

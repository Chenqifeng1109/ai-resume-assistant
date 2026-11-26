"""OfferForge 阶段 B 一键体检脚本的纯函数单元测试（零网络、零外部 AI 依赖）。"""

import tempfile
import unittest
from pathlib import Path

from scripts.e2e_health_check import (
    compute_job_collection_metrics,
    generate_varied_demo_docx,
    next_resume_sequence,
    parse_salary_range_k,
    select_variant,
)


class E2EHealthCheckHelperTests(unittest.TestCase):
    def test_next_resume_sequence_and_variant_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(next_resume_sequence(root), 1)
            (root / "01_模拟简历_甲.docx").write_bytes(b"")
            (root / "03_模拟简历_丙.docx").write_bytes(b"")
            self.assertEqual(next_resume_sequence(root), 4)

            v1 = select_variant("auto", 1)
            v2 = select_variant("auto", 2)
            v3 = select_variant("auto", 3)
            self.assertEqual(len({v1["id"], v2["id"], v3["id"]}), 3)
            self.assertEqual(len({v1["layout"], v2["layout"], v3["layout"]}), 3)

    def test_generate_varied_demo_docx_creates_numbered_file_for_all_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated_names = []
            for idx in ("0", "1", "2"):
                path, variant = generate_varied_demo_docx(root, variant_arg=idx)
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 1000)
                generated_names.append(path.name)
                self.assertTrue(variant["omitted_fields"])
            self.assertTrue(generated_names[0].startswith("01_"))
            self.assertTrue(generated_names[1].startswith("02_"))
            self.assertTrue(generated_names[2].startswith("03_"))

    def test_parse_salary_range_k_handles_common_formats(self):
        self.assertEqual(parse_salary_range_k("18k-30k"), (18.0, 30.0))
        self.assertEqual(parse_salary_range_k("20-35K·15薪"), (20.0, 35.0))
        self.assertEqual(parse_salary_range_k("1.5万-2.5万/月"), (15.0, 25.0))
        self.assertEqual(parse_salary_range_k("18000-28000元/月"), (18.0, 28.0))
        self.assertIsNone(parse_salary_range_k("薪资面议"))
        self.assertIsNone(parse_salary_range_k(""))

    def test_compute_job_collection_metrics_multidimensional(self):
        jobs = [
            {
                "title": "AI产品经理",
                "source": "meituan",
                "url": "https://zhaopin.meituan.com/job/1",
                "salary": "25k-35k",
                "match_score": 88,
            },
            {
                "title": "高级策略产品经理",
                "source": "ncss",
                "url": "https://www.ncss.cn/job/2",
                "salary": "10k-15k",
                "match_score": 72,
            },
            {
                "title": "前台行政专员",
                "source": "iguopin",
                "url": "javascript:void(0)",
                "salary": "面议",
            },
        ]
        m = compute_job_collection_metrics(
            jobs,
            relevance_terms=["产品", "AI", "策略"],
            target_salary_k=(20.0, 35.0),
        )
        self.assertEqual(m["total"], 3)
        self.assertEqual(m["sources"], {"meituan": 1, "ncss": 1, "iguopin": 1})
        self.assertEqual(m["url_valid_count"], 2)
        self.assertEqual(m["relevant_count"], 2)
        self.assertEqual(m["salary_labeled_count"], 2)
        self.assertEqual(m["salary_matched_count"], 1)
        self.assertEqual(m["salary_match_rate"], 50.0)
        self.assertEqual(m["scored_count"], 2)
        self.assertEqual(m["score_avg"], 80.0)


if __name__ == "__main__":
    unittest.main()

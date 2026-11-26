import unittest
from pathlib import Path


class ResumeParseProgressUiTests(unittest.TestCase):
    def test_uploading_state_has_an_honest_indeterminate_progress_bar(self):
        source = Path("frontend/src/components/AIAssistant.jsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("uploading &&", source)
        self.assertIn("正在解析简历", source)
        self.assertIn("上传 · 读取 · AI提取 · 检查", source)
        self.assertIn("parseProgressFlow", source)
        self.assertIn("optTask &&", source)
        self.assertIn("OPTIMIZATION_STAGE_LABELS", source)
        self.assertIn("正在读取简历底稿", source)
        self.assertIn("正在解析结构化结果", source)
        self.assertIn("optTask.progress", source)
        self.assertIn("batchLoading ? React.createElement", source)
        self.assertIn("正在批量匹配岗位", source)
        self.assertIn("读取岗位 · 逐岗评分 · 筛选结果 · 保存", source)
        self.assertNotIn("随机进度", source)

    def test_job_collection_has_an_honest_startup_progress_bar(self):
        source = Path("frontend/src/components/JobMarket.jsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("scrapeLoading &&", source)
        self.assertIn("pollScrapeStatus", source)
        self.assertIn("/api/jobs/scrape/status", source)
        self.assertIn("岗位采集完成，共", source)
        self.assertIn("无法读取岗位采集状态", source)
        self.assertIn('aria-label="岗位采集处理中"', source)
        self.assertIn("jobProgressFlow", source)
        self.assertNotIn("随机进度", source)

    def test_gap_suggestion_details_are_collapsed_until_requested(self):
        source = Path("frontend/src/components/AIAssistant.jsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("expandedGapIndexes", source)
        self.assertIn("查看建议", source)
        self.assertIn("收起", source)
        self.assertIn("岗位依据：", source)
        self.assertIn("当前状态：", source)
        self.assertIn("写入条件：", source)


if __name__ == "__main__":
    unittest.main()

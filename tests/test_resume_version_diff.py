import unittest

from modules.resume_version_diff import build_resume_diff


class ResumeVersionDiffTests(unittest.TestCase):
    def test_identical_snapshots_have_no_changes(self):
        profile = {"name": "小林", "skills": ["Python"]}

        result = build_resume_diff(profile, profile)

        self.assertFalse(result["has_changes"])
        self.assertEqual(result["counts"]["total"], 0)
        self.assertEqual(result["changes"], [])

    def test_added_deleted_and_modified_fields_are_separated(self):
        before = {"name": "小林", "summary": "旧总结", "interests": ["跑步"]}
        after = {"name": "小林", "summary": "新总结", "awards": [{"name": "校赛一等奖"}]}

        result = build_resume_diff(before, after)
        changes = {item["field"]: item for item in result["changes"]}

        self.assertEqual(changes["summary"]["change_type"], "modified")
        self.assertEqual(changes["interests"]["change_type"], "deleted")
        self.assertEqual(changes["awards"]["change_type"], "added")
        self.assertEqual(result["counts"], {"added": 1, "deleted": 1, "modified": 1, "total": 3})

    def test_internal_fields_are_not_exposed_and_inputs_are_not_mutated(self):
        before = {"raw_text": "原文", "original_profile": {"name": "旧"}, "skills": []}
        after = {"raw_text": "新原文", "_optimization_meta": {"version": 2}, "skills": ["Python"]}

        result = build_resume_diff(before, after)

        self.assertEqual([item["field"] for item in result["changes"]], ["skills"])
        self.assertEqual(before["raw_text"], "原文")
        self.assertEqual(after["skills"], ["Python"])


if __name__ == "__main__":
    unittest.main()

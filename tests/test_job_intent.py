import unittest

from pydantic import ValidationError

from modules.job_scraper import JobScraper, get_metro_code
from services.job_intent import (
    JobIntentConfirmRequest,
    confirm_job_intent,
    extract_job_intent,
)


class FakeIntentClient:
    payload = {}
    prompt = ""
    message = ""

    def chat_json(self, system_prompt, user_message):
        type(self).prompt = system_prompt
        type(self).message = user_message
        return dict(type(self).payload)


class JobIntentTests(unittest.TestCase):
    def _extract(self, text, payload):
        FakeIntentClient.payload = payload
        return extract_job_intent(text, client_factory=FakeIntentClient)

    def test_complete_intent_has_four_confirmable_parts(self):
        result = self._extract(
            "想在广州找AI产品助理，期望8k到10k，不接受长期出差",
            {
                "position": "AI产品助理",
                "city": "广州",
                "salary_min": 8000,
                "salary_max": 10000,
                "restrictions": ["不接受长期出差"],
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["intent"]["missing_fields"], [])
        self.assertEqual(result["intent"]["status"], "needs_confirmation")
        self.assertIn("【任务】", FakeIntentClient.prompt)
        self.assertIn("【失败行为】", FakeIntentClient.prompt)

    def test_missing_city_and_salary_stay_missing(self):
        result = self._extract(
            "考虑产品运营，不接受夜班",
            {
                "position": "产品运营",
                "city": "",
                "salary_min": None,
                "salary_max": None,
                "restrictions": ["考虑产品运营", "不接受夜班"],
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["intent"]["missing_fields"],
            ["city", "salary"],
        )
        self.assertEqual(result["intent"]["city"], "")

    def test_reversed_salary_is_not_silently_swapped(self):
        result = self._extract(
            "深圳数据助理，期望12k到8k",
            {
                "position": "数据助理",
                "city": "深圳",
                "salary_min": 12000,
                "salary_max": 8000,
                "restrictions": [],
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["intent"]["salary_min"], 12000)
        self.assertEqual(result["intent"]["salary_max"], 8000)
        self.assertEqual(len(result["intent"]["warnings"]), 1)

    def test_confirm_rejects_reversed_salary(self):
        with self.assertRaises(ValidationError):
            JobIntentConfirmRequest(
                position="数据助理",
                city="深圳",
                salary_min=12000,
                salary_max=8000,
            )

    def test_confirm_marks_user_values_as_confirmed(self):
        request = JobIntentConfirmRequest(
            position="AI产品助理",
            city="广州",
            salary_min=8000,
            salary_max=10000,
            restrictions=["不接受长期出差"],
        )

        result = confirm_job_intent(request)

        self.assertTrue(result["ok"])
        self.assertEqual(result["intent"]["status"], "confirmed")
        self.assertIsNotNone(result["intent"]["confirmed_at"])

    def test_confirmed_city_drives_scraper_location_and_city_code(self):
        scraper = JobScraper()

        scraper.set_profile(
            {
                "desired_position": "数据助理",
                "target_city": "深圳",
            }
        )

        self.assertEqual(scraper.location, "深圳")
        self.assertEqual(get_metro_code(scraper.location), "040000")


if __name__ == "__main__":
    unittest.main()

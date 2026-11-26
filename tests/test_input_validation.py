import unittest

from core.input_validation import (
    parse_index_list,
    validate_csv_choices,
    validate_http_url,
    validate_integer,
    validate_text,
)


class InputValidationTests(unittest.TestCase):
    def test_integer_accepts_legal_boundaries(self):
        self.assertEqual(validate_integer(0, "score", minimum=0, maximum=100), (0, None))
        self.assertEqual(
            validate_integer("100", "score", minimum=0, maximum=100),
            (100, None),
        )

    def test_integer_rejects_boolean_and_out_of_range(self):
        for value in (True, -1, 101):
            _, error = validate_integer(value, "score", minimum=0, maximum=100)
            self.assertEqual(error["error_code"], "INVALID_INPUT")
            self.assertEqual(error["field"], "score")

    def test_text_enforces_required_and_maximum_length(self):
        self.assertIsNone(validate_text("x" * 100, "target", max_length=100)[1])
        for value in ("", "x" * 101):
            _, error = validate_text(
                value,
                "target",
                required=True,
                max_length=100,
            )
            self.assertEqual(error["field"], "target")

    def test_index_list_rejects_invalid_and_duplicate_items(self):
        self.assertEqual(parse_index_list("0, 2,19"), ([0, 2, 19], None))
        for value in ("0,bad", "0,0", "0,,1"):
            _, error = parse_index_list(value)
            self.assertEqual(error["field"], "job_indices")

    def test_platforms_use_a_whitelist(self):
        allowed = {"51前程无忧", "liepin"}
        choices, error = validate_csv_choices(
            "51前程无忧,liepin",
            "platforms",
            allowed,
        )
        self.assertEqual(choices, ["51前程无忧", "liepin"])
        self.assertIsNone(error)
        self.assertEqual(
            validate_csv_choices("unknown", "platforms", allowed)[1]["field"],
            "platforms",
        )

    def test_url_only_accepts_http_and_https(self):
        self.assertIsNone(validate_http_url("https://example.com/job/1")[1])
        for value in ("javascript:alert(1)", "file:///tmp/job", "not-a-url"):
            _, error = validate_http_url(value)
            self.assertEqual(error["field"], "url")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest

from core.file_security import resolve_file_in_directory, validate_filename


class FileSecurityTests(unittest.TestCase):
    def test_accepts_a_plain_allowed_filename(self):
        self.assertEqual(
            validate_filename("resume_demo.json", {".json"}),
            "resume_demo.json",
        )

    def test_rejects_paths_reserved_names_and_wrong_extensions(self):
        invalid_names = (
            "../secret.json",
            "folder/secret.json",
            "C:\\secret.json",
            "CON.json",
            "resume.exe",
        )
        for filename in invalid_names:
            with self.subTest(filename=filename):
                self.assertIsNone(validate_filename(filename, {".json"}))

    def test_resolved_path_stays_inside_the_allowed_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = resolve_file_in_directory(
                directory,
                "resume_demo.json",
                {".json"},
            )
            self.assertIsNotNone(result)
            self.assertTrue(result[1].startswith(directory))
            self.assertIsNone(
                resolve_file_in_directory(
                    directory,
                    "../escape.json",
                    {".json"},
                )
            )


if __name__ == "__main__":
    unittest.main()

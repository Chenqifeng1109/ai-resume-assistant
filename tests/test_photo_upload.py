import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import services.resume_documents as documents


def make_image_bytes(image_format: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color=(30, 120, 200)).save(
        buffer,
        format=image_format,
    )
    return buffer.getvalue()


class FakePhoto:
    def __init__(self, content: bytes, content_type: str):
        self.content = content
        self.content_type = content_type
        self.closed = False

    async def read(self):
        return self.content

    async def close(self):
        self.closed = True


class OversizedVerifiedImage:
    format = "JPEG"
    size = (5000, 5000)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def verify(self):
        return None


class PhotoUploadTests(unittest.TestCase):
    def run_upload(self, root: str, photo: FakePhoto):
        data_dir = Path(root) / "data"
        data_dir.mkdir(exist_ok=True)
        with patch.object(documents, "DATA_DIR", str(data_dir)):
            result = asyncio.run(
                documents.upload_photo("resume_demo.json", photo)
            )
        return result

    def test_rejects_invalid_empty_oversized_and_mismatched_files(self):
        invalid_cases = (
            (b"not an image", "text/plain"),
            (b"", "image/jpeg"),
            (b"x" * (documents.MAX_PHOTO_SIZE + 1), "image/jpeg"),
            (make_image_bytes("PNG"), "image/jpeg"),
        )
        for content, content_type in invalid_cases:
            with self.subTest(content_type=content_type, size=len(content)):
                with tempfile.TemporaryDirectory() as root:
                    photo = FakePhoto(content, content_type)
                    result = self.run_upload(root, photo)

                    self.assertFalse(result["ok"])
                    self.assertEqual(result["error_code"], "INVALID_INPUT")
                    self.assertEqual(result["field"], "photo")
                    self.assertTrue(photo.closed)
                    self.assertFalse((Path(root) / "photos").exists())

    def test_accepts_real_jpeg_and_png_and_removes_old_format(self):
        with tempfile.TemporaryDirectory() as root:
            jpeg = FakePhoto(make_image_bytes("JPEG"), "image/jpeg")
            jpeg_result = self.run_upload(root, jpeg)
            photo_dir = Path(root) / "photos"
            jpeg_path = photo_dir / "resume_demo.photo.jpg"

            self.assertTrue(jpeg_result["ok"])
            self.assertEqual(jpeg_result["content_type"], "image/jpeg")
            self.assertTrue(jpeg_path.exists())

            png = FakePhoto(make_image_bytes("PNG"), "image/png")
            png_result = self.run_upload(root, png)
            png_path = photo_dir / "resume_demo.photo.png"

            self.assertTrue(png_result["ok"])
            self.assertEqual(png_result["content_type"], "image/png")
            self.assertTrue(png_path.exists())
            self.assertFalse(jpeg_path.exists())
            with Image.open(png_path) as image:
                image.verify()

    def test_rejects_more_than_twenty_million_pixels(self):
        with patch.object(
            documents.Image,
            "open",
            return_value=OversizedVerifiedImage(),
        ):
            _, _, error = documents._inspect_photo_content(
                b"fake image bytes",
                "image/jpeg",
            )

        self.assertEqual(error["error_code"], "INVALID_INPUT")
        self.assertEqual(error["field"], "photo")

    def test_template_embeds_png_with_the_correct_mime_type(self):
        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root) / "data"
            photo_dir = Path(root) / "photos"
            data_dir.mkdir()
            photo_dir.mkdir()
            (data_dir / "resume_demo.json").write_text(
                json.dumps({"name": "Demo"}),
                encoding="utf-8",
            )
            (photo_dir / "resume_demo.photo.png").write_bytes(
                make_image_bytes("PNG")
            )

            with patch.object(documents, "DATA_DIR", str(data_dir)):
                response = documents.resume_template(
                    "resume_demo.json",
                    "classic",
                )

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"data:image/png;base64,", response.body)


if __name__ == "__main__":
    unittest.main()

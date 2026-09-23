from unittest import TestCase

from curriculum.upload_views import _content_looks_valid, _ext_of


class UploadValidationTests(TestCase):
    def test_extension_is_normalized(self):
        self.assertEqual(_ext_of("Lecture.PDF"), "pdf")
        self.assertEqual(_ext_of("no-extension"), "")

    def test_known_file_signatures_are_required(self):
        self.assertTrue(_content_looks_valid("pdf", b"%PDF-1.7"))
        self.assertFalse(_content_looks_valid("pdf", b"MZ\x90\x00"))
        self.assertTrue(_content_looks_valid("png", b"\x89PNG\r\n"))
        self.assertFalse(_content_looks_valid("png", b"not-an-image"))

    def test_video_and_svg_are_supported_without_fixed_magic_bytes(self):
        self.assertTrue(_content_looks_valid("mp4", b"ftyp"))
        self.assertTrue(_content_looks_valid("svg", b"<svg"))

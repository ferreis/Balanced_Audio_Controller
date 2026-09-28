from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import analysis_engine


class AnalysisEngineTests(unittest.TestCase):
    def test_backend_resolution(self) -> None:
        self.assertEqual(analysis_engine.resolve_backend("auto", True), "ffmpeg")
        self.assertEqual(analysis_engine.resolve_backend("auto", False), "webaudio")
        self.assertEqual(analysis_engine.resolve_backend("ffmpeg", False), "ffmpeg")
        self.assertEqual(analysis_engine.resolve_backend("webaudio", True), "webaudio")

    def test_parse_loudnorm_json(self) -> None:
        stderr = "prefix\n{\n  \"input_i\" : \"-23.41\",\n  \"input_tp\" : \"-1.20\",\n  \"input_lra\" : \"3.10\",\n  \"input_thresh\" : \"-33.00\"\n}\nsuffix"
        parsed = analysis_engine.parse_loudnorm_json(stderr)
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed["input_i"], -23.41)
        self.assertAlmostEqual(parsed["input_tp"], -1.20)

    def test_extract_only_expected_binary_member(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wheel = root / "test.whl"
            destination = root / "ffmpeg"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("../../outside", b"evil")
                archive.writestr(
                    "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-test",
                    b"binary",
                )
            with patch.object(analysis_engine, "is_executable_usable", return_value=True):
                analysis_engine._extract_binary(wheel, destination)
            self.assertEqual(destination.read_bytes(), b"binary")
            self.assertFalse((root.parent / "outside").exists())

    def test_extract_rejects_multiple_ffmpeg_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wheel = root / "test.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("imageio_ffmpeg/binaries/ffmpeg-a", b"a")
                archive.writestr("imageio_ffmpeg/binaries/ffmpeg-b", b"b")
            with self.assertRaises(RuntimeError):
                analysis_engine._extract_binary(wheel, root / "ffmpeg")


if __name__ == "__main__":
    unittest.main()

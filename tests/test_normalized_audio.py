from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import normalized_audio


class NormalizedAudioTests(unittest.TestCase):
    def test_extract_sound_filenames_and_field_value(self) -> None:
        fields = ["x [sound:a.mp3] y", "[sound:b file.ogg] [sound:a.mp3]"]
        self.assertEqual(normalized_audio.extract_sound_filenames(fields), {"a.mp3", "b file.ogg"})
        value = normalized_audio.field_value_for_files(["bac_norm_a_test.m4a", "bac_norm_b_test.wav"])
        self.assertTrue(normalized_audio.is_managed_field_value(value))
        self.assertFalse(normalized_audio.is_managed_field_value("user content"))

    def test_media_stem_is_safe_and_deterministic(self) -> None:
        first = normalized_audio.normalized_media_stem("../áudio estranho.mp3", "a" * 64, -24, False)
        second = normalized_audio.normalized_media_stem("../áudio estranho.mp3", "a" * 64, -24, False)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("bac_norm_"))
        self.assertNotIn("/", first)
        self.assertNotIn("..", first)

    def test_template_block_is_idempotent_and_removable(self) -> None:
        original = "<div>{{Front}}</div>"
        once = normalized_audio.upsert_template_block(original, "BAC Áudio Normalizado")
        twice = normalized_audio.upsert_template_block(once, "BAC Áudio Normalizado")
        self.assertEqual(once, twice)
        self.assertIn("{{BAC Áudio Normalizado}}", once)
        removed = normalized_audio.remove_template_block(once)
        self.assertNotIn(normalized_audio.TEMPLATE_START, removed)
        self.assertIn("{{Front}}", removed)

    def test_render_uses_argument_list_and_shell_false(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mp3"
            source.write_bytes(b"source")
            destination = root / "bac_norm_test.m4a"
            calls = []

            def fake_run(command, **kwargs):
                calls.append((command, kwargs))
                Path(command[-1]).write_bytes(b"normalized")
                return SimpleNamespace(returncode=0, stderr="")

            measurement = {
                "input_i": -18.0,
                "input_tp": -2.0,
                "input_lra": 4.0,
                "input_thresh": -28.0,
                "target_offset": -0.2,
            }
            with patch.object(normalized_audio.subprocess, "run", side_effect=fake_run):
                output = normalized_audio.render_normalized_audio(
                    "ffmpeg",
                    source,
                    destination,
                    measurement,
                    -24.0,
                    False,
                    -1.5,
                    7.0,
                )
            self.assertEqual(output, destination)
            command, kwargs = calls[0]
            self.assertIs(kwargs["shell"], False)
            self.assertIn("-nostdin", command)
            self.assertIn("-map_metadata", command)
            self.assertIn("measured_I=-18.000", command[command.index("-af") + 1])


if __name__ == "__main__":
    unittest.main()

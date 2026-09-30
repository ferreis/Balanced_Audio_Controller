from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "v011.py").read_text(encoding="utf-8")


def load_function(name: str, namespace: dict[str, Any]):
    tree = ast.parse(SOURCE)
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(ROOT / "v011.py"), "exec"), namespace)
    return namespace[name]


class PlaybackModeTests(unittest.TestCase):
    def test_explicit_and_legacy_modes(self) -> None:
        ns = {"Any": Any, "PLAYBACK_MODES": {"profile", "realtime", "created"}, "_conf": lambda: {}}
        playback_mode = load_function("_playback_mode", ns)

        self.assertEqual(playback_mode({"playback_mode": "profile"}), "profile")
        self.assertEqual(playback_mode({"playback_mode": "realtime"}), "realtime")
        self.assertEqual(playback_mode({"playback_mode": "created"}), "created")
        self.assertEqual(playback_mode({"deck_profile_enabled": True, "normalize": True}), "profile")
        self.assertEqual(playback_mode({"deck_profile_enabled": False, "normalize": True}), "realtime")
        self.assertEqual(playback_mode({"deck_profile_enabled": False, "normalize": False}), "created")

    def test_generated_filename_rejects_path_traversal(self) -> None:
        core = SimpleNamespace(
            _is_materialized_audio=lambda value: str(value).startswith("bac_norm_"),
            AUDIO_EXTENSIONS={"m4a", "wav", "mp3"},
        )
        ns = {"Any": Any, "_core": lambda: core}
        safe_generated_filename = load_function("_safe_generated_filename", ns)

        self.assertEqual(safe_generated_filename("bac_norm_abcd_voice.m4a"), "bac_norm_abcd_voice.m4a")
        self.assertIsNone(safe_generated_filename("../bac_norm_abcd_voice.m4a"))
        self.assertIsNone(safe_generated_filename("folder/bac_norm_abcd_voice.m4a"))
        self.assertIsNone(safe_generated_filename("bac_norm_abcd_voice.exe"))
        self.assertIsNone(safe_generated_filename("bac_norm_abcd\x00voice.m4a"))

    def test_created_mode_selects_generated_copy_and_other_modes_drop_it(self) -> None:
        core = SimpleNamespace(
            _is_materialized_audio=lambda value: str(value).startswith("bac_norm_")
        )
        ns = {
            "_core": lambda: core,
            "_safe_generated_filename": lambda value: value if str(value).startswith("bac_norm_") else None,
        }
        selected_filename = load_function("_selected_filename", ns)
        mapping = {"voice.mp3": "bac_norm_1234_voice.m4a"}

        self.assertEqual(selected_filename("voice.mp3", "created", mapping), "bac_norm_1234_voice.m4a")
        self.assertEqual(selected_filename("bac_norm_1234_voice.m4a", "created", mapping), "bac_norm_1234_voice.m4a")
        self.assertEqual(selected_filename("voice.mp3", "profile", mapping), "voice.mp3")
        self.assertEqual(selected_filename("voice.mp3", "realtime", mapping), "voice.mp3")
        self.assertIsNone(selected_filename("bac_norm_1234_voice.m4a", "profile", mapping))
        self.assertIsNone(selected_filename("bac_norm_1234_voice.m4a", "realtime", mapping))

    def test_security_guards_are_present(self) -> None:
        self.assertIn("candidate.relative_to(media_root)", SOURCE)
        self.assertNotIn("shell=True", SOURCE)
        self.assertIn("tags[:] = rewritten", SOURCE)


if __name__ == "__main__":
    unittest.main()

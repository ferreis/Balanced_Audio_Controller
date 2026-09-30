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


class FakeTag:
    def __init__(self, filename: str) -> None:
        self.filename = filename


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

    def _rewrite_namespace(self, mapping: dict[str, str]):
        core = SimpleNamespace(
            _is_materialized_audio=lambda value: str(value).startswith("bac_norm_"),
            AUDIO_EXTENSIONS={"mp3", "m4a"},
        )
        selected = lambda filename, _mode, current_mapping: (
            filename if filename.startswith("bac_norm_") else current_mapping.get(filename, filename)
        )
        return {
            "Any": Any,
            "SoundOrVideoTag": FakeTag,
            "_core": lambda: core,
            "_playback_mode": lambda: "created",
            "_available_materialized_mapping": lambda _deck_id: mapping,
            "_safe_generated_filename": lambda value: value if str(value).startswith("bac_norm_") else None,
            "_selected_filename": selected,
            "_copy_sound_tag": lambda tag, filename: FakeTag(filename),
        }

    def test_created_mode_keeps_render_cache_unchanged(self) -> None:
        rewrite = load_function("_rewrite_playback_tags", self._rewrite_namespace({}))
        tags = [FakeTag("voice.mp3"), FakeTag("bac_norm_1234_voice.m4a")]
        original_ids = [id(tag) for tag in tags]

        rewritten = rewrite(tags, 1)

        self.assertEqual(
            [tag.filename for tag in tags],
            ["voice.mp3", "bac_norm_1234_voice.m4a"],
        )
        self.assertEqual([id(tag) for tag in tags], original_ids)
        self.assertEqual(
            [tag.filename for tag in rewritten],
            ["bac_norm_1234_voice.m4a"],
        )

    def test_created_mode_deduplicates_copy_without_mutating_source(self) -> None:
        mapping = {"voice.mp3": "bac_norm_1234_voice.m4a"}
        rewrite = load_function("_rewrite_playback_tags", self._rewrite_namespace(mapping))
        tags = [FakeTag("voice.mp3"), FakeTag("bac_norm_1234_voice.m4a")]

        rewritten = rewrite(tags, 1)

        self.assertEqual(
            [tag.filename for tag in tags],
            ["voice.mp3", "bac_norm_1234_voice.m4a"],
        )
        self.assertEqual(
            [tag.filename for tag in rewritten],
            ["bac_norm_1234_voice.m4a"],
        )

    def test_player_wrapper_delegates_copy_and_preserves_clicked_tag_list(self) -> None:
        delegated: list[list[str]] = []
        ns = {
            "Any": Any,
            "_current_playback_deck_id": lambda: 42,
            "_rewrite_playback_tags": lambda tags, deck_id: [FakeTag(f"normalized-{deck_id}.m4a")],
            "_ORIGINAL_PLAY_TAGS": lambda tags: delegated.append([tag.filename for tag in tags]),
        }
        play_tags = load_function("_play_tags_without_mutating_render_cache", ns)
        cached_tags = [FakeTag("voice.mp3"), FakeTag("bac_norm_voice.m4a")]

        play_tags(cached_tags)

        self.assertEqual(
            [tag.filename for tag in cached_tags],
            ["voice.mp3", "bac_norm_voice.m4a"],
        )
        self.assertEqual(delegated, [["normalized-42.m4a"]])

    def test_security_and_cache_guards_are_present(self) -> None:
        self.assertIn("candidate.relative_to(media_root)", SOURCE)
        self.assertNotIn("shell=True", SOURCE)
        self.assertNotIn("tags[:] = rewritten", SOURCE)
        self.assertNotIn("gui_hooks.av_player_will_play_tags.append", SOURCE)
        self.assertIn("_ORIGINAL_PLAY_TAGS(rewritten)", SOURCE)
        self.assertIn("av_player.play_tags = _play_tags_without_mutating_render_cache", SOURCE)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "__init__.py").read_text(encoding="utf-8")


def load_function(name: str, namespace: dict[str, Any]):
    tree = ast.parse(SOURCE)
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(ROOT / "__init__.py"), "exec"), namespace)
    return namespace[name]


class FakePlayer:
    def __init__(self) -> None:
        self.properties: list[tuple[str, float]] = []
        self.commands: list[tuple[Any, ...]] = []

    def set_property(self, key: str, value: float) -> None:
        self.properties.append((key, value))

    def command(self, *args: Any) -> None:
        self.commands.append(args)


class PlaybackRegressionTests(unittest.TestCase):
    def base_namespace(self, player: FakePlayer) -> dict[str, Any]:
        config = {
            "speed": 1.25,
            "volume": 0.75,
            "normalize": True,
            "loudness_target": -24,
            "dual_mono": False,
            "deck_profile_enabled": True,
        }
        return {
            "Any": Any,
            "_config": lambda: config,
            "_language": lambda conf: "en",
            "_is_mpv_player": lambda value: value is player,
            "_is_materialized_audio": lambda filename: False,
            "av_player": SimpleNamespace(current_player=player),
            "_current_audio_filename": lambda: "current.mp3",
            "_remove_filter": lambda *args: None,
            "NORMALIZE_FILTER_NAME": "@normalize",
            "DECK_GAIN_FILTER_NAME": "@deck",
            "_profile_entry_for_current_deck": lambda filename, conf: (None, None),
            "_profile_matches_config": lambda profile, conf: True,
            "_deck_gain_filter": lambda gain: f"deck:{gain}",
            "_normalizer_filter": lambda conf: "normalize",
            "t": lambda language, key, **values: key,
        }

    def test_speed_volume_update_does_not_rebuild_filters(self) -> None:
        player = FakePlayer()
        ns = self.base_namespace(player)
        removed: list[tuple[Any, ...]] = []
        ns["_remove_filter"] = lambda *args: removed.append(args)
        ns["_profile_entry_for_current_deck"] = lambda *_: self.fail(
            "profile lookup must not run for speed/volume-only updates"
        )
        apply_settings = load_function("_apply_native_settings", ns)

        supported, status = apply_settings(
            player, "current.mp3", update_filters=False
        )

        self.assertTrue(supported)
        self.assertEqual(status, "")
        self.assertEqual(removed, [])
        self.assertEqual(player.commands, [])
        self.assertIn(("speed", 1.25), player.properties)
        self.assertIn(("volume", 75.0), player.properties)

    def test_filter_refresh_reuses_current_filename_for_deck_profile(self) -> None:
        player = FakePlayer()
        ns = self.base_namespace(player)
        filenames: list[str | None] = []

        def profile_entry(filename, conf):
            filenames.append(filename)
            return ({"target": -24, "dual_mono": False}, {"gain_db": 3.5})

        ns["_profile_entry_for_current_deck"] = profile_entry
        apply_settings = load_function("_apply_native_settings", ns)

        supported, _status = apply_settings(player, None, update_filters=True)

        self.assertTrue(supported)
        self.assertEqual(filenames, ["current.mp3"])
        self.assertIn(("af", "add", "deck:3.5"), player.commands)

    def test_playback_is_registered_before_file_starts(self) -> None:
        self.assertIn(
            "gui_hooks.av_player_will_play.append(_on_av_player_will_play)",
            SOURCE,
        )
        self.assertNotIn(
            "gui_hooks.av_player_did_begin_playing.append(_on_av_player_did_begin_playing)",
            SOURCE,
        )


    def test_materialized_audio_bypasses_runtime_normalization(self) -> None:
        player = FakePlayer()
        ns = self.base_namespace(player)
        removed: list[tuple[Any, ...]] = []
        ns["_remove_filter"] = lambda *args: removed.append(args)
        ns["_is_materialized_audio"] = lambda filename: bool(filename and filename.startswith("bac_norm_"))
        ns["_profile_entry_for_current_deck"] = lambda *_: self.fail(
            "materialized audio must not query/apply deck profile gain"
        )
        apply_settings = load_function("_apply_native_settings", ns)

        supported, status = apply_settings(player, "bac_norm_abcd_voice.m4a")

        self.assertTrue(supported)
        self.assertEqual(status, "status_materialized_audio")
        self.assertEqual(player.commands, [])
        self.assertEqual(len(removed), 2)

    def test_deck_analysis_excludes_materialized_audio(self) -> None:
        self.assertIn(
            "files = {filename for filename in files if not _is_materialized_audio(filename)}",
            SOURCE,
        )



if __name__ == "__main__":
    unittest.main()

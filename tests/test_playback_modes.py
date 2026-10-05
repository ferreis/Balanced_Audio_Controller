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


class FakePlayer:
    def __init__(self) -> None:
        self.commands: list[tuple[Any, ...]] = []
        self.properties: list[tuple[str, float]] = []

    def set_property(self, name: str, value: float) -> None:
        self.properties.append((name, value))

    def command(self, *args: Any) -> None:
        self.commands.append(tuple(args))


class PlaybackModeTests(unittest.TestCase):
    def test_explicit_and_legacy_modes(self) -> None:
        ns = {"Any": Any, "PLAYBACK_MODES": {"profile", "realtime", "created"}, "_conf": lambda: {}}
        playback_mode = load_function("_playback_mode", ns)

        self.assertEqual(playback_mode({"playback_mode": "profile"}), "profile")
        self.assertEqual(playback_mode({"playback_mode": "realtime"}), "realtime")
        self.assertEqual(playback_mode({"playback_mode": "created"}), "created")
        self.assertEqual(
            playback_mode({"playback_mode": "realtime", "deck_profile_enabled": True, "normalize": False}),
            "realtime",
        )
        self.assertEqual(playback_mode({"deck_profile_enabled": True, "normalize": True}), "profile")
        self.assertEqual(playback_mode({"deck_profile_enabled": False, "normalize": True}), "realtime")
        self.assertEqual(playback_mode({"deck_profile_enabled": False, "normalize": False}), "created")

    def test_overvolume_gain_is_clamped_and_filter_has_limiter(self) -> None:
        ns = {
            "Any": Any,
            "OVERVOLUME_DEFAULT_GAIN_DB": 6.0,
            "OVERVOLUME_MAX_GAIN_DB": 12.0,
            "OVERVOLUME_FILTER_NAME": "@ferreis_overvolume",
            "OVERVOLUME_LIMIT_DB": -1.5,
            "_conf": lambda: {},
        }
        gain = load_function("_overvolume_gain_db", ns)
        ns["_overvolume_gain_db"] = gain
        overvolume_filter = load_function("_overvolume_filter", ns)

        self.assertEqual(gain({"overvolume_gain_db": -5}), 0.0)
        self.assertEqual(gain({"overvolume_gain_db": 99}), 12.0)
        self.assertEqual(gain({"overvolume_gain_db": "invalid"}), 6.0)

        filter_spec = overvolume_filter({"overvolume_gain_db": 99})
        self.assertIn("@ferreis_overvolume:lavfi=[", filter_spec)
        self.assertIn("volume=12.000dB", filter_spec)
        self.assertIn("alimiter=limit=0.841395", filter_spec)
        self.assertIn("level=false", filter_spec)

    def test_overvolume_is_removed_when_disabled_and_added_when_enabled(self) -> None:
        player = FakePlayer()
        core = SimpleNamespace(
            _remove_filter=lambda current, name: current.command("af", "remove", name)
        )
        ns = {
            "Any": Any,
            "_core": lambda: core,
            "OVERVOLUME_FILTER_NAME": "@ferreis_overvolume",
            "_overvolume_gain_db": lambda conf: max(0.0, min(12.0, float(conf.get("overvolume_gain_db", 6.0)))),
            "_overvolume_filter": lambda conf: "@ferreis_overvolume:lavfi=[volume=6.000dB,alimiter=limit=0.841395:level=false]",
        }
        apply_overvolume = load_function("_apply_overvolume", ns)

        applied, gain = apply_overvolume(player, {"overvolume_enabled": False, "overvolume_gain_db": 6})
        self.assertFalse(applied)
        self.assertEqual(gain, 6.0)
        self.assertEqual(player.commands, [("af", "remove", "@ferreis_overvolume")])

        player.commands.clear()
        applied, gain = apply_overvolume(player, {"overvolume_enabled": True, "overvolume_gain_db": 6})
        self.assertTrue(applied)
        self.assertEqual(gain, 6.0)
        self.assertEqual(player.commands[0], ("af", "remove", "@ferreis_overvolume"))
        self.assertEqual(player.commands[1][0:2], ("af", "add"))
        self.assertIn("volume=6.000dB", player.commands[1][2])

    def test_overvolume_is_appended_after_realtime_normalization(self) -> None:
        player = FakePlayer()
        core = SimpleNamespace(
            _language=lambda _conf: "en",
            _is_mpv_player=lambda _player: True,
            _current_audio_filename=lambda: "voice.mp3",
            _remove_filter=lambda current, name: current.command("af", "remove", name),
            NORMALIZE_FILTER_NAME="@normalize",
            DECK_GAIN_FILTER_NAME="@deck",
            _is_materialized_audio=lambda _filename: False,
            _normalizer_filter=lambda _conf: "@normalize:lavfi=[loudnorm]",
        )

        def apply_boost(current: FakePlayer, _conf: dict[str, Any]):
            current.command("af", "add", "@ferreis_overvolume:lavfi=[volume=6dB,alimiter]")
            return True, 6.0

        ns = {
            "Any": Any,
            "_core": lambda: core,
            "_conf": lambda: {
                "speed": 1.0,
                "volume": 1.0,
                "loudness_target": -24,
                "overvolume_enabled": True,
            },
            "av_player": SimpleNamespace(current_player=player),
            "t": lambda _lang, key, **_values: key,
            "OVERVOLUME_FILTER_NAME": "@ferreis_overvolume",
            "_apply_overvolume": apply_boost,
            "_local": lambda _lang, key, **_values: key,
            "_playback_mode": lambda _conf: "realtime",
        }
        apply_native = load_function("_apply_native_settings", ns)

        supported, _status = apply_native(player=player, filename="voice.mp3", deck_id=1)

        self.assertTrue(supported)
        filters_added = [command[2] for command in player.commands if command[:2] == ("af", "add")]
        self.assertEqual(filters_added[0], "@normalize:lavfi=[loudnorm]")
        self.assertTrue(filters_added[1].startswith("@ferreis_overvolume:"))

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

    def test_created_mode_without_valid_mapping_falls_back_to_original_without_mutation(self) -> None:
        rewrite = load_function("_rewrite_playback_tags", self._rewrite_namespace({}))
        tags = [FakeTag("voice.mp3"), FakeTag("bac_norm_1234_voice.m4a")]
        original_ids = [id(tag) for tag in tags]

        rewritten = rewrite(tags, 1)

        self.assertEqual(
            [tag.filename for tag in tags],
            ["voice.mp3", "bac_norm_1234_voice.m4a"],
        )
        self.assertEqual([id(tag) for tag in tags], original_ids)
        self.assertEqual([tag.filename for tag in rewritten], ["voice.mp3"])

    def test_created_mode_does_not_inject_generated_copy_missing_from_native_card(self) -> None:
        mapping = {"voice.mp3": "bac_norm_1234_voice.m4a"}
        rewrite = load_function("_rewrite_playback_tags", self._rewrite_namespace(mapping))
        tags = [FakeTag("voice.mp3")]

        rewritten = rewrite(tags, 1)

        self.assertEqual([tag.filename for tag in tags], ["voice.mp3"])
        self.assertEqual([tag.filename for tag in rewritten], ["voice.mp3"])
        self.assertIs(rewritten[0], tags[0])

    def test_created_mode_deduplicates_copy_and_keeps_unmapped_original(self) -> None:
        mapping = {"voice.mp3": "bac_norm_1234_voice.m4a"}
        rewrite = load_function("_rewrite_playback_tags", self._rewrite_namespace(mapping))
        tags = [
            FakeTag("voice.mp3"),
            FakeTag("bac_norm_1234_voice.m4a"),
            FakeTag("bac_norm_old_voice.m4a"),
            FakeTag("other.mp3"),
        ]

        rewritten = rewrite(tags, 1)

        self.assertEqual(
            [tag.filename for tag in tags],
            ["voice.mp3", "bac_norm_1234_voice.m4a", "bac_norm_old_voice.m4a", "other.mp3"],
        )
        self.assertEqual(
            [tag.filename for tag in rewritten],
            ["bac_norm_1234_voice.m4a", "other.mp3"],
        )

    def test_created_ready_requires_native_template_metadata(self) -> None:
        profile = {
            "materialized": {"insert_template": True},
            "normalized_field_setup": {"insert_template": True, "template_count": 1},
        }
        core = SimpleNamespace(_get_deck_profile=lambda _deck_id: profile)
        ns = {
            "_core": lambda: core,
            "_available_materialized_mapping": lambda _deck_id: {"voice.mp3": "bac_norm_voice.m4a"},
        }
        ready = load_function("_materialized_native_ready", ns)

        self.assertTrue(ready(7, {"voice.mp3": "bac_norm_voice.m4a"}))
        profile["materialized"]["insert_template"] = False
        self.assertFalse(ready(7, {"voice.mp3": "bac_norm_voice.m4a"}))
        profile["materialized"]["insert_template"] = True
        profile["normalized_field_setup"]["template_count"] = 0
        self.assertFalse(ready(7, {"voice.mp3": "bac_norm_voice.m4a"}))

    def test_existing_generated_media_can_repair_native_card_integration(self) -> None:
        writes: list[dict[str, Any]] = []
        applied: list[tuple[Any, ...]] = []
        repaired: set[int] = set()
        profile = {"materialized": {"files": {"voice.mp3": "bac_norm_voice.m4a"}}}
        conf = {"normalized_audio_insert_template": False}
        core = SimpleNamespace(_get_deck_profile=lambda _deck_id: profile)
        v010 = SimpleNamespace(
            _current_deck=lambda _context: (7, "Deck"),
            _collect_materialization_plan=lambda _deck_id, _profile: {"notes": {1: {"mid": 2}}},
            _apply_materialization=lambda *args: applied.append(args),
        )
        mw = SimpleNamespace(
            addonManager=SimpleNamespace(
                writeConfig=lambda _package, value: writes.append(dict(value))
            )
        )
        ns = {
            "Any": Any,
            "v010": v010,
            "_available_materialized_mapping": lambda _deck_id: {"voice.mp3": "bac_norm_voice.m4a"},
            "_core": lambda: core,
            "_conf": lambda: conf,
            "mw": mw,
            "__package__": "ferreis_audio_controller",
            "_NATIVE_INTEGRATION_REPAIRED": repaired,
        }
        repair = load_function("_ensure_materialized_card_integration", ns)

        self.assertTrue(repair(object()))
        self.assertTrue(conf["normalized_audio_insert_template"])
        self.assertTrue(writes[-1]["normalized_audio_insert_template"])
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0][0:4], (7, "Deck", {"notes": {1: {"mid": 2}}}, {"voice.mp3": "bac_norm_voice.m4a"}))
        self.assertIs(applied[0][4], True)
        self.assertIn(7, repaired)

    def test_analysis_is_blocked_while_normalized_audio_is_being_created(self) -> None:
        calls: list[str] = []
        notices: list[str] = []
        ns = {
            "v010": SimpleNamespace(_current_deck=lambda _context: (7, "Deck")),
            "_deck_is_materializing": lambda *_args: True,
            "_push_workflow_notice": lambda _context, key: notices.append(key),
            "_ORIGINAL_START_ANALYSIS": lambda _context: calls.append("analysis"),
        }
        coordinated = load_function("_start_analysis_coordinated", ns)

        coordinated(object())

        self.assertEqual(calls, [])
        self.assertEqual(notices, ["busy_materializing"])

        ns["_deck_is_materializing"] = lambda *_args: False
        coordinated = load_function("_start_analysis_coordinated", ns)
        coordinated(object())
        self.assertEqual(calls, ["analysis"])

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
        self.assertIn("core._profile_matches_config(profile, _conf())", SOURCE)
        self.assertNotIn("shell=True", SOURCE)
        self.assertNotIn("tags[:] = rewritten", SOURCE)
        self.assertNotIn("gui_hooks.av_player_will_play_tags.append", SOURCE)
        self.assertIn("_ORIGINAL_PLAY_TAGS(rewritten)", SOURCE)
        self.assertIn("av_player.play_tags = _play_tags_without_mutating_render_cache", SOURCE)
        self.assertIn("OVERVOLUME_MAX_GAIN_DB = 12.0", SOURCE)
        self.assertIn("alimiter=limit=", SOURCE)
        self.assertIn("level=false", SOURCE)
        self.assertIn("v010._start_analysis = _start_analysis_coordinated", SOURCE)
        self.assertIn("v010._clear_current_deck_profile = _clear_profile_coordinated", SOURCE)
        self.assertIn('updated["normalized_audio_insert_template"] = True', SOURCE)
        self.assertIn("native_generated", SOURCE)
        self.assertIn("_ensure_materialized_card_integration", SOURCE)


if __name__ == "__main__":
    unittest.main()

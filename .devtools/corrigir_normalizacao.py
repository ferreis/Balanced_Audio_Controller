from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise SystemExit(f"Trecho não encontrado: {label}")
    return source.replace(old, new, 1)


init_path = ROOT / "__init__.py"
source = init_path.read_text(encoding="utf-8")

source = replace_once(
    source,
    "_PROFILE_LOCK = threading.Lock()\n_ANALYSIS_LOCK = threading.Lock()\n_ANALYSIS_RUNNING: set[str] = set()\n",
    "_PROFILE_LOCK = threading.Lock()\n_ANALYSIS_LOCK = threading.Lock()\n_PLAYBACK_LOCK = threading.RLock()\n_ANALYSIS_RUNNING: set[str] = set()\n_CURRENT_AUDIO_FILENAME: str | None = None\n",
    "locks de reprodução",
)

marker = (
    "def _current_reviewer_deck_id() -> int | None:\n"
    "    card = _current_reviewer_card()\n"
    "    return _card_deck_id(card) if card else None\n\n"
)
helpers = marker + (
    "def _current_audio_filename() -> str | None:\n"
    "    with _PLAYBACK_LOCK:\n"
    "        return _CURRENT_AUDIO_FILENAME\n\n\n"
    "def _set_current_audio_filename(filename: str | None) -> None:\n"
    "    global _CURRENT_AUDIO_FILENAME\n"
    "    with _PLAYBACK_LOCK:\n"
    "        _CURRENT_AUDIO_FILENAME = filename\n\n\n"
)
source = replace_once(source, marker, helpers, "estado do áudio atual")

start = source.index("def _apply_native_settings(")
end = source.index("\ndef _tag_filename", start)
replacement = '''def _apply_native_settings(
    player: Any | None = None,
    filename: str | None = None,
    *,
    update_filters: bool = True,
) -> tuple[bool, str]:
    conf = _config()
    lang = _language(conf)
    player = player or av_player.current_player
    if not _is_mpv_player(player):
        return False, t(lang, "status_native_no_mpv")

    speed = max(0.25, min(2.0, float(conf.get("speed", 1.0))))
    volume = max(0.0, min(1.0, float(conf.get("volume", 1.0))))
    normalize = bool(conf.get("normalize", True))
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))

    try:
        player.set_property("speed", speed)
        player.set_property("volume", volume * 100.0)
    except Exception as exc:
        print("[Balanced Audio Controller] unable to set MPV speed/volume:", exc)
        return False, t(lang, "status_mpv_control_failed")

    # Alterar velocidade/volume não deve reconstruir o grafo de filtros do MPV.
    # Recriar loudnorm durante a reprodução causa cortes audíveis e também pode
    # substituir indevidamente o ganho específico do arquivo analisado.
    if not update_filters:
        return True, ""

    if filename is None:
        filename = _current_audio_filename()

    _remove_filter(player, NORMALIZE_FILTER_NAME)
    _remove_filter(player, DECK_GAIN_FILTER_NAME)

    profile, entry = _profile_entry_for_current_deck(filename, conf)
    if entry is not None:
        try:
            gain_db = float(entry.get("gain_db", 0.0))
            player.command("af", "add", _deck_gain_filter(gain_db))
            return True, t(lang, "status_deck_profile_gain", gain=gain_db)
        except Exception as exc:
            print("[Balanced Audio Controller] unable to apply deck gain:", exc)

    if (
        profile
        and bool(conf.get("deck_profile_enabled", False))
        and not _profile_matches_config(profile, conf)
    ):
        profile_note = t(lang, "status_profile_stale_prefix")
    else:
        profile_note = ""

    if normalize:
        try:
            player.command("af", "add", _normalizer_filter(conf))
            return True, t(
                lang,
                "status_realtime_normalization",
                prefix=profile_note,
                target=target,
            )
        except Exception as exc:
            print("[Balanced Audio Controller] loudnorm unavailable:", exc)
            return True, t(
                lang,
                "status_loudnorm_unavailable",
                prefix=profile_note,
            )

    return True, t(lang, "status_normalization_off", prefix=profile_note)
'''
source = source[:start] + replacement + source[end:]

source = replace_once(
    source,
    '''def _on_av_player_did_begin_playing(player: Any, tag: Any) -> None:
    filename = _tag_filename(tag)
    _supported, status = _apply_native_settings(player, filename)
    _push_status(status)
''',
    '''def _on_av_player_will_play(tag: Any) -> None:
    # O Anki define current_player antes deste hook e só chama player.play()
    # depois. Assim o filtro já está pronto quando o arquivo começa a tocar.
    filename = _tag_filename(tag)
    _set_current_audio_filename(filename)
    player = av_player.current_player
    _supported, status = _apply_native_settings(player, filename)
    if status:
        _push_status(status)


def _on_av_player_did_end_playing(player: Any) -> None:
    _set_current_audio_filename(None)
''',
    "hook pré-playback",
)

source = replace_once(
    source,
    '''            _clear_deck_profile(deck_id)
            _push_deck_profile_state(_deck_profile_summary(deck_id))
        return (True, None)
''',
    '''            _clear_deck_profile(deck_id)
            _push_deck_profile_state(_deck_profile_summary(deck_id))
            _supported, status = _apply_native_settings(
                filename=_current_audio_filename()
            )
            if status:
                _push_status(status)
        return (True, None)
''',
    "limpeza de perfil",
)

source = replace_once(
    source,
    '''        if card:
            _push_deck_profile_state(_deck_profile_summary(_card_deck_id(card)))
        return (True, None)

    if not message.startswith("ferreis_audio:set:"):
''',
    '''        if card:
            _push_deck_profile_state(_deck_profile_summary(_card_deck_id(card)))
        _supported, status = _apply_native_settings(
            filename=_current_audio_filename()
        )
        if status:
            _push_status(status)
        return (True, None)

    if not message.startswith("ferreis_audio:set:"):
''',
    "ativação do perfil",
)

source = replace_once(
    source,
    '''        _supported, status = _apply_native_settings()
        context.web.eval(
            "window.FerreisAnkiAudio && window.FerreisAnkiAudio.setStatus("
            + json.dumps(status, ensure_ascii=False)
            + ");"
        )
        return (True, None)
''',
    '''        update_filters = key in {"normalize", "loudness_target", "dual_mono"}
        _supported, status = _apply_native_settings(
            filename=_current_audio_filename(),
            update_filters=update_filters,
        )
        if status:
            context.web.eval(
                "window.FerreisAnkiAudio && window.FerreisAnkiAudio.setStatus("
                + json.dumps(status, ensure_ascii=False)
                + ");"
            )
        return (True, None)
''',
    "atualização seletiva dos filtros",
)

source = replace_once(
    source,
    "gui_hooks.av_player_did_begin_playing.append(_on_av_player_did_begin_playing)\n",
    "gui_hooks.av_player_will_play.append(_on_av_player_will_play)\n"
    "gui_hooks.av_player_did_end_playing.append(_on_av_player_did_end_playing)\n",
    "registro dos hooks de áudio",
)

init_path.write_text(source, encoding="utf-8")

js_path = ROOT / "web" / "audio_controller.js"
js = js_path.read_text(encoding="utf-8")
js = replace_once(
    js,
    '''      loudness.addEventListener("input", () => {
        const value = clamp(Number(loudness.value), -50, -20);
        this.config.loudness_target = value;
        this.updateLoudnessValue(value);
        pycmd(`ferreis_audio:set:loudness_target:${value}`);
      });
''',
    '''      loudness.addEventListener("input", () => {
        const value = clamp(Number(loudness.value), -50, -20);
        this.config.loudness_target = value;
        this.updateLoudnessValue(value);
      });

      loudness.addEventListener("change", () => {
        const value = clamp(Number(loudness.value), -50, -20);
        this.config.loudness_target = value;
        this.updateLoudnessValue(value);
        pycmd(`ferreis_audio:set:loudness_target:${value}`);
      });
''',
    "commit do slider de LUFS",
)
js_path.write_text(js, encoding="utf-8")

(ROOT / "tests" / "test_playback_regression.py").write_text(
    r'''from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
''',
    encoding="utf-8",
)

playwright_path = ROOT / "tests" / "test_audio_controller_playwright.py"
pw = playwright_path.read_text(encoding="utf-8")
insertion = r'''
    def test_loudness_slider_commits_only_on_change(self) -> None:
        page = self.page_with_config(base_config())
        try:
            page.evaluate("window.__pycmdMessages=[]")
            slider = page.locator(".fac-loudness")
            slider.evaluate(
                """el => {
                    el.value = '-30';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
            )
            self.assertEqual(page.evaluate("window.__pycmdMessages"), [])
            self.assertEqual(
                page.locator(".fac-loudness-value").inner_text(), "-30 LUFS"
            )

            slider.evaluate(
                """el => el.dispatchEvent(new Event('change', { bubbles: true }))"""
            )
            self.assertEqual(
                page.evaluate("window.__pycmdMessages"),
                ["ferreis_audio:set:loudness_target:-30"],
            )
        finally:
            page.close()

'''
marker = '\n\nif __name__ == "__main__":\n'
if marker not in pw:
    raise SystemExit("Ponto de inserção do teste Playwright não encontrado")
pw = pw.replace(marker, "\n" + insertion + marker, 1)
playwright_path.write_text(pw, encoding="utf-8")

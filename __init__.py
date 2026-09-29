from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aqt.reviewer
from anki.sound import SoundOrVideoTag
from aqt import gui_hooks, mw
from aqt.sound import av_player
from aqt.webview import WebContent

from .i18n import resolve_language, t, web_strings

AUDIO_EXTENSIONS = {
    "3gp",
    "flac",
    "m4a",
    "mp3",
    "oga",
    "ogg",
    "opus",
    "spx",
    "wav",
}

NORMALIZE_FILTER_NAME = "@ferreis_normalize"
DECK_GAIN_FILTER_NAME = "@ferreis_deck_gain"
MATERIALIZED_AUDIO_PREFIX = "bac_norm_"
TRUE_PEAK_LIMIT = -1.5
LRA_TARGET = 7.0
PROFILE_FILE_VERSION = 1

_PROFILE_LOCK = threading.Lock()
_ANALYSIS_LOCK = threading.Lock()
_PLAYBACK_LOCK = threading.RLock()
_ANALYSIS_RUNNING: set[str] = set()
_CURRENT_AUDIO_FILENAME: str | None = None
_CURRENT_AUDIO_DECK_ID: int | None = None
_ACTIVE_CARD_CONTEXT: Any | None = None


def _config() -> dict[str, Any]:
    return mw.addonManager.getConfig(__name__) or {}


def _language(conf: dict[str, Any] | None = None) -> str:
    current = conf if conf is not None else _config()
    return resolve_language(current.get("language", "auto"))


def _save_setting(key: str, value: Any) -> None:
    conf = _config()
    conf[key] = value
    mw.addonManager.writeConfig(__name__, conf)


def _audio_filenames(tags: list[Any]) -> list[str]:
    files: list[str] = []
    for tag in tags:
        if not isinstance(tag, SoundOrVideoTag):
            continue
        filename = tag.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in AUDIO_EXTENSIONS:
            files.append(filename)
    return files


def _card_has_audio(card) -> bool:
    return bool(_audio_filenames(card.question_av_tags()) or _audio_filenames(card.answer_av_tags()))


def _card_deck_id(card) -> int:
    original_deck_id = int(getattr(card, "odid", 0) or 0)
    return original_deck_id or int(card.did)


def _deck_name(deck_id: int) -> str:
    try:
        deck = mw.col.decks.get(deck_id)
        if deck:
            return str(deck.get("name", deck_id))
    except Exception:
        pass
    return str(deck_id)


def _current_reviewer_card():
    reviewer = getattr(mw, "reviewer", None)
    return getattr(reviewer, "card", None)


def _current_reviewer_deck_id() -> int | None:
    card = _current_reviewer_card()
    return _card_deck_id(card) if card else None


def _context_surface(context: object | None) -> str:
    if isinstance(context, aqt.reviewer.Reviewer):
        return "reviewer"
    if context is None:
        return ""
    cls = type(context)
    module = str(getattr(cls, "__module__", ""))
    name = str(getattr(cls, "__name__", ""))
    if module == "aqt.browser.previewer" and name.endswith("Previewer"):
        return "previewer"
    if module == "aqt.clayout" and name == "CardLayout":
        return "card_layout"
    return ""


def _is_supported_card_context(context: object | None) -> bool:
    return bool(_context_surface(context))


def _card_from_context(context: object | None):
    if not _is_supported_card_context(context):
        return None
    candidate = getattr(context, "card", None)
    if callable(candidate):
        try:
            candidate = candidate()
        except Exception:
            candidate = None
    if candidate is not None:
        return candidate
    return getattr(context, "rendered_card", None)


def _context_web(context: object | None):
    if not _is_supported_card_context(context):
        return None
    if isinstance(context, aqt.reviewer.Reviewer):
        return getattr(context, "web", None)
    surface = _context_surface(context)
    if surface == "previewer":
        return getattr(context, "_web", None)
    if surface == "card_layout":
        return getattr(context, "preview_web", None)
    return None


def _set_active_card_context(context: object | None) -> None:
    global _ACTIVE_CARD_CONTEXT
    with _PLAYBACK_LOCK:
        _ACTIVE_CARD_CONTEXT = context if _is_supported_card_context(context) else None


def _active_card_context() -> object | None:
    with _PLAYBACK_LOCK:
        return _ACTIVE_CARD_CONTEXT


def _current_audio_filename() -> str | None:
    with _PLAYBACK_LOCK:
        return _CURRENT_AUDIO_FILENAME


def _set_current_audio_filename(filename: str | None) -> None:
    global _CURRENT_AUDIO_FILENAME
    with _PLAYBACK_LOCK:
        _CURRENT_AUDIO_FILENAME = filename


def _current_audio_deck_id() -> int | None:
    with _PLAYBACK_LOCK:
        return _CURRENT_AUDIO_DECK_ID


def _set_current_audio_deck_id(deck_id: int | None) -> None:
    global _CURRENT_AUDIO_DECK_ID
    with _PLAYBACK_LOCK:
        _CURRENT_AUDIO_DECK_ID = deck_id


def _profiles_path() -> Path:
    folder = Path(__file__).resolve().parent / "user_files"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "deck_profiles.json"


def _empty_profiles() -> dict[str, Any]:
    return {"version": PROFILE_FILE_VERSION, "decks": {}}


def _load_profiles() -> dict[str, Any]:
    path = _profiles_path()
    with _PROFILE_LOCK:
        if not path.exists():
            return _empty_profiles()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _empty_profiles()
        if not isinstance(data, dict):
            return _empty_profiles()
        data.setdefault("version", PROFILE_FILE_VERSION)
        data.setdefault("decks", {})
        return data


def _write_profiles(data: dict[str, Any]) -> None:
    path = _profiles_path()
    tmp = path.with_suffix(".json.tmp")
    with _PROFILE_LOCK:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def _get_deck_profile(deck_id: int | None) -> dict[str, Any] | None:
    if deck_id is None:
        return None
    data = _load_profiles()
    profile = data.get("decks", {}).get(str(deck_id))
    return profile if isinstance(profile, dict) else None


def _set_deck_profile(deck_id: int, profile: dict[str, Any]) -> None:
    data = _load_profiles()
    decks = data.setdefault("decks", {})
    decks[str(deck_id)] = profile
    _write_profiles(data)


def _clear_deck_profile(deck_id: int) -> None:
    data = _load_profiles()
    decks = data.setdefault("decks", {})
    decks.pop(str(deck_id), None)
    _write_profiles(data)


def _is_mpv_player(player: Any) -> bool:
    return bool(player and hasattr(player, "set_property") and hasattr(player, "command"))


def _remove_filter(player: Any, filter_name: str) -> None:
    if not _is_mpv_player(player):
        return
    try:
        player.command("af", "remove", filter_name)
    except Exception:
        pass


def _is_materialized_audio(filename: str | None) -> bool:
    if not filename:
        return False
    basename = Path(str(filename).replace("\\", "/")).name
    return basename.casefold().startswith(MATERIALIZED_AUDIO_PREFIX.casefold())


def _normalizer_filter(conf: dict[str, Any]) -> str:
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))
    dual_mono = "true" if bool(conf.get("dual_mono", False)) else "false"
    return (
        f"{NORMALIZE_FILTER_NAME}:lavfi=["
        f"loudnorm=I={target:.1f}:TP={TRUE_PEAK_LIMIT:.1f}:LRA={LRA_TARGET:.0f}:dual_mono={dual_mono}"
        f"]"
    )


def _deck_gain_filter(gain_db: float) -> str:
    gain_db = max(-40.0, min(24.0, float(gain_db)))
    return f"{DECK_GAIN_FILTER_NAME}:lavfi=[volume={gain_db:.3f}dB]"


def _profile_matches_config(profile: dict[str, Any], conf: dict[str, Any]) -> bool:
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))
    return (
        abs(float(profile.get("target", 999)) - target) < 0.01
        and bool(profile.get("dual_mono", False)) == bool(conf.get("dual_mono", False))
    )


def _profile_entry_for_current_deck(
    filename: str | None,
    conf: dict[str, Any],
    deck_id: int | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not filename or not bool(conf.get("deck_profile_enabled", False)):
        return None, None

    deck_id = deck_id if deck_id is not None else _current_audio_deck_id()
    if deck_id is None:
        deck_id = _current_reviewer_deck_id()
    profile = _get_deck_profile(deck_id)
    if not profile or not _profile_matches_config(profile, conf):
        return profile, None

    files = profile.get("files", {})
    if not isinstance(files, dict):
        return profile, None
    entry = files.get(filename)
    return profile, entry if isinstance(entry, dict) else None


def _apply_native_settings(
    player: Any | None = None,
    filename: str | None = None,
    deck_id: int | None = None,
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

    # Cópias bac_norm_* já foram normalizadas fisicamente em disco. Aplicar
    # loudnorm ou ganho do perfil novamente distorceria o resultado e poderia
    # provocar uma segunda normalização desnecessária.
    if _is_materialized_audio(filename):
        return True, t(lang, "status_materialized_audio")

    if deck_id is None:
        profile, entry = _profile_entry_for_current_deck(filename, conf)
    else:
        profile, entry = _profile_entry_for_current_deck(filename, conf, deck_id)
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

def _tag_filename(tag: Any) -> str | None:
    if isinstance(tag, SoundOrVideoTag):
        return tag.filename
    return None


def _push_status(text: str, context: object | None = None) -> None:
    target = context or _active_card_context()
    web = _context_web(target)
    if not web:
        reviewer = getattr(mw, "reviewer", None)
        web = getattr(reviewer, "web", None)
    if not web:
        return
    try:
        web.eval(
            "window.FerreisAnkiAudio && window.FerreisAnkiAudio.setStatus("
            + json.dumps(text, ensure_ascii=False)
            + ");"
        )
    except Exception:
        pass


def _analysis_is_running(deck_id: int) -> bool:
    with _ANALYSIS_LOCK:
        return str(deck_id) in _ANALYSIS_RUNNING


def _set_analysis_running(deck_id: int, running: bool) -> None:
    with _ANALYSIS_LOCK:
        key = str(deck_id)
        if running:
            _ANALYSIS_RUNNING.add(key)
        else:
            _ANALYSIS_RUNNING.discard(key)


def _deck_profile_summary(deck_id: int, deck_name: str | None = None) -> dict[str, Any]:
    conf = _config()
    profile = _get_deck_profile(deck_id)
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))
    result: dict[str, Any] = {
        "deck_id": deck_id,
        "deck_name": deck_name or _deck_name(deck_id),
        "enabled": bool(conf.get("deck_profile_enabled", False)),
        "exists": bool(profile),
        "analyzing": _analysis_is_running(deck_id),
        "target": target,
        "stale": False,
    }

    if not profile:
        return result

    stats = profile.get("stats", {}) if isinstance(profile.get("stats"), dict) else {}
    result.update(
        {
            "profile_target": profile.get("target"),
            "profile_dual_mono": bool(profile.get("dual_mono", False)),
            "file_count": int(profile.get("file_count", 0) or 0),
            "failed_count": int(profile.get("failed_count", 0) or 0),
            "analyzed_at": profile.get("analyzed_at"),
            "min_lufs": stats.get("min_lufs"),
            "max_lufs": stats.get("max_lufs"),
            "average_lufs": stats.get("average_lufs"),
            "stale": not _profile_matches_config(profile, conf),
        }
    )
    return result


def _push_deck_profile_state(
    state: dict[str, Any], context: object | None = None
) -> None:
    target = context or _active_card_context()
    web = _context_web(target)
    if not web:
        reviewer = getattr(mw, "reviewer", None)
        web = getattr(reviewer, "web", None)
    if not web:
        return
    try:
        web.eval(
            "window.FerreisAnkiAudio && window.FerreisAnkiAudio.updateDeckProfile("
            + json.dumps(state, ensure_ascii=False)
            + ");"
        )
    except Exception:
        pass


def _find_ffmpeg() -> str | None:
    executable = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if executable:
        return executable

    import sys

    candidates = [
        Path(sys.executable).resolve().parent / "ffmpeg",
        Path(sys.executable).resolve().parent / "ffmpeg.exe",
        Path(sys.executable).resolve().parent / "bin" / "ffmpeg",
        Path(sys.executable).resolve().parent / "bin" / "ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _parse_loudnorm_json(stderr: str) -> dict[str, float] | None:
    blocks = re.findall(r"\{\s*\"input_i\".*?\}", stderr, flags=re.DOTALL)
    if not blocks:
        return None
    try:
        raw = json.loads(blocks[-1])
        return {
            "input_i": float(raw["input_i"]),
            "input_tp": float(raw["input_tp"]),
            "input_lra": float(raw.get("input_lra", 0.0)),
            "input_thresh": float(raw.get("input_thresh", 0.0)),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _measure_loudness(
    ffmpeg: str, path: Path, target: float, dual_mono: bool
) -> dict[str, float] | None:
    filter_spec = (
        f"loudnorm=I={target:.1f}:TP={TRUE_PEAK_LIMIT:.1f}:LRA={LRA_TARGET:.0f}:"
        f"dual_mono={'true' if dual_mono else 'false'}:print_format=json"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-af",
        filter_spec,
        "-f",
        "null",
        "-",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    return _parse_loudnorm_json(completed.stderr)


def _compute_gain_db(input_i: float, input_tp: float, target: float) -> float:
    desired_gain = target - input_i
    max_gain_before_peak_limit = TRUE_PEAK_LIMIT - input_tp
    gain = min(desired_gain, max_gain_before_peak_limit)
    return round(max(-40.0, min(24.0, gain)), 3)


def _collect_deck_audio_files(deck_id: int) -> tuple[str, list[str]]:
    deck_name = _deck_name(deck_id)
    search_name = deck_name.replace("\\", "\\\\").replace('"', '\\"')
    card_ids = mw.col.find_cards(f'deck:"{search_name}"')
    files: set[str] = set()

    for card_id in card_ids:
        card = mw.col.get_card(card_id)
        files.update(_audio_filenames(card.question_av_tags()))
        files.update(_audio_filenames(card.answer_av_tags()))

    files = {filename for filename in files if not _is_materialized_audio(filename)}
    return deck_name, sorted(files, key=str.casefold)


def _start_deck_analysis(context: object) -> None:
    card = _card_from_context(context) or _current_reviewer_card()
    if not card:
        return

    conf = _config()
    lang = _language(conf)
    deck_id = _card_deck_id(card)

    if _analysis_is_running(deck_id):
        _push_deck_profile_state(
            {
                **_deck_profile_summary(deck_id),
                "message": t(lang, "analysis_already_running"),
            }
        )
        return

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        _push_deck_profile_state(
            {
                **_deck_profile_summary(deck_id),
                "error": t(lang, "ffmpeg_not_found"),
            }
        )
        return

    try:
        deck_name, filenames = _collect_deck_audio_files(deck_id)
    except Exception as exc:
        print("[Balanced Audio Controller] unable to collect deck audio:", exc)
        _push_deck_profile_state(
            {
                **_deck_profile_summary(deck_id),
                "error": t(lang, "deck_audio_list_failed"),
            }
        )
        return

    if not filenames:
        _push_deck_profile_state(
            {
                **_deck_profile_summary(deck_id, deck_name),
                "error": t(lang, "deck_no_audio"),
            }
        )
        return

    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))
    dual_mono = bool(conf.get("dual_mono", False))
    media_dir = Path(mw.col.media.dir())
    total = len(filenames)

    _set_analysis_running(deck_id, True)
    _push_deck_profile_state(
        {
            **_deck_profile_summary(deck_id, deck_name),
            "analyzing": True,
            "processed": 0,
            "total": total,
            "progress": 0,
            "message": t(lang, "analysis_progress", processed=0, total=total),
        }
    )

    def worker() -> dict[str, Any]:
        entries: dict[str, Any] = {}
        failed: list[str] = []
        loudness_values: list[float] = []

        for index, filename in enumerate(filenames, start=1):
            path = media_dir / filename
            measurement = None
            if path.is_file():
                try:
                    measurement = _measure_loudness(ffmpeg, path, target, dual_mono)
                except Exception as exc:
                    print(
                        f"[Balanced Audio Controller] analysis failed for {filename}:",
                        exc,
                    )

            if measurement is None:
                failed.append(filename)
            else:
                input_i = measurement["input_i"]
                input_tp = measurement["input_tp"]
                gain_db = _compute_gain_db(input_i, input_tp, target)
                entries[filename] = {**measurement, "gain_db": gain_db}
                loudness_values.append(input_i)

            progress = round(index * 100 / total)
            try:
                mw.taskman.run_on_main(
                    lambda i=index, p=progress: _push_deck_profile_state(
                        {
                            **_deck_profile_summary(deck_id, deck_name),
                            "analyzing": True,
                            "processed": i,
                            "total": total,
                            "progress": p,
                            "message": t(
                                lang,
                                "analysis_progress",
                                processed=i,
                                total=total,
                            ),
                        }
                    )
                )
            except Exception:
                pass

        if loudness_values:
            stats = {
                "min_lufs": round(min(loudness_values), 2),
                "max_lufs": round(max(loudness_values), 2),
                "average_lufs": round(
                    sum(loudness_values) / len(loudness_values), 2
                ),
            }
        else:
            stats = {"min_lufs": None, "max_lufs": None, "average_lufs": None}

        profile = {
            "version": PROFILE_FILE_VERSION,
            "deck_id": deck_id,
            "deck_name": deck_name,
            "target": target,
            "true_peak_limit": TRUE_PEAK_LIMIT,
            "dual_mono": dual_mono,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(entries),
            "failed_count": len(failed),
            "failed_files": failed,
            "stats": stats,
            "files": entries,
        }
        _set_deck_profile(deck_id, profile)
        return profile

    def on_done(future) -> None:
        _set_analysis_running(deck_id, False)
        try:
            profile = future.result()
            _save_setting("deck_profile_enabled", True)
            state = _deck_profile_summary(deck_id, deck_name)
            state.update(
                {
                    "enabled": True,
                    "analyzing": False,
                    "progress": 100,
                    "processed": total,
                    "total": total,
                    "message": t(
                        lang,
                        "profile_created",
                        count=profile["file_count"],
                    ),
                }
            )
            _push_deck_profile_state(state)
        except Exception as exc:
            print("[Balanced Audio Controller] deck analysis failed:", exc)
            _push_deck_profile_state(
                {
                    **_deck_profile_summary(deck_id, deck_name),
                    "analyzing": False,
                    "error": t(lang, "analysis_failed"),
                }
            )

    mw.taskman.run_in_background(worker, on_done)


def _on_av_player_will_play_tags(tags: list[Any], side: str, context: object) -> None:
    del tags, side
    if not _is_supported_card_context(context):
        _set_current_audio_deck_id(None)
        return
    _set_active_card_context(context)
    card = _card_from_context(context)
    _set_current_audio_deck_id(_card_deck_id(card) if card else None)


def _on_av_player_will_play(tag: Any) -> None:
    # O Anki define current_player antes deste hook e só chama player.play()
    # depois. Assim o filtro já está pronto quando o arquivo começa a tocar.
    filename = _tag_filename(tag)
    _set_current_audio_filename(filename)
    player = av_player.current_player
    _supported, status = _apply_native_settings(
        player, filename, deck_id=_current_audio_deck_id()
    )
    if status:
        _push_status(status)


def _on_av_player_did_end_playing(player: Any) -> None:
    _set_current_audio_filename(None)


def _on_card_will_show(text: str, card, kind: str) -> str:
    kind_info = {
        "reviewQuestion": ("reviewer", "question"),
        "reviewAnswer": ("reviewer", "answer"),
        "previewQuestion": ("previewer", "question"),
        "previewAnswer": ("previewer", "answer"),
        "clayoutQuestion": ("card_layout", "question"),
        "clayoutAnswer": ("card_layout", "answer"),
    }.get(kind)
    if kind_info is None:
        return text

    surface, side = kind_info
    # No revisor, o painel só aparece em cards com áudio. Em pré-visualização
    # ele também aparece sem áudio para ajudar a detectar/configurar a face.
    if surface == "reviewer" and not _card_has_audio(card):
        return text

    conf = _config()
    lang = _language(conf)
    deck_id = _card_deck_id(card)
    deck_name = _deck_name(deck_id)
    side_tags = card.question_av_tags() if side == "question" else card.answer_av_tags()
    payload = {
        "language": lang,
        "surface": surface,
        "side": side,
        "side_audio_count": len(_audio_filenames(side_tags)),
        "i18n": web_strings(lang),
        "speed": max(0.25, min(2.0, float(conf.get("speed", 1.0)))),
        "volume": max(0.0, min(1.0, float(conf.get("volume", 1.0)))),
        "normalize": bool(conf.get("normalize", True)),
        "loudness_target": max(
            -50.0, min(-20.0, float(conf.get("loudness_target", -24.0)))
        ),
        "dual_mono": bool(conf.get("dual_mono", False)),
        "deck_profile": _deck_profile_summary(deck_id, deck_name),
    }
    encoded = html.escape(json.dumps(payload, ensure_ascii=False), quote=True)

    controller = f"""
<div id="ferreis-audio-controller" data-config="{encoded}"></div>
<script>
setTimeout(function() {{
  if (window.FerreisAnkiAudio) window.FerreisAnkiAudio.mount();
}}, 0);
</script>
"""
    return text + controller


def _on_webview_will_set_content(
    web_content: WebContent, context: object | None
) -> None:
    if not _is_supported_card_context(context):
        return
    _set_active_card_context(context)
    addon_package = mw.addonManager.addonFromModule(__name__)
    web_content.css.append(f"/_addons/{addon_package}/web/audio_controller.css")
    web_content.js.append(f"/_addons/{addon_package}/web/audio_controller.js")


def _on_js_message(handled, message: str, context):
    if not _is_supported_card_context(context):
        return handled
    _set_active_card_context(context)
    card = _card_from_context(context) or _current_reviewer_card()

    if message == "ferreis_audio:deck:analyze":
        _start_deck_analysis(context)
        return (True, None)

    if message == "ferreis_audio:deck:clear":
        card = _card_from_context(context) or _current_reviewer_card()
        if card:
            deck_id = _card_deck_id(card)
            _clear_deck_profile(deck_id)
            _push_deck_profile_state(_deck_profile_summary(deck_id))
            _supported, status = _apply_native_settings(
                filename=_current_audio_filename()
            )
            if status:
                _push_status(status)
        return (True, None)

    if message.startswith("ferreis_audio:deck:enable:"):
        raw = message.rsplit(":", 1)[-1]
        value = raw == "1"
        _save_setting("deck_profile_enabled", value)
        card = getattr(context, "card", None) or _current_reviewer_card()
        if card:
            _push_deck_profile_state(_deck_profile_summary(_card_deck_id(card)))
        _supported, status = _apply_native_settings(
            filename=_current_audio_filename()
        )
        if status:
            _push_status(status)
        return (True, None)

    if not message.startswith("ferreis_audio:set:"):
        return handled

    try:
        _, _, key, raw = message.split(":", 3)
        if key == "speed":
            value = max(0.25, min(2.0, float(raw)))
            _save_setting("speed", value)
        elif key == "volume":
            value = max(0.0, min(1.0, float(raw)))
            _save_setting("volume", value)
        elif key == "normalize":
            value = raw == "1"
            _save_setting("normalize", value)
        elif key == "loudness_target":
            value = max(-50.0, min(-20.0, float(raw)))
            _save_setting("loudness_target", value)
            deck_id = _card_deck_id(card) if card else _current_reviewer_deck_id()
            if deck_id is not None:
                _push_deck_profile_state(_deck_profile_summary(deck_id), context)
        elif key == "dual_mono":
            value = raw == "1"
            _save_setting("dual_mono", value)
            deck_id = _card_deck_id(card) if card else _current_reviewer_deck_id()
            if deck_id is not None:
                _push_deck_profile_state(_deck_profile_summary(deck_id), context)
        else:
            return handled

        update_filters = key in {"normalize", "loudness_target", "dual_mono"}
        _supported, status = _apply_native_settings(
            filename=_current_audio_filename(),
            deck_id=_card_deck_id(card) if card else _current_audio_deck_id(),
            update_filters=update_filters,
        )
        web = _context_web(context)
        if status and web:
            web.eval(
                "window.FerreisAnkiAudio && window.FerreisAnkiAudio.setStatus("
                + json.dumps(status, ensure_ascii=False)
                + ");"
            )
        return (True, None)
    except Exception as exc:
        print("[Balanced Audio Controller] setting error:", exc)
        return (True, None)


mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js)")

gui_hooks.card_will_show.append(_on_card_will_show)
gui_hooks.webview_will_set_content.append(_on_webview_will_set_content)
gui_hooks.webview_did_receive_js_message.append(_on_js_message)
gui_hooks.av_player_will_play_tags.append(_on_av_player_will_play_tags)
gui_hooks.av_player_will_play.append(_on_av_player_will_play)
gui_hooks.av_player_did_end_playing.append(_on_av_player_did_end_playing)

# Carrega a extensão somente após o núcleo concluir a própria inicialização.
# Isso evita importação circular entre __init__, i18n e v010.
try:
    from . import v010 as _v010  # noqa: F401,E402
except Exception as _v010_error:
    print("[Balanced Audio Controller] v0.10 extension load failed:", _v010_error)

from __future__ import annotations

import html
import json
from typing import Any

import aqt.reviewer
from anki.sound import SoundOrVideoTag
from aqt import gui_hooks, mw
from aqt.sound import av_player
from aqt.webview import WebContent

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

# Named MPV filter. A label lets us replace only our own filter without
# interfering with filters created by Anki or other add-ons.
NORMALIZE_FILTER_NAME = "@ferreis_normalize"


def _config() -> dict[str, Any]:
    return mw.addonManager.getConfig(__name__) or {}


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


def _save_setting(key: str, value: Any) -> None:
    conf = _config()
    conf[key] = value
    mw.addonManager.writeConfig(__name__, conf)


def _is_mpv_player(player: Any) -> bool:
    # MpvManager exposes set_property() and command(). Structural detection keeps
    # us independent of Anki's private concrete MPV class.
    return bool(player and hasattr(player, "set_property") and hasattr(player, "command"))


def _remove_normalizer(player: Any) -> None:
    if not _is_mpv_player(player):
        return
    try:
        player.command("af", "remove", NORMALIZE_FILTER_NAME)
    except Exception:
        # Removing a missing filter is harmless and can raise on some MPV builds.
        pass


def _normalizer_filter(conf: dict[str, Any]) -> str:
    """Build an FFmpeg EBU R128 loudness-normalization filter for MPV.

    This is deliberately different from changing MPV's volume property. The
    loudnorm filter measures perceived loudness and dynamically corrects the
    stream toward the requested integrated-loudness target while respecting a
    true-peak ceiling.
    """
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))
    dual_mono = "true" if bool(conf.get("dual_mono", False)) else "false"

    # TP=-1.5 dBTP leaves headroom and reduces clipping risk. LRA=7 is FFmpeg's
    # standard speech-friendly default. With no measured_* values supplied,
    # loudnorm operates in its real-time/dynamic mode, which is appropriate for
    # Anki playback where we do not want to rewrite media files first.
    return (
        f"{NORMALIZE_FILTER_NAME}:lavfi=["
        f"loudnorm=I={target:.1f}:TP=-1.5:LRA=7:dual_mono={dual_mono}"
        f"]"
    )


def _apply_native_settings(player: Any | None = None) -> tuple[bool, str]:
    """Apply saved settings to Anki's native MPV player.

    Playback is never intercepted. If MPV controls or loudnorm are unavailable,
    the original Anki audio path continues to work.
    """
    player = player or av_player.current_player
    if not _is_mpv_player(player):
        return False, "Player nativo sem controle MPV"

    conf = _config()
    speed = max(0.25, min(2.0, float(conf.get("speed", 1.0))))
    volume = max(0.0, min(1.0, float(conf.get("volume", 1.0))))
    normalize = bool(conf.get("normalize", True))
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))

    try:
        player.set_property("speed", speed)
        player.set_property("volume", volume * 100.0)
    except Exception as exc:
        print("[Balanced Audio Controller] unable to set MPV speed/volume:", exc)
        return False, "Não foi possível controlar o MPV"

    _remove_normalizer(player)
    if normalize:
        try:
            player.command("af", "add", _normalizer_filter(conf))
            return True, f"Normalização ativa · {target:.0f} LUFS"
        except Exception as exc:
            # loudnorm support depends on the bundled MPV/FFmpeg build. Never
            # block Anki's native playback if the filter is unavailable.
            print("[Balanced Audio Controller] loudnorm unavailable:", exc)
            return True, "Velocidade/volume ativos; loudnorm indisponível"

    return True, "Normalização desligada"


def _push_status(text: str) -> None:
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


def _on_av_player_did_begin_playing(player: Any, _tag: Any) -> None:
    # Apply settings after Anki starts each native audio file. The card's own
    # replay buttons and autoplay remain completely untouched.
    _supported, status = _apply_native_settings(player)
    _push_status(status)


def _on_card_will_show(text: str, card, kind: str) -> str:
    if kind not in ("reviewQuestion", "reviewAnswer") or not _card_has_audio(card):
        return text

    conf = _config()
    payload = {
        "speed": max(0.25, min(2.0, float(conf.get("speed", 1.0)))),
        "volume": max(0.0, min(1.0, float(conf.get("volume", 1.0)))),
        "normalize": bool(conf.get("normalize", True)),
        "loudness_target": max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0)))),
        "dual_mono": bool(conf.get("dual_mono", False)),
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


def _on_webview_will_set_content(web_content: WebContent, context: object | None) -> None:
    if not isinstance(context, aqt.reviewer.Reviewer):
        return
    addon_package = mw.addonManager.addonFromModule(__name__)
    web_content.css.append(f"/_addons/{addon_package}/web/audio_controller.css")
    web_content.js.append(f"/_addons/{addon_package}/web/audio_controller.js")


def _on_js_message(handled, message: str, context):
    if not isinstance(context, aqt.reviewer.Reviewer):
        return handled

    if not message.startswith("ferreis_audio:set:"):
        # Native Anki messages (including replay commands) pass through untouched.
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
        elif key == "dual_mono":
            value = raw == "1"
            _save_setting("dual_mono", value)
        else:
            return handled

        _supported, status = _apply_native_settings()
        context.web.eval(
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
gui_hooks.av_player_did_begin_playing.append(_on_av_player_did_begin_playing)

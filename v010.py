from __future__ import annotations

import json
import math
import secrets
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import aqt.reviewer
from aqt import gui_hooks, mw
from aqt.webview import WebContent

from .analysis_engine import ffmpeg_status, find_ffmpeg, install_managed_ffmpeg, measure_with_ffmpeg, resolve_backend
from .i18n import t

ADDON_ROOT = Path(__file__).resolve().parent
TRUE_PEAK_LIMIT = -1.5
LRA_TARGET = 7.0
_SESSIONS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()
_INSTALLING = False


def _core():
    return sys.modules[__package__]


def _conf() -> dict[str, Any]:
    return mw.addonManager.getConfig(__package__) or {}


def _lang() -> str:
    core = _core()
    return core._language(_conf())


def _ffmpeg_state() -> dict[str, Any]:
    state = ffmpeg_status(ADDON_ROOT)
    with _LOCK:
        state["installing"] = _INSTALLING
    return state


def _state(deck_id: int, deck_name: str | None = None) -> dict[str, Any]:
    core = _core()
    state = core._deck_profile_summary(deck_id, deck_name)
    conf = _conf()
    ffmpeg = _ffmpeg_state()
    configured = str(conf.get("analysis_backend", "auto"))
    state.update({
        "analysis_backend": configured,
        "resolved_backend": resolve_backend(configured, bool(ffmpeg["available"])),
        "ffmpeg": ffmpeg,
    })
    profile = core._get_deck_profile(deck_id)
    if isinstance(profile, dict):
        state["profile_backend"] = profile.get("analysis_backend", "ffmpeg")
        state["approximate"] = bool(profile.get("approximate", False))
    return state


def _push_state(state: dict[str, Any]) -> None:
    reviewer = getattr(mw, "reviewer", None)
    web = getattr(reviewer, "web", None)
    if not web:
        return
    payload = json.dumps(state, ensure_ascii=False)
    web.eval(f"window.BACV010 && window.BACV010.updateState({payload});")
    try:
        web.eval(f"window.FerreisAnkiAudio && window.FerreisAnkiAudio.updateDeckProfile({payload});")
    except Exception:
        pass


def _current_deck(context=None) -> tuple[int, str] | None:
    core = _core()
    card = getattr(context, "card", None) if context is not None else None
    card = card or core._current_reviewer_card()
    if not card:
        return None
    deck_id = core._card_deck_id(card)
    return deck_id, core._deck_name(deck_id)


def _safe_media_path(media_dir: Path, filename: str) -> Path | None:
    if not filename or "\x00" in filename:
        return None
    try:
        root = media_dir.resolve(strict=True)
        candidate = (root / filename).resolve(strict=True)
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def _stats(entries: dict[str, Any]) -> dict[str, float | None]:
    vals = [float(v["input_i"]) for v in entries.values() if isinstance(v, dict) and math.isfinite(float(v.get("input_i", math.nan)))]
    if not vals:
        return {"min_lufs": None, "max_lufs": None, "average_lufs": None}
    return {"min_lufs": round(min(vals), 2), "max_lufs": round(max(vals), 2), "average_lufs": round(sum(vals) / len(vals), 2)}


def _profile(deck_id: int, deck_name: str, target: float, dual_mono: bool, backend: str, entries: dict[str, Any], failed: list[str]) -> dict[str, Any]:
    return {
        "version": 2,
        "analysis_backend": backend,
        "approximate": backend == "webaudio",
        "deck_id": deck_id,
        "deck_name": deck_name,
        "target": target,
        "true_peak_limit": TRUE_PEAK_LIMIT,
        "dual_mono": dual_mono,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(entries),
        "failed_count": len(failed),
        "failed_files": failed,
        "stats": _stats(entries),
        "files": entries,
    }


def _start_ffmpeg_analysis(context) -> None:
    core = _core()
    current = _current_deck(context)
    if not current:
        return
    deck_id, deck_name = current
    lang = _lang()
    ffmpeg, _source = find_ffmpeg(ADDON_ROOT)
    if not ffmpeg:
        state = _state(deck_id, deck_name)
        state["error"] = t(lang, "ffmpeg_required_backend")
        _push_state(state)
        return
    if core._analysis_is_running(deck_id):
        return
    try:
        deck_name, filenames = core._collect_deck_audio_files(deck_id)
    except Exception:
        state = _state(deck_id, deck_name)
        state["error"] = t(lang, "deck_audio_list_failed")
        _push_state(state)
        return
    if not filenames:
        state = _state(deck_id, deck_name)
        state["error"] = t(lang, "deck_no_audio")
        _push_state(state)
        return

    conf = _conf()
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24))))
    dual_mono = bool(conf.get("dual_mono", False))
    media_dir = Path(mw.col.media.dir())
    total = len(filenames)
    core._set_analysis_running(deck_id, True)
    initial = _state(deck_id, deck_name)
    initial.update({"analyzing": True, "processed": 0, "total": total, "progress": 0, "message": t(lang, "analysis_progress", processed=0, total=total)})
    _push_state(initial)

    def worker():
        entries: dict[str, Any] = {}
        failed: list[str] = []
        for index, filename in enumerate(filenames, 1):
            path = _safe_media_path(media_dir, filename)
            measurement = None
            if path:
                try:
                    measurement = measure_with_ffmpeg(ffmpeg, path, target, dual_mono, TRUE_PEAK_LIMIT, LRA_TARGET)
                except Exception:
                    measurement = None
            if measurement:
                gain = core._compute_gain_db(float(measurement["input_i"]), float(measurement["input_tp"]), target)
                entries[filename] = {**measurement, "gain_db": gain}
            else:
                failed.append(filename)
            progress = round(index * 100 / total)
            try:
                mw.taskman.run_on_main(lambda i=index, p=progress: _push_state({**_state(deck_id, deck_name), "analyzing": True, "processed": i, "total": total, "progress": p, "message": t(lang, "analysis_progress", processed=i, total=total)}))
            except Exception:
                pass
        result = _profile(deck_id, deck_name, target, dual_mono, "ffmpeg", entries, failed)
        core._set_deck_profile(deck_id, result)
        return result

    def done(future):
        core._set_analysis_running(deck_id, False)
        try:
            result = future.result()
            core._save_setting("deck_profile_enabled", True)
            state = _state(deck_id, deck_name)
            state.update({"enabled": True, "analyzing": False, "progress": 100, "processed": total, "total": total, "message": t(lang, "profile_created", count=result["file_count"])})
        except Exception:
            state = _state(deck_id, deck_name)
            state.update({"analyzing": False, "error": t(lang, "analysis_failed")})
        _push_state(state)

    mw.taskman.run_in_background(worker, done)


def _start_webaudio_analysis(context) -> None:
    core = _core()
    current = _current_deck(context)
    if not current:
        return
    deck_id, deck_name = current
    lang = _lang()
    if core._analysis_is_running(deck_id):
        return
    try:
        deck_name, filenames = core._collect_deck_audio_files(deck_id)
    except Exception:
        state = _state(deck_id, deck_name); state["error"] = t(lang, "deck_audio_list_failed"); _push_state(state); return
    if not filenames:
        state = _state(deck_id, deck_name); state["error"] = t(lang, "deck_no_audio"); _push_state(state); return

    conf = _conf()
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24))))
    dual_mono = bool(conf.get("dual_mono", False))
    session_id = secrets.token_urlsafe(18)
    with _LOCK:
        _SESSIONS[session_id] = {"deck_id": deck_id, "deck_name": deck_name, "lang": lang, "target": target, "dual_mono": dual_mono, "files": set(filenames), "seen": set(), "entries": {}, "failed": [], "processed": 0, "total": len(filenames)}
    core._set_analysis_running(deck_id, True)
    state = _state(deck_id, deck_name)
    state.update({"analyzing": True, "processed": 0, "total": len(filenames), "progress": 0, "message": t(lang, "analysis_progress_webaudio", processed=0, total=len(filenames))})
    _push_state(state)
    payload = json.dumps({"session": session_id, "files": filenames, "dual_mono": dual_mono}, ensure_ascii=False)
    context.web.eval(f"window.BACV010 && window.BACV010.startWebAudioAnalysis({payload});")


def _start_analysis(context) -> None:
    conf = _conf()
    ffmpeg = _ffmpeg_state()
    configured = str(conf.get("analysis_backend", "auto"))
    backend = resolve_backend(configured, bool(ffmpeg["available"]))
    if backend == "ffmpeg" and not ffmpeg["available"]:
        current = _current_deck(context)
        if current:
            state = _state(*current); state["error"] = t(_lang(), "ffmpeg_required_backend"); _push_state(state)
        return
    if backend == "ffmpeg":
        _start_ffmpeg_analysis(context)
    else:
        _start_webaudio_analysis(context)


def _handle_item(message: str) -> None:
    prefix = "ferreis_audio:v010:webaudio:item:"
    if len(message) > 20000:
        return
    rest = message[len(prefix):]
    if ":" not in rest:
        return
    session_id, encoded = rest.split(":", 1)
    with _LOCK:
        session = _SESSIONS.get(session_id)
        if not session:
            return
        try:
            data = json.loads(unquote(encoded))
        except Exception:
            return
        filename = str(data.get("filename", ""))
        if filename not in session["files"] or filename in session["seen"]:
            return
        session["seen"].add(filename)
        session["processed"] += 1
        if bool(data.get("ok")):
            try:
                input_i = float(data["input_i"]); input_tp = float(data["input_tp"])
                if not (math.isfinite(input_i) and math.isfinite(input_tp) and -120 <= input_i <= 20 and -120 <= input_tp <= 20):
                    raise ValueError
                core = _core()
                gain = core._compute_gain_db(input_i, input_tp, float(session["target"]))
                session["entries"][filename] = {"input_i": input_i, "input_tp": input_tp, "input_lra": 0.0, "input_thresh": -70.0, "gain_db": gain}
            except Exception:
                session["failed"].append(filename)
        else:
            session["failed"].append(filename)
        processed = int(session["processed"]); total = int(session["total"]); deck_id = int(session["deck_id"]); deck_name = str(session["deck_name"]); lang = str(session["lang"])
    _push_state({**_state(deck_id, deck_name), "analyzing": True, "processed": processed, "total": total, "progress": round(processed * 100 / max(1, total)), "message": t(lang, "analysis_progress_webaudio", processed=processed, total=total)})


def _handle_done(message: str) -> None:
    core = _core()
    session_id = message.split(":")[-1].strip()
    with _LOCK:
        session = _SESSIONS.pop(session_id, None)
    if not session:
        return
    deck_id = int(session["deck_id"]); deck_name = str(session["deck_name"]); lang = str(session["lang"])
    core._set_analysis_running(deck_id, False)
    missing = set(session["files"]) - set(session["seen"])
    failed = list(session["failed"]) + sorted(missing, key=str.casefold)
    entries = dict(session["entries"])
    if not entries:
        state = _state(deck_id, deck_name); state["analyzing"] = False; state["error"] = t(lang, "analysis_webaudio_failed"); _push_state(state); return
    result = _profile(deck_id, deck_name, float(session["target"]), bool(session["dual_mono"]), "webaudio", entries, failed)
    core._set_deck_profile(deck_id, result)
    core._save_setting("deck_profile_enabled", True)
    state = _state(deck_id, deck_name)
    state.update({"enabled": True, "analyzing": False, "progress": 100, "processed": int(session["total"]), "total": int(session["total"]), "message": t(lang, "profile_created_webaudio", count=result["file_count"])})
    _push_state(state)


def _install_ffmpeg() -> None:
    global _INSTALLING
    lang = _lang()
    status = _ffmpeg_state()
    if status["available"]:
        return
    if not status["installer_available"]:
        _core()._push_status(t(lang, "ffmpeg_install_unavailable")); return
    with _LOCK:
        if _INSTALLING:
            return
        _INSTALLING = True
    current = _current_deck()
    if current:
        state = _state(*current); state["message"] = t(lang, "ffmpeg_installing", installer=status.get("installer_name") or "imageio-ffmpeg"); _push_state(state)

    def worker():
        return install_managed_ffmpeg(ADDON_ROOT)

    def done(future):
        global _INSTALLING
        with _LOCK:
            _INSTALLING = False
        try:
            future.result(); message = t(lang, "ffmpeg_installed")
        except Exception as exc:
            print("[Balanced Audio Controller] FFmpeg installation failed:", exc); message = t(lang, "ffmpeg_install_failed")
        _core()._push_status(message)
        current_deck = _current_deck()
        if current_deck:
            state = _state(*current_deck); state["message"] = message; _push_state(state)

    mw.taskman.run_in_background(worker, done)


def _on_web_content(web_content: WebContent, context: object | None) -> None:
    if not isinstance(context, aqt.reviewer.Reviewer):
        return
    package = mw.addonManager.addonFromModule(__package__)
    web_content.js.append(f"/_addons/{package}/web/audio_controller_v010.js")


def _on_message(handled, message: str, context):
    if not isinstance(context, aqt.reviewer.Reviewer):
        return handled
    if message == "ferreis_audio:v010:state":
        current = _current_deck(context)
        if current: _push_state(_state(*current))
        return (True, None)
    if message == "ferreis_audio:v010:analyze":
        _start_analysis(context); return (True, None)
    if message == "ferreis_audio:v010:ffmpeg:install":
        _install_ffmpeg(); return (True, None)
    if message.startswith("ferreis_audio:v010:backend:"):
        value = message.rsplit(":", 1)[-1]
        if value not in {"auto", "ffmpeg", "webaudio"}: value = "auto"
        _core()._save_setting("analysis_backend", value)
        current = _current_deck(context)
        if current: _push_state(_state(*current))
        return (True, None)
    if message.startswith("ferreis_audio:v010:webaudio:item:"):
        _handle_item(message); return (True, None)
    if message.startswith("ferreis_audio:v010:webaudio:done:"):
        _handle_done(message); return (True, None)
    return handled


gui_hooks.webview_will_set_content.append(_on_web_content)
gui_hooks.webview_did_receive_js_message.append(_on_message)

from __future__ import annotations

import json
import math
import secrets
import shutil
import sys
import tempfile
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
from .normalized_audio import (
    FIELD_BASE_NAME,
    MAX_OUTPUT_BYTES,
    extract_sound_filenames,
    field_value_for_files,
    file_sha256,
    is_managed_field_value,
    normalized_media_stem,
    remove_template_block,
    render_normalized_audio,
    upsert_template_block,
)

ADDON_ROOT = Path(__file__).resolve().parent
TRUE_PEAK_LIMIT = -1.5
LRA_TARGET = 7.0
_SESSIONS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()
_INSTALLING = False
_MATERIALIZING: set[str] = set()


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
    with _LOCK:
        materializing = str(deck_id) in _MATERIALIZING
    state.update({
        "analysis_backend": configured,
        "resolved_backend": resolve_backend(configured, bool(ffmpeg["available"])),
        "ffmpeg": ffmpeg,
        "materializing": materializing,
        "insert_normalized_template": bool(conf.get("normalized_audio_insert_template", True)),
    })
    profile = core._get_deck_profile(deck_id)
    if isinstance(profile, dict):
        state["profile_backend"] = profile.get("analysis_backend", "ffmpeg")
        state["approximate"] = bool(profile.get("approximate", False))
        materialized = profile.get("materialized")
        if isinstance(materialized, dict):
            state["materialized_audio_count"] = int(materialized.get("audio_count", 0) or 0)
            state["materialized_note_count"] = int(materialized.get("note_count", 0) or 0)
            state["materialized_at"] = materialized.get("created_at")
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



def _materializing(deck_id: int, value: bool) -> None:
    with _LOCK:
        key = str(deck_id)
        if value:
            _MATERIALIZING.add(key)
        else:
            _MATERIALIZING.discard(key)


def _collect_materialization_plan(deck_id: int, profile: dict[str, Any]) -> dict[str, Any]:
    core = _core()
    files = profile.get("files", {})
    if not isinstance(files, dict) or not files:
        return {"notes": {}, "template_ords": {}, "sources": []}
    profile_files = set(str(name) for name in files)
    deck_name = core._deck_name(deck_id)
    search_name = deck_name.replace("\\", "\\\\").replace('"', '\\"')
    card_ids = mw.col.find_cards(f'deck:"{search_name}"')
    note_cache: dict[int, Any] = {}
    notes: dict[int, dict[str, Any]] = {}
    template_ords: dict[int, set[int]] = {}

    for card_id in card_ids:
        card = mw.col.get_card(card_id)
        note_id = int(card.nid)
        note = note_cache.get(note_id)
        if note is None:
            note = mw.col.get_note(card.nid)
            note_cache[note_id] = note
        relevant = extract_sound_filenames(note.fields) & profile_files
        if not relevant:
            continue
        mid = int(note.mid)
        item = notes.setdefault(note_id, {"mid": mid, "sources": set()})
        item["sources"].update(relevant)
        template_ords.setdefault(mid, set()).add(int(card.ord))

    return {
        "notes": {
            note_id: {"mid": item["mid"], "sources": sorted(item["sources"], key=str.casefold)}
            for note_id, item in notes.items()
        },
        "template_ords": {mid: sorted(ords) for mid, ords in template_ords.items()},
        "sources": sorted(
            {source for item in notes.values() for source in item["sources"]},
            key=str.casefold,
        ),
    }


def _choose_normalized_field(
    model: dict[str, Any], note_ids: list[int], previous: str | None
) -> tuple[str, bool]:
    names = {str(field.get("name", "")) for field in model.get("flds", [])}
    if previous and previous in names:
        return previous, False

    for index in range(1, 100):
        candidate = FIELD_BASE_NAME if index == 1 else f"{FIELD_BASE_NAME} {index}"
        if candidate not in names:
            return candidate, True
        safe_to_reuse = True
        for note_id in note_ids:
            note = mw.col.get_note(note_id)
            try:
                value = note[candidate]
            except KeyError:
                safe_to_reuse = False
                break
            if not is_managed_field_value(value):
                safe_to_reuse = False
                break
        if safe_to_reuse:
            return candidate, False
    raise RuntimeError("unable to allocate a safe normalized audio field")


def _apply_materialization(
    deck_id: int,
    deck_name: str,
    plan: dict[str, Any],
    generated: dict[str, str],
    insert_template: bool,
    profile: dict[str, Any],
) -> tuple[int, dict[str, str]]:
    notes = plan["notes"]
    by_mid: dict[int, list[int]] = {}
    for note_id, item in notes.items():
        by_mid.setdefault(int(item["mid"]), []).append(int(note_id))

    previous_materialized = profile.get("materialized") if isinstance(profile.get("materialized"), dict) else {}
    previous_fields = previous_materialized.get("fields", {}) if isinstance(previous_materialized, dict) else {}
    fields: dict[str, str] = {}

    for mid, note_ids in by_mid.items():
        model = mw.col.models.get(mid)
        if not model:
            continue
        previous = previous_fields.get(str(mid)) if isinstance(previous_fields, dict) else None
        field_name, create_field = _choose_normalized_field(model, note_ids, str(previous) if previous else None)
        changed = False
        if create_field:
            mw.col.models.add_field(model, mw.col.models.new_field(field_name))
            changed = True

        templates = model.get("tmpls", [])
        for raw_ord in plan["template_ords"].get(mid, []):
            if not templates:
                continue
            template_index = raw_ord if 0 <= raw_ord < len(templates) else 0
            template = templates[template_index]
            current = str(template.get("afmt", ""))
            updated = upsert_template_block(current, field_name) if insert_template else remove_template_block(current)
            if updated != current:
                template["afmt"] = updated
                changed = True
        if changed:
            mw.col.models.update_dict(model)
        fields[str(mid)] = field_name

    updated_notes = 0
    for raw_note_id, item in notes.items():
        note_id = int(raw_note_id)
        field_name = fields.get(str(int(item["mid"])))
        if not field_name:
            continue
        media_names = [generated[source] for source in item["sources"] if source in generated]
        value = field_value_for_files(media_names)
        if not value:
            continue
        note = mw.col.get_note(note_id)
        if field_name not in note:
            continue
        current = note[field_name]
        if current and not is_managed_field_value(current):
            continue
        if current != value:
            note[field_name] = value
            mw.col.update_note(note)
        updated_notes += 1

    refreshed = core = _core()
    current_profile = core._get_deck_profile(deck_id) or dict(profile)
    current_profile["materialized"] = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audio_count": len(generated),
        "note_count": updated_notes,
        "files": generated,
        "fields": fields,
        "insert_template": bool(insert_template),
    }
    core._set_deck_profile(deck_id, current_profile)
    return updated_notes, fields


def _start_materialization(context) -> None:
    core = _core()
    current = _current_deck(context)
    if not current:
        return
    deck_id, deck_name = current
    lang = _lang()
    if core._analysis_is_running(deck_id) or _state(deck_id, deck_name).get("materializing"):
        return

    profile = core._get_deck_profile(deck_id)
    if not isinstance(profile, dict) or not profile.get("files"):
        state = _state(deck_id, deck_name)
        state["error"] = t(lang, "materialize_profile_required")
        _push_state(state)
        return
    if not core._profile_matches_config(profile, _conf()):
        state = _state(deck_id, deck_name)
        state["error"] = t(lang, "materialize_profile_stale")
        _push_state(state)
        return

    ffmpeg, _source = find_ffmpeg(ADDON_ROOT)
    if not ffmpeg:
        state = _state(deck_id, deck_name)
        state["error"] = t(lang, "materialize_requires_ffmpeg")
        _push_state(state)
        return

    plan = _collect_materialization_plan(deck_id, profile)
    sources = list(plan["sources"])
    if not sources or not plan["notes"]:
        state = _state(deck_id, deck_name)
        state["error"] = t(lang, "materialize_no_linked_audio")
        _push_state(state)
        return

    target = float(profile.get("target", -24.0))
    dual_mono = bool(profile.get("dual_mono", False))
    insert_template = bool(_conf().get("normalized_audio_insert_template", True))
    media_dir = Path(mw.col.media.dir())
    total = len(sources)
    _materializing(deck_id, True)
    state = _state(deck_id, deck_name)
    state.update({"materializing": True, "materialize_processed": 0, "materialize_total": total, "message": t(lang, "materialize_progress", processed=0, total=total)})
    _push_state(state)

    def worker():
        temp_dir = Path(tempfile.mkdtemp(prefix="bac-normalized-"))
        generated: list[dict[str, str]] = []
        failed: list[str] = []
        try:
            for index, filename in enumerate(sources, 1):
                source_path = _safe_media_path(media_dir, filename)
                if not source_path:
                    failed.append(filename)
                    continue
                try:
                    measurement = measure_with_ffmpeg(
                        ffmpeg,
                        source_path,
                        target,
                        dual_mono,
                        TRUE_PEAK_LIMIT,
                        LRA_TARGET,
                    )
                    if not measurement:
                        raise RuntimeError("loudness measurement failed")
                    digest = file_sha256(source_path)
                    stem = normalized_media_stem(filename, digest, target, dual_mono)
                    desired = temp_dir / f"{stem}.m4a"
                    rendered = render_normalized_audio(
                        ffmpeg,
                        source_path,
                        desired,
                        measurement,
                        target,
                        dual_mono,
                        TRUE_PEAK_LIMIT,
                        LRA_TARGET,
                    )
                    if rendered.stat().st_size > MAX_OUTPUT_BYTES:
                        raise RuntimeError("normalized audio exceeds size limit")
                    generated.append({"source": filename, "path": str(rendered)})
                except Exception as exc:
                    print(f"[Balanced Audio Controller] normalized copy failed for {filename}:", exc)
                    failed.append(filename)
                progress = round(index * 100 / total)
                try:
                    mw.taskman.run_on_main(
                        lambda i=index, p=progress: _push_state({
                            **_state(deck_id, deck_name),
                            "materializing": True,
                            "materialize_processed": i,
                            "materialize_total": total,
                            "materialize_progress": p,
                            "message": t(lang, "materialize_progress", processed=i, total=total),
                        })
                    )
                except Exception:
                    pass
            return {"temp_dir": str(temp_dir), "generated": generated, "failed": failed}
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def done(future):
        _materializing(deck_id, False)
        temp_dir: str | None = None
        try:
            result = future.result()
            temp_dir = result.get("temp_dir")
            generated_map: dict[str, str] = {}
            for item in result.get("generated", []):
                path = Path(item["path"])
                if not path.is_file() or not path.name.startswith("bac_norm_"):
                    continue
                stored_name = mw.col.media.add_file(str(path))
                generated_map[str(item["source"])] = stored_name
            if not generated_map:
                raise RuntimeError("no normalized audio could be created")
            note_count, _fields = _apply_materialization(
                deck_id,
                deck_name,
                plan,
                generated_map,
                insert_template,
                profile,
            )
            state = _state(deck_id, deck_name)
            state.update({
                "materializing": False,
                "materialized_audio_count": len(generated_map),
                "materialized_note_count": note_count,
                "message": t(lang, "materialize_done", count=len(generated_map), notes=note_count),
            })
        except Exception as exc:
            print("[Balanced Audio Controller] materialization failed:", exc)
            state = _state(deck_id, deck_name)
            state.update({"materializing": False, "error": t(lang, "materialize_failed")})
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
        _push_state(state)

    mw.taskman.run_in_background(worker, done)

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
    if message == "ferreis_audio:v010:materialize":
        _start_materialization(context); return (True, None)
    if message.startswith("ferreis_audio:v010:materialize:insert:"):
        value = message.rsplit(":", 1)[-1] == "1"
        _core()._save_setting("normalized_audio_insert_template", value)
        current = _current_deck(context)
        if current: _push_state(_state(*current))
        return (True, None)
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

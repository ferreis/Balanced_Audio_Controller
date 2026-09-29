from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('.')

NORMALIZED_AUDIO = r'''from __future__ import annotations

import hashlib
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

FIELD_BASE_NAME = "BAC Áudio Normalizado"
GENERATED_PREFIX = "bac_norm_"
TEMPLATE_START = "<!-- BAC:NORMALIZED:AUDIO:START -->"
TEMPLATE_END = "<!-- BAC:NORMALIZED:AUDIO:END -->"
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
_SOUND_RE = re.compile(r"\[sound:([^\]\r\n]+)\]", flags=re.IGNORECASE)
_MANAGED_VALUE_RE = re.compile(
    r"^(?:\s*\[sound:bac_norm_[^\]\r\n]+\]\s*)*$",
    flags=re.IGNORECASE,
)


def extract_sound_filenames(fields: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for value in fields:
        for match in _SOUND_RE.finditer(str(value or "")):
            filename = match.group(1).strip()
            if filename:
                result.add(filename)
    return result


def is_managed_field_value(value: str | None) -> bool:
    return bool(_MANAGED_VALUE_RE.fullmatch(str(value or "")))


def field_value_for_files(filenames: Iterable[str]) -> str:
    safe: list[str] = []
    for filename in filenames:
        value = str(filename or "").strip()
        if not value or "\x00" in value or "]" in value or "\r" in value or "\n" in value:
            continue
        safe.append(f"[sound:{value}]")
    return " ".join(dict.fromkeys(safe))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalized_media_stem(
    source_filename: str,
    source_digest: str,
    target: float,
    dual_mono: bool,
) -> str:
    basename = Path(str(source_filename).replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(basename).stem).strip("._-")
    stem = (stem or "audio")[:48]
    identity = f"{source_digest}\0{basename}\0{float(target):.3f}\0{int(bool(dual_mono))}"
    short = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{GENERATED_PREFIX}{short}_{stem}"


def _validated_field_name(field_name: str) -> str:
    value = str(field_name or "").strip()
    if not value or any(token in value for token in ("{{", "}}", "\r", "\n")):
        raise ValueError("invalid normalized audio field name")
    return value


def template_block(field_name: str) -> str:
    field = _validated_field_name(field_name)
    return (
        f"{TEMPLATE_START}\n"
        f"{{{{#{field}}}}}<div class=\"bac-normalized-audio\">{{{{{field}}}}}</div>{{{{/{field}}}}}\n"
        f"{TEMPLATE_END}"
    )


def upsert_template_block(html: str, field_name: str) -> str:
    source = str(html or "")
    block = template_block(field_name)
    start = source.find(TEMPLATE_START)
    end = source.find(TEMPLATE_END, start + len(TEMPLATE_START)) if start >= 0 else -1
    if start >= 0 and end >= 0:
        end += len(TEMPLATE_END)
        return source[:start].rstrip() + "\n\n" + block + source[end:]
    return source.rstrip() + "\n\n" + block


def remove_template_block(html: str) -> str:
    source = str(html or "")
    start = source.find(TEMPLATE_START)
    end = source.find(TEMPLATE_END, start + len(TEMPLATE_START)) if start >= 0 else -1
    if start < 0 or end < 0:
        return source
    end += len(TEMPLATE_END)
    return (source[:start].rstrip() + source[end:]).strip()


def _creation_flags() -> int:
    if sys.platform.startswith("win"):
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return 0


def _loudnorm_filter(
    measurement: dict[str, Any],
    target: float,
    dual_mono: bool,
    true_peak_limit: float,
    lra_target: float,
) -> str:
    required = {
        "input_i": float(measurement["input_i"]),
        "input_tp": float(measurement["input_tp"]),
        "input_lra": float(measurement.get("input_lra", 0.0)),
        "input_thresh": float(measurement.get("input_thresh", -70.0)),
        "target_offset": float(measurement.get("target_offset", 0.0)),
    }
    if not all(math.isfinite(value) for value in required.values()):
        raise ValueError("invalid loudness measurement")
    return (
        f"loudnorm=I={float(target):.1f}:TP={float(true_peak_limit):.1f}:LRA={float(lra_target):.0f}:"
        f"measured_I={required['input_i']:.3f}:measured_TP={required['input_tp']:.3f}:"
        f"measured_LRA={required['input_lra']:.3f}:measured_thresh={required['input_thresh']:.3f}:"
        f"offset={required['target_offset']:.3f}:linear=true:dual_mono={'true' if dual_mono else 'false'}"
    )


def _run_render(command: list[str], destination: Path) -> bool:
    completed = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
        shell=False,
        creationflags=_creation_flags(),
    )
    return (
        completed.returncode == 0
        and destination.is_file()
        and 0 < destination.stat().st_size <= MAX_OUTPUT_BYTES
    )


def render_normalized_audio(
    ffmpeg: str,
    source: Path,
    destination_m4a: Path,
    measurement: dict[str, Any],
    target: float,
    dual_mono: bool,
    true_peak_limit: float,
    lra_target: float,
) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination_m4a.parent.mkdir(parents=True, exist_ok=True)
    filter_spec = _loudnorm_filter(
        measurement,
        target,
        dual_mono,
        true_peak_limit,
        lra_target,
    )

    base = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-map_metadata",
        "-1",
        "-af",
        filter_spec,
    ]
    aac_command = base + ["-c:a", "aac", "-b:a", "128k", str(destination_m4a)]
    if _run_render(aac_command, destination_m4a):
        return destination_m4a

    try:
        destination_m4a.unlink(missing_ok=True)
    except Exception:
        pass

    # PCM/WAV is the compatibility fallback if the local FFmpeg build lacks AAC.
    destination_wav = destination_m4a.with_suffix(".wav")
    wav_command = base + ["-c:a", "pcm_s16le", str(destination_wav)]
    if _run_render(wav_command, destination_wav):
        return destination_wav

    try:
        destination_wav.unlink(missing_ok=True)
    except Exception:
        pass
    raise RuntimeError("FFmpeg could not create a normalized audio copy")
'''
(ROOT / 'normalized_audio.py').write_text(NORMALIZED_AUDIO, encoding='utf-8')

# Extend loudnorm parsing with target_offset for a true second pass.
analysis_path = ROOT / 'analysis_engine.py'
analysis = analysis_path.read_text(encoding='utf-8')
old = '''        values = {\n            "input_i": float(raw["input_i"]),\n            "input_tp": float(raw["input_tp"]),\n            "input_lra": float(raw.get("input_lra", 0.0)),\n            "input_thresh": float(raw.get("input_thresh", 0.0)),\n        }\n'''
new = '''        values = {\n            "input_i": float(raw["input_i"]),\n            "input_tp": float(raw["input_tp"]),\n            "input_lra": float(raw.get("input_lra", 0.0)),\n            "input_thresh": float(raw.get("input_thresh", 0.0)),\n            "target_offset": float(raw.get("target_offset", 0.0)),\n        }\n'''
if old not in analysis:
    raise SystemExit('analysis_engine: bloco de parse não encontrado')
analysis_path.write_text(analysis.replace(old, new, 1), encoding='utf-8')

# Add materialization flow to v0.10 extension.
v010_path = ROOT / 'v010.py'
v010 = v010_path.read_text(encoding='utf-8')
v010 = v010.replace('import secrets\nimport sys\nimport threading\n', 'import secrets\nimport shutil\nimport sys\nimport tempfile\nimport threading\n', 1)
old_import = 'from .analysis_engine import ffmpeg_status, find_ffmpeg, install_managed_ffmpeg, measure_with_ffmpeg, resolve_backend\nfrom .i18n import t\n'
new_import = '''from .analysis_engine import ffmpeg_status, find_ffmpeg, install_managed_ffmpeg, measure_with_ffmpeg, resolve_backend\nfrom .i18n import t\nfrom .normalized_audio import (\n    FIELD_BASE_NAME,\n    MAX_OUTPUT_BYTES,\n    extract_sound_filenames,\n    field_value_for_files,\n    file_sha256,\n    is_managed_field_value,\n    normalized_media_stem,\n    remove_template_block,\n    render_normalized_audio,\n    upsert_template_block,\n)\n'''
if old_import not in v010:
    raise SystemExit('v010: imports não encontrados')
v010 = v010.replace(old_import, new_import, 1)
v010 = v010.replace('_INSTALLING = False\n', '_INSTALLING = False\n_MATERIALIZING: set[str] = set()\n', 1)

old_state = '''    state.update({\n        "analysis_backend": configured,\n        "resolved_backend": resolve_backend(configured, bool(ffmpeg["available"])),\n        "ffmpeg": ffmpeg,\n    })\n    profile = core._get_deck_profile(deck_id)\n    if isinstance(profile, dict):\n        state["profile_backend"] = profile.get("analysis_backend", "ffmpeg")\n        state["approximate"] = bool(profile.get("approximate", False))\n    return state\n'''
new_state = '''    with _LOCK:\n        materializing = str(deck_id) in _MATERIALIZING\n    state.update({\n        "analysis_backend": configured,\n        "resolved_backend": resolve_backend(configured, bool(ffmpeg["available"])),\n        "ffmpeg": ffmpeg,\n        "materializing": materializing,\n        "insert_normalized_template": bool(conf.get("normalized_audio_insert_template", True)),\n    })\n    profile = core._get_deck_profile(deck_id)\n    if isinstance(profile, dict):\n        state["profile_backend"] = profile.get("analysis_backend", "ffmpeg")\n        state["approximate"] = bool(profile.get("approximate", False))\n        materialized = profile.get("materialized")\n        if isinstance(materialized, dict):\n            state["materialized_audio_count"] = int(materialized.get("audio_count", 0) or 0)\n            state["materialized_note_count"] = int(materialized.get("note_count", 0) or 0)\n            state["materialized_at"] = materialized.get("created_at")\n    return state\n'''
if old_state not in v010:
    raise SystemExit('v010: bloco state não encontrado')
v010 = v010.replace(old_state, new_state, 1)

marker = '\ndef _install_ffmpeg() -> None:\n'
if marker not in v010:
    raise SystemExit('v010: marcador install não encontrado')
materialization = r'''

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
'''
v010 = v010.replace(marker, materialization + marker, 1)

message_marker = '''    if message == "ferreis_audio:v010:ffmpeg:install":\n        _install_ffmpeg(); return (True, None)\n'''
message_new = '''    if message == "ferreis_audio:v010:ffmpeg:install":\n        _install_ffmpeg(); return (True, None)\n    if message == "ferreis_audio:v010:materialize":\n        _start_materialization(context); return (True, None)\n    if message.startswith("ferreis_audio:v010:materialize:insert:"):\n        value = message.rsplit(":", 1)[-1] == "1"\n        _core()._save_setting("normalized_audio_insert_template", value)\n        current = _current_deck(context)\n        if current: _push_state(_state(*current))\n        return (True, None)\n'''
if message_marker not in v010:
    raise SystemExit('v010: handler ffmpeg não encontrado')
v010 = v010.replace(message_marker, message_new, 1)
v010_path.write_text(v010, encoding='utf-8')

# Extend v0.10 UI with materialization controls.
js_path = ROOT / 'web' / 'audio_controller_v010.js'
js = js_path.read_text(encoding='utf-8')
old_engine_insert = '''      block.insertBefore(engine, actions);\n\n      const oldAnalyze = this.root.querySelector(".fac-analyze-deck");\n'''
new_engine_insert = '''      block.insertBefore(engine, actions);\n\n      const materialize = document.createElement("div");\n      materialize.className = "fac-materialize-audio";\n      materialize.innerHTML = `\n        <label class="fac-check-row fac-materialize-template-wrap" title="${t("insert_normalized_template_hint")}">\n          <input class="fac-materialize-template" type="checkbox">\n          <span>${t("insert_normalized_template")}</span>\n        </label>\n        <button class="fac-action fac-materialize-normalized" type="button">${t("materialize_audio")}</button>\n        <div class="fac-materialize-note"></div>\n      `;\n      actions.insertAdjacentElement("afterend", materialize);\n\n      const oldAnalyze = this.root.querySelector(".fac-analyze-deck");\n'''
if old_engine_insert not in js:
    raise SystemExit('js: inserção do engine não encontrada')
js = js.replace(old_engine_insert, new_engine_insert, 1)

events_marker = '''      this.root.querySelector(".fac-install-ffmpeg").addEventListener("click", () => {\n        pycmd("ferreis_audio:v010:ffmpeg:install");\n      });\n\n      const base = window.FerreisAnkiAudio;\n'''
events_new = '''      this.root.querySelector(".fac-install-ffmpeg").addEventListener("click", () => {\n        pycmd("ferreis_audio:v010:ffmpeg:install");\n      });\n      this.root.querySelector(".fac-materialize-normalized").addEventListener("click", () => {\n        this.state.materializing = true;\n        this.updateState(this.state);\n        pycmd("ferreis_audio:v010:materialize");\n      });\n      this.root.querySelector(".fac-materialize-template").addEventListener("change", (event) => {\n        const enabled = Boolean(event.target.checked);\n        this.state.insert_normalized_template = enabled;\n        pycmd(`ferreis_audio:v010:materialize:insert:${enabled ? 1 : 0}`);\n      });\n\n      const base = window.FerreisAnkiAudio;\n'''
if events_marker not in js:
    raise SystemExit('js: eventos ffmpeg não encontrados')
js = js.replace(events_marker, events_new, 1)

update_marker = '''      const note = this.root.querySelector(".fac-engine-note");\n      if (!select || !status || !install || !note) return;\n\n      select.value = this.state.analysis_backend || "auto";\n'''
update_new = '''      const note = this.root.querySelector(".fac-engine-note");\n      const materialize = this.root.querySelector(".fac-materialize-normalized");\n      const materializeTemplate = this.root.querySelector(".fac-materialize-template");\n      const materializeNote = this.root.querySelector(".fac-materialize-note");\n      if (!select || !status || !install || !note || !materialize || !materializeTemplate || !materializeNote) return;\n\n      select.value = this.state.analysis_backend || "auto";\n'''
if update_marker not in js:
    raise SystemExit('js: updateState vars não encontradas')
js = js.replace(update_marker, update_new, 1)

end_update = '''      note.textContent = resolved === "webaudio" ? t("webaudio_hint") : t("ffmpeg_installer_hint");\n    },\n'''
end_new = '''      note.textContent = resolved === "webaudio" ? t("webaudio_hint") : t("ffmpeg_installer_hint");\n\n      materializeTemplate.checked = this.state.insert_normalized_template !== false;\n      materializeTemplate.disabled = Boolean(this.state.materializing || this.state.analyzing);\n      materialize.disabled = Boolean(\n        this.state.materializing ||\n        this.state.analyzing ||\n        !this.state.exists ||\n        this.state.stale ||\n        !ff.available\n      );\n      materialize.textContent = this.state.materializing ? t("materializing_audio") : t("materialize_audio");\n      if (!ff.available) {\n        materializeNote.textContent = t("materialize_requires_ffmpeg");\n      } else if (this.state.stale) {\n        materializeNote.textContent = t("materialize_profile_stale");\n      } else if (Number(this.state.materialized_audio_count || 0) > 0) {\n        materializeNote.textContent = t("materialized_summary", {\n          count: Number(this.state.materialized_audio_count || 0),\n          notes: Number(this.state.materialized_note_count || 0),\n        });\n      } else {\n        materializeNote.textContent = t("materialize_hint");\n      }\n    },\n'''
if end_update not in js:
    raise SystemExit('js: final updateState não encontrado')
js_path.write_text(js.replace(end_update, end_new, 1), encoding='utf-8')

# Add translations.
i18n_path = ROOT / 'i18n.py'
i18n = i18n_path.read_text(encoding='utf-8')
english_anchor = '        "preparing_analysis": "Preparing analysis...",\n'
english_add = '''        "preparing_analysis": "Preparing analysis...",\n        "materialize_audio": "Create normalized copies",\n        "materializing_audio": "Creating normalized copies...",\n        "materialize_hint": "Creates a second normalized audio file and links it to a dedicated note field. Originals are preserved.",\n        "insert_normalized_template": "Insert normalized audio on card back",\n        "insert_normalized_template_hint": "Adds the dedicated normalized-audio field to the back template of affected card types.",\n        "materialize_requires_ffmpeg": "FFmpeg is required to create normalized audio files.",\n        "materialize_profile_required": "Analyze the deck before creating normalized copies.",\n        "materialize_profile_stale": "Reanalyze the deck before creating copies because the normalization target changed.",\n        "materialize_no_linked_audio": "No analyzed audio could be linked to note fields in this deck.",\n        "materialize_progress": "Creating normalized audio {processed}/{total}...",\n        "materialize_done": "Created {count} normalized audio file(s) and linked {notes} note(s).",\n        "materialize_failed": "Unable to create normalized audio copies.",\n        "materialized_summary": "{count} normalized file(s) linked to {notes} note(s)",\n'''
if english_anchor not in i18n:
    raise SystemExit('i18n: anchor en não encontrado')
i18n = i18n.replace(english_anchor, english_add, 1)
portuguese_anchor = '        "preparing_analysis": "Preparando análise...",\n'
portuguese_add = '''        "preparing_analysis": "Preparando análise...",\n        "materialize_audio": "Criar cópias normalizadas",\n        "materializing_audio": "Criando cópias normalizadas...",\n        "materialize_hint": "Cria um segundo arquivo de áudio já normalizado e vincula a um campo próprio da nota. Os originais são preservados.",\n        "insert_normalized_template": "Inserir áudio normalizado no verso do card",\n        "insert_normalized_template_hint": "Adiciona o campo de áudio normalizado ao template do verso dos tipos de card afetados.",\n        "materialize_requires_ffmpeg": "O FFmpeg é necessário para criar arquivos de áudio normalizados.",\n        "materialize_profile_required": "Analise o deck antes de criar as cópias normalizadas.",\n        "materialize_profile_stale": "Reanalise o deck antes de criar cópias porque o alvo de normalização mudou.",\n        "materialize_no_linked_audio": "Nenhum áudio analisado pôde ser vinculado aos campos das notas deste deck.",\n        "materialize_progress": "Criando áudio normalizado {processed}/{total}...",\n        "materialize_done": "Foram criados {count} áudio(s) normalizado(s) e vinculadas {notes} nota(s).",\n        "materialize_failed": "Não foi possível criar as cópias de áudio normalizadas.",\n        "materialized_summary": "{count} arquivo(s) normalizado(s) vinculado(s) a {notes} nota(s)",\n'''
if portuguese_anchor not in i18n:
    raise SystemExit('i18n: anchor pt não encontrado')
i18n = i18n.replace(portuguese_anchor, portuguese_add, 1)
keys_anchor = '    "preparing_analysis",\n'
keys_add = '''    "preparing_analysis",\n    "materialize_audio",\n    "materializing_audio",\n    "materialize_hint",\n    "insert_normalized_template",\n    "insert_normalized_template_hint",\n    "materialize_requires_ffmpeg",\n    "materialize_profile_required",\n    "materialize_profile_stale",\n    "materialize_no_linked_audio",\n    "materialize_progress",\n    "materialize_done",\n    "materialize_failed",\n    "materialized_summary",\n'''
if keys_anchor not in i18n:
    raise SystemExit('i18n: WEB keys anchor não encontrado')
i18n_path.write_text(i18n.replace(keys_anchor, keys_add, 1), encoding='utf-8')

# Config defaults and schema.
config_path = ROOT / 'config.json'
config = json.loads(config_path.read_text(encoding='utf-8'))
config['normalized_audio_insert_template'] = True
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

schema_path = ROOT / 'config.schema.json'
schema = json.loads(schema_path.read_text(encoding='utf-8'))
schema['properties']['normalized_audio_insert_template'] = {
    'type': 'boolean',
    'default': True,
    'title': 'Insert normalized audio on card back / Inserir áudio normalizado no verso do card',
    'description': 'When materializing normalized copies, add the dedicated BAC normalized-audio field to affected card back templates. / Ao materializar cópias normalizadas, adiciona o campo dedicado de áudio normalizado do BAC aos templates do verso dos cards afetados.'
}
schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Build package must include the new module.
build_path = ROOT / 'build.py'
build = build_path.read_text(encoding='utf-8')
anchor = '    "analysis_engine.py",\n'
if anchor not in build:
    raise SystemExit('build: anchor não encontrado')
build_path.write_text(build.replace(anchor, anchor + '    "normalized_audio.py",\n', 1), encoding='utf-8')

# Documentation.
readme_path = ROOT / 'README.md'
readme = readme_path.read_text(encoding='utf-8')
section = r'''

## Materialized normalized audio / Áudio normalizado materializado

After a deck has been analyzed, **Create normalized copies / Criar cópias normalizadas** can render a second, already-normalized audio file for each analyzed source. This operation requires FFmpeg because it writes real audio files; the built-in WebAudio analyzer remains available for analysis only.

The original media is never overwritten. Generated files use a deterministic `bac_norm_...` name and are imported through Anki's media manager. The add-on creates a dedicated **BAC Áudio Normalizado** note field (or a numbered alternative if that name is already used by unrelated content), writes native `[sound:...]` references into it, and can automatically add that field to the back template of the affected card types.

Depois que o deck for analisado, **Criar cópias normalizadas** pode gerar um segundo arquivo de áudio já normalizado para cada áudio analisado. Essa operação exige FFmpeg porque grava arquivos de áudio reais; o analisador WebAudio interno continua disponível para análise sem FFmpeg.

A mídia original nunca é sobrescrita. Os arquivos gerados usam nomes determinísticos `bac_norm_...` e são importados pelo gerenciador de mídia do Anki. O add-on cria um campo dedicado **BAC Áudio Normalizado** na nota (ou uma alternativa numerada caso esse nome já contenha dados não relacionados), grava referências nativas `[sound:...]` nele e pode inserir automaticamente esse campo no template do verso dos tipos de card afetados.
'''
if '## Materialized normalized audio / Áudio normalizado materializado' not in readme:
    readme_path.write_text(readme.rstrip() + section + '\n', encoding='utf-8')

# Unit tests for deterministic/safe helper behavior.
normalized_test = r'''from __future__ import annotations

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
'''
(ROOT / 'tests' / 'test_normalized_audio.py').write_text(normalized_test, encoding='utf-8')

# Extend analysis parser test with target offset.
test_analysis_path = ROOT / 'tests' / 'test_analysis_engine.py'
test_analysis = test_analysis_path.read_text(encoding='utf-8')
test_analysis = test_analysis.replace('  \\"input_thresh\\" : \\"-33.00\\"\\n}', '  \\"input_thresh\\" : \\"-33.00\\",\\n  \\"target_offset\\" : \\"-0.15\\"\\n}', 1)
needle = '        self.assertAlmostEqual(parsed["input_tp"], -1.20)\n'
if needle not in test_analysis:
    raise SystemExit('test_analysis: assertion anchor não encontrado')
test_analysis = test_analysis.replace(needle, needle + '        self.assertAlmostEqual(parsed["target_offset"], -0.15)\n', 1)
test_analysis_path.write_text(test_analysis, encoding='utf-8')

# Extend Playwright i18n and UI behavior test.
pw_path = ROOT / 'tests' / 'test_audio_controller_playwright.py'
pw = pw_path.read_text(encoding='utf-8')
i18n_anchor = '    "preparing_analysis": "Preparing analysis...",\n'
i18n_add = '''    "preparing_analysis": "Preparing analysis...",\n    "materialize_audio": "Create normalized copies",\n    "materializing_audio": "Creating normalized copies...",\n    "materialize_hint": "Create files",\n    "insert_normalized_template": "Insert normalized audio on card back",\n    "insert_normalized_template_hint": "Insert field",\n    "materialize_requires_ffmpeg": "FFmpeg required",\n    "materialize_profile_stale": "Reanalyze first",\n    "materialized_summary": "{count} normalized file(s) linked to {notes} note(s)",\n'''
if i18n_anchor not in pw:
    raise SystemExit('playwright: i18n anchor não encontrado')
pw = pw.replace(i18n_anchor, i18n_add, 1)

insert_test = r'''
    def test_materialize_controls_require_profile_and_ffmpeg(self) -> None:
        config = base_config()
        page = self.page_with_config(config)
        try:
            button = page.locator(".fac-materialize-normalized")
            checkbox = page.locator(".fac-materialize-template")
            self.assertTrue(button.is_disabled())
            self.assertTrue(checkbox.is_checked())
            self.assertEqual(page.locator(".fac-materialize-note").inner_text(), "FFmpeg required")

            page.evaluate(
                """window.BACV010.updateState({
                    exists: true,
                    stale: false,
                    ffmpeg: { available: true, installing: false, installer_available: true },
                    insert_normalized_template: true
                })"""
            )
            self.assertFalse(button.is_disabled())
            page.evaluate("window.__pycmdMessages=[]")
            button.click()
            self.assertIn("ferreis_audio:v010:materialize", page.evaluate("window.__pycmdMessages"))

            page.evaluate("window.BACV010.updateState({ materializing: false, analyzing: false })")
            checkbox.uncheck()
            self.assertIn(
                "ferreis_audio:v010:materialize:insert:0",
                page.evaluate("window.__pycmdMessages"),
            )
        finally:
            page.close()

'''
final_marker = '\n\n\nif __name__ == "__main__":\n'
if final_marker not in pw:
    raise SystemExit('playwright: final marker não encontrado')
pw_path.write_text(pw.replace(final_marker, '\n' + insert_test + final_marker, 1), encoding='utf-8')

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from anki.sound import SoundOrVideoTag
from aqt import gui_hooks, mw
from aqt.sound import av_player
from aqt.webview import WebContent

from .i18n import t
from . import v010

PLAYBACK_MODES = {"profile", "realtime", "created"}
OVERVOLUME_FILTER_NAME = "@ferreis_overvolume"
OVERVOLUME_DEFAULT_GAIN_DB = 6.0
OVERVOLUME_MAX_GAIN_DB = 12.0
OVERVOLUME_LIMIT_DB = -1.5
_NATIVE_INTEGRATION_REPAIRED: set[int] = set()


def _core():
    return sys.modules[__package__]


def _conf() -> dict[str, Any]:
    return mw.addonManager.getConfig(__package__) or {}


def _playback_mode(conf: dict[str, Any] | None = None) -> str:
    current = conf if conf is not None else _conf()
    configured = str(current.get("playback_mode", "")).strip().lower()
    if configured in PLAYBACK_MODES:
        return configured
    if bool(current.get("deck_profile_enabled", False)):
        return "profile"
    if bool(current.get("normalize", True)):
        return "realtime"
    return "created"


def _save_playback_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in PLAYBACK_MODES:
        normalized = "realtime"
    conf = _conf()
    conf["playback_mode"] = normalized
    conf["normalize"] = normalized == "realtime"
    conf["deck_profile_enabled"] = normalized == "profile"
    mw.addonManager.writeConfig(__package__, conf)
    return normalized


def _overvolume_gain_db(conf: dict[str, Any] | None = None) -> float:
    current = conf if conf is not None else _conf()
    try:
        value = float(current.get("overvolume_gain_db", OVERVOLUME_DEFAULT_GAIN_DB))
    except (TypeError, ValueError):
        value = OVERVOLUME_DEFAULT_GAIN_DB
    return max(0.0, min(OVERVOLUME_MAX_GAIN_DB, value))


def _overvolume_filter(conf: dict[str, Any]) -> str:
    gain_db = _overvolume_gain_db(conf)
    limit = 10.0 ** (OVERVOLUME_LIMIT_DB / 20.0)
    return (
        f"{OVERVOLUME_FILTER_NAME}:lavfi=["
        f"volume={gain_db:.3f}dB,"
        f"alimiter=limit={limit:.6f}:level=false"
        f"]"
    )


def _apply_overvolume(player: Any, conf: dict[str, Any]) -> tuple[bool, float]:
    core = _core()
    core._remove_filter(player, OVERVOLUME_FILTER_NAME)
    gain_db = _overvolume_gain_db(conf)
    if not bool(conf.get("overvolume_enabled", False)) or gain_db <= 0.0:
        return False, gain_db
    try:
        player.command("af", "add", _overvolume_filter(conf))
        return True, gain_db
    except Exception as exc:
        print("[Balanced Audio Controller] OverVolume unavailable:", exc)
        return False, gain_db


def _local(lang: str, key: str, **values: Any) -> str:
    messages = {
        "en": {
            "playback_mode": "Playback mode",
            "mode_profile": "Analyzed profile",
            "mode_realtime": "Real time",
            "mode_created": "Created audio",
            "mode_hint": "Choose exactly one normalization source. Real time works immediately; Analyzed profile needs deck analysis; Created audio needs analysis followed by generated copies.",
            "mode_profile_hint": "Uses the gain measured for each file when the deck was analyzed. If the profile is missing or outdated, no fallback normalization is applied.",
            "mode_realtime_hint": "Normalizes the original audio while it plays using the native MPV/FFmpeg loudnorm filter.",
            "mode_created_hint": "Keeps the original audio unchanged and adds a second native player for the physical normalized copy stored in Anki. Both remain available even if the add-on is disabled.",
            "overvolume": "OverVolume",
            "overvolume_hint": "Adds extra playback gain after the selected normalization mode. Use it when audio is still too quiet at 100% volume. It never changes the media file.",
            "overvolume_gain": "OverVolume boost",
            "overvolume_gain_hint": "Extra gain from 0 to +12 dB. A limiter is applied afterward to reduce digital clipping; high values can make noise or existing distortion more audible.",
            "language_hint": "Automatic follows the computer language; unsupported languages use English.",
            "analysis_hint": "Automatic prefers FFmpeg and falls back to the built-in analyzer. FFmpeg is more accurate; the built-in analyzer needs no external executable.",
            "analyze_hint": "Measures the current deck and stores a per-file normalization profile. Analysis does not change the selected playback mode.",
            "clear_hint": "Deletes only the analyzed profile for the current deck. Original media files are not removed.",
            "tab_playback": "Playback",
            "tab_analysis": "Analysis",
            "tab_created": "Created audio",
            "analysis_flow_hint": "Analysis prepares the data used by Analyzed profile and by normalized-copy generation. It is independent from Real-time playback.",
            "created_flow_hint": "Recommended order: 1) Analyze deck, 2) Create normalized copies, 3) select Created audio. Creating copies never replaces or deletes the original audio. It stores physical bac_norm_* media in Anki, writes native [sound:...] references to a dedicated field, and inserts that field into the card template as an additional player.",
            "prepare_optional_hint": "Optional: prepare or repair the normalized-audio field and card template without generating new physical audio files.",
            "busy_materializing": "Wait for normalized-audio creation to finish before analyzing or clearing the profile.",
            "busy_analyzing": "Wait for deck analysis to finish before changing generated-audio data.",
            "status_profile_missing": "Analyzed-profile mode · no valid gain for this audio",
            "status_profile_stale": "Analyzed-profile mode · profile is outdated; reanalyze the deck",
            "status_created_missing": "Created-audio mode · native normalized audio is not attached to this card; original audio is playing",
            "status_materialized_audio": "Already-normalized audio copy · normalization bypassed",
            "status_overvolume": "OverVolume {gain:+.1f} dB",
        },
        "pt-BR": {
            "playback_mode": "Modo de reprodução",
            "mode_profile": "Perfil analisado",
            "mode_realtime": "Em tempo real",
            "mode_created": "Áudios criados",
            "mode_hint": "Escolha exatamente uma fonte de normalização. Em tempo real funciona imediatamente; Perfil analisado exige análise; Áudios criados exige análise seguida da geração das cópias.",
            "mode_profile_hint": "Usa o ganho medido para cada arquivo quando o deck foi analisado. Se o perfil estiver ausente ou desatualizado, não aplica normalização alternativa.",
            "mode_realtime_hint": "Normaliza o áudio original enquanto ele toca usando o filtro loudnorm do MPV/FFmpeg nativo.",
            "mode_created_hint": "Mantém o áudio original intacto e adiciona um segundo player nativo para a cópia normalizada física gravada no Anki. Os dois continuam disponíveis mesmo se o add-on for desativado.",
            "overvolume": "OverVolume",
            "overvolume_hint": "Adiciona ganho extra na reprodução depois do modo de normalização escolhido. Use quando o áudio continuar baixo mesmo em 100%. O arquivo de mídia nunca é alterado.",
            "overvolume_gain": "Ganho do OverVolume",
            "overvolume_gain_hint": "Ganho extra de 0 a +12 dB. Um limitador é aplicado depois para reduzir clipping digital; valores altos podem deixar ruído ou distorções existentes mais perceptíveis.",
            "language_hint": "Automático segue o idioma do computador; idiomas não suportados usam inglês.",
            "analysis_hint": "Automático prefere FFmpeg e usa o analisador interno como fallback. FFmpeg é mais preciso; o analisador interno não exige executável externo.",
            "analyze_hint": "Mede os áudios do deck atual e salva um perfil de normalização por arquivo. A análise não altera o modo de reprodução selecionado.",
            "clear_hint": "Exclui somente o perfil analisado do deck atual. Os arquivos de mídia originais não são removidos.",
            "tab_playback": "Reprodução",
            "tab_analysis": "Análise",
            "tab_created": "Áudios criados",
            "analysis_flow_hint": "A análise prepara os dados usados pelo Perfil analisado e pela geração de cópias normalizadas. Ela é independente da reprodução Em tempo real.",
            "created_flow_hint": "Ordem recomendada: 1) Analisar deck, 2) Criar cópias normalizadas, 3) selecionar Áudios criados. Criar cópias nunca substitui nem apaga o áudio original. O add-on grava a mídia física bac_norm_* no Anki, escreve [sound:...] em um campo dedicado e insere esse campo no template do card como um player adicional.",
            "prepare_optional_hint": "Opcional: prepare ou repare o campo de áudio normalizado e o template do card sem gerar novos arquivos físicos de áudio.",
            "busy_materializing": "Aguarde a criação dos áudios normalizados terminar antes de analisar ou limpar o perfil.",
            "busy_analyzing": "Aguarde a análise do deck terminar antes de alterar os dados de áudio gerado.",
            "status_profile_missing": "Modo perfil analisado · não há ganho válido para este áudio",
            "status_profile_stale": "Modo perfil analisado · perfil desatualizado; reanalise o deck",
            "status_created_missing": "Modo áudios criados · o áudio normalizado nativo não está vinculado a este card; o original está tocando",
            "status_materialized_audio": "Cópia de áudio já normalizada · normalização ignorada",
            "status_overvolume": "OverVolume {gain:+.1f} dB",
        },
    }
    language = "pt-BR" if lang == "pt-BR" else "en"
    text = messages[language].get(key, key)
    return text.format(**values)


def _safe_generated_filename(filename: Any) -> str | None:
    value = str(filename or "").strip()
    if not value or "\x00" in value or "/" in value or "\\" in value:
        return None
    core = _core()
    if not core._is_materialized_audio(value):
        return None
    extension = value.rsplit(".", 1)[-1].lower() if "." in value else ""
    if extension not in core.AUDIO_EXTENSIONS:
        return None
    return value


def _available_materialized_mapping(deck_id: int | None) -> dict[str, str]:
    if deck_id is None:
        return {}
    core = _core()
    profile = core._get_deck_profile(deck_id)
    if not isinstance(profile, dict) or not core._profile_matches_config(profile, _conf()):
        return {}
    materialized = profile.get("materialized")
    if not isinstance(materialized, dict):
        return {}
    files = materialized.get("files")
    if not isinstance(files, dict):
        return {}

    try:
        media_root = Path(mw.col.media.dir()).resolve(strict=True)
    except (OSError, RuntimeError, ValueError, AttributeError):
        return {}

    result: dict[str, str] = {}
    for source, raw_target in files.items():
        source_name = str(source or "")
        target = _safe_generated_filename(raw_target)
        if not source_name or "\x00" in source_name or target is None:
            continue
        try:
            candidate = (media_root / target).resolve(strict=True)
            candidate.relative_to(media_root)
        except (OSError, RuntimeError, ValueError):
            continue
        if candidate.is_file():
            result[source_name] = target
    return result


def _materialized_native_ready(deck_id: int, mapping: dict[str, str] | None = None) -> bool:
    core = _core()
    profile = core._get_deck_profile(deck_id)
    if not isinstance(profile, dict):
        return False
    materialized = profile.get("materialized")
    setup = profile.get("normalized_field_setup")
    if not isinstance(materialized, dict) or not isinstance(setup, dict):
        return False
    if not bool(materialized.get("insert_template")) or not bool(setup.get("insert_template")):
        return False
    if int(setup.get("template_count", 0) or 0) <= 0:
        return False
    current_mapping = mapping if mapping is not None else _available_materialized_mapping(deck_id)
    return bool(current_mapping)


def _ensure_materialized_card_integration(context: object | None) -> bool:
    current = v010._current_deck(context)
    if not current:
        return False
    deck_id, deck_name = current
    mapping = _available_materialized_mapping(deck_id)
    if not mapping:
        return False
    profile = _core()._get_deck_profile(deck_id)
    if not isinstance(profile, dict):
        return False

    conf = _conf()
    if not bool(conf.get("normalized_audio_insert_template", True)):
        conf["normalized_audio_insert_template"] = True
        mw.addonManager.writeConfig(__package__, conf)

    plan = v010._collect_materialization_plan(deck_id, profile)
    if not plan.get("notes"):
        return False
    v010._apply_materialization(
        deck_id,
        deck_name,
        plan,
        mapping,
        True,
        profile,
    )
    _NATIVE_INTEGRATION_REPAIRED.add(deck_id)
    return True


def _selected_filename(filename: str, mode: str, mapping: dict[str, str]) -> str | None:
    # Áudios criados são um segundo player nativo do card. Nenhum modo pode
    # substituir o original ou esconder a cópia que já está no HTML do Anki.
    del mode, mapping
    return filename


def _copy_sound_tag(tag: SoundOrVideoTag, filename: str) -> SoundOrVideoTag:
    try:
        return replace(tag, filename=filename)
    except Exception:
        try:
            return type(tag)(filename=filename)
        except Exception:
            return SoundOrVideoTag(filename=filename)


def _current_playback_deck_id() -> int | None:
    core = _core()
    context = core._active_card_context()
    if not core._is_supported_card_context(context):
        return None
    card = core._card_from_context(context)
    if card is None:
        card = core._current_reviewer_card()
    return core._card_deck_id(card) if card else None


def _rewrite_playback_tags(tags: list[Any], deck_id: int | None) -> list[Any]:
    # O HTML/template do card é a fonte de verdade. Se ele contém o player do
    # original e o player da cópia bac_norm_*, ambos precisam chegar intactos
    # ao player nativo. O add-on não substitui, remove ou injeta tags de áudio.
    del deck_id
    return list(tags)


_ORIGINAL_PLAY_TAGS = getattr(
    av_player, "_bac_v011_original_play_tags", av_player.play_tags
)


def _play_tags_without_mutating_render_cache(tags: list[Any]) -> None:
    # Card.question_av_tags()/answer_av_tags() retornam a lista mantida dentro do
    # render_output cacheado pelo Anki. Nunca alteramos essa lista nem sua ordem,
    # preservando os índices play:q:N/play:a:N e os dois players nativos.
    rewritten = _rewrite_playback_tags(list(tags), _current_playback_deck_id())
    _ORIGINAL_PLAY_TAGS(rewritten)


def _profile_entry(filename: str | None, conf: dict[str, Any], deck_id: int | None):
    core = _core()
    if not filename:
        return None, None
    if deck_id is None:
        deck_id = core._current_audio_deck_id()
    if deck_id is None:
        deck_id = core._current_reviewer_deck_id()
    profile = core._get_deck_profile(deck_id)
    if not isinstance(profile, dict):
        return None, None
    if not core._profile_matches_config(profile, conf):
        return profile, None
    files = profile.get("files")
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
    core = _core()
    conf = _conf()
    lang = core._language(conf)
    player = player or av_player.current_player
    if not core._is_mpv_player(player):
        return False, t(lang, "status_native_no_mpv")

    speed = max(0.25, min(2.0, float(conf.get("speed", 1.0))))
    volume = max(0.0, min(1.0, float(conf.get("volume", 1.0))))
    target = max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0))))
    try:
        player.set_property("speed", speed)
        player.set_property("volume", volume * 100.0)
    except Exception as exc:
        print("[Balanced Audio Controller] unable to set MPV speed/volume:", exc)
        return False, t(lang, "status_mpv_control_failed")

    if not update_filters:
        return True, ""
    if filename is None:
        filename = core._current_audio_filename()

    core._remove_filter(player, core.NORMALIZE_FILTER_NAME)
    core._remove_filter(player, core.DECK_GAIN_FILTER_NAME)
    core._remove_filter(player, OVERVOLUME_FILTER_NAME)

    def finish(status: str) -> tuple[bool, str]:
        applied, gain_db = _apply_overvolume(player, conf)
        if applied:
            status = f"{status} · {_local(lang, 'status_overvolume', gain=gain_db)}"
        return True, status

    if core._is_materialized_audio(filename):
        return finish(_local(lang, "status_materialized_audio"))

    mode = _playback_mode(conf)
    if mode == "profile":
        profile, entry = _profile_entry(filename, conf, deck_id)
        if entry is not None:
            try:
                gain_db = float(entry.get("gain_db", 0.0))
                player.command("af", "add", core._deck_gain_filter(gain_db))
                return finish(t(lang, "status_deck_profile_gain", gain=gain_db))
            except Exception as exc:
                print("[Balanced Audio Controller] unable to apply deck gain:", exc)
        if profile and not core._profile_matches_config(profile, conf):
            return finish(_local(lang, "status_profile_stale"))
        return finish(_local(lang, "status_profile_missing"))

    if mode == "realtime":
        try:
            player.command("af", "add", core._normalizer_filter(conf))
            return finish(t(lang, "status_realtime_normalization", prefix="", target=target))
        except Exception as exc:
            print("[Balanced Audio Controller] loudnorm unavailable:", exc)
            return finish(t(lang, "status_loudnorm_unavailable", prefix=""))

    return finish(_local(lang, "status_created_missing"))


_ORIGINAL_STATE = v010._state
_ORIGINAL_START_ANALYSIS = getattr(
    v010, "_bac_v011_original_start_analysis", v010._start_analysis
)
_ORIGINAL_CLEAR_PROFILE = getattr(
    v010, "_bac_v011_original_clear_profile", v010._clear_current_deck_profile
)


def _state(deck_id: int, deck_name: str | None = None) -> dict[str, Any]:
    state = _ORIGINAL_STATE(deck_id, deck_name)
    conf = _conf()
    mode = _playback_mode(conf)
    mapping = _available_materialized_mapping(deck_id)
    state["playback_mode"] = mode
    state["enabled"] = mode == "profile"
    state["overvolume_enabled"] = bool(conf.get("overvolume_enabled", False))
    state["overvolume_gain_db"] = _overvolume_gain_db(conf)
    state["created_ready"] = _materialized_native_ready(deck_id, mapping)
    return state


def _deck_is_materializing(deck_id: int, deck_name: str | None = None) -> bool:
    return bool(_ORIGINAL_STATE(deck_id, deck_name).get("materializing"))


def _push_workflow_notice(context: object | None, key: str) -> None:
    current = v010._current_deck(context)
    if not current:
        return
    state = _state(*current)
    state["message"] = _local(_core()._language(_conf()), key)
    v010._push_state(state)


def _start_analysis_coordinated(context) -> None:
    current = v010._current_deck(context)
    if current and _deck_is_materializing(*current):
        _push_workflow_notice(context, "busy_materializing")
        return
    _ORIGINAL_START_ANALYSIS(context)


def _clear_profile_coordinated(context) -> None:
    current = v010._current_deck(context)
    if current:
        deck_id, deck_name = current
        if _core()._analysis_is_running(deck_id):
            _push_workflow_notice(context, "busy_analyzing")
            return
        if _deck_is_materializing(deck_id, deck_name):
            _push_workflow_notice(context, "busy_materializing")
            return
    _ORIGINAL_CLEAR_PROFILE(context)


def _description_label(text: str, parent):
    from aqt.qt import QLabel

    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setStyleSheet("color: palette(mid); font-size: 11px;")
    return label


def _open_settings_dialog(context: object | None = None) -> None:
    from aqt.qt import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QRadioButton,
        QTabWidget,
        QVBoxLayout,
        QWidget,
        qconnect,
    )

    lang = _core()._language(_conf())
    conf = _conf()
    core = _core()
    action_context = context if core._is_supported_card_context(context) else v010._active_reviewer()
    current = v010._current_deck(action_context) if action_context else None

    dialog = QDialog(mw)
    dialog.setWindowTitle(t(lang, "settings_title"))
    dialog.setMinimumWidth(620)
    dialog.setMinimumHeight(520)
    layout = QVBoxLayout(dialog)

    deck_group = QGroupBox(t(lang, "settings_current_deck"), dialog)
    deck_layout = QVBoxLayout(deck_group)
    if current:
        deck_label = QLabel(current[1], deck_group)
        deck_label.setWordWrap(True)
        deck_label.setStyleSheet("font-weight: 600;")
        deck_layout.addWidget(deck_label)
    else:
        deck_layout.addWidget(_description_label(t(lang, "settings_no_active_deck"), deck_group))
    layout.addWidget(deck_group)

    tabs = QTabWidget(dialog)
    playback_tab = QWidget(tabs)
    analysis_tab = QWidget(tabs)
    created_tab = QWidget(tabs)
    tabs.addTab(playback_tab, _local(lang, "tab_playback"))
    tabs.addTab(analysis_tab, _local(lang, "tab_analysis"))
    tabs.addTab(created_tab, _local(lang, "tab_created"))
    layout.addWidget(tabs, 1)

    def add_row(form: QFormLayout, parent: QWidget, label_text: str, control, description: str) -> None:
        wrapper = QWidget(parent)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(3)
        wrapper_layout.addWidget(control)
        wrapper_layout.addWidget(_description_label(description, wrapper))
        form.addRow(label_text, wrapper)

    playback_layout = QVBoxLayout(playback_tab)
    playback_form = QFormLayout()
    language = QComboBox(playback_tab)
    language.addItem("Automático / Automatic", "auto")
    language.addItem("English", "en")
    language.addItem("Português (Brasil)", "pt-BR")
    language_index = language.findData(str(conf.get("language", "auto")))
    language.setCurrentIndex(language_index if language_index >= 0 else 0)
    add_row(playback_form, playback_tab, t(lang, "settings_language"), language, _local(lang, "language_hint"))

    mode_box = QWidget(playback_tab)
    mode_layout = QHBoxLayout(mode_box)
    mode_layout.setContentsMargins(0, 0, 0, 0)
    mode_buttons: dict[str, QRadioButton] = {}
    for mode, key in (
        ("profile", "mode_profile"),
        ("realtime", "mode_realtime"),
        ("created", "mode_created"),
    ):
        button = QRadioButton(_local(lang, key), mode_box)
        mode_buttons[mode] = button
        mode_layout.addWidget(button)
    mode_buttons[_playback_mode(conf)].setChecked(True)
    add_row(playback_form, playback_tab, _local(lang, "playback_mode"), mode_box, _local(lang, "mode_hint"))

    overvolume = QCheckBox(_local(lang, "overvolume"), playback_tab)
    overvolume.setChecked(bool(conf.get("overvolume_enabled", False)))
    add_row(playback_form, playback_tab, "", overvolume, _local(lang, "overvolume_hint"))

    overvolume_gain = QDoubleSpinBox(playback_tab)
    overvolume_gain.setRange(0.0, OVERVOLUME_MAX_GAIN_DB)
    overvolume_gain.setDecimals(1)
    overvolume_gain.setSingleStep(0.5)
    overvolume_gain.setSuffix(" dB")
    overvolume_gain.setValue(_overvolume_gain_db(conf))
    overvolume_gain.setEnabled(overvolume.isChecked())
    add_row(
        playback_form,
        playback_tab,
        _local(lang, "overvolume_gain"),
        overvolume_gain,
        _local(lang, "overvolume_gain_hint"),
    )
    qconnect(overvolume.toggled, lambda checked: overvolume_gain.setEnabled(bool(checked)))
    playback_layout.addLayout(playback_form)
    playback_layout.addStretch(1)

    analysis_layout = QVBoxLayout(analysis_tab)
    analysis_layout.addWidget(_description_label(_local(lang, "analysis_flow_hint"), analysis_tab))
    analysis_form = QFormLayout()
    target = QDoubleSpinBox(analysis_tab)
    target.setRange(-50.0, -20.0)
    target.setDecimals(0)
    target.setSingleStep(1.0)
    target.setSuffix(" LUFS")
    target.setValue(max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0)))))
    add_row(analysis_form, analysis_tab, t(lang, "target_loudness"), target, t(lang, "target_loudness_hint"))

    dual_mono = QCheckBox(t(lang, "dual_mono"), analysis_tab)
    dual_mono.setChecked(bool(conf.get("dual_mono", False)))
    add_row(analysis_form, analysis_tab, "", dual_mono, t(lang, "dual_mono_hint"))

    backend = QComboBox(analysis_tab)
    backend.addItem(t(lang, "analysis_auto"), "auto")
    backend.addItem(t(lang, "analysis_ffmpeg"), "ffmpeg")
    backend.addItem(t(lang, "analysis_webaudio"), "webaudio")
    backend_index = backend.findData(str(conf.get("analysis_backend", "auto")))
    backend.setCurrentIndex(backend_index if backend_index >= 0 else 0)
    add_row(analysis_form, analysis_tab, t(lang, "analysis_method"), backend, _local(lang, "analysis_hint"))
    analysis_layout.addLayout(analysis_form)

    ffmpeg_group = QGroupBox(t(lang, "settings_ffmpeg"), analysis_tab)
    ffmpeg_outer = QVBoxLayout(ffmpeg_group)
    ffmpeg_row = QHBoxLayout()
    ffmpeg_state = v010._ffmpeg_state()
    ffmpeg_label = QLabel(
        t(lang, "ffmpeg_ready") if ffmpeg_state.get("available") else t(lang, "ffmpeg_missing"),
        ffmpeg_group,
    )
    install_button = QPushButton(t(lang, "install_ffmpeg"), ffmpeg_group)
    install_button.setEnabled(
        not bool(ffmpeg_state.get("available"))
        and bool(ffmpeg_state.get("installer_available"))
        and not bool(ffmpeg_state.get("installing"))
    )
    ffmpeg_row.addWidget(ffmpeg_label, 1)
    ffmpeg_row.addWidget(install_button)
    ffmpeg_outer.addLayout(ffmpeg_row)
    ffmpeg_outer.addWidget(_description_label(t(lang, "ffmpeg_installer_hint"), ffmpeg_group))
    analysis_layout.addWidget(ffmpeg_group)

    action_available = action_context is not None and current is not None
    busy = False
    if current:
        busy = core._analysis_is_running(current[0]) or _deck_is_materializing(*current)

    analyze_button = QPushButton(t(lang, "analyze_deck"), analysis_tab)
    analyze_button.setEnabled(action_available and not busy)
    analysis_layout.addWidget(analyze_button)
    analysis_layout.addWidget(_description_label(_local(lang, "analyze_hint"), analysis_tab))

    clear_button = QPushButton(t(lang, "settings_clear_profile"), analysis_tab)
    clear_button.setEnabled(action_available and not busy)
    analysis_layout.addWidget(clear_button)
    analysis_layout.addWidget(_description_label(_local(lang, "clear_hint"), analysis_tab))
    analysis_layout.addStretch(1)

    created_layout = QVBoxLayout(created_tab)
    created_layout.addWidget(_description_label(_local(lang, "created_flow_hint"), created_tab))
    created_form = QFormLayout()
    insert_template = QCheckBox(t(lang, "insert_normalized_template"), created_tab)
    insert_template.setChecked(True)
    insert_template.setEnabled(False)
    add_row(
        created_form,
        created_tab,
        "",
        insert_template,
        t(lang, "insert_normalized_template_hint"),
    )
    created_layout.addLayout(created_form)

    materialize_button = QPushButton(t(lang, "materialize_audio"), created_tab)
    materialize_button.setEnabled(action_available and not busy)
    created_layout.addWidget(materialize_button)
    created_layout.addWidget(_description_label(t(lang, "materialize_hint"), created_tab))

    prepare_button = QPushButton(t(lang, "prepare_normalized_field"), created_tab)
    prepare_button.setEnabled(action_available and not busy)
    created_layout.addWidget(prepare_button)
    created_layout.addWidget(_description_label(_local(lang, "prepare_optional_hint"), created_tab))
    created_layout.addStretch(1)

    def selected_mode() -> str:
        for mode, button in mode_buttons.items():
            if button.isChecked():
                return mode
        return "realtime"

    def apply_settings() -> None:
        updated = _conf()
        mode = selected_mode()
        updated["language"] = str(language.currentData() or "auto")
        updated["playback_mode"] = mode
        updated["normalize"] = mode == "realtime"
        updated["deck_profile_enabled"] = mode == "profile"
        updated["overvolume_enabled"] = bool(overvolume.isChecked())
        updated["overvolume_gain_db"] = max(
            0.0, min(OVERVOLUME_MAX_GAIN_DB, float(overvolume_gain.value()))
        )
        updated["loudness_target"] = float(target.value())
        updated["dual_mono"] = bool(dual_mono.isChecked())
        selected_backend = str(backend.currentData() or "auto")
        updated["analysis_backend"] = selected_backend if selected_backend in {"auto", "ffmpeg", "webaudio"} else "auto"
        # Áudios criados são mídia persistente do Anki, portanto a integração
        # nativa com campo/template é obrigatória e não pode depender do add-on.
        updated["normalized_audio_insert_template"] = True
        mw.addonManager.writeConfig(__package__, updated)

        current_deck = v010._current_deck(action_context)
        _supported, status = core._apply_native_settings(
            filename=core._current_audio_filename(),
            deck_id=current_deck[0] if current_deck else core._current_audio_deck_id(),
            update_filters=True,
        )
        if status:
            core._push_status(status, action_context)
        if current_deck:
            v010._push_state(_state(*current_deck))

    def install_ffmpeg_from_dialog() -> None:
        v010._install_ffmpeg()
        ffmpeg_label.setText(t(lang, "ffmpeg_installing_ui"))
        install_button.setEnabled(False)

    def run_action(action) -> None:
        if action_context is None or current is None:
            return
        apply_settings()
        action(action_context)

    qconnect(install_button.clicked, install_ffmpeg_from_dialog)
    qconnect(analyze_button.clicked, lambda _checked=False: run_action(_start_analysis_coordinated))
    qconnect(clear_button.clicked, lambda _checked=False: run_action(_clear_profile_coordinated))
    qconnect(materialize_button.clicked, lambda _checked=False: run_action(v010._start_materialization))
    qconnect(prepare_button.clicked, lambda _checked=False: run_action(v010._prepare_normalized_field_setup))

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )

    def save_and_close() -> None:
        apply_settings()
        dialog.accept()

    qconnect(buttons.accepted, save_and_close)
    qconnect(buttons.rejected, dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


def _refresh_mode(context: object | None) -> None:
    core = _core()
    current = v010._current_deck(context)
    _supported, status = core._apply_native_settings(
        filename=core._current_audio_filename(),
        deck_id=current[0] if current else core._current_audio_deck_id(),
        update_filters=True,
    )
    if status:
        core._push_status(status, context)
    if current:
        v010._push_state(_state(*current))


def _on_message(handled, message: str, context):
    if message.startswith("ferreis_audio:v011:mode:"):
        mode = message.rsplit(":", 1)[-1]
        if mode not in PLAYBACK_MODES:
            return (True, None)
        _save_playback_mode(mode)
        if mode == "created":
            _ensure_materialized_card_integration(context)
        _refresh_mode(context)
        return (True, None)

    if message.startswith("ferreis_audio:v011:overvolume:"):
        parts = message.split(":", 4)
        if len(parts) != 5:
            return (True, None)
        action, raw = parts[3], parts[4]
        conf = _conf()
        if action == "enabled":
            conf["overvolume_enabled"] = raw == "1"
        elif action == "gain":
            try:
                gain_db = float(raw)
            except (TypeError, ValueError):
                return (True, None)
            conf["overvolume_gain_db"] = max(0.0, min(OVERVOLUME_MAX_GAIN_DB, gain_db))
        else:
            return (True, None)
        mw.addonManager.writeConfig(__package__, conf)
        _refresh_mode(context)
        return (True, None)

    # Compatibilidade com versões antigas do painel. O checkbox legado fica
    # oculto na interface atual para evitar duas fontes de verdade para o modo.
    if message.startswith("ferreis_audio:set:normalize:"):
        value = message.rsplit(":", 1)[-1] == "1"
        if value:
            _save_playback_mode("realtime")
        elif _playback_mode() == "realtime":
            current = v010._current_deck(context)
            profile = _core()._get_deck_profile(current[0]) if current else None
            _save_playback_mode("profile" if isinstance(profile, dict) else "created")
        _refresh_mode(context)
        return (True, None)

    if message.startswith("ferreis_audio:deck:enable:"):
        enabled = message.rsplit(":", 1)[-1] == "1"
        _save_playback_mode("profile" if enabled else "realtime")
        _refresh_mode(context)
        return (True, None)
    return handled


def _on_web_content(web_content: WebContent, context: object | None) -> None:
    core = _core()
    if not core._is_supported_card_context(context):
        return
    current = v010._current_deck(context)
    if current and _playback_mode() == "created" and current[0] not in _NATIVE_INTEGRATION_REPAIRED:
        try:
            _ensure_materialized_card_integration(context)
        except Exception as exc:
            print("[Balanced Audio Controller] unable to repair created-audio card integration:", exc)
    package = mw.addonManager.addonFromModule(__package__)
    web_content.js.append(f"/_addons/{package}/web/audio_controller_v011.js")


def _install() -> None:
    core = _core()
    core._apply_native_settings = _apply_native_settings
    v010._state = _state
    v010._open_settings_dialog = _open_settings_dialog
    if not hasattr(v010, "_bac_v011_original_start_analysis"):
        setattr(v010, "_bac_v011_original_start_analysis", _ORIGINAL_START_ANALYSIS)
    if not hasattr(v010, "_bac_v011_original_clear_profile"):
        setattr(v010, "_bac_v011_original_clear_profile", _ORIGINAL_CLEAR_PROFILE)
    v010._start_analysis = _start_analysis_coordinated
    v010._clear_current_deck_profile = _clear_profile_coordinated
    if not hasattr(av_player, "_bac_v011_original_play_tags"):
        setattr(av_player, "_bac_v011_original_play_tags", _ORIGINAL_PLAY_TAGS)
    av_player.play_tags = _play_tags_without_mutating_render_cache
    gui_hooks.webview_did_receive_js_message.append(_on_message)
    gui_hooks.webview_will_set_content.append(_on_web_content)


_install()

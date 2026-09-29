from __future__ import annotations

from pathlib import Path

ROOT = Path('.')


def replace_once(path: str, old: str, new: str, label: str) -> None:
    file = ROOT / path
    text = file.read_text(encoding='utf-8')
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f'{path}: padrão não encontrado: {label}')
    file.write_text(text.replace(old, new, 1), encoding='utf-8')


def append_once(path: str, marker: str, content: str, label: str) -> None:
    file = ROOT / path
    text = file.read_text(encoding='utf-8')
    if content.strip() in text:
        return
    if marker not in text:
        raise RuntimeError(f'{path}: marcador não encontrado: {label}')
    file.write_text(text.replace(marker, marker + content, 1), encoding='utf-8')


# ---------------------------------------------------------------------------
# Núcleo: o mesmo componente passa a funcionar no Reviewer, Previewer e
# CardLayout, e o contexto do deck acompanha a reprodução em ambas as faces.
# ---------------------------------------------------------------------------
replace_once(
    '__init__.py',
    '''_ANALYSIS_RUNNING: set[str] = set()\n_CURRENT_AUDIO_FILENAME: str | None = None\n''',
    '''_ANALYSIS_RUNNING: set[str] = set()\n_CURRENT_AUDIO_FILENAME: str | None = None\n_CURRENT_AUDIO_DECK_ID: int | None = None\n_ACTIVE_CARD_CONTEXT: Any | None = None\n''',
    'estado do contexto de reprodução',
)

replace_once(
    '__init__.py',
    '''def _current_reviewer_card():\n    reviewer = getattr(mw, "reviewer", None)\n    return getattr(reviewer, "card", None)\n\n\ndef _current_reviewer_deck_id() -> int | None:\n    card = _current_reviewer_card()\n    return _card_deck_id(card) if card else None\ndef _current_audio_filename() -> str | None:\n    with _PLAYBACK_LOCK:\n        return _CURRENT_AUDIO_FILENAME\n\n\ndef _set_current_audio_filename(filename: str | None) -> None:\n    global _CURRENT_AUDIO_FILENAME\n    with _PLAYBACK_LOCK:\n        _CURRENT_AUDIO_FILENAME = filename\n''',
    '''def _current_reviewer_card():\n    reviewer = getattr(mw, "reviewer", None)\n    return getattr(reviewer, "card", None)\n\n\ndef _current_reviewer_deck_id() -> int | None:\n    card = _current_reviewer_card()\n    return _card_deck_id(card) if card else None\n\n\ndef _context_surface(context: object | None) -> str:\n    if isinstance(context, aqt.reviewer.Reviewer):\n        return "reviewer"\n    if context is None:\n        return ""\n    cls = type(context)\n    module = str(getattr(cls, "__module__", ""))\n    name = str(getattr(cls, "__name__", ""))\n    if module == "aqt.browser.previewer" and name.endswith("Previewer"):\n        return "previewer"\n    if module == "aqt.clayout" and name == "CardLayout":\n        return "card_layout"\n    return ""\n\n\ndef _is_supported_card_context(context: object | None) -> bool:\n    return bool(_context_surface(context))\n\n\ndef _card_from_context(context: object | None):\n    if not _is_supported_card_context(context):\n        return None\n    candidate = getattr(context, "card", None)\n    if callable(candidate):\n        try:\n            candidate = candidate()\n        except Exception:\n            candidate = None\n    if candidate is not None:\n        return candidate\n    return getattr(context, "rendered_card", None)\n\n\ndef _context_web(context: object | None):\n    if not _is_supported_card_context(context):\n        return None\n    if isinstance(context, aqt.reviewer.Reviewer):\n        return getattr(context, "web", None)\n    surface = _context_surface(context)\n    if surface == "previewer":\n        return getattr(context, "_web", None)\n    if surface == "card_layout":\n        return getattr(context, "preview_web", None)\n    return None\n\n\ndef _set_active_card_context(context: object | None) -> None:\n    global _ACTIVE_CARD_CONTEXT\n    with _PLAYBACK_LOCK:\n        _ACTIVE_CARD_CONTEXT = context if _is_supported_card_context(context) else None\n\n\ndef _active_card_context() -> object | None:\n    with _PLAYBACK_LOCK:\n        return _ACTIVE_CARD_CONTEXT\n\n\ndef _current_audio_filename() -> str | None:\n    with _PLAYBACK_LOCK:\n        return _CURRENT_AUDIO_FILENAME\n\n\ndef _set_current_audio_filename(filename: str | None) -> None:\n    global _CURRENT_AUDIO_FILENAME\n    with _PLAYBACK_LOCK:\n        _CURRENT_AUDIO_FILENAME = filename\n\n\ndef _current_audio_deck_id() -> int | None:\n    with _PLAYBACK_LOCK:\n        return _CURRENT_AUDIO_DECK_ID\n\n\ndef _set_current_audio_deck_id(deck_id: int | None) -> None:\n    global _CURRENT_AUDIO_DECK_ID\n    with _PLAYBACK_LOCK:\n        _CURRENT_AUDIO_DECK_ID = deck_id\n''',
    'helpers de contexto do card',
)

replace_once(
    '__init__.py',
    '''def _profile_entry_for_current_deck(\n    filename: str | None, conf: dict[str, Any]\n) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:\n    if not filename or not bool(conf.get("deck_profile_enabled", False)):\n        return None, None\n\n    deck_id = _current_reviewer_deck_id()\n''',
    '''def _profile_entry_for_current_deck(\n    filename: str | None,\n    conf: dict[str, Any],\n    deck_id: int | None = None,\n) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:\n    if not filename or not bool(conf.get("deck_profile_enabled", False)):\n        return None, None\n\n    deck_id = deck_id if deck_id is not None else _current_audio_deck_id()\n    if deck_id is None:\n        deck_id = _current_reviewer_deck_id()\n''',
    'perfil por contexto de reprodução',
)

replace_once(
    '__init__.py',
    '''def _apply_native_settings(\n    player: Any | None = None,\n    filename: str | None = None,\n    *,\n    update_filters: bool = True,\n) -> tuple[bool, str]:''',
    '''def _apply_native_settings(\n    player: Any | None = None,\n    filename: str | None = None,\n    deck_id: int | None = None,\n    *,\n    update_filters: bool = True,\n) -> tuple[bool, str]:''',
    'deck id na aplicação nativa',
)
replace_once(
    '__init__.py',
    '    profile, entry = _profile_entry_for_current_deck(filename, conf)\n',
    '    profile, entry = _profile_entry_for_current_deck(filename, conf, deck_id)\n',
    'perfil recebe deck id',
)

replace_once(
    '__init__.py',
    '''def _push_status(text: str) -> None:\n    reviewer = getattr(mw, "reviewer", None)\n    web = getattr(reviewer, "web", None)\n    if not web:\n        return\n''',
    '''def _push_status(text: str, context: object | None = None) -> None:\n    target = context or _active_card_context()\n    web = _context_web(target)\n    if not web:\n        reviewer = getattr(mw, "reviewer", None)\n        web = getattr(reviewer, "web", None)\n    if not web:\n        return\n''',
    'status no webview ativo',
)

replace_once(
    '__init__.py',
    '''def _push_deck_profile_state(state: dict[str, Any]) -> None:\n    reviewer = getattr(mw, "reviewer", None)\n    web = getattr(reviewer, "web", None)\n    if not web:\n        return\n''',
    '''def _push_deck_profile_state(\n    state: dict[str, Any], context: object | None = None\n) -> None:\n    target = context or _active_card_context()\n    web = _context_web(target)\n    if not web:\n        reviewer = getattr(mw, "reviewer", None)\n        web = getattr(reviewer, "web", None)\n    if not web:\n        return\n''',
    'estado do perfil no webview ativo',
)

replace_once(
    '__init__.py',
    '''def _start_deck_analysis(context: aqt.reviewer.Reviewer) -> None:\n    card = getattr(context, "card", None) or _current_reviewer_card()\n''',
    '''def _start_deck_analysis(context: object) -> None:\n    card = _card_from_context(context) or _current_reviewer_card()\n''',
    'análise com contexto genérico',
)

replace_once(
    '__init__.py',
    '''def _on_av_player_will_play(tag: Any) -> None:\n''',
    '''def _on_av_player_will_play_tags(tags: list[Any], side: str, context: object) -> None:\n    del tags, side\n    if not _is_supported_card_context(context):\n        _set_current_audio_deck_id(None)\n        return\n    _set_active_card_context(context)\n    card = _card_from_context(context)\n    _set_current_audio_deck_id(_card_deck_id(card) if card else None)\n\n\ndef _on_av_player_will_play(tag: Any) -> None:\n''',
    'hook de contexto antes da fila de áudio',
)
replace_once(
    '__init__.py',
    '''    _supported, status = _apply_native_settings(player, filename)\n    if status:\n        _push_status(status)\n''',
    '''    _supported, status = _apply_native_settings(\n        player, filename, deck_id=_current_audio_deck_id()\n    )\n    if status:\n        _push_status(status)\n''',
    'aplicar contexto na reprodução',
)

replace_once(
    '__init__.py',
    '''def _on_card_will_show(text: str, card, kind: str) -> str:\n    if kind not in ("reviewQuestion", "reviewAnswer") or not _card_has_audio(card):\n        return text\n\n    conf = _config()\n''',
    '''def _on_card_will_show(text: str, card, kind: str) -> str:\n    kind_info = {\n        "reviewQuestion": ("reviewer", "question"),\n        "reviewAnswer": ("reviewer", "answer"),\n        "previewQuestion": ("previewer", "question"),\n        "previewAnswer": ("previewer", "answer"),\n        "clayoutQuestion": ("card_layout", "question"),\n        "clayoutAnswer": ("card_layout", "answer"),\n    }.get(kind)\n    if kind_info is None:\n        return text\n\n    surface, side = kind_info\n    # No revisor, o painel só aparece em cards com áudio. Em pré-visualização\n    # ele também aparece sem áudio para ajudar a detectar/configurar a face.\n    if surface == "reviewer" and not _card_has_audio(card):\n        return text\n\n    conf = _config()\n''',
    'kinds de preview',
)
replace_once(
    '__init__.py',
    '''    payload = {\n        "language": lang,\n''',
    '''    side_tags = card.question_av_tags() if side == "question" else card.answer_av_tags()\n    payload = {\n        "language": lang,\n        "surface": surface,\n        "side": side,\n        "side_audio_count": len(_audio_filenames(side_tags)),\n''',
    'metadados da face no payload',
)

replace_once(
    '__init__.py',
    '''    if not isinstance(context, aqt.reviewer.Reviewer):\n        return\n    addon_package = mw.addonManager.addonFromModule(__name__)\n''',
    '''    if not _is_supported_card_context(context):\n        return\n    _set_active_card_context(context)\n    addon_package = mw.addonManager.addonFromModule(__name__)\n''',
    'assets nos previews',
)

replace_once(
    '__init__.py',
    '''def _on_js_message(handled, message: str, context):\n    if not isinstance(context, aqt.reviewer.Reviewer):\n        return handled\n\n    if message == "ferreis_audio:deck:analyze":\n''',
    '''def _on_js_message(handled, message: str, context):\n    if not _is_supported_card_context(context):\n        return handled\n    _set_active_card_context(context)\n    card = _card_from_context(context) or _current_reviewer_card()\n\n    if message == "ferreis_audio:deck:analyze":\n''',
    'mensagens nos previews',
)
replace_once(
    '__init__.py',
    '        card = getattr(context, "card", None) or _current_reviewer_card()\n',
    '        card = _card_from_context(context) or _current_reviewer_card()\n',
    'card ao limpar perfil',
)
replace_once(
    '__init__.py',
    '        card = getattr(context, "card", None) or _current_reviewer_card()\n',
    '        card = _card_from_context(context) or _current_reviewer_card()\n',
    'card ao habilitar perfil',
)

# loudness_target e dual_mono: usar o card do contexto quando existir.
init_path = ROOT / '__init__.py'
init_text = init_path.read_text(encoding='utf-8')
old_deck_lookup = '''            deck_id = _current_reviewer_deck_id()\n            if deck_id is not None:\n                _push_deck_profile_state(_deck_profile_summary(deck_id))\n'''
new_deck_lookup = '''            deck_id = _card_deck_id(card) if card else _current_reviewer_deck_id()\n            if deck_id is not None:\n                _push_deck_profile_state(_deck_profile_summary(deck_id), context)\n'''
if old_deck_lookup in init_text:
    init_text = init_text.replace(old_deck_lookup, new_deck_lookup, 2)
init_path.write_text(init_text, encoding='utf-8')

replace_once(
    '__init__.py',
    '''        _supported, status = _apply_native_settings(\n            filename=_current_audio_filename(),\n            update_filters=update_filters,\n        )\n        if status:\n            context.web.eval(\n                "window.FerreisAnkiAudio && window.FerreisAnkiAudio.setStatus("\n                + json.dumps(status, ensure_ascii=False)\n                + ");"\n            )\n''',
    '''        _supported, status = _apply_native_settings(\n            filename=_current_audio_filename(),\n            deck_id=_card_deck_id(card) if card else _current_audio_deck_id(),\n            update_filters=update_filters,\n        )\n        web = _context_web(context)\n        if status and web:\n            web.eval(\n                "window.FerreisAnkiAudio && window.FerreisAnkiAudio.setStatus("\n                + json.dumps(status, ensure_ascii=False)\n                + ");"\n            )\n''',
    'status de configuração no webview correto',
)

replace_once(
    '__init__.py',
    '''gui_hooks.webview_did_receive_js_message.append(_on_js_message)\ngui_hooks.av_player_will_play.append(_on_av_player_will_play)\n''',
    '''gui_hooks.webview_did_receive_js_message.append(_on_js_message)\ngui_hooks.av_player_will_play_tags.append(_on_av_player_will_play_tags)\ngui_hooks.av_player_will_play.append(_on_av_player_will_play)\n''',
    'registro do contexto de reprodução',
)

# ---------------------------------------------------------------------------
# UI: pré-visualização usa o mesmo componente, com indicador Frente/Verso e
# acesso direto às configurações. O componente v0.10 é religado a cada render.
# ---------------------------------------------------------------------------
replace_once(
    'web/audio_controller.js',
    '''      this.render();\n      requestAnimationFrame(() => this.restoreSidePanelPosition());\n''',
    '''      this.render();\n      window.BACV010?.attach?.(root);\n      requestAnimationFrame(() => this.restoreSidePanelPosition());\n''',
    'reativar extensão em nova face',
)
replace_once(
    'web/audio_controller.js',
    '''    t(key, values = {}) {\n      const dictionary = this.config?.i18n || {};\n      const template = dictionary[key] || key;\n      return String(template).replace(/\\{(\\w+)\\}/g, (_match, name) =>\n        Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : `{${name}}`\n      );\n    },\n\n    render() {\n''',
    '''    t(key, values = {}) {\n      const dictionary = this.config?.i18n || {};\n      const template = dictionary[key] || key;\n      return String(template).replace(/\\{(\\w+)\\}/g, (_match, name) =>\n        Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : `{${name}}`\n      );\n    },\n\n    isPreviewSurface() {\n      return ["previewer", "card_layout"].includes(String(this.config?.surface || ""));\n    },\n\n    previewSideLabel() {\n      return this.t(this.config?.side === "answer" ? "preview_back" : "preview_front");\n    },\n\n    render() {\n''',
    'helpers de preview no componente',
)
replace_once(
    'web/audio_controller.js',
    '''          <div class="fac-side-body">\n            <section class="fac-block">\n''',
    '''          <div class="fac-side-body">\n            ${this.isPreviewSurface() ? `\n            <section class="fac-block fac-preview-tools">\n              <div class="fac-row fac-row-label">\n                <span>${t("preview_mode")}</span>\n                <span class="fac-preview-side-badge">${this.previewSideLabel()}</span>\n              </div>\n              <div class="fac-preview-audio-count">${t("preview_audio_count", { count: Number(this.config.side_audio_count || 0) })}</div>\n              <button class="fac-action fac-open-settings" type="button">${t("preview_open_settings")}</button>\n            </section>\n            ` : ""}\n\n            <section class="fac-block">\n''',
    'ferramentas de preview',
)
replace_once(
    'web/audio_controller.js',
    '''      this.root.querySelector(".fac-analyze-deck").addEventListener("click", () => {\n''',
    '''      const settingsButton = this.root.querySelector(".fac-open-settings");\n      if (settingsButton) {\n        settingsButton.addEventListener("click", () => {\n          pycmd("ferreis_audio:v010:settings");\n        });\n      }\n\n      this.root.querySelector(".fac-analyze-deck").addEventListener("click", () => {\n''',
    'abrir configurações no preview',
)

replace_once(
    'web/audio_controller_v010.js',
    '''    root: null,\n    state: {},\n    mounted: false,\n''',
    '''    root: null,\n    state: {},\n    mountedRoot: null,\n''',
    'estado de montagem por root',
)
replace_once(
    'web/audio_controller_v010.js',
    '''        if (root && base && root.dataset.mounted === "1") {\n          this.root = root;\n          this.augment();\n          return;\n        }\n''',
    '''        if (root && base && root.dataset.mounted === "1") {\n          this.attach(root);\n          return;\n        }\n''',
    'boot liga ao root atual',
)
replace_once(
    'web/audio_controller_v010.js',
    '''    augment() {\n      if (this.mounted || !this.root) return;\n      const handle = this.root.querySelector(".fac-side-handle");\n      const oldAnalyze = this.root.querySelector(".fac-analyze-deck");\n      if (!handle || !oldAnalyze) return;\n      this.mounted = true;\n''',
    '''    attach(root) {\n      if (!root || this.mountedRoot === root) return;\n      this.root = root;\n      this.mountedRoot = root;\n      this.augment();\n    },\n\n    augment() {\n      if (!this.root) return;\n      const handle = this.root.querySelector(".fac-side-handle");\n      const oldAnalyze = this.root.querySelector(".fac-analyze-deck");\n      if (!handle || !oldAnalyze) return;\n''',
    'reativar v010 em cada face',
)

# CSS do bloco de preview e botão Analisar ocupando a largura disponível.
replace_once(
    'web/audio_controller.css',
    '  grid-template-columns: minmax(0, 1fr) 58px;\n',
    '  grid-template-columns: minmax(0, 1fr);\n',
    'ações do deck em uma coluna',
)
append_once(
    'web/audio_controller.css',
    '''#ferreis-audio-controller .fac-status {\n  display: block;\n  max-width: 100%;\n  margin-top: 8px;\n  overflow: hidden;\n  color: var(--fac-muted);\n  font-size: 10px;\n  line-height: 1.25;\n  text-overflow: ellipsis;\n  white-space: nowrap;\n}\n''',
    '''\n#ferreis-audio-controller .fac-preview-tools {\n  gap: 8px;\n}\n\n#ferreis-audio-controller .fac-preview-side-badge {\n  padding: 2px 7px;\n  border: 1px solid rgba(106, 169, 255, 0.42);\n  border-radius: 999px;\n  color: var(--fac-accent);\n  font-size: 9px;\n  line-height: 1.2;\n}\n\n#ferreis-audio-controller .fac-preview-audio-count {\n  color: var(--fac-muted);\n  font-size: 10px;\n  line-height: 1.35;\n}\n\n#ferreis-audio-controller .fac-open-settings {\n  width: 100%;\n}\n''',
    'estilos do preview',
)

# ---------------------------------------------------------------------------
# Extensão v0.10: ações/configurações passam a conhecer o contexto de preview.
# ---------------------------------------------------------------------------
replace_once(
    'v010.py',
    '''def _push_state(state: dict[str, Any]) -> None:\n    reviewer = getattr(mw, "reviewer", None)\n    web = getattr(reviewer, "web", None)\n    if not web:\n        return\n''',
    '''def _push_state(state: dict[str, Any]) -> None:\n    core = _core()\n    web = core._context_web(core._active_card_context())\n    if not web:\n        reviewer = getattr(mw, "reviewer", None)\n        web = getattr(reviewer, "web", None)\n    if not web:\n        return\n''',
    'estado no preview ativo',
)
replace_once(
    'v010.py',
    '''def _current_deck(context=None) -> tuple[int, str] | None:\n    core = _core()\n    card = getattr(context, "card", None) if context is not None else None\n    card = card or core._current_reviewer_card()\n''',
    '''def _current_deck(context=None) -> tuple[int, str] | None:\n    core = _core()\n    card = core._card_from_context(context) if context is not None else None\n    card = card or core._current_reviewer_card()\n''',
    'deck do Previewer/CardLayout',
)
replace_once(
    'v010.py',
    '''    deck_id, deck_name = current\n    lang = _lang()\n    if core._analysis_is_running(deck_id):\n''',
    '''    deck_id, deck_name = current\n    web = core._context_web(context)\n    if not web:\n        return\n    lang = _lang()\n    if core._analysis_is_running(deck_id):\n''',
    'webview da análise interna',
)
replace_once(
    'v010.py',
    '    context.web.eval(f"window.BACV010 && window.BACV010.startWebAudioAnalysis({payload});")\n',
    '    web.eval(f"window.BACV010 && window.BACV010.startWebAudioAnalysis({payload});")\n',
    'WebAudio no webview do contexto',
)
replace_once(
    'v010.py',
    '    current = _current_deck()\n    if current:\n        state = _state(*current); state["message"] = t(lang, "ffmpeg_installing", installer=status.get("installer_name") or "imageio-ffmpeg"); _push_state(state)\n',
    '    current = _current_deck(_core()._active_card_context())\n    if current:\n        state = _state(*current); state["message"] = t(lang, "ffmpeg_installing", installer=status.get("installer_name") or "imageio-ffmpeg"); _push_state(state)\n',
    'ffmpeg usa deck do preview',
)
replace_once(
    'v010.py',
    '        current_deck = _current_deck()\n',
    '        current_deck = _current_deck(_core()._active_card_context())\n',
    'fim da instalação usa deck do preview',
)
replace_once(
    'v010.py',
    'def _open_settings_dialog() -> None:\n',
    'def _open_settings_dialog(context: object | None = None) -> None:\n',
    'dialog recebe contexto',
)
replace_once(
    'v010.py',
    '''    lang = _lang()\n    conf = _conf()\n    dialog = QDialog(mw)\n''',
    '''    lang = _lang()\n    conf = _conf()\n    core = _core()\n    action_context = (\n        context if core._is_supported_card_context(context) else _active_reviewer()\n    )\n    dialog = QDialog(mw)\n''',
    'contexto das ações do dialog',
)
replace_once(
    'v010.py',
    '''        core = _core()\n        _supported, status = core._apply_native_settings(\n            filename=core._current_audio_filename(),\n            update_filters=True,\n        )\n        if status:\n            core._push_status(status)\n        current = _current_deck()\n        if current:\n            _push_state(_state(*current))\n''',
    '''        current = _current_deck(action_context)\n        _supported, status = core._apply_native_settings(\n            filename=core._current_audio_filename(),\n            deck_id=current[0] if current else core._current_audio_deck_id(),\n            update_filters=True,\n        )\n        if status:\n            core._push_status(status, action_context)\n        if current:\n            _push_state(_state(*current))\n''',
    'salvar configuração no contexto atual',
)
replace_once(
    'v010.py',
    '''    reviewer = _active_reviewer()\n    current = _current_deck(reviewer) if reviewer else None\n''',
    '''    current = _current_deck(action_context) if action_context else None\n''',
    'deck atual no dialog',
)
replace_once(
    'v010.py',
    '''    for button in (analyze_button, prepare_button, materialize_button, clear_button):\n        button.setEnabled(reviewer is not None)\n        actions_layout.addWidget(button)\n''',
    '''    for button in (analyze_button, prepare_button, materialize_button, clear_button):\n        button.setEnabled(action_context is not None and current is not None)\n        actions_layout.addWidget(button)\n''',
    'ações habilitadas no preview',
)
replace_once(
    'v010.py',
    '''    def run_action(action) -> None:\n        if reviewer is None:\n            return\n        apply_settings()\n        action(reviewer)\n''',
    '''    def run_action(action) -> None:\n        if action_context is None or current is None:\n            return\n        apply_settings()\n        action(action_context)\n''',
    'executar ação pelo contexto',
)
replace_once(
    'v010.py',
    '    qconnect(settings_action.triggered, _open_settings_dialog)\n',
    '    qconnect(settings_action.triggered, lambda: _open_settings_dialog())\n',
    'menu abre dialog sem contexto Qt',
)
replace_once(
    'v010.py',
    '''def _on_web_content(web_content: WebContent, context: object | None) -> None:\n    if not isinstance(context, aqt.reviewer.Reviewer):\n        return\n''',
    '''def _on_web_content(web_content: WebContent, context: object | None) -> None:\n    if not _core()._is_supported_card_context(context):\n        return\n''',
    'v010 nos webviews de preview',
)
replace_once(
    'v010.py',
    '''def _on_message(handled, message: str, context):\n    if not isinstance(context, aqt.reviewer.Reviewer):\n        return handled\n    if message == "ferreis_audio:v010:state":\n''',
    '''def _on_message(handled, message: str, context):\n    core = _core()\n    if not core._is_supported_card_context(context):\n        return handled\n    core._set_active_card_context(context)\n    if message == "ferreis_audio:v010:settings":\n        _open_settings_dialog(context); return (True, None)\n    if message == "ferreis_audio:v010:state":\n''',
    'mensagens v010 no preview',
)

# ---------------------------------------------------------------------------
# Traduções e texto de ajuda.
# ---------------------------------------------------------------------------
replace_once(
    'i18n.py',
    '''        "clear": "Clear",\n        "settings_menu_action": "Settings...",\n''',
    '''        "clear": "Clear",\n        "preview_mode": "Preview",\n        "preview_front": "Front",\n        "preview_back": "Back",\n        "preview_audio_count": "{count} audio file(s) on this side",\n        "preview_open_settings": "Audio settings...",\n        "settings_menu_action": "Settings...",\n''',
    'traduções preview en',
)
replace_once(
    'i18n.py',
    '''        "clear": "Limpar",\n        "settings_menu_action": "Configurações...",\n''',
    '''        "clear": "Limpar",\n        "preview_mode": "Pré-visualização",\n        "preview_front": "Frente",\n        "preview_back": "Verso",\n        "preview_audio_count": "{count} áudio(s) nesta face",\n        "preview_open_settings": "Configurações de áudio...",\n        "settings_menu_action": "Configurações...",\n''',
    'traduções preview pt-BR',
)
replace_once(
    'i18n.py',
    '        "settings_no_active_deck": "Open a card in the reviewer to use these actions.",\n',
    '        "settings_no_active_deck": "Open a card in the reviewer or preview to use these actions.",\n',
    'ajuda de deck ativo en',
)
replace_once(
    'i18n.py',
    '        "settings_no_active_deck": "Abra um card no revisor para usar estas ações.",\n',
    '        "settings_no_active_deck": "Abra um card no revisor ou na pré-visualização para usar estas ações.",\n',
    'ajuda de deck ativo pt-BR',
)
replace_once(
    'i18n.py',
    '''    "clear",\n    "analysis_method",\n''',
    '''    "clear",\n    "preview_mode",\n    "preview_front",\n    "preview_back",\n    "preview_audio_count",\n    "preview_open_settings",\n    "analysis_method",\n''',
    'chaves web de preview',
)

# ---------------------------------------------------------------------------
# Playwright: frente/verso são o mesmo componente, com novo root a cada render.
# ---------------------------------------------------------------------------
replace_once(
    'tests/test_audio_controller_playwright.py',
    '''    "clear": "Clear",\n    "analysis_method": "Analysis method",\n''',
    '''    "clear": "Clear",\n    "preview_mode": "Preview",\n    "preview_front": "Front",\n    "preview_back": "Back",\n    "preview_audio_count": "{count} audio file(s) on this side",\n    "preview_open_settings": "Audio settings...",\n    "analysis_method": "Analysis method",\n''',
    'i18n do Playwright',
)
replace_once(
    'tests/test_audio_controller_playwright.py',
    '''        "language": "en",\n        "i18n": I18N,\n        "speed": 1.0,\n''',
    '''        "language": "en",\n        "i18n": I18N,\n        "surface": "reviewer",\n        "side": "question",\n        "side_audio_count": 1,\n        "speed": 1.0,\n''',
    'contexto base do Playwright',
)

playwright_tests = '''\n    def test_preview_panel_exposes_side_and_settings(self) -> None:\n        config = base_config()\n        config.update({"surface": "previewer", "side": "question", "side_audio_count": 2})\n        page = self.page_with_config(config)\n        try:\n            self.assertEqual(page.locator(".fac-preview-side-badge").inner_text(), "Front")\n            self.assertEqual(page.locator(".fac-preview-audio-count").inner_text(), "2 audio file(s) on this side")\n            page.evaluate("window.__pycmdMessages=[]")\n            page.locator(".fac-open-settings").click()\n            self.assertIn("ferreis_audio:v010:settings", page.evaluate("window.__pycmdMessages"))\n        finally:\n            page.close()\n\n    def test_front_and_back_rebind_the_same_component(self) -> None:\n        config = base_config()\n        config.update({"surface": "previewer", "side": "question", "side_audio_count": 1})\n        page = self.page_with_config(config)\n        try:\n            page.locator(".fac-panel-toggle").click()\n            self.assertIn("fac-minimized", page.locator(".fac-side-panel").get_attribute("class") or "")\n\n            back = base_config()\n            back.update({"surface": "previewer", "side": "answer", "side_audio_count": 3})\n            page.evaluate(\n                """config => {\n                    const oldRoot = document.getElementById('ferreis-audio-controller');\n                    const newRoot = document.createElement('div');\n                    newRoot.id = 'ferreis-audio-controller';\n                    newRoot.dataset.config = JSON.stringify(config);\n                    oldRoot.replaceWith(newRoot);\n                    window.FerreisAnkiAudio.mount();\n                }""",\n                back,\n            )\n            page.wait_for_selector(".fac-panel-toggle")\n\n            self.assertEqual(page.locator(".fac-side-panel").count(), 1)\n            self.assertEqual(page.locator(".fac-panel-toggle").count(), 1)\n            self.assertEqual(page.locator(".fac-preview-side-badge").inner_text(), "Back")\n            self.assertEqual(page.locator(".fac-preview-audio-count").inner_text(), "3 audio file(s) on this side")\n            self.assertTrue(page.evaluate("window.BACV010.root === document.getElementById('ferreis-audio-controller')"))\n            self.assertIn("fac-minimized", page.locator(".fac-side-panel").get_attribute("class") or "")\n\n            page.evaluate("window.__pycmdMessages=[]")\n            page.locator(".fac-analyze-deck").click()\n            self.assertIn("ferreis_audio:v010:analyze", page.evaluate("window.__pycmdMessages"))\n        finally:\n            page.close()\n\n'''
replace_once(
    'tests/test_audio_controller_playwright.py',
    '''\n\n\n\n\nif __name__ == "__main__":\n''',
    '\n' + playwright_tests + '\nif __name__ == "__main__":\n',
    'testes de preview',
)

preview_test = ROOT / 'tests' / 'test_preview_context.py'
if not preview_test.exists():
    preview_test.write_text('''from __future__ import annotations\n\nimport unittest\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass PreviewContextTests(unittest.TestCase):\n    def test_core_supports_reviewer_previewer_and_card_layout(self) -> None:\n        source = (ROOT / "__init__.py").read_text(encoding="utf-8")\n        for expected in (\n            '\"previewQuestion\": (\"previewer\", \"question\")',\n            '\"previewAnswer\": (\"previewer\", \"answer\")',\n            '\"clayoutQuestion\": (\"card_layout\", \"question\")',\n            '\"clayoutAnswer\": (\"card_layout\", \"answer\")',\n            'gui_hooks.av_player_will_play_tags.append(_on_av_player_will_play_tags)',\n            '_current_audio_deck_id()',\n        ):\n            self.assertIn(expected, source)\n\n    def test_v010_settings_and_actions_accept_preview_context(self) -> None:\n        source = (ROOT / "v010.py").read_text(encoding="utf-8")\n        self.assertIn('ferreis_audio:v010:settings', source)\n        self.assertIn('core._is_supported_card_context(context)', source)\n        self.assertIn('action_context', source)\n        self.assertNotIn('context.web.eval(', source)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8')

print('Integração do painel com Previewer/CardLayout aplicada.')

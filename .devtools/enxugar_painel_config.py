from __future__ import annotations

import re
from pathlib import Path

ROOT = Path('.')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'padrão não encontrado: {label}')
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f'padrão regex não encontrado: {label} ({count})')
    return updated


# Idempotência para reexecuções do workflow após o commit automático.
v010_path = ROOT / 'v010.py'
v010 = v010_path.read_text(encoding='utf-8')
if 'def _open_settings_dialog()' in v010:
    print('Reorganização já aplicada; nada a alterar.')
    raise SystemExit(0)

# 1) Painel do revisor: apenas controles usados durante o estudo.
js_path = ROOT / 'web' / 'audio_controller.js'
js = js_path.read_text(encoding='utf-8')

js = sub_once(
    js,
    r'''            <section class="fac-block fac-normalization-block">.*?            </section>\n\n            <section class="fac-block fac-deck-profile-block">''',
    '''            <section class="fac-block fac-normalization-block">\n              <label class="fac-check-row" title="${t("realtime_normalization_hint")}">\n                <input class="fac-normalize" type="checkbox">\n                <span>${t("realtime_normalization")}</span>\n              </label>\n            </section>\n\n            <section class="fac-block fac-deck-profile-block">''',
    'bloco de normalização',
)

js = sub_once(
    js,
    r'''\n              <label class="fac-check-row fac-deck-enable-wrap".*?</label>\n\n              <div class="fac-deck-actions">\n                <button class="fac-action fac-analyze-deck" type="button">\$\{t\("analyze_deck"\)\}</button>\n                <button class="fac-action fac-action-secondary fac-clear-deck" type="button">\$\{t\("clear"\)\}</button>\n              </div>''',
    '''\n              <div class="fac-deck-actions">\n                <button class="fac-action fac-analyze-deck" type="button">${t("analyze_deck")}</button>\n              </div>''',
    'ações do perfil',
)

js = sub_once(
    js,
    r'''\n      const loudness = this\.root\.querySelector\("\.fac-loudness"\);.*?      this\.updateNormalizationEnabledState\(\);\n''',
    '\n',
    'inicialização de opções avançadas',
)

js = replace_once(
    js,
    '''      normalize.addEventListener("change", (event) => {\n        this.config.normalize = Boolean(event.target.checked);\n        this.updateNormalizationEnabledState();\n        pycmd(`ferreis_audio:set:normalize:${this.config.normalize ? 1 : 0}`);\n      });''',
    '''      normalize.addEventListener("change", (event) => {\n        this.config.normalize = Boolean(event.target.checked);\n        pycmd(`ferreis_audio:set:normalize:${this.config.normalize ? 1 : 0}`);\n      });''',
    'toggle de normalização',
)

js = sub_once(
    js,
    r'''\n      loudness\.addEventListener\("input".*?      dualMono\.addEventListener\("change", \(event\) => \{.*?      \}\);\n''',
    '\n',
    'eventos de loudness e dual mono',
)

js = sub_once(
    js,
    r'''\n      this\.root\.querySelector\("\.fac-deck-enable"\).*?      \}\);\n\n      this\.root\.querySelector\("\.fac-analyze-deck"\)''',
    '''\n      this.root.querySelector(".fac-analyze-deck")''',
    'toggle do perfil no painel',
)

js = sub_once(
    js,
    r'''\n      this\.root\.querySelector\("\.fac-clear-deck"\).*?      \}\);\n''',
    '\n',
    'limpar perfil no painel',
)

js = sub_once(
    js,
    r'''\n    updateLoudnessValue\(value\) \{.*?    \},\n\n    updateNormalizationEnabledState\(\) \{.*?    \},\n''',
    '\n',
    'métodos de opções avançadas',
)

js = replace_once(js, '      const enable = this.root.querySelector(".fac-deck-enable");\n', '', 'query enable')
js = replace_once(js, '      const clear = this.root.querySelector(".fac-clear-deck");\n', '', 'query clear')
js = sub_once(
    js,
    r'''      if \(enable\) \{.*?      \}\n      if \(analyze\) analyze\.disabled = Boolean\(profile\.analyzing\);\n      if \(clear\) clear\.disabled = !profile\.exists \|\| Boolean\(profile\.analyzing\);''',
    '      if (analyze) analyze.disabled = Boolean(profile.analyzing);',
    'estado de ações avançadas',
)

for forbidden in ('.fac-loudness', '.fac-dual-mono', '.fac-deck-enable', '.fac-clear-deck'):
    if forbidden in js:
        raise RuntimeError(f'controle avançado ainda presente no painel: {forbidden}')
js_path.write_text(js, encoding='utf-8')

# 2) Extensão v0.10: mantém análise WebAudio/minimização, sem adicionar controles avançados ao painel.
vjs_path = ROOT / 'web' / 'audio_controller_v010.js'
vjs = vjs_path.read_text(encoding='utf-8')

vjs = sub_once(
    vjs,
    r'''    augment\(\) \{.*?\n    panelLabel\(minimized\) \{''',
    '''    augment() {\n      if (this.mounted || !this.root) return;\n      const handle = this.root.querySelector(".fac-side-handle");\n      const oldAnalyze = this.root.querySelector(".fac-analyze-deck");\n      if (!handle || !oldAnalyze) return;\n      this.mounted = true;\n\n      this.installMinimizeStyles();\n      this.installMinimizeControl(handle);\n\n      const fresh = oldAnalyze.cloneNode(true);\n      oldAnalyze.replaceWith(fresh);\n      fresh.addEventListener("click", () => {\n        const base = window.FerreisAnkiAudio;\n        base?.updateDeckProfile?.({ ...(base.config?.deck_profile || {}), analyzing: true, progress: 0, message: t("preparing_analysis") });\n        pycmd("ferreis_audio:v010:analyze");\n      });\n\n      const base = window.FerreisAnkiAudio;\n      this.state = {\n        ...(base?.config?.deck_profile || {}),\n        analysis_backend: base?.config?.analysis_backend || base?.config?.deck_profile?.analysis_backend || "auto",\n      };\n      this.updateState(this.state);\n      if (base?.updateDeckProfile && !base.__bacV010Patched) {\n        const original = base.updateDeckProfile.bind(base);\n        base.updateDeckProfile = (state) => {\n          original(state);\n          this.updateState(state || {});\n        };\n        base.__bacV010Patched = true;\n      }\n      pycmd("ferreis_audio:v010:state");\n    },\n\n    panelLabel(minimized) {''',
    'augment v010',
)

vjs = sub_once(
    vjs,
    r'''\n    resolvedBackend\(\) \{.*?\n    mediaUrl\(filename\) \{''',
    '''\n    updateState(state) {\n      this.state = { ...this.state, ...(state || {}) };\n    },\n\n    mediaUrl(filename) {''',
    'estado avançado v010',
)

for forbidden in (
    '.fac-analysis-backend',
    '.fac-install-ffmpeg',
    '.fac-materialize-normalized',
    '.fac-prepare-normalized-field',
    '.fac-materialize-template',
):
    if forbidden in vjs:
        raise RuntimeError(f'controle avançado v0.10 ainda presente no painel: {forbidden}')
vjs_path.write_text(vjs, encoding='utf-8')

# 3) Configurações e ações avançadas em Ferramentas.
settings_code = r'''

def _active_reviewer():
    reviewer = getattr(mw, "reviewer", None)
    return reviewer if reviewer is not None and getattr(reviewer, "card", None) else None


def _clear_current_deck_profile(context) -> None:
    current = _current_deck(context)
    if not current:
        return
    deck_id, deck_name = current
    core = _core()
    core._clear_deck_profile(deck_id)
    _push_state(_state(deck_id, deck_name))
    _supported, status = core._apply_native_settings(
        filename=core._current_audio_filename()
    )
    if status:
        core._push_status(status)


def _open_settings_dialog() -> None:
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
        QVBoxLayout,
        QWidget,
        qconnect,
    )

    lang = _lang()
    conf = _conf()
    dialog = QDialog(mw)
    dialog.setWindowTitle(t(lang, "settings_title"))
    dialog.setMinimumWidth(470)
    layout = QVBoxLayout(dialog)

    form = QFormLayout()

    language = QComboBox(dialog)
    language.addItem("Automático / Automatic", "auto")
    language.addItem("English", "en")
    language.addItem("Português (Brasil)", "pt-BR")
    language_index = language.findData(str(conf.get("language", "auto")))
    language.setCurrentIndex(language_index if language_index >= 0 else 0)
    form.addRow(t(lang, "settings_language"), language)

    target = QDoubleSpinBox(dialog)
    target.setRange(-50.0, -20.0)
    target.setDecimals(0)
    target.setSingleStep(1.0)
    target.setSuffix(" LUFS")
    target.setValue(max(-50.0, min(-20.0, float(conf.get("loudness_target", -24.0)))))
    form.addRow(t(lang, "target_loudness"), target)

    dual_mono = QCheckBox(t(lang, "dual_mono"), dialog)
    dual_mono.setChecked(bool(conf.get("dual_mono", False)))
    form.addRow("", dual_mono)

    use_profile = QCheckBox(t(lang, "use_analyzed_profile"), dialog)
    use_profile.setChecked(bool(conf.get("deck_profile_enabled", False)))
    form.addRow("", use_profile)

    backend = QComboBox(dialog)
    backend.addItem(t(lang, "analysis_auto"), "auto")
    backend.addItem(t(lang, "analysis_ffmpeg"), "ffmpeg")
    backend.addItem(t(lang, "analysis_webaudio"), "webaudio")
    backend_index = backend.findData(str(conf.get("analysis_backend", "auto")))
    backend.setCurrentIndex(backend_index if backend_index >= 0 else 0)
    form.addRow(t(lang, "analysis_method"), backend)

    insert_template = QCheckBox(t(lang, "insert_normalized_template"), dialog)
    insert_template.setChecked(bool(conf.get("normalized_audio_insert_template", True)))
    form.addRow("", insert_template)
    layout.addLayout(form)

    ffmpeg_group = QGroupBox(t(lang, "settings_ffmpeg"), dialog)
    ffmpeg_layout = QHBoxLayout(ffmpeg_group)
    ffmpeg_state = _ffmpeg_state()
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
    ffmpeg_layout.addWidget(ffmpeg_label, 1)
    ffmpeg_layout.addWidget(install_button)
    layout.addWidget(ffmpeg_group)

    def apply_settings() -> None:
        updated = _conf()
        updated["language"] = str(language.currentData() or "auto")
        updated["loudness_target"] = float(target.value())
        updated["dual_mono"] = bool(dual_mono.isChecked())
        updated["deck_profile_enabled"] = bool(use_profile.isChecked())
        selected_backend = str(backend.currentData() or "auto")
        updated["analysis_backend"] = (
            selected_backend if selected_backend in {"auto", "ffmpeg", "webaudio"} else "auto"
        )
        updated["normalized_audio_insert_template"] = bool(insert_template.isChecked())
        mw.addonManager.writeConfig(__package__, updated)

        core = _core()
        _supported, status = core._apply_native_settings(
            filename=core._current_audio_filename(),
            update_filters=True,
        )
        if status:
            core._push_status(status)
        current = _current_deck()
        if current:
            _push_state(_state(*current))

    def install_ffmpeg_from_dialog() -> None:
        _install_ffmpeg()
        ffmpeg_label.setText(t(lang, "ffmpeg_installing_ui"))
        install_button.setEnabled(False)

    qconnect(install_button.clicked, install_ffmpeg_from_dialog)

    actions_group = QGroupBox(t(lang, "settings_current_deck"), dialog)
    actions_layout = QVBoxLayout(actions_group)
    reviewer = _active_reviewer()
    current = _current_deck(reviewer) if reviewer else None
    if current:
        deck_label = QLabel(current[1], actions_group)
        deck_label.setWordWrap(True)
        actions_layout.addWidget(deck_label)
    else:
        hint = QLabel(t(lang, "settings_no_active_deck"), actions_group)
        hint.setWordWrap(True)
        actions_layout.addWidget(hint)

    analyze_button = QPushButton(t(lang, "analyze_deck"), actions_group)
    prepare_button = QPushButton(t(lang, "prepare_normalized_field"), actions_group)
    materialize_button = QPushButton(t(lang, "materialize_audio"), actions_group)
    clear_button = QPushButton(t(lang, "settings_clear_profile"), actions_group)
    for button in (analyze_button, prepare_button, materialize_button, clear_button):
        button.setEnabled(reviewer is not None)
        actions_layout.addWidget(button)
    layout.addWidget(actions_group)

    def run_action(action) -> None:
        if reviewer is None:
            return
        apply_settings()
        action(reviewer)

    qconnect(analyze_button.clicked, lambda: run_action(_start_analysis))
    qconnect(prepare_button.clicked, lambda: run_action(_prepare_normalized_field_setup))
    qconnect(materialize_button.clicked, lambda: run_action(_start_materialization))
    qconnect(clear_button.clicked, lambda: run_action(_clear_current_deck_profile))

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        parent=dialog,
    )

    def save_and_close() -> None:
        apply_settings()
        dialog.accept()

    qconnect(buttons.accepted, save_and_close)
    qconnect(buttons.rejected, dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


def _register_tools_menu() -> None:
    from aqt.qt import QAction, QMenu, qconnect

    if getattr(mw, "_balanced_audio_tools_menu", None) is not None:
        return
    menu = QMenu("Balanced Audio Controller", mw)
    settings_action = QAction(t(_lang(), "settings_menu_action"), mw)
    qconnect(settings_action.triggered, _open_settings_dialog)
    menu.addAction(settings_action)
    mw.form.menuTools.addMenu(menu)
    mw._balanced_audio_tools_menu = menu
    mw._balanced_audio_settings_action = settings_action

'''

v010 = replace_once(v010, '\ndef _on_web_content(web_content: WebContent, context: object | None) -> None:\n', settings_code + '\ndef _on_web_content(web_content: WebContent, context: object | None) -> None:\n', 'inserção do diálogo')
v010 = replace_once(
    v010,
    '\ngui_hooks.webview_will_set_content.append(_on_web_content)\n',
    '\n_register_tools_menu()\n\ngui_hooks.webview_will_set_content.append(_on_web_content)\n',
    'registro do menu Ferramentas',
)
v010_path.write_text(v010, encoding='utf-8')

# 4) Traduções do menu/configurações nativas.
i18n_path = ROOT / 'i18n.py'
i18n = i18n_path.read_text(encoding='utf-8')
i18n = replace_once(
    i18n,
    '        "clear": "Clear",\n',
    '        "clear": "Clear",\n        "settings_menu_action": "Settings...",\n        "settings_title": "Balanced Audio Controller settings",\n        "settings_language": "Language",\n        "settings_ffmpeg": "FFmpeg",\n        "settings_current_deck": "Current deck actions",\n        "settings_no_active_deck": "Open a card in the reviewer to use these actions.",\n        "settings_clear_profile": "Clear analyzed profile",\n',
    'traduções EN de configuração',
)
i18n = replace_once(
    i18n,
    '        "clear": "Limpar",\n',
    '        "clear": "Limpar",\n        "settings_menu_action": "Configurações...",\n        "settings_title": "Configurações do Balanced Audio Controller",\n        "settings_language": "Idioma",\n        "settings_ffmpeg": "FFmpeg",\n        "settings_current_deck": "Ações do deck atual",\n        "settings_no_active_deck": "Abra um card no revisor para usar estas ações.",\n        "settings_clear_profile": "Limpar perfil analisado",\n',
    'traduções PT de configuração',
)
i18n_path.write_text(i18n, encoding='utf-8')

# 5) Playwright acompanha a nova UI compacta.
test_path = ROOT / 'tests' / 'test_audio_controller_playwright.py'
test = test_path.read_text(encoding='utf-8')
test = replace_once(test, '        page.wait_for_selector(".fac-analysis-backend")\n', '        page.wait_for_selector(".fac-panel-toggle")\n', 'seletor de montagem')

test = sub_once(
    test,
    r'''    def test_backend_controls_and_install_command\(self\) -> None:.*?    def test_panel_can_minimize_and_expand\(self\) -> None:''',
    '''    def test_reviewer_panel_keeps_only_study_controls(self) -> None:\n        page = self.page_with_config(base_config())\n        try:\n            for selector in (\n                ".fac-speed",\n                ".fac-volume",\n                ".fac-normalize",\n                ".fac-deck-badge",\n                ".fac-deck-name",\n                ".fac-analyze-deck",\n            ):\n                self.assertTrue(page.locator(selector).is_visible(), selector)\n\n            for selector in (\n                ".fac-loudness",\n                ".fac-dual-mono",\n                ".fac-deck-enable",\n                ".fac-clear-deck",\n                ".fac-analysis-backend",\n                ".fac-install-ffmpeg",\n                ".fac-prepare-normalized-field",\n                ".fac-materialize-normalized",\n                ".fac-materialize-template",\n            ):\n                self.assertEqual(page.locator(selector).count(), 0, selector)\n\n            page.evaluate("window.__pycmdMessages=[]")\n            page.locator(".fac-analyze-deck").click()\n            self.assertIn("ferreis_audio:v010:analyze", page.evaluate("window.__pycmdMessages"))\n        finally:\n            page.close()\n\n    def test_panel_can_minimize_and_expand(self) -> None:''',
    'testes de controles avançados',
)

test = sub_once(
    test,
    r'''\n    def test_loudness_slider_commits_only_on_change\(self\) -> None:.*?\n    def test_prepare_field_and_html_does_not_require_ffmpeg\(self\) -> None:''',
    '''\n    def test_normalization_toggle_remains_in_quick_panel(self) -> None:\n        page = self.page_with_config(base_config())\n        try:\n            page.evaluate("window.__pycmdMessages=[]")\n            checkbox = page.locator(".fac-normalize")\n            checkbox.uncheck()\n            self.assertIn(\n                "ferreis_audio:set:normalize:0",\n                page.evaluate("window.__pycmdMessages"),\n            )\n        finally:\n            page.close()\n\n    def test_prepare_field_and_html_does_not_require_ffmpeg(self) -> None:''',
    'teste antigo de loudness',
)

test = sub_once(
    test,
    r'''\n    def test_prepare_field_and_html_does_not_require_ffmpeg\(self\) -> None:.*?\n    def test_materialize_controls_require_profile_and_ffmpeg\(self\) -> None:.*?        finally:\n            page\.close\(\)\n''',
    '\n',
    'testes de ações avançadas removidas do painel',
)
test_path.write_text(test, encoding='utf-8')

# 6) Documentação curta da nova organização.
readme_path = ROOT / 'README.md'
readme = readme_path.read_text(encoding='utf-8')
marker = '## Materialized normalized audio / Áudio normalizado materializado\n'
if marker not in readme:
    raise RuntimeError('seção de áudio materializado não encontrada no README')
intro = '''## Compact reviewer panel / Painel compacto no revisor\n\nThe reviewer panel intentionally keeps only the controls used while studying: speed, volume, real-time normalization, deck-profile status and **Analyze deck**. Advanced options and maintenance actions are available under **Tools → Balanced Audio Controller → Settings**.\n\nO painel do revisor mantém somente os controles usados durante o estudo: velocidade, volume, normalização em tempo real, status do perfil e **Analisar deck**. As opções avançadas e ações de manutenção ficam em **Ferramentas → Balanced Audio Controller → Configurações**.\n\n'''
readme = readme.replace(marker, intro + marker, 1)
readme_path.write_text(readme, encoding='utf-8')

print('Painel enxuto e configurações em Ferramentas aplicados.')

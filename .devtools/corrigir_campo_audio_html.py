from __future__ import annotations

from pathlib import Path

ROOT = Path('.')


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding='utf-8')
    if old not in source:
        raise SystemExit(f'{label}: trecho não encontrado em {path}')
    path.write_text(source.replace(old, new, 1), encoding='utf-8')


# 1) Helpers puros para detectar em qual lado do template o áudio original é usado.
path = ROOT / 'normalized_audio.py'
source = path.read_text(encoding='utf-8')
anchor = '''def template_block(field_name: str) -> str:\n'''
addition = '''def template_references_field(html: str, field_name: str) -> bool:\n    field = _validated_field_name(field_name)\n    pattern = re.compile(\n        r"\\{\\{\\s*(?:[#/^]\\s*)?" + re.escape(field) + r"\\s*\\}\\}",\n    )\n    return bool(pattern.search(str(html or "")))\n\n\ndef template_sides_for_fields(\n    template: dict[str, Any], field_names: Iterable[str]\n) -> tuple[str, ...]:\n    fields = [str(name).strip() for name in field_names if str(name).strip()]\n    sides: list[str] = []\n    for side in ("qfmt", "afmt"):\n        html = str(template.get(side, ""))\n        if any(template_references_field(html, field) for field in fields):\n            sides.append(side)\n    return tuple(sides)\n\n\n'''
if addition.strip() not in source:
    if anchor not in source:
        raise SystemExit('normalized_audio: anchor template_block ausente')
    source = source.replace(anchor, addition + anchor, 1)
    path.write_text(source, encoding='utf-8')


# 2) Backend: criar campo independentemente do FFmpeg e inserir na mesma face do áudio original.
path = ROOT / 'v010.py'
source = path.read_text(encoding='utf-8')
source = source.replace(
    '''    remove_template_block,\n    render_normalized_audio,\n    upsert_template_block,\n)\n''',
    '''    remove_template_block,\n    render_normalized_audio,\n    template_sides_for_fields,\n    upsert_template_block,\n)\n''',
    1,
)

old_state = '''        materialized = profile.get("materialized")\n        if isinstance(materialized, dict):\n            state["materialized_audio_count"] = int(materialized.get("audio_count", 0) or 0)\n            state["materialized_note_count"] = int(materialized.get("note_count", 0) or 0)\n            state["materialized_at"] = materialized.get("created_at")\n'''
new_state = '''        field_setup = profile.get("normalized_field_setup")\n        if isinstance(field_setup, dict):\n            setup_fields = field_setup.get("fields", {})\n            if isinstance(setup_fields, dict):\n                names = sorted({str(name) for name in setup_fields.values() if str(name)})\n                state["normalized_field_count"] = len(names)\n                state["normalized_field_names"] = names\n            state["normalized_template_count"] = int(field_setup.get("template_count", 0) or 0)\n            state["normalized_field_setup_at"] = field_setup.get("updated_at")\n        materialized = profile.get("materialized")\n        if isinstance(materialized, dict):\n            state["materialized_audio_count"] = int(materialized.get("audio_count", 0) or 0)\n            state["materialized_note_count"] = int(materialized.get("note_count", 0) or 0)\n            state["materialized_at"] = materialized.get("created_at")\n'''
if old_state not in source:
    raise SystemExit('v010: bloco state não encontrado')
source = source.replace(old_state, new_state, 1)

old_collect_init = '''    note_cache: dict[int, Any] = {}\n    notes: dict[int, dict[str, Any]] = {}\n    template_ords: dict[int, set[int]] = {}\n\n    for card_id in card_ids:\n'''
new_collect_init = '''    note_cache: dict[int, Any] = {}\n    notes: dict[int, dict[str, Any]] = {}\n    template_ords: dict[int, set[int]] = {}\n    source_fields: dict[int, set[str]] = {}\n    model_fields: dict[int, list[str]] = {}\n\n    for card_id in card_ids:\n'''
if old_collect_init not in source:
    raise SystemExit('v010: inicialização do plano não encontrada')
source = source.replace(old_collect_init, new_collect_init, 1)

old_collect_body = '''        relevant = extract_sound_filenames(note.fields) & profile_files\n        if not relevant:\n            continue\n        mid = int(note.mid)\n        item = notes.setdefault(note_id, {"mid": mid, "sources": set()})\n        item["sources"].update(relevant)\n        template_ords.setdefault(mid, set()).add(int(card.ord))\n'''
new_collect_body = '''        mid = int(note.mid)\n        field_names = model_fields.get(mid)\n        if field_names is None:\n            model = mw.col.models.get(mid)\n            if not model:\n                continue\n            field_names = [str(field.get("name", "")) for field in model.get("flds", [])]\n            model_fields[mid] = field_names\n\n        relevant: set[str] = set()\n        relevant_fields: set[str] = set()\n        for index, value in enumerate(note.fields):\n            matches = extract_sound_filenames([value]) & profile_files\n            if not matches:\n                continue\n            relevant.update(matches)\n            if index < len(field_names) and field_names[index]:\n                relevant_fields.add(field_names[index])\n\n        if not relevant:\n            continue\n        item = notes.setdefault(note_id, {"mid": mid, "sources": set()})\n        item["sources"].update(relevant)\n        source_fields.setdefault(mid, set()).update(relevant_fields)\n        template_ords.setdefault(mid, set()).add(int(card.ord))\n'''
if old_collect_body not in source:
    raise SystemExit('v010: corpo de coleta não encontrado')
source = source.replace(old_collect_body, new_collect_body, 1)

old_collect_return = '''        "template_ords": {mid: sorted(ords) for mid, ords in template_ords.items()},\n        "sources": sorted(\n'''
new_collect_return = '''        "template_ords": {mid: sorted(ords) for mid, ords in template_ords.items()},\n        "source_fields": {mid: sorted(fields, key=str.casefold) for mid, fields in source_fields.items()},\n        "sources": sorted(\n'''
if old_collect_return not in source:
    raise SystemExit('v010: retorno do plano não encontrado')
source = source.replace(old_collect_return, new_collect_return, 1)

start = source.index('def _apply_materialization(\n')
updated_notes_marker = source.index('    updated_notes = 0\n', start)
header_and_setup = source[start:updated_notes_marker]
new_helpers_and_header = '''def _previous_normalized_fields(profile: dict[str, Any]) -> dict[str, str]:\n    setup = profile.get("normalized_field_setup")\n    if isinstance(setup, dict) and isinstance(setup.get("fields"), dict):\n        return {str(key): str(value) for key, value in setup["fields"].items()}\n    materialized = profile.get("materialized")\n    if isinstance(materialized, dict) and isinstance(materialized.get("fields"), dict):\n        return {str(key): str(value) for key, value in materialized["fields"].items()}\n    return {}\n\n\ndef _template_targets_for_model(\n    model: dict[str, Any], ords: list[int], source_fields: list[str]\n) -> dict[str, list[str]]:\n    templates = model.get("tmpls", [])\n    targets: dict[str, list[str]] = {}\n    for raw_ord in ords:\n        if not templates:\n            continue\n        template_index = raw_ord if 0 <= raw_ord < len(templates) else 0\n        template = templates[template_index]\n        sides = list(template_sides_for_fields(template, source_fields))\n        # Compatibilidade: quando não for possível detectar a referência original,\n        # mantém o comportamento seguro anterior e usa o verso.\n        if not sides:\n            sides = ["afmt"]\n        targets[str(template_index)] = sides\n    return targets\n\n\ndef _ensure_normalized_fields_and_templates(\n    plan: dict[str, Any], insert_template: bool, profile: dict[str, Any]\n) -> tuple[dict[str, str], int, int, dict[str, dict[str, list[str]]]]:\n    notes = plan["notes"]\n    by_mid: dict[int, list[int]] = {}\n    for note_id, item in notes.items():\n        by_mid.setdefault(int(item["mid"]), []).append(int(note_id))\n\n    previous_fields = _previous_normalized_fields(profile)\n    fields: dict[str, str] = {}\n    created_fields = 0\n    template_changes = 0\n    all_targets: dict[str, dict[str, list[str]]] = {}\n\n    for mid, note_ids in by_mid.items():\n        model = mw.col.models.get(mid)\n        if not model:\n            continue\n        previous = previous_fields.get(str(mid))\n        field_name, create_field = _choose_normalized_field(model, note_ids, previous)\n        changed = False\n        if create_field:\n            mw.col.models.add_field(model, mw.col.models.new_field(field_name))\n            created_fields += 1\n            changed = True\n\n        targets = _template_targets_for_model(\n            model,\n            plan["template_ords"].get(mid, []),\n            plan.get("source_fields", {}).get(mid, []),\n        )\n        all_targets[str(mid)] = targets\n        templates = model.get("tmpls", [])\n        for raw_index, sides in targets.items():\n            template_index = int(raw_index)\n            if template_index < 0 or template_index >= len(templates):\n                continue\n            template = templates[template_index]\n            for side in ("qfmt", "afmt"):\n                current = str(template.get(side, ""))\n                cleaned = remove_template_block(current)\n                updated = (\n                    upsert_template_block(cleaned, field_name)\n                    if insert_template and side in sides\n                    else cleaned\n                )\n                if updated != current:\n                    template[side] = updated\n                    template_changes += 1\n                    changed = True\n        if changed:\n            mw.col.models.update_dict(model)\n        fields[str(mid)] = field_name\n\n    return fields, created_fields, template_changes, all_targets\n\n\ndef _store_field_setup(\n    deck_id: int,\n    profile: dict[str, Any],\n    fields: dict[str, str],\n    insert_template: bool,\n    targets: dict[str, dict[str, list[str]]],\n) -> dict[str, Any]:\n    core = _core()\n    current_profile = core._get_deck_profile(deck_id) or dict(profile)\n    template_count = (\n        sum(len(sides) for by_template in targets.values() for sides in by_template.values())\n        if insert_template\n        else 0\n    )\n    current_profile["normalized_field_setup"] = {\n        "version": 1,\n        "updated_at": datetime.now(timezone.utc).isoformat(),\n        "fields": fields,\n        "insert_template": bool(insert_template),\n        "template_count": template_count,\n        "targets": targets,\n    }\n    core._set_deck_profile(deck_id, current_profile)\n    return current_profile\n\n\ndef _apply_materialization(\n    deck_id: int,\n    deck_name: str,\n    plan: dict[str, Any],\n    generated: dict[str, str],\n    insert_template: bool,\n    profile: dict[str, Any],\n) -> tuple[int, dict[str, str]]:\n    notes = plan["notes"]\n    fields, _created_fields, _template_changes, targets = _ensure_normalized_fields_and_templates(\n        plan, insert_template, profile\n    )\n    current_profile = _store_field_setup(\n        deck_id, profile, fields, insert_template, targets\n    )\n\n'''
source = source[:start] + new_helpers_and_header + source[updated_notes_marker:]

old_profile_update = '''    refreshed = core = _core()\n    current_profile = core._get_deck_profile(deck_id) or dict(profile)\n    current_profile["materialized"] = {\n'''
new_profile_update = '''    core = _core()\n    current_profile = core._get_deck_profile(deck_id) or current_profile\n    current_profile["materialized"] = {\n'''
if old_profile_update not in source:
    raise SystemExit('v010: atualização materialized não encontrada')
source = source.replace(old_profile_update, new_profile_update, 1)

marker = '''def _start_materialization(context) -> None:\n'''
prepare_function = '''def _prepare_normalized_field_setup(context) -> None:\n    core = _core()\n    current = _current_deck(context)\n    if not current:\n        return\n    deck_id, deck_name = current\n    lang = _lang()\n    if core._analysis_is_running(deck_id) or _state(deck_id, deck_name).get("materializing"):\n        return\n\n    profile = core._get_deck_profile(deck_id)\n    if not isinstance(profile, dict) or not profile.get("files"):\n        state = _state(deck_id, deck_name)\n        state["error"] = t(lang, "field_setup_profile_required")\n        _push_state(state)\n        return\n\n    plan = _collect_materialization_plan(deck_id, profile)\n    if not plan["notes"]:\n        state = _state(deck_id, deck_name)\n        state["error"] = t(lang, "field_setup_no_linked_audio")\n        _push_state(state)\n        return\n\n    insert_template = bool(_conf().get("normalized_audio_insert_template", True))\n    fields, _created, _changes, targets = _ensure_normalized_fields_and_templates(\n        plan, insert_template, profile\n    )\n    _store_field_setup(deck_id, profile, fields, insert_template, targets)\n    template_count = (\n        sum(len(sides) for by_template in targets.values() for sides in by_template.values())\n        if insert_template\n        else 0\n    )\n    state = _state(deck_id, deck_name)\n    state["message"] = t(\n        lang,\n        "field_setup_done",\n        fields=len(set(fields.values())),\n        templates=template_count,\n    )\n    _push_state(state)\n\n\n'''
if prepare_function.strip() not in source:
    if marker not in source:
        raise SystemExit('v010: marcador _start_materialization ausente')
    source = source.replace(marker, prepare_function + marker, 1)

old_handler = '''    if message == "ferreis_audio:v010:materialize":\n        _start_materialization(context); return (True, None)\n'''
new_handler = '''    if message == "ferreis_audio:v010:prepare-field":\n        _prepare_normalized_field_setup(context); return (True, None)\n    if message == "ferreis_audio:v010:materialize":\n        _start_materialization(context); return (True, None)\n'''
if old_handler not in source:
    raise SystemExit('v010: handler materialize não encontrado')
source = source.replace(old_handler, new_handler, 1)
path.write_text(source, encoding='utf-8')


# 3) Interface: ação separada e explícita para criar o input/campo e atualizar HTML.
path = ROOT / 'web' / 'audio_controller_v010.js'
source = path.read_text(encoding='utf-8')
old_markup = '''        <label class="fac-check-row fac-materialize-template-wrap" title="${t("insert_normalized_template_hint")}">\n          <input class="fac-materialize-template" type="checkbox">\n          <span>${t("insert_normalized_template")}</span>\n        </label>\n        <button class="fac-action fac-materialize-normalized" type="button">${t("materialize_audio")}</button>\n        <div class="fac-materialize-note"></div>\n'''
new_markup = '''        <label class="fac-check-row fac-materialize-template-wrap" title="${t("insert_normalized_template_hint")}">\n          <input class="fac-materialize-template" type="checkbox">\n          <span>${t("insert_normalized_template")}</span>\n        </label>\n        <button class="fac-action fac-prepare-normalized-field" type="button">${t("prepare_normalized_field")}</button>\n        <div class="fac-field-setup-note"></div>\n        <button class="fac-action fac-materialize-normalized" type="button">${t("materialize_audio")}</button>\n        <div class="fac-materialize-note"></div>\n'''
if old_markup not in source:
    raise SystemExit('js: markup materialize não encontrado')
source = source.replace(old_markup, new_markup, 1)

old_listener = '''      this.root.querySelector(".fac-materialize-normalized").addEventListener("click", () => {\n        this.state.materializing = true;\n        this.updateState(this.state);\n        pycmd("ferreis_audio:v010:materialize");\n      });\n'''
new_listener = '''      this.root.querySelector(".fac-prepare-normalized-field").addEventListener("click", () => {\n        pycmd("ferreis_audio:v010:prepare-field");\n      });\n      this.root.querySelector(".fac-materialize-normalized").addEventListener("click", () => {\n        this.state.materializing = true;\n        this.updateState(this.state);\n        pycmd("ferreis_audio:v010:materialize");\n      });\n'''
if old_listener not in source:
    raise SystemExit('js: listener materialize não encontrado')
source = source.replace(old_listener, new_listener, 1)

old_locators = '''      const materialize = this.root.querySelector(".fac-materialize-normalized");\n      const materializeTemplate = this.root.querySelector(".fac-materialize-template");\n      const materializeNote = this.root.querySelector(".fac-materialize-note");\n      if (!select || !status || !install || !note || !materialize || !materializeTemplate || !materializeNote) return;\n'''
new_locators = '''      const prepareField = this.root.querySelector(".fac-prepare-normalized-field");\n      const fieldSetupNote = this.root.querySelector(".fac-field-setup-note");\n      const materialize = this.root.querySelector(".fac-materialize-normalized");\n      const materializeTemplate = this.root.querySelector(".fac-materialize-template");\n      const materializeNote = this.root.querySelector(".fac-materialize-note");\n      if (!select || !status || !install || !note || !prepareField || !fieldSetupNote || !materialize || !materializeTemplate || !materializeNote) return;\n'''
if old_locators not in source:
    raise SystemExit('js: locators materialize não encontrados')
source = source.replace(old_locators, new_locators, 1)

old_state_controls = '''      materializeTemplate.checked = this.state.insert_normalized_template !== false;\n      materializeTemplate.disabled = Boolean(this.state.materializing || this.state.analyzing);\n      materialize.disabled = Boolean(\n'''
new_state_controls = '''      materializeTemplate.checked = this.state.insert_normalized_template !== false;\n      materializeTemplate.disabled = Boolean(this.state.materializing || this.state.analyzing);\n      prepareField.disabled = Boolean(\n        this.state.materializing ||\n        this.state.analyzing ||\n        !this.state.exists\n      );\n      prepareField.textContent = t("prepare_normalized_field");\n      if (Number(this.state.normalized_field_count || 0) > 0) {\n        fieldSetupNote.textContent = t("normalized_field_ready", {\n          fields: Number(this.state.normalized_field_count || 0),\n          templates: Number(this.state.normalized_template_count || 0),\n        });\n      } else {\n        fieldSetupNote.textContent = t("prepare_normalized_field_hint");\n      }\n      materialize.disabled = Boolean(\n'''
if old_state_controls not in source:
    raise SystemExit('js: state controls não encontrado')
source = source.replace(old_state_controls, new_state_controls, 1)
path.write_text(source, encoding='utf-8')


# 4) Traduções.
path = ROOT / 'i18n.py'
source = path.read_text(encoding='utf-8')
source = source.replace(
    '        "materialize_audio": "Create normalized copies",\n',
    '        "prepare_normalized_field": "Create audio field + update card HTML",\n'
    '        "prepare_normalized_field_hint": "Creates/reuses a dedicated normalized-audio field and inserts it on the same card side where the original audio field is used. No FFmpeg is required for this step.",\n'
    '        "normalized_field_ready": "{fields} normalized-audio field(s) ready; inserted in {templates} template side(s).",\n'
    '        "field_setup_profile_required": "Analyze the deck before creating the normalized-audio field.",\n'
    '        "field_setup_no_linked_audio": "No analyzed audio could be matched to note fields in this deck.",\n'
    '        "field_setup_done": "Normalized-audio field ready: {fields} field(s), {templates} template side(s) updated.",\n'
    '        "materialize_audio": "Create normalized copies",\n',
    1,
)
source = source.replace(
    '        "insert_normalized_template": "Insert normalized audio on card back",\n'
    '        "insert_normalized_template_hint": "Adds the dedicated normalized-audio field to the back template of affected card types.",\n',
    '        "insert_normalized_template": "Insert normalized field in card HTML",\n'
    '        "insert_normalized_template_hint": "Inserts the normalized-audio field on the same side (front/back) where the original audio field is already referenced.",\n',
    1,
)
source = source.replace(
    '        "materialize_audio": "Criar cópias normalizadas",\n',
    '        "prepare_normalized_field": "Criar campo de áudio + atualizar HTML",\n'
    '        "prepare_normalized_field_hint": "Cria/reutiliza um campo próprio de áudio normalizado e o insere na mesma face do card onde o campo de áudio original é usado. Esta etapa não exige FFmpeg.",\n'
    '        "normalized_field_ready": "{fields} campo(s) de áudio normalizado pronto(s); inserido(s) em {templates} face(s) de template.",\n'
    '        "field_setup_profile_required": "Analise o deck antes de criar o campo de áudio normalizado.",\n'
    '        "field_setup_no_linked_audio": "Nenhum áudio analisado pôde ser associado aos campos das notas deste deck.",\n'
    '        "field_setup_done": "Campo de áudio normalizado pronto: {fields} campo(s), {templates} face(s) de template atualizada(s).",\n'
    '        "materialize_audio": "Criar cópias normalizadas",\n',
    1,
)
source = source.replace(
    '        "insert_normalized_template": "Inserir áudio normalizado no verso do card",\n'
    '        "insert_normalized_template_hint": "Adiciona o campo de áudio normalizado ao template do verso dos tipos de card afetados.",\n',
    '        "insert_normalized_template": "Inserir campo normalizado no HTML do card",\n'
    '        "insert_normalized_template_hint": "Insere o campo de áudio normalizado na mesma face (frente/verso) em que o campo de áudio original já é referenciado.",\n',
    1,
)
web_anchor = '    "materialize_audio",\n'
web_add = (
    '    "prepare_normalized_field",\n'
    '    "prepare_normalized_field_hint",\n'
    '    "normalized_field_ready",\n'
    '    "field_setup_profile_required",\n'
    '    "field_setup_no_linked_audio",\n'
    '    "field_setup_done",\n'
    + web_anchor
)
if '    "prepare_normalized_field",\n' not in source:
    if web_anchor not in source:
        raise SystemExit('i18n: WEB_TRANSLATION_KEYS anchor ausente')
    source = source.replace(web_anchor, web_add, 1)
path.write_text(source, encoding='utf-8')


# 5) Configuração: refletir a nova semântica frente/verso.
path = ROOT / 'config.schema.json'
source = path.read_text(encoding='utf-8')
source = source.replace(
    '"title": "Insert normalized audio on card back / Inserir áudio normalizado no verso do card",\n      "description": "When materializing normalized copies, add the dedicated BAC normalized-audio field to affected card back templates. / Ao materializar cópias normalizadas, adiciona o campo dedicado de áudio normalizado do BAC aos templates do verso dos cards afetados."',
    '"title": "Insert normalized audio in card HTML / Inserir áudio normalizado no HTML do card",\n      "description": "Insert the dedicated BAC normalized-audio field on the same card side where the original audio field is referenced. / Insere o campo dedicado de áudio normalizado do BAC na mesma face do card em que o campo de áudio original é referenciado."',
    1,
)
path.write_text(source, encoding='utf-8')


# 6) README.
path = ROOT / 'README.md'
source = path.read_text(encoding='utf-8')
source = source.replace(
    'and can automatically add that field to the back template of the affected card types.',
    'and can automatically add that field to the same template side (front or back) where the original audio field is used. A separate **Create audio field + update card HTML** action prepares the field/template even before physical audio copies are generated.',
    1,
)
source = source.replace(
    'e pode inserir automaticamente esse campo no template do verso dos tipos de card afetados.',
    'e pode inserir automaticamente esse campo na mesma face do template (frente ou verso) em que o áudio original é usado. A ação separada **Criar campo de áudio + atualizar HTML** prepara o campo/template mesmo antes de gerar as cópias físicas.',
    1,
)
path.write_text(source, encoding='utf-8')


# 7) Testes unitários dos templates.
path = ROOT / 'tests' / 'test_normalized_audio.py'
source = path.read_text(encoding='utf-8')
marker = '''    def test_render_uses_argument_list_and_shell_false(self) -> None:\n'''
test = '''    def test_detects_original_audio_side_in_template(self) -> None:\n        template = {\n            "qfmt": "<div>{{Áudio 2}}</div>",\n            "afmt": "{{FrontSide}}<hr>{{Meaning}}",\n        }\n        self.assertEqual(\n            normalized_audio.template_sides_for_fields(template, ["Áudio", "Áudio 2"]),\n            ("qfmt",),\n        )\n        self.assertTrue(\n            normalized_audio.template_references_field(template["qfmt"], "Áudio 2")\n        )\n        self.assertFalse(\n            normalized_audio.template_references_field(template["afmt"], "Áudio 2")\n        )\n\n'''
if 'test_detects_original_audio_side_in_template' not in source:
    if marker not in source:
        raise SystemExit('teste normalized_audio: marcador ausente')
    source = source.replace(marker, test + marker, 1)
path.write_text(source, encoding='utf-8')


# 8) Playwright: botão explícito deve funcionar sem FFmpeg.
path = ROOT / 'tests' / 'test_audio_controller_playwright.py'
source = path.read_text(encoding='utf-8')
source = source.replace(
    '    "materialize_audio": "Create normalized copies",\n',
    '    "prepare_normalized_field": "Create audio field + update card HTML",\n'
    '    "prepare_normalized_field_hint": "Prepare field",\n'
    '    "normalized_field_ready": "{fields} field(s), {templates} template side(s)",\n'
    '    "field_setup_profile_required": "Analyze first",\n'
    '    "field_setup_no_linked_audio": "No linked audio",\n'
    '    "field_setup_done": "Field ready",\n'
    '    "materialize_audio": "Create normalized copies",\n',
    1,
)
source = source.replace(
    '    "insert_normalized_template": "Insert normalized audio on card back",\n',
    '    "insert_normalized_template": "Insert normalized field in card HTML",\n',
    1,
)
marker = '''    def test_materialize_controls_require_profile_and_ffmpeg(self) -> None:\n'''
playwright_test = '''    def test_prepare_field_and_html_does_not_require_ffmpeg(self) -> None:\n        page = self.page_with_config(base_config())\n        try:\n            prepare = page.locator(".fac-prepare-normalized-field")\n            materialize = page.locator(".fac-materialize-normalized")\n            self.assertTrue(prepare.is_disabled())\n            self.assertTrue(materialize.is_disabled())\n\n            page.evaluate(\n                """window.BACV010.updateState({\n                    exists: true,\n                    stale: false,\n                    ffmpeg: { available: false, installing: false, installer_available: true },\n                    insert_normalized_template: true\n                })"""\n            )\n            self.assertFalse(prepare.is_disabled())\n            self.assertTrue(materialize.is_disabled())\n\n            page.evaluate("window.__pycmdMessages=[]")\n            prepare.click()\n            self.assertIn(\n                "ferreis_audio:v010:prepare-field",\n                page.evaluate("window.__pycmdMessages"),\n            )\n\n            page.evaluate(\n                """window.BACV010.updateState({\n                    normalized_field_count: 1,\n                    normalized_template_count: 1\n                })"""\n            )\n            self.assertIn("1 field(s)", page.locator(".fac-field-setup-note").inner_text())\n        finally:\n            page.close()\n\n'''
if 'test_prepare_field_and_html_does_not_require_ffmpeg' not in source:
    if marker not in source:
        raise SystemExit('playwright: marcador materialize ausente')
    source = source.replace(marker, playwright_test + marker, 1)
path.write_text(source, encoding='utf-8')

print('Correção de campo/HTML aplicada.')

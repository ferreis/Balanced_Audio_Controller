from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"{path}: padrão não encontrado: {label}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "__init__.py",
    "    profile, entry = _profile_entry_for_current_deck(filename, conf, deck_id)\n",
    """    if deck_id is None:\n        profile, entry = _profile_entry_for_current_deck(filename, conf)\n    else:\n        profile, entry = _profile_entry_for_current_deck(filename, conf, deck_id)\n""",
    "compatibilidade da busca de perfil",
)

replace_once(
    "web/audio_controller_v010.js",
    """    state: {},\n    mountedRoot: null,\n""",
    """    state: {},\n    mountedRoot: null,\n    minimizedState: null,\n""",
    "estado minimizado em memória",
)

replace_once(
    "web/audio_controller_v010.js",
    """    readMinimizedState() {\n      try {\n""",
    """    readMinimizedState() {\n      if (typeof this.minimizedState === \"boolean\") return this.minimizedState;\n      try {\n""",
    "fallback de estado minimizado",
)

replace_once(
    "web/audio_controller_v010.js",
    """      const collapsed = Boolean(minimized);\n      panel.classList.toggle(\"fac-minimized\", collapsed);\n""",
    """      const collapsed = Boolean(minimized);\n      this.minimizedState = collapsed;\n      panel.classList.toggle(\"fac-minimized\", collapsed);\n""",
    "persistência em memória entre frente e verso",
)

replace_once(
    "tests/test_extension_loading.py",
    '        self.assertIn("def _open_settings_dialog()", source)\n',
    '        self.assertIn("def _open_settings_dialog(", source)\n',
    "assinatura do diálogo com contexto opcional",
)

print("Regressões do preview corrigidas.")

from pathlib import Path

root = Path('.')
i18n_path = root / 'i18n.py'
init_path = root / '__init__.py'
v010_path = root / 'v010.py'
test_path = root / 'tests' / 'test_extension_loading.py'

block = '''\n# v0.10 is loaded from i18n because this module is imported during add-on startup.\n# The extension registers only dev-branch hooks and leaves the stable playback core intact.\ntry:\n    from . import v010 as _v010  # noqa: F401,E402\nexcept Exception as _v010_error:\n    print("[Balanced Audio Controller] v0.10 extension load failed:", _v010_error)\n'''

i18n = i18n_path.read_text(encoding='utf-8')
if block in i18n:
    i18n = i18n.replace(block, '\n', 1)
    i18n_path.write_text(i18n, encoding='utf-8')

init = init_path.read_text(encoding='utf-8')
loader = '''\n\n# Carrega a extensão somente após o núcleo concluir a própria inicialização.\n# Isso evita importação circular entre __init__, i18n e v010.\ntry:\n    from . import v010 as _v010  # noqa: F401,E402\nexcept Exception as _v010_error:\n    print("[Balanced Audio Controller] v0.10 extension load failed:", _v010_error)\n'''
if 'from . import v010 as _v010' not in init:
    init = init.rstrip() + loader
    init_path.write_text(init, encoding='utf-8')

v010 = v010_path.read_text(encoding='utf-8')
v010 = v010.replace(
    '''    buttons = QDialogButtonBox(\n        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,\n        parent=dialog,\n    )''',
    '''    button_flags = (\n        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel\n    )\n    buttons = QDialogButtonBox(button_flags)''',
    1,
)
v010_path.write_text(v010, encoding='utf-8')

if not test_path.exists():
    test_path.write_text('''from __future__ import annotations\n\nimport unittest\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass ExtensionLoadingTests(unittest.TestCase):\n    def test_v010_loads_after_core_functions_are_defined(self) -> None:\n        init = (ROOT / "__init__.py").read_text(encoding="utf-8")\n        i18n = (ROOT / "i18n.py").read_text(encoding="utf-8")\n        self.assertNotIn("from . import v010 as _v010", i18n)\n        loader = init.rfind("from . import v010 as _v010")\n        self.assertGreater(loader, init.find("def _language"))\n        self.assertGreater(loader, init.find("gui_hooks.av_player_will_play.append"))\n\n    def test_settings_menu_registration_occurs_inside_v010(self) -> None:\n        source = (ROOT / "v010.py").read_text(encoding="utf-8")\n        self.assertIn("def _open_settings_dialog()", source)\n        self.assertIn("def _register_tools_menu()", source)\n        self.assertIn("mw.form.menuTools.addMenu(menu)", source)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8')

print('Ordem de carga da extensão corrigida.')

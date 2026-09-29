from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExtensionLoadingTests(unittest.TestCase):
    def test_v010_loads_after_core_functions_are_defined(self) -> None:
        init = (ROOT / "__init__.py").read_text(encoding="utf-8")
        i18n = (ROOT / "i18n.py").read_text(encoding="utf-8")
        self.assertNotIn("from . import v010 as _v010", i18n)
        loader = init.rfind("from . import v010 as _v010")
        self.assertGreater(loader, init.find("def _language"))
        self.assertGreater(loader, init.find("gui_hooks.av_player_will_play.append"))

    def test_settings_menu_registration_occurs_inside_v010(self) -> None:
        source = (ROOT / "v010.py").read_text(encoding="utf-8")
        self.assertIn("def _open_settings_dialog(", source)
        self.assertIn("def _register_tools_menu()", source)
        self.assertIn("mw.form.menuTools.addMenu(menu)", source)


if __name__ == "__main__":
    unittest.main()

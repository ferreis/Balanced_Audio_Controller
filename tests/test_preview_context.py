from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PreviewContextTests(unittest.TestCase):
    def test_core_supports_reviewer_previewer_and_card_layout(self) -> None:
        source = (ROOT / "__init__.py").read_text(encoding="utf-8")
        for expected in (
            '"previewQuestion": ("previewer", "question")',
            '"previewAnswer": ("previewer", "answer")',
            '"clayoutQuestion": ("card_layout", "question")',
            '"clayoutAnswer": ("card_layout", "answer")',
            'gui_hooks.av_player_will_play_tags.append(_on_av_player_will_play_tags)',
            '_current_audio_deck_id()',
        ):
            self.assertIn(expected, source)

    def test_v010_settings_and_actions_accept_preview_context(self) -> None:
        source = (ROOT / "v010.py").read_text(encoding="utf-8")
        self.assertIn('ferreis_audio:v010:settings', source)
        self.assertIn('core._is_supported_card_context(context)', source)
        self.assertIn('action_context', source)
        self.assertNotIn('context.web.eval(', source)


if __name__ == "__main__":
    unittest.main()

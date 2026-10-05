from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.test_audio_controller_playwright import base_config

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "web" / "audio_controller.js"
SCRIPT_V010 = ROOT / "web" / "audio_controller_v010.js"
SCRIPT_V011 = ROOT / "web" / "audio_controller_v011.js"


class AudioControllerV011PlaywrightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = sync_playwright().start()
        executable = (
            os.environ.get("BAC_CHROMIUM_EXECUTABLE")
            or shutil.which("chromium")
            or shutil.which("chromium-browser")
            or shutil.which("google-chrome")
        )
        kwargs = {"headless": True}
        if executable:
            kwargs["executable_path"] = executable
            kwargs["args"] = ["--no-sandbox"]
        try:
            cls.browser = cls.pw.chromium.launch(**kwargs)
        except Exception as exc:
            cls.pw.stop()
            raise unittest.SkipTest(f"Chromium/Playwright unavailable: {exc}")

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "browser", None):
            cls.browser.close()
        if getattr(cls, "pw", None):
            cls.pw.stop()

    def page_with_config(self, config: dict):
        page = self.browser.new_page()
        encoded = json.dumps(config).replace("&", "&amp;").replace('"', "&quot;")
        page.set_content(
            '<base href="http://127.0.0.1:8765/">'
            f'<div id="ferreis-audio-controller" data-config="{encoded}"></div>'
        )
        page.evaluate("window.__pycmdMessages=[]; window.pycmd=(m)=>window.__pycmdMessages.push(m);")
        page.add_script_tag(path=str(SCRIPT))
        page.evaluate("window.FerreisAnkiAudio.mount()")
        page.add_script_tag(path=str(SCRIPT_V010))
        page.add_script_tag(path=str(SCRIPT_V011))
        page.wait_for_selector(".fac-playback-mode-select")
        return page

    def test_mode_selector_switches_between_three_sources(self) -> None:
        page = self.page_with_config(base_config())
        try:
            selector = page.locator(".fac-playback-mode-select")
            self.assertTrue(selector.is_visible())
            self.assertEqual(selector.input_value(), "realtime")
            self.assertEqual(selector.locator("option").count(), 3)

            page.evaluate("window.__pycmdMessages=[]")
            selector.select_option("created")
            self.assertIn(
                "ferreis_audio:v011:mode:created",
                page.evaluate("window.__pycmdMessages"),
            )
            self.assertFalse(page.locator(".fac-normalize").is_checked())
            self.assertIn("generated normalized copy", page.locator(".fac-playback-mode-hint").inner_text())

            page.evaluate("window.BACV010.updateState({playback_mode: 'profile'})")
            self.assertEqual(selector.input_value(), "profile")
            self.assertIn("measured", page.locator(".fac-playback-mode-hint").inner_text())
        finally:
            page.close()

    def test_overvolume_switch_gain_and_backend_state_sync(self) -> None:
        page = self.page_with_config(base_config())
        try:
            enabled = page.locator(".fac-overvolume-enabled")
            gain = page.locator(".fac-overvolume-gain")
            value = page.locator(".fac-overvolume-value")

            self.assertTrue(enabled.is_visible())
            self.assertFalse(enabled.is_checked())
            self.assertTrue(gain.is_disabled())
            self.assertEqual(gain.input_value(), "6")
            self.assertEqual(value.inner_text(), "+6.0 dB")
            self.assertIn("still too quiet", page.locator(".fac-overvolume-hint").inner_text())

            page.evaluate("window.__pycmdMessages=[]")
            enabled.check()
            self.assertIn(
                "ferreis_audio:v011:overvolume:enabled:1",
                page.evaluate("window.__pycmdMessages"),
            )
            self.assertFalse(gain.is_disabled())

            page.evaluate(
                """() => {
                    const slider = document.querySelector('.fac-overvolume-gain');
                    slider.value = '9.5';
                    slider.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
            )
            self.assertIn(
                "ferreis_audio:v011:overvolume:gain:9.5",
                page.evaluate("window.__pycmdMessages"),
            )
            self.assertEqual(value.inner_text(), "+9.5 dB")

            page.evaluate(
                "window.BACV010.updateState({overvolume_enabled: false, overvolume_gain_db: 12})"
            )
            self.assertFalse(enabled.is_checked())
            self.assertTrue(gain.is_disabled())
            self.assertEqual(gain.input_value(), "12")
            self.assertEqual(value.inner_text(), "+12.0 dB")
        finally:
            page.close()

    def test_mode_selector_is_rebound_after_front_back_render(self) -> None:
        config = base_config()
        config.update({"surface": "previewer", "side": "question"})
        page = self.page_with_config(config)
        try:
            back = base_config()
            back.update({"surface": "previewer", "side": "answer"})
            page.evaluate(
                """config => {
                    const oldRoot = document.getElementById('ferreis-audio-controller');
                    const newRoot = document.createElement('div');
                    newRoot.id = 'ferreis-audio-controller';
                    newRoot.dataset.config = JSON.stringify(config);
                    oldRoot.replaceWith(newRoot);
                    window.FerreisAnkiAudio.mount();
                }""",
                back,
            )
            page.wait_for_selector(".fac-playback-mode-select")
            self.assertEqual(page.locator(".fac-playback-mode-select").count(), 1)
            self.assertEqual(page.locator(".fac-overvolume-block").count(), 1)
            self.assertTrue(
                page.evaluate(
                    "window.BACV011.root === document.getElementById('ferreis-audio-controller')"
                )
            )
        finally:
            page.close()

    def test_switching_mode_does_not_change_anki_replay_indices(self) -> None:
        page = self.page_with_config(base_config())
        try:
            page.evaluate(
                """() => {
                    const host = document.createElement('div');
                    host.id = 'anki-replay-fixture';
                    host.innerHTML = `
                      <a class="replay-button soundLink" onclick="pycmd('play:q:0'); return false;"></a>
                      <a class="replay-button soundLink" onclick="pycmd('play:q:1'); return false;"></a>
                    `;
                    document.body.prepend(host);
                }"""
            )
            before = page.locator("#anki-replay-fixture .replay-button").evaluate_all(
                "els => els.map(el => el.getAttribute('onclick'))"
            )

            selector = page.locator(".fac-playback-mode-select")
            selector.select_option("created")
            selector.select_option("profile")
            selector.select_option("realtime")

            after = page.locator("#anki-replay-fixture .replay-button").evaluate_all(
                "els => els.map(el => el.getAttribute('onclick'))"
            )
            self.assertEqual(after, before)
            self.assertEqual(page.locator("#anki-replay-fixture .replay-button").count(), 2)
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()

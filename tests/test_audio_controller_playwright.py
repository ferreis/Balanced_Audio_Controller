from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "web" / "audio_controller.js"
SCRIPT_V010 = ROOT / "web" / "audio_controller_v010.js"

I18N = {
    "audio_control_aria": "Audio controls",
    "drag_hint": "Drag to move",
    "audio": "Audio",
    "speed": "Speed",
    "decrease_speed": "Decrease speed by 0.5x",
    "playback_speed": "Playback speed",
    "increase_speed": "Increase speed by 0.5x",
    "volume": "Volume",
    "output_volume": "Output volume",
    "realtime_normalization": "Real-time normalization",
    "realtime_normalization_hint": "Normalize",
    "target_loudness": "Target loudness",
    "target_loudness_hint": "Target loudness",
    "dual_mono": "Treat mono as dual-mono",
    "dual_mono_hint": "Dual mono",
    "deck_profile": "Deck profile",
    "not_analyzed": "Not analyzed",
    "analyzing": "Analyzing",
    "reanalyze": "Reanalyze",
    "ready": "Ready",
    "current_deck": "Current deck",
    "use_analyzed_profile": "Use analyzed profile",
    "use_analyzed_profile_hint": "Use profile",
    "analyze_deck": "Analyze deck",
    "clear": "Clear",
    "analysis_method": "Analysis method",
    "analysis_auto": "Automatic",
    "analysis_ffmpeg": "FFmpeg",
    "analysis_webaudio": "Built-in (no FFmpeg)",
    "analysis_webaudio_short": "Built-in",
    "ffmpeg_ready": "FFmpeg available",
    "ffmpeg_missing": "FFmpeg not found",
    "install_ffmpeg": "Install FFmpeg",
    "ffmpeg_installing_ui": "Installing FFmpeg...",
    "ffmpeg_installer_hint": "Optional FFmpeg",
    "webaudio_hint": "Built-in analysis is approximate",
    "profile_method_ffmpeg": "FFmpeg profile",
    "profile_method_webaudio": "Built-in approximate profile",
    "preparing_analysis": "Preparing analysis...",
    "native_player": "Anki native player",
    "audio_count": "{count} audio file(s)",
    "failure_count": "{count} failure(s)",
    "target_changed": "target changed",
    "loudness_range": "{min} to {max} LUFS",
    "deck_summary_empty": "Analyze the deck",
}


def base_config() -> dict:
    return {
        "language": "en",
        "i18n": I18N,
        "speed": 1.0,
        "volume": 1.0,
        "normalize": True,
        "loudness_target": -24,
        "dual_mono": False,
        "analysis_backend": "auto",
        "deck_profile": {
            "deck_name": "Test deck",
            "enabled": False,
            "exists": False,
            "analyzing": False,
            "analysis_backend": "auto",
            "resolved_backend": "webaudio",
            "ffmpeg": {
                "available": False,
                "installing": False,
                "installer_available": True,
                "installer_name": "imageio-ffmpeg 0.6.0",
            },
        },
    }


class AudioControllerPlaywrightTests(unittest.TestCase):
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
        page.wait_for_selector(".fac-analysis-backend")
        return page

    def test_backend_controls_and_install_command(self) -> None:
        page = self.page_with_config(base_config())
        try:
            self.assertEqual(page.locator(".fac-analysis-backend").input_value(), "auto")
            self.assertEqual(page.locator(".fac-engine-status").inner_text(), "Built-in")
            self.assertTrue(page.locator(".fac-install-ffmpeg").is_visible())
            page.locator(".fac-install-ffmpeg").click()
            self.assertIn("ferreis_audio:v010:ffmpeg:install", page.evaluate("window.__pycmdMessages"))
            page.locator(".fac-analysis-backend").select_option("webaudio")
            self.assertIn("ferreis_audio:v010:backend:webaudio", page.evaluate("window.__pycmdMessages"))
            page.locator(".fac-analyze-deck").click()
            self.assertIn("ferreis_audio:v010:analyze", page.evaluate("window.__pycmdMessages"))
        finally:
            page.close()

    def test_ffmpeg_available_hides_installer(self) -> None:
        config = base_config()
        config["deck_profile"]["ffmpeg"] = {
            "available": True,
            "installing": False,
            "installer_available": True,
            "installer_name": "imageio-ffmpeg 0.6.0",
        }
        config["deck_profile"]["resolved_backend"] = "ffmpeg"
        page = self.page_with_config(config)
        try:
            self.assertEqual(page.locator(".fac-engine-status").inner_text(), "FFmpeg available")
            self.assertFalse(page.locator(".fac-install-ffmpeg").is_visible())
        finally:
            page.close()

    def test_builtin_loudness_measurement_and_dual_mono(self) -> None:
        page = self.page_with_config(base_config())
        try:
            result = page.evaluate(
                """
                () => {
                  const sampleRate = 48000;
                  const data = new Float32Array(sampleRate);
                  for (let i = 0; i < data.length; i++) {
                    data[i] = 0.1 * Math.sin(2 * Math.PI * 1000 * i / sampleRate);
                  }
                  const audioBuffer = {
                    sampleRate,
                    length: data.length,
                    numberOfChannels: 1,
                    getChannelData: () => data,
                  };
                  const mono = window.BACV010.measureAudioBuffer(audioBuffer, false);
                  const dual = window.BACV010.measureAudioBuffer(audioBuffer, true);
                  return { mono, dual };
                }
                """
            )
            self.assertTrue(-30 < result["mono"]["input_i"] < -15)
            self.assertTrue(-22 < result["mono"]["input_tp"] < -17)
            delta = result["dual"]["input_i"] - result["mono"]["input_i"]
            self.assertTrue(2.8 < delta < 3.2, delta)
        finally:
            page.close()

    def test_media_url_encodes_filename_and_rejects_traversal(self) -> None:
        page = self.page_with_config(base_config())
        try:
            url = page.evaluate("window.BACV010.mediaUrl('áudio teste.mp3')")
            self.assertIn("%C3%A1udio%20teste.mp3", url)
            rejected = page.evaluate("window.BACV010.mediaUrl('../outside.mp3')")
            self.assertIsNone(rejected)
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()

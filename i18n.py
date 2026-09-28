from __future__ import annotations

import locale
import os
from typing import Any

SUPPORTED_LANGUAGES = {"en", "pt-BR"}
DEFAULT_LANGUAGE = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "audio_control_aria": "Audio controls",
        "drag_hint": "Drag to move. Double-click to restore the default position.",
        "audio": "Audio",
        "speed": "Speed",
        "decrease_speed": "Decrease speed by 0.5x",
        "playback_speed": "Playback speed",
        "increase_speed": "Increase speed by 0.5x",
        "volume": "Volume",
        "output_volume": "Output volume",
        "realtime_normalization": "Real-time normalization",
        "realtime_normalization_hint": "Normalize perceived loudness in real time with MPV/FFmpeg loudnorm (EBU R128).",
        "target_loudness": "Target loudness",
        "target_loudness_hint": "Integrated target loudness in LUFS",
        "dual_mono": "Treat mono as dual-mono",
        "dual_mono_hint": "Compensate loudness measurement for mono audio intended for stereo playback.",
        "deck_profile": "Deck profile",
        "not_analyzed": "Not analyzed",
        "analyzing": "Analyzing",
        "reanalyze": "Reanalyze",
        "ready": "Ready",
        "current_deck": "Current deck",
        "use_analyzed_profile": "Use analyzed profile",
        "use_analyzed_profile_hint": "Use the measured gain for each audio file in this deck. The deck profile takes priority over real-time normalization.",
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
        "ffmpeg_installer_hint": "Optional: install a verified FFmpeg binary for the most accurate deck analysis.",
        "webaudio_hint": "Built-in analysis uses WebAudio and gated RMS. It requires no external installation and is approximate.",
        "profile_method_ffmpeg": "FFmpeg profile",
        "profile_method_webaudio": "Built-in approximate profile",
        "preparing_analysis": "Preparing analysis...",
        "native_player": "Anki native player",
        "audio_count": "{count} audio file(s)",
        "failure_count": "{count} failure(s)",
        "target_changed": "target changed",
        "loudness_range": "{min} to {max} LUFS",
        "deck_summary_empty": "Analyze the deck to calculate a specific gain for each audio file.",
        "status_native_no_mpv": "Native player without MPV control",
        "status_mpv_control_failed": "Unable to control MPV",
        "status_deck_profile_gain": "Deck profile · {gain:+.1f} dB",
        "status_profile_stale_prefix": "Profile is outdated; ",
        "status_realtime_normalization": "{prefix}real-time normalization · {target:.0f} LUFS",
        "status_loudnorm_unavailable": "{prefix}speed/volume active; loudnorm unavailable",
        "status_normalization_off": "{prefix}normalization off",
        "analysis_already_running": "Analysis is already running.",
        "ffmpeg_not_found": "FFmpeg was not found.",
        "ffmpeg_required_backend": "FFmpeg mode is selected, but FFmpeg is not available. Install it or choose Automatic/Built-in analysis.",
        "ffmpeg_already_available": "FFmpeg is already available.",
        "ffmpeg_install_unavailable": "Automatic FFmpeg installation is not available on this system. Use Built-in analysis or install FFmpeg manually.",
        "ffmpeg_installing": "Installing FFmpeg with {installer}...",
        "ffmpeg_installed": "FFmpeg installed and ready.",
        "ffmpeg_install_failed": "FFmpeg installation failed. Built-in analysis is still available.",
        "deck_audio_list_failed": "Unable to list the deck audio files.",
        "deck_no_audio": "No audio files were found in this deck.",
        "analysis_progress": "Analyzing {processed}/{total} with FFmpeg...",
        "analysis_progress_webaudio": "Analyzing {processed}/{total} with the built-in engine...",
        "profile_created": "FFmpeg profile created for {count} audio file(s).",
        "profile_created_webaudio": "Built-in approximate profile created for {count} audio file(s).",
        "analysis_webaudio_failed": "Built-in analysis could not decode any audio files. Try installing FFmpeg.",
        "analysis_failed": "Deck analysis failed.",
    },
    "pt-BR": {
        "audio_control_aria": "Controles de áudio",
        "drag_hint": "Arraste para mover. Clique duas vezes para restaurar a posição padrão.",
        "audio": "Áudio",
        "speed": "Velocidade",
        "decrease_speed": "Diminuir velocidade em 0,5x",
        "playback_speed": "Velocidade de reprodução",
        "increase_speed": "Aumentar velocidade em 0,5x",
        "volume": "Volume",
        "output_volume": "Volume de saída",
        "realtime_normalization": "Normalização em tempo real",
        "realtime_normalization_hint": "Normaliza o loudness percebido em tempo real usando loudnorm do MPV/FFmpeg (EBU R128).",
        "target_loudness": "Loudness alvo",
        "target_loudness_hint": "Loudness integrado alvo em LUFS",
        "dual_mono": "Tratar mono como dual-mono",
        "dual_mono_hint": "Compensa a medição de loudness de áudio mono destinado à reprodução estéreo.",
        "deck_profile": "Perfil do deck",
        "not_analyzed": "Não analisado",
        "analyzing": "Analisando",
        "reanalyze": "Reanalisar",
        "ready": "Pronto",
        "current_deck": "Deck atual",
        "use_analyzed_profile": "Usar perfil analisado",
        "use_analyzed_profile_hint": "Usa o ganho medido para cada arquivo de áudio deste deck. O perfil do deck tem prioridade sobre a normalização em tempo real.",
        "analyze_deck": "Analisar deck",
        "clear": "Limpar",
        "analysis_method": "Método de análise",
        "analysis_auto": "Automático",
        "analysis_ffmpeg": "FFmpeg",
        "analysis_webaudio": "Interno (sem FFmpeg)",
        "analysis_webaudio_short": "Interno",
        "ffmpeg_ready": "FFmpeg disponível",
        "ffmpeg_missing": "FFmpeg não encontrado",
        "install_ffmpeg": "Instalar FFmpeg",
        "ffmpeg_installing_ui": "Instalando FFmpeg...",
        "ffmpeg_installer_hint": "Opcional: instale um binário verificado do FFmpeg para obter a análise mais precisa do deck.",
        "webaudio_hint": "A análise interna usa WebAudio e RMS com gate. Não exige instalação externa e é aproximada.",
        "profile_method_ffmpeg": "Perfil FFmpeg",
        "profile_method_webaudio": "Perfil interno aproximado",
        "preparing_analysis": "Preparando análise...",
        "native_player": "Player nativo do Anki",
        "audio_count": "{count} áudio(s)",
        "failure_count": "{count} falha(s)",
        "target_changed": "alvo mudou",
        "loudness_range": "{min} a {max} LUFS",
        "deck_summary_empty": "Analise o deck para calcular um ganho específico para cada áudio.",
        "status_native_no_mpv": "Player nativo sem controle MPV",
        "status_mpv_control_failed": "Não foi possível controlar o MPV",
        "status_deck_profile_gain": "Perfil do deck · {gain:+.1f} dB",
        "status_profile_stale_prefix": "Perfil desatualizado; ",
        "status_realtime_normalization": "{prefix}normalização em tempo real · {target:.0f} LUFS",
        "status_loudnorm_unavailable": "{prefix}velocidade/volume ativos; loudnorm indisponível",
        "status_normalization_off": "{prefix}normalização desligada",
        "analysis_already_running": "A análise já está em andamento.",
        "ffmpeg_not_found": "FFmpeg não encontrado.",
        "ffmpeg_required_backend": "O modo FFmpeg está selecionado, mas o FFmpeg não está disponível. Instale-o ou escolha Automático/Interno.",
        "ffmpeg_already_available": "O FFmpeg já está disponível.",
        "ffmpeg_install_unavailable": "A instalação automática do FFmpeg não está disponível neste sistema. Use a análise Interna ou instale o FFmpeg manualmente.",
        "ffmpeg_installing": "Instalando o FFmpeg com {installer}...",
        "ffmpeg_installed": "FFmpeg instalado e pronto.",
        "ffmpeg_install_failed": "A instalação do FFmpeg falhou. A análise Interna continua disponível.",
        "deck_audio_list_failed": "Não foi possível listar os áudios do deck.",
        "deck_no_audio": "Nenhum arquivo de áudio foi encontrado neste deck.",
        "analysis_progress": "Analisando {processed}/{total} com FFmpeg...",
        "analysis_progress_webaudio": "Analisando {processed}/{total} com o mecanismo interno...",
        "profile_created": "Perfil FFmpeg criado para {count} áudio(s).",
        "profile_created_webaudio": "Perfil interno aproximado criado para {count} áudio(s).",
        "analysis_webaudio_failed": "A análise interna não conseguiu decodificar nenhum áudio. Tente instalar o FFmpeg.",
        "analysis_failed": "Falha ao analisar o deck.",
    },
}

WEB_TRANSLATION_KEYS = {
    "audio_control_aria",
    "drag_hint",
    "audio",
    "speed",
    "decrease_speed",
    "playback_speed",
    "increase_speed",
    "volume",
    "output_volume",
    "realtime_normalization",
    "realtime_normalization_hint",
    "target_loudness",
    "target_loudness_hint",
    "dual_mono",
    "dual_mono_hint",
    "deck_profile",
    "not_analyzed",
    "analyzing",
    "reanalyze",
    "ready",
    "current_deck",
    "use_analyzed_profile",
    "use_analyzed_profile_hint",
    "analyze_deck",
    "clear",
    "analysis_method",
    "analysis_auto",
    "analysis_ffmpeg",
    "analysis_webaudio",
    "analysis_webaudio_short",
    "ffmpeg_ready",
    "ffmpeg_missing",
    "install_ffmpeg",
    "ffmpeg_installing_ui",
    "ffmpeg_installer_hint",
    "webaudio_hint",
    "profile_method_ffmpeg",
    "profile_method_webaudio",
    "preparing_analysis",
    "native_player",
    "audio_count",
    "failure_count",
    "target_changed",
    "loudness_range",
    "deck_summary_empty",
}


def _normalize_locale_name(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().replace("_", "-").split(".", 1)[0]


def detect_system_language() -> str:
    candidates: list[str] = []
    try:
        from aqt.qt import QLocale

        candidates.append(str(QLocale.system().name()))
    except Exception:
        pass
    try:
        current_locale = locale.getlocale()[0]
        if current_locale:
            candidates.append(current_locale)
    except Exception:
        pass
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key)
        if value:
            candidates.append(value)
    for candidate in candidates:
        if _normalize_locale_name(candidate).lower().startswith("pt"):
            return "pt-BR"
    return DEFAULT_LANGUAGE


def resolve_language(configured: Any = "auto") -> str:
    value = str(configured or "auto").strip()
    if value == "auto":
        return detect_system_language()
    if value in SUPPORTED_LANGUAGES:
        return value
    return DEFAULT_LANGUAGE


def t(language: str, key: str, **values: Any) -> str:
    lang = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    template = TRANSLATIONS.get(lang, {}).get(key)
    if template is None:
        template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    try:
        return template.format(**values)
    except Exception:
        return template


def web_strings(language: str) -> dict[str, str]:
    return {key: t(language, key) for key in WEB_TRANSLATION_KEYS}

# v0.10 is loaded from i18n because this module is imported during add-on startup.
# The extension registers only dev-branch hooks and leaves the stable playback core intact.
try:
    from . import v010 as _v010  # noqa: F401,E402
except Exception as _v010_error:
    print("[Balanced Audio Controller] v0.10 extension load failed:", _v010_error)

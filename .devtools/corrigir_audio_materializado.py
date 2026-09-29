from __future__ import annotations

from pathlib import Path

ROOT = Path('.')

init_path = ROOT / '__init__.py'
source = init_path.read_text(encoding='utf-8')

old_constants = '''NORMALIZE_FILTER_NAME = "@ferreis_normalize"\nDECK_GAIN_FILTER_NAME = "@ferreis_deck_gain"\nTRUE_PEAK_LIMIT = -1.5\n'''
new_constants = '''NORMALIZE_FILTER_NAME = "@ferreis_normalize"\nDECK_GAIN_FILTER_NAME = "@ferreis_deck_gain"\nMATERIALIZED_AUDIO_PREFIX = "bac_norm_"\nTRUE_PEAK_LIMIT = -1.5\n'''
if old_constants not in source:
    raise SystemExit('constantes de áudio não encontradas')
source = source.replace(old_constants, new_constants, 1)

marker = '''def _remove_filter(player: Any, filter_name: str) -> None:\n    if not _is_mpv_player(player):\n        return\n    try:\n        player.command("af", "remove", filter_name)\n    except Exception:\n        pass\n\n\n'''
helper = marker + '''def _is_materialized_audio(filename: str | None) -> bool:\n    if not filename:\n        return False\n    basename = Path(str(filename).replace("\\\\", "/")).name\n    return basename.casefold().startswith(MATERIALIZED_AUDIO_PREFIX.casefold())\n\n\n'''
if marker not in source:
    raise SystemExit('marcador de filtro não encontrado')
source = source.replace(marker, helper, 1)

old_filters = '''    _remove_filter(player, NORMALIZE_FILTER_NAME)\n    _remove_filter(player, DECK_GAIN_FILTER_NAME)\n\n    profile, entry = _profile_entry_for_current_deck(filename, conf)\n'''
new_filters = '''    _remove_filter(player, NORMALIZE_FILTER_NAME)\n    _remove_filter(player, DECK_GAIN_FILTER_NAME)\n\n    # Cópias bac_norm_* já foram normalizadas fisicamente em disco. Aplicar\n    # loudnorm ou ganho do perfil novamente distorceria o resultado e poderia\n    # provocar uma segunda normalização desnecessária.\n    if _is_materialized_audio(filename):\n        return True, t(lang, "status_materialized_audio")\n\n    profile, entry = _profile_entry_for_current_deck(filename, conf)\n'''
if old_filters not in source:
    raise SystemExit('bloco de aplicação de filtros não encontrado')
source = source.replace(old_filters, new_filters, 1)

old_return = '''    return deck_name, sorted(files, key=str.casefold)\n'''
new_return = '''    files = {filename for filename in files if not _is_materialized_audio(filename)}\n    return deck_name, sorted(files, key=str.casefold)\n'''
if old_return not in source:
    raise SystemExit('retorno de arquivos do deck não encontrado')
source = source.replace(old_return, new_return, 1)
init_path.write_text(source, encoding='utf-8')

# Não permitir que perfis antigos que eventualmente já contenham bac_norm_*\n# alimentem uma nova geração recursiva de cópias.
v010_path = ROOT / 'v010.py'
v010 = v010_path.read_text(encoding='utf-8')
old_import = '''from .normalized_audio import (\n    FIELD_BASE_NAME,\n    MAX_OUTPUT_BYTES,\n'''
new_import = '''from .normalized_audio import (\n    FIELD_BASE_NAME,\n    GENERATED_PREFIX,\n    MAX_OUTPUT_BYTES,\n'''
if old_import not in v010:
    raise SystemExit('import de normalized_audio não encontrado')
v010 = v010.replace(old_import, new_import, 1)
old_profile_files = '''    profile_files = set(str(name) for name in files)\n'''
new_profile_files = '''    profile_files = {\n        str(name)\n        for name in files\n        if not Path(str(name).replace("\\\\", "/")).name.casefold().startswith(\n            GENERATED_PREFIX.casefold()\n        )\n    }\n'''
if old_profile_files not in v010:
    raise SystemExit('profile_files não encontrado')
v010 = v010.replace(old_profile_files, new_profile_files, 1)
v010_path.write_text(v010, encoding='utf-8')

# Mensagem de status para cópia já normalizada.
i18n_path = ROOT / 'i18n.py'
i18n = i18n_path.read_text(encoding='utf-8')
en_anchor = '        "status_deck_profile_gain": "Deck profile · {gain:+.1f} dB",\n'
pt_anchor = '        "status_deck_profile_gain": "Perfil do deck · {gain:+.1f} dB",\n'
if en_anchor not in i18n or pt_anchor not in i18n:
    raise SystemExit('status_deck_profile_gain não encontrado')
i18n = i18n.replace(en_anchor, en_anchor + '        "status_materialized_audio": "Already-normalized audio copy · filters bypassed",\n', 1)
i18n = i18n.replace(pt_anchor, pt_anchor + '        "status_materialized_audio": "Cópia de áudio já normalizada · filtros ignorados",\n', 1)
i18n_path.write_text(i18n, encoding='utf-8')

# Regressões: cópia materializada não recebe filtro e análise ignora bac_norm_*.
test_path = ROOT / 'tests' / 'test_playback_regression.py'
test = test_path.read_text(encoding='utf-8')
insert = r'''
    def test_materialized_audio_bypasses_runtime_normalization(self) -> None:
        player = FakePlayer()
        ns = self.base_namespace(player)
        removed: list[tuple[Any, ...]] = []
        ns["_remove_filter"] = lambda *args: removed.append(args)
        ns["_is_materialized_audio"] = lambda filename: bool(filename and filename.startswith("bac_norm_"))
        ns["_profile_entry_for_current_deck"] = lambda *_: self.fail(
            "materialized audio must not query/apply deck profile gain"
        )
        apply_settings = load_function("_apply_native_settings", ns)

        supported, status = apply_settings(player, "bac_norm_abcd_voice.m4a")

        self.assertTrue(supported)
        self.assertEqual(status, "status_materialized_audio")
        self.assertEqual(player.commands, [])
        self.assertEqual(len(removed), 2)

    def test_deck_analysis_excludes_materialized_audio(self) -> None:
        self.assertIn(
            "files = {filename for filename in files if not _is_materialized_audio(filename)}",
            SOURCE,
        )

'''
marker_test = '\n\nif __name__ == "__main__":\n'
if marker_test not in test:
    raise SystemExit('final de test_playback_regression não encontrado')
test_path.write_text(test.replace(marker_test, '\n' + insert + marker_test, 1), encoding='utf-8')

# Proteção adicional específica da materialização.
normalized_test_path = ROOT / 'tests' / 'test_normalized_audio.py'
normalized_test = normalized_test_path.read_text(encoding='utf-8')
if 'GENERATED_PREFIX = "bac_norm_"' not in (ROOT / 'normalized_audio.py').read_text(encoding='utf-8'):
    raise SystemExit('prefixo de mídia normalizada ausente')
if 'test_media_stem_is_safe_and_deterministic' not in normalized_test:
    raise SystemExit('teste de nome determinístico ausente')

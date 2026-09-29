from pathlib import Path

path = Path('v010.py')
text = path.read_text(encoding='utf-8')
old = '''def _start_webaudio_analysis(context) -> None:\n    core = _core()\n    current = _current_deck(context)\n    if not current:\n        return\n    deck_id, deck_name = current\n    lang = _lang()\n'''
new = '''def _start_webaudio_analysis(context) -> None:\n    core = _core()\n    current = _current_deck(context)\n    if not current:\n        return\n    deck_id, deck_name = current\n    web = core._context_web(context)\n    if not web:\n        return\n    lang = _lang()\n'''
if new not in text:
    if old not in text:
        raise RuntimeError('bloco WebAudio não encontrado')
    text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('Contexto WebAudio do preview validado.')

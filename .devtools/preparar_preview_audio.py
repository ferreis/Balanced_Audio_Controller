from pathlib import Path

path = Path('__init__.py')
text = path.read_text(encoding='utf-8')

if 'def _context_surface(context: object | None) -> str:' not in text:
    start = text.index('def _current_reviewer_card():')
    end = text.index('\n\ndef _profiles_path()', start)
    block = '''def _current_reviewer_card():
    reviewer = getattr(mw, "reviewer", None)
    return getattr(reviewer, "card", None)


def _current_reviewer_deck_id() -> int | None:
    card = _current_reviewer_card()
    return _card_deck_id(card) if card else None


def _context_surface(context: object | None) -> str:
    if isinstance(context, aqt.reviewer.Reviewer):
        return "reviewer"
    if context is None:
        return ""
    cls = type(context)
    module = str(getattr(cls, "__module__", ""))
    name = str(getattr(cls, "__name__", ""))
    if module == "aqt.browser.previewer" and name.endswith("Previewer"):
        return "previewer"
    if module == "aqt.clayout" and name == "CardLayout":
        return "card_layout"
    return ""


def _is_supported_card_context(context: object | None) -> bool:
    return bool(_context_surface(context))


def _card_from_context(context: object | None):
    if not _is_supported_card_context(context):
        return None
    candidate = getattr(context, "card", None)
    if callable(candidate):
        try:
            candidate = candidate()
        except Exception:
            candidate = None
    if candidate is not None:
        return candidate
    return getattr(context, "rendered_card", None)


def _context_web(context: object | None):
    if not _is_supported_card_context(context):
        return None
    if isinstance(context, aqt.reviewer.Reviewer):
        return getattr(context, "web", None)
    surface = _context_surface(context)
    if surface == "previewer":
        return getattr(context, "_web", None)
    if surface == "card_layout":
        return getattr(context, "preview_web", None)
    return None


def _set_active_card_context(context: object | None) -> None:
    global _ACTIVE_CARD_CONTEXT
    with _PLAYBACK_LOCK:
        _ACTIVE_CARD_CONTEXT = context if _is_supported_card_context(context) else None


def _active_card_context() -> object | None:
    with _PLAYBACK_LOCK:
        return _ACTIVE_CARD_CONTEXT


def _current_audio_filename() -> str | None:
    with _PLAYBACK_LOCK:
        return _CURRENT_AUDIO_FILENAME


def _set_current_audio_filename(filename: str | None) -> None:
    global _CURRENT_AUDIO_FILENAME
    with _PLAYBACK_LOCK:
        _CURRENT_AUDIO_FILENAME = filename


def _current_audio_deck_id() -> int | None:
    with _PLAYBACK_LOCK:
        return _CURRENT_AUDIO_DECK_ID


def _set_current_audio_deck_id(deck_id: int | None) -> None:
    global _CURRENT_AUDIO_DECK_ID
    with _PLAYBACK_LOCK:
        _CURRENT_AUDIO_DECK_ID = deck_id
'''
    text = text[:start] + block + text[end:]
    path.write_text(text, encoding='utf-8')

print('Bloco de contexto do preview preparado.')

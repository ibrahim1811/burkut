import pyperclip


def get_clipboard() -> str:
    try:
        return pyperclip.paste() or ""
    except Exception:
        return ""


def set_clipboard(text: str) -> None:
    pyperclip.copy(text)


def clear_clipboard() -> None:
    pyperclip.copy("")

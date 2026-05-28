"""Ses asistanı ile widget arasında paylaşılan durum."""
_indicator = None


def set_indicator(ind) -> None:
    global _indicator
    _indicator = ind


def get_indicator():
    return _indicator

import pygetwindow as gw
from typing import Optional


def get_windows() -> list[dict]:
    windows = []
    for w in gw.getAllWindows():
        if w.title and w.visible:
            windows.append({
                "title": w.title,
                "width": w.width,
                "height": w.height,
                "left": w.left,
                "top": w.top,
                "minimized": w.isMinimized,
                "active": w.isActive,
            })
    return windows


def get_active_window() -> Optional[str]:
    w = gw.getActiveWindow()
    return w.title if w else None


def focus_window(title: str) -> bool:
    matches = gw.getWindowsWithTitle(title)
    if not matches:
        return False
    try:
        matches[0].activate()
        return True
    except Exception:
        return False


def close_window(title: str) -> bool:
    matches = gw.getWindowsWithTitle(title)
    if not matches:
        return False
    try:
        matches[0].close()
        return True
    except Exception:
        return False


def minimize_window(title: str) -> bool:
    matches = gw.getWindowsWithTitle(title)
    if not matches:
        return False
    try:
        matches[0].minimize()
        return True
    except Exception:
        return False


def maximize_window(title: str) -> bool:
    matches = gw.getWindowsWithTitle(title)
    if not matches:
        return False
    try:
        matches[0].maximize()
        return True
    except Exception:
        return False

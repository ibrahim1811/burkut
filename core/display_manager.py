import ctypes
import ctypes.wintypes
import subprocess


def lock_screen() -> None:
    ctypes.windll.user32.LockWorkStation()


def get_resolution() -> tuple[int, int]:
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def get_monitors() -> list[dict]:
    try:
        import screeninfo
        monitors = screeninfo.get_monitors()
        return [{"name": m.name, "width": m.width, "height": m.height, "primary": m.is_primary} for m in monitors]
    except Exception:
        w, h = get_resolution()
        return [{"name": "Primary", "width": w, "height": h, "primary": True}]


def get_brightness() -> int:
    try:
        import screen_brightness_control as sbc
        val = sbc.get_brightness()
        if isinstance(val, list):
            return val[0]
        return val
    except Exception:
        return -1


def set_brightness(level: int) -> int:
    level = max(0, min(100, level))
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return level
    except Exception as e:
        raise RuntimeError(f"Parlaklık ayarlanamadı: {e}")

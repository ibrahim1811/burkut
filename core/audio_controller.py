from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import math


def _get_volume_interface():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> int:
    vol = _get_volume_interface()
    scalar = vol.GetMasterVolumeLevelScalar()
    return round(scalar * 100)


def set_volume(level: int) -> int:
    level = max(0, min(100, level))
    vol = _get_volume_interface()
    vol.SetMasterVolumeLevelScalar(level / 100.0, None)
    return level


def volume_up(step: int = 10) -> int:
    current = get_volume()
    return set_volume(current + step)


def volume_down(step: int = 10) -> int:
    current = get_volume()
    return set_volume(current - step)


def is_muted() -> bool:
    vol = _get_volume_interface()
    return bool(vol.GetMute())


def mute() -> None:
    vol = _get_volume_interface()
    vol.SetMute(True, None)


def unmute() -> None:
    vol = _get_volume_interface()
    vol.SetMute(False, None)


def toggle_mute() -> bool:
    if is_muted():
        unmute()
        return False
    else:
        mute()
        return True


def get_volume_info() -> dict:
    return {
        "level": get_volume(),
        "muted": is_muted(),
    }

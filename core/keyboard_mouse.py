import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def get_mouse_position() -> tuple[int, int]:
    return pyautogui.position()


def move_mouse(x: int, y: int, duration: float = 0.2) -> None:
    pyautogui.moveTo(x, y, duration=duration)


def click(x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> None:
    pyautogui.click(x, y, clicks=clicks, button=button)


def right_click(x: int = None, y: int = None) -> None:
    pyautogui.rightClick(x, y)


def double_click(x: int = None, y: int = None) -> None:
    pyautogui.doubleClick(x, y)


def scroll(amount: int, x: int = None, y: int = None) -> None:
    pyautogui.scroll(amount, x=x, y=y)


def type_text(text: str, interval: float = 0.02) -> None:
    pyautogui.write(text, interval=interval)


def type_text_unicode(text: str) -> None:
    import subprocess
    subprocess.Popen(
        ["powershell", "-Command",
         f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetText('{text}'); "
         f"[System.Windows.Forms.SendKeys]::SendWait('^v')"]
    )


def press_key(*keys: str) -> None:
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)


def hotkey(*keys: str) -> None:
    pyautogui.hotkey(*keys)

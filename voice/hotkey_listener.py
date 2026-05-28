import threading
import time
from typing import Callable
from pynput import keyboard


class HotkeyListener:
    """Ctrl+Space push-to-talk. Basılı tut = kayıt, bırak = işle."""

    def __init__(self, on_start: Callable, on_stop: Callable):
        self._on_start = on_start
        self._on_stop = on_stop
        self._ctrl_held = False
        self._space_held = False
        self._recording = False
        self._stop_lock = threading.Lock()

    def _on_press(self, key):
        try:
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._ctrl_held = True
            elif key == keyboard.Key.space:
                self._space_held = True

            if self._ctrl_held and self._space_held and not self._recording:
                with self._stop_lock:
                    if not self._recording:
                        self._recording = True
                        t = threading.Thread(target=self._on_start, daemon=True)
                        t.start()
        except Exception as e:
            print(f"[Hotkey] press hata: {e}")

    def _on_release(self, key):
        try:
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._ctrl_held = False
            elif key == keyboard.Key.space:
                self._space_held = False

            # İkisinden biri bırakıldıysa ve kayıt devam ediyorsa durdur
            if self._recording and not (self._ctrl_held and self._space_held):
                with self._stop_lock:
                    if self._recording:
                        self._recording = False
                        t = threading.Thread(target=self._on_stop, daemon=True)
                        t.start()
        except Exception as e:
            print(f"[Hotkey] release hata: {e}")

    def start(self):
        print("[Hotkey] Dinleniyor — Ctrl+Space basılı tut, konuş, bırak.")
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()

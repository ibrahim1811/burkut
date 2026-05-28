import threading
from typing import Callable
from pynput import keyboard


class HotkeyListener:
    """Ctrl+Space tek dokunuş — bas başla, VAD otomatik durdurur.
    Kayıt sırasında tekrar Ctrl+Space basarsan zorla durdurur."""

    def __init__(self, on_start: Callable, on_stop: Callable):
        self._on_start  = on_start
        self._on_stop   = on_stop
        self._ctrl_held = False
        self._recording = False
        self._lock      = threading.Lock()

    def reset_recording(self):
        """VAD auto-stop sonrası çağrılır — listener durumunu sıfırla."""
        with self._lock:
            self._recording = False

    def _on_press(self, key):
        try:
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._ctrl_held = True
                return

            if key == keyboard.Key.space and self._ctrl_held:
                with self._lock:
                    if not self._recording:
                        self._recording = True
                        threading.Thread(target=self._on_start, daemon=True).start()
                    else:
                        # Kayıt sırasında tekrar basış → zorla durdur
                        self._recording = False
                        threading.Thread(target=self._on_stop, daemon=True).start()
        except Exception as e:
            print(f"[Hotkey] press hata: {e}")

    def _on_release(self, key):
        try:
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._ctrl_held = False
        except Exception:
            pass

    def start(self):
        print("[Hotkey] Dinleniyor — Ctrl+Space: başla (VAD otomatik durdurur).")
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()

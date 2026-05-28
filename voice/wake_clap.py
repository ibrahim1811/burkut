"""
Çift alkış tetikleyici — sounddevice kullanır (AudioRecorder ile çatışmaz).
2 saniye içinde 2 alkış → on_wake() çağırır.
"""

import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE    = 16000
BLOCK_SIZE     = 1024        # ~64 ms/kare
CLAP_THRESHOLD = 0.12        # float32 RMS eşiği — düşürürsen hassaslaşır
CLAP_MIN_GAP   = 0.12        # Aynı alkışın çerçevelere yayılmasını önler (sn)
CLAP_WINDOW    = 2.0         # İki alkış bu kadar saniye içinde olmalı


class WakeGestureListener:
    def __init__(self, on_wake: Callable[[], None]):
        self._on_wake = on_wake
        self._running = threading.Event()

    def start(self):
        self._running.set()
        threading.Thread(target=self._loop, daemon=True, name="WakeClap").start()

    def stop(self):
        self._running.clear()

    def _loop(self):
        clap_times: list[float] = []

        def _callback(indata, frames, time_info, status):
            if not self._running.is_set():
                return

            rms = float(np.sqrt(np.mean(indata ** 2)))
            now = time.monotonic()

            # Pencere dışı eski alkışları temizle
            while clap_times and now - clap_times[0] > CLAP_WINDOW:
                clap_times.pop(0)

            if rms > CLAP_THRESHOLD:
                if not clap_times or (now - clap_times[-1]) > CLAP_MIN_GAP:
                    clap_times.append(now)
                    print(f"[Wake] 👏 Alkış #{len(clap_times)}")

                    if len(clap_times) >= 2:
                        clap_times.clear()
                        print("[Wake] ✅ Çift alkış — tetiklendi")
                        # Callback thread'inden on_wake'i ayrı thread'de çağır
                        threading.Thread(target=self._on_wake, daemon=True).start()

        from voice.shared_state import get_mic_device
        device = get_mic_device()

        try:
            with sd.InputStream(
                device=device,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=BLOCK_SIZE,
                callback=_callback,
            ):
                print("[Wake] Çift alkış dinleyicisi başladı.")
                while self._running.is_set():
                    time.sleep(0.1)
        except Exception as e:
            print(f"[Wake] Hata: {e}")

"""
'Bürküt' kelime tetikleyicisi — Vosk offline.
Hiç API çağrısı yapmaz, tamamen yerel çalışır.
İlk çalıştırmada Türkçe model indirilir (~35 MB, tek seferlik).
"""

import json
import queue
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK       = 4000       # 0.25 sn / paket — hızlı tepki
KEYWORDS    = ["bürküt", "burkut", "burküt", "bürkut", "birkut"]
COOLDOWN    = 3.0        # iki tetikleyici arasındaki minimum süre (sn)


class WakeWordListener:
    def __init__(self, on_wake: Callable, is_busy_fn: Callable = None):
        self._on_wake   = on_wake
        self._is_busy   = is_busy_fn or (lambda: False)
        self._running   = threading.Event()
        self._last_fire = 0.0
        self._q: queue.Queue = queue.Queue()

    def start(self):
        self._running.set()
        threading.Thread(target=self._stream_loop,    daemon=True, name="WakeWordStream").start()
        threading.Thread(target=self._recognize_loop, daemon=True, name="WakeWordRec").start()

    def stop(self):
        self._running.clear()

    # ── Ses akışı ──────────────────────────────────────────────────────
    def _stream_loop(self):
        from voice.shared_state import get_mic_device
        device = get_mic_device()

        def _cb(indata, *_):
            # float32 → int16 bytes (Vosk formatı)
            self._q.put((indata[:, 0] * 32767).astype(np.int16).tobytes())

        try:
            with sd.InputStream(
                device=device,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK,
                callback=_cb,
            ):
                while self._running.is_set():
                    time.sleep(0.1)
        except Exception as e:
            print(f"[WakeWord] Akış hatası: {e}")

    # ── Vosk offline tanıma ────────────────────────────────────────────
    def _recognize_loop(self):
        try:
            import vosk
            vosk.SetLogLevel(-1)   # spam logları kapat
        except ImportError:
            print("[WakeWord] vosk kurulu değil — pip install vosk")
            return

        print("[WakeWord] Türkçe model yükleniyor (ilk seferde indirilir)...")
        try:
            model = vosk.Model(lang="tr")
        except Exception as e:
            print(f"[WakeWord] Model yüklenemedi: {e}")
            return

        grammar = json.dumps(KEYWORDS + ["[unk]"])
        rec     = vosk.KaldiRecognizer(model, SAMPLE_RATE, grammar)
        print("[WakeWord] ✅ 'Bürküt' dinleyicisi hazır — sıfır API çağrısı.")

        while self._running.is_set():
            try:
                data = self._q.get(timeout=0.5)
            except queue.Empty:
                continue

            if rec.AcceptWaveform(data):
                text = json.loads(rec.Result()).get("text", "")
            else:
                text = json.loads(rec.PartialResult()).get("partial", "")

            if text and any(kw in text.lower() for kw in KEYWORDS):
                self._fire()

    def _fire(self):
        now = time.monotonic()
        if now - self._last_fire < COOLDOWN or self._is_busy():
            return
        self._last_fire = now
        print("[WakeWord] ✅ 'Bürküt' algılandı — tetikleniyor")
        threading.Thread(target=self._on_wake, daemon=True).start()

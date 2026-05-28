import tempfile
import threading
import time
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav

SAMPLE_RATE = 16000
MIN_SECONDS = 0.5
MAX_SECONDS = 30


class AudioRecorder:
    def __init__(self):
        self._recording = False
        self._frames = []
        self._lock = threading.Lock()
        self._start_time = None
        self._stream = None

    def start(self):
        with self._lock:
            self._frames = []
            self._recording = True
            self._start_time = time.time()

        def callback(indata, frames, time_info, status):
            if self._recording:
                with self._lock:
                    self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=1024,
                callback=callback,
            )
            self._stream.start()
        except Exception as e:
            self._recording = False
            raise RuntimeError(f"Mikrofon açılamadı: {e}")

    def stop(self) -> str:
        # Çok kısa kayıtları reddet
        if self._start_time and (time.time() - self._start_time) < MIN_SECONDS:
            time.sleep(MIN_SECONDS)

        self._recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            frames = self._frames.copy()
            self._frames = []

        if not frames:
            return ""

        try:
            audio = np.concatenate(frames, axis=0).flatten()
        except Exception:
            return ""

        # Sessiz kayıt kontrolü (RMS < eşik)
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 0.002:
            return ""

        audio_int16 = (audio * 32767).astype(np.int16)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav.write(tmp.name, SAMPLE_RATE, audio_int16)
        tmp.close()
        return tmp.name

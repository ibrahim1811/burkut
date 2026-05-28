import tempfile
import threading
import time
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav

SAMPLE_RATE    = 16000
MIN_SECONDS    = 0.5
MAX_SECONDS    = 30
SILENCE_RMS    = 0.008   # bu RMS altı sessizlik sayılır
SILENCE_HOLD   = 1.5     # kaç sn sessizlik → otomatik durdur
VAD_INTERVAL   = 0.05    # VAD kontrol aralığı (sn)


class AudioRecorder:
    def __init__(self):
        self._recording   = False
        self._frames      = []
        self._lock        = threading.Lock()
        self._start_time  = None
        self._stream      = None

    def start(self, on_auto_stop=None):
        with self._lock:
            self._frames     = []
            self._recording  = True
            self._start_time = time.time()

        def callback(indata, frames, time_info, status):
            if self._recording:
                with self._lock:
                    self._frames.append(indata.copy())

        try:
            from voice.shared_state import get_mic_device
            self._stream = sd.InputStream(
                device=get_mic_device(),
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

        if on_auto_stop:
            threading.Thread(
                target=self._vad_loop,
                args=(on_auto_stop,),
                daemon=True,
            ).start()

    def _vad_loop(self, on_stop):
        """Sessizlik tespiti: konuşma biter → SILENCE_HOLD sn bekle → otomatik durdur."""
        chunk_size     = int(SAMPLE_RATE * VAD_INTERVAL)
        silence_start  = None
        speech_found   = False

        while self._recording:
            time.sleep(VAD_INTERVAL)
            elapsed = time.time() - self._start_time

            if elapsed >= MAX_SECONDS:
                on_stop()
                return

            with self._lock:
                if not self._frames:
                    continue
                all_audio = np.concatenate(self._frames, axis=0).flatten()

            chunk = all_audio[-chunk_size:] if len(all_audio) >= chunk_size else all_audio
            rms   = float(np.sqrt(np.mean(chunk ** 2)))

            if rms > SILENCE_RMS:
                speech_found  = True
                silence_start = None
            elif speech_found:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= SILENCE_HOLD:
                    on_stop()
                    return

    def stop(self) -> str:
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
            frames       = self._frames.copy()
            self._frames = []

        if not frames:
            return ""

        try:
            audio = np.concatenate(frames, axis=0).flatten()
        except Exception:
            return ""

        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 0.002:
            return ""

        audio_int16 = (audio * 32767).astype(np.int16)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav.write(tmp.name, SAMPLE_RATE, audio_int16)
        tmp.close()
        return tmp.name

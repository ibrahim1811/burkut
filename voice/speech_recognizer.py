import os
import threading
import concurrent.futures

_model = None
_model_lock = threading.Lock()
_model_size = "small"
_TRANSCRIBE_TIMEOUT = 30  # saniye — bu kadar süre geçince hata döndür


def _load_model():
    global _model
    from faster_whisper import WhisperModel
    with _model_lock:
        if _model is not None:
            return  # başka thread zaten yükledi
        try:
            _model = WhisperModel(_model_size, device="cuda", compute_type="float16")
            print("[SES] Whisper modeli CUDA'da yüklendi.")
        except Exception as cuda_err:
            print(f"[SES] CUDA yüklenemedi ({cuda_err}), CPU'ya geçiliyor...")
            try:
                _model = WhisperModel(_model_size, device="cpu", compute_type="int8")
                print("[SES] Whisper modeli CPU'da yüklendi.")
            except Exception as e:
                print(f"[SES] Model yüklenemedi: {e}")
                _model = None


def is_ready() -> bool:
    return _model is not None


def preload(on_complete=None):
    def _worker():
        _load_model()
        if on_complete:
            try:
                on_complete()
            except Exception:
                pass
    threading.Thread(target=_worker, daemon=True).start()


def _do_transcribe(audio_path: str) -> str:
    segments, _ = _model.transcribe(
        audio_path,
        language="tr",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    return " ".join(s.text.strip() for s in segments).strip()


def transcribe(audio_path: str) -> str:
    # Model henüz yüklü değilse yükle (bloklama)
    if not is_ready():
        _load_model()
    if not is_ready():
        print("[SES] Model yüklenemedi, transkripsiyon atlanıyor.")
        return ""

    try:
        # Zaman aşımı ile çalıştır — CUDA donması durumunda sonsuz beklemez
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_transcribe, audio_path)
            try:
                result = future.result(timeout=_TRANSCRIBE_TIMEOUT)
                return result
            except concurrent.futures.TimeoutError:
                print(f"[SES] Transkripsiyon zaman aşımı ({_TRANSCRIBE_TIMEOUT}s)!")
                return ""
    except Exception as e:
        print(f"[SES] Transkript hatası: {e}")
        return ""
    finally:
        try:
            os.unlink(audio_path)
        except Exception:
            pass

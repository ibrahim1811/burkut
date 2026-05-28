import threading
import queue
import pyttsx3

_engine = None
_tts_queue: queue.Queue = queue.Queue()
_tts_thread = None
_ready = threading.Event()


def _tts_worker():
    global _engine
    try:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 165)
        _engine.setProperty("volume", 1.0)

        voices = _engine.getProperty("voices")
        # Türkçe ses ara
        turkish_voice = None
        for v in voices:
            vid = v.id.lower()
            vname = v.name.lower()
            if "tr" in vid or "turkish" in vid or "turkish" in vname or "türk" in vname:
                turkish_voice = v.id
                break
        # Bulunamazsa mevcut ilk Türkçe benzeri veya genel
        if turkish_voice:
            _engine.setProperty("voice", turkish_voice)
            print(f"[TTS] Türkçe ses: {turkish_voice}")
        else:
            # İlk sesi kullan (genellikle yerel dil)
            if voices:
                _engine.setProperty("voice", voices[0].id)
            print("[TTS] Türkçe ses bulunamadı, varsayılan kullanılıyor.")

    except Exception as e:
        print(f"[TTS] Motor başlatılamadı: {e}")
        _ready.set()
        return

    _ready.set()

    while True:
        try:
            text = _tts_queue.get(timeout=0.5)
            if text is None:
                break
            try:
                _engine.say(text)
                _engine.runAndWait()
            except Exception as e:
                print(f"[TTS] Konuşma hatası: {e}")
                try:
                    _engine.stop()
                except Exception:
                    pass
        except queue.Empty:
            continue


def start():
    global _tts_thread
    if _tts_thread and _tts_thread.is_alive():
        return
    _ready.clear()
    _tts_thread = threading.Thread(target=_tts_worker, daemon=True)
    _tts_thread.start()
    _ready.wait(timeout=5)


def speak(text: str) -> None:
    if not _tts_thread or not _tts_thread.is_alive():
        start()
    _tts_queue.put(text)


def wait_ready():
    _ready.wait(timeout=5)

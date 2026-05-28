"""
STT — Groq Whisper API ile ses tanıma.
"""

import os
import threading

from dotenv import load_dotenv
load_dotenv()


def is_ready() -> bool:
    """Groq API key mevcut mu kontrol et."""
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def preload(on_complete=None):
    """Groq API'de model yükleme yok — hemen hazır, callback'i çalıştır."""
    def _worker():
        if on_complete:
            try:
                on_complete()
            except Exception:
                pass
    threading.Thread(target=_worker, daemon=True).start()


def transcribe(audio_path: str) -> str:
    """WAV dosyasını Groq Whisper API ile transkribe et."""
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY") or None)
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), audio_data),
            model="whisper-large-v3-turbo",
            language="tr",
            response_format="text",
        )
        return transcription.strip() if transcription else ""
    except Exception as e:
        print(f"[SES] Groq Whisper hatası: {e}")
        return ""
    finally:
        try:
            os.unlink(audio_path)
        except Exception:
            pass

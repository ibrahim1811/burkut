"""
TTS — edge-tts ile Türkçe sesli yanıt.
"""

import asyncio
import os
import queue
import tempfile
import threading

import sounddevice as sd
import soundfile as sf

VOICE = "tr-TR-AhmetNeural"

_tts_queue: queue.Queue = queue.Queue()
_tts_thread = None
_ready = threading.Event()


async def _synthesize(text: str, output_path: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_path)


def _tts_worker():
    _ready.set()
    while True:
        try:
            text = _tts_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        if text is None:
            break
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp = f.name
            asyncio.run(_synthesize(text, tmp))
            data, sr = sf.read(tmp)
            sd.play(data, sr)
            sd.wait()
        except Exception as e:
            print(f"[TTS] edge-tts hatası: {e}")
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass


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

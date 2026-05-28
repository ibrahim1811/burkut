import io
import tempfile
import os


def take_webcam_photo() -> io.BytesIO:
    """Webcam'den tek kare alır, JPEG BytesIO döner."""
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Kamera bulunamadı veya açılamadı.")

    # Kameranın hazırlanması için birkaç kare at
    for _ in range(5):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("Kameradan görüntü alınamadı.")

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf


def record_audio(duration: int) -> str:
    """Mikrofondan ses kaydeder, geçici WAV dosya yolunu döner."""
    import sounddevice as sd
    import scipy.io.wavfile as wavfile
    import numpy as np

    sample_rate = 44100
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    sd.wait()

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    wavfile.write(tmp.name, sample_rate, recording)
    return tmp.name

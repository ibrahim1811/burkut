import sys
import os
import json
import threading
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import groq as _groq

from voice.audio_recorder import AudioRecorder
from voice.hotkey_listener import HotkeyListener
from voice import speech_recognizer, text_to_speech, shared_state
from voice.command_parser import parse

_groq_client = _groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))

_NLU_SYSTEM = """Sen Bürküt'sün. Kullanıcının Türkçe sesli komutunu analiz et ve SADECE JSON döndür.

{"intent": "...", "params": {...}}

Intent seçenekleri:
- "weather": {"city": "şehir adı, belirtilmediyse Istanbul"}
- "reminder_set": {"text": "hatırlatma içeriği", "when": "zaman ifadesi (örn: yarın sabah, 5 dakika sonra, 15:30)"}
- "reminder_list": {}
- "general": {"answer": "Türkçe kısa ve doğal cevap, maksimum 2 cümle"}
- "system": {"cmd": "shutdown|restart|sleep|hibernate|screenshot|status|volume_up|volume_down|volume_set|mute|lock|clipboard|gpu|brightness_set|windows|help|launch|open_file|open_url|open_folder|close_proc", "args": []}

Sadece JSON döndür. Başka hiçbir şey yazma."""


_recorder           = AudioRecorder()
_busy               = threading.Lock()
_wake_listener      = None
_wake_word_listener = None
_hotkey             = None   # HotkeyListener referansı — VAD reset için


def set_indicator(indicator):
    shared_state.set_indicator(indicator)


def _notify(action: str, text: str = ""):
    ind = shared_state.get_indicator()
    if ind:
        try:
            ind.notify(action, text)
        except Exception:
            pass


def _on_start():
    if not speech_recognizer.is_ready():
        _notify("loading")
        print("[SES] Model henüz hazır değil, komut yoksayıldı.")
        return
    if not _busy.acquire(blocking=False):
        print("[SES] Zaten işleniyor, yoksayıldı.")
        return
    try:
        _notify("listening")
        print("[SES] Kayıt başladı (VAD aktif)...")
        text_to_speech.speak("Dinliyorum efendim.")
        _recorder.start(on_auto_stop=_on_vad_stop)
    except Exception as e:
        print(f"[SES] Kayıt başlatma hatası: {e}")
        _notify("error", str(e))
        _busy.release()


def _on_vad_stop():
    """VAD sessizlik tespiti sonrası çağrılır — listener durumunu sıfırla."""
    if _hotkey:
        _hotkey.reset_recording()
    _on_stop()


def _on_stop():
    try:
        _notify("processing")
        print("[SES] Kayıt durdu, işleniyor...")

        audio_path = _recorder.stop()

        if not audio_path:
            print("[SES] Ses tespit edilemedi (çok kısa veya sessiz).")
            return

        text = speech_recognizer.transcribe(audio_path)
        print(f"[SES] Transkript: '{text}'")

        if not text or len(text.strip()) < 2:
            text_to_speech.speak("Anlayamadım.")
            return

        _notify("transcript", text)
        _execute(text)
    except Exception as e:
        print(f"[SES] İşleme hatası: {e}")
        _notify("error", str(e))
    finally:
        # _notify("done") her durumda çağrılır
        _notify("done")
        try:
            _busy.release()
        except RuntimeError:
            pass


def _groq_nlu(text: str) -> dict:
    try:
        completion = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _NLU_SYSTEM},
                {"role": "user", "content": text},
            ],
            max_tokens=256,
            temperature=0.1,
        )
        raw = completion.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[NLU] Groq hatası: {e}")
        return {"intent": "general", "params": {"answer": "Anlayamadım efendim."}}


def _handle_intent(intent: str, params: dict) -> None:
    try:
        if intent == "weather":
            from ai.news_weather import get_weather
            city = params.get("city", "Istanbul")
            full = get_weather(city)
            summary = _groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Aşağıdaki hava durumu verisini sesli asistan için 1-2 cümleye özetle. Sadece metin yaz, emoji yok."},
                    {"role": "user", "content": full},
                ],
                max_tokens=80,
            ).choices[0].message.content.strip()
            text_to_speech.speak(summary)

        elif intent == "reminder_set":
            from ai.calendar_mgr import add_calendar_event
            reminder_text = params.get("text", "")
            when_str = params.get("when", "")
            ok, _ = add_calendar_event(chat_id=0, text=reminder_text, when_str=when_str)
            if ok:
                text_to_speech.speak(f"Tamam efendim, {when_str} için hatırlatırım.")
            else:
                text_to_speech.speak("Zamanı anlayamadım, tekrar söyler misiniz?")

        elif intent == "reminder_list":
            from ai.calendar_mgr import get_reminders_text
            reminders = get_reminders_text(chat_id=0)
            if "yok" in reminders.lower():
                text_to_speech.speak("Aktif hatırlatmanız yok efendim.")
            else:
                clean = re.sub(r"[*_`#━]", "", reminders)
                text_to_speech.speak(clean[:400])

        elif intent == "general":
            answer = params.get("answer", "Anlayamadım.")
            text_to_speech.speak(answer)

        elif intent == "system":
            cmd = params.get("cmd", "unknown")
            args = params.get("args", [])
            _execute_system(cmd, args)

        else:
            text_to_speech.speak("Anlayamadım efendim.")

    except Exception as e:
        print(f"[NLU] Intent işleme hatası ({intent}): {e}")
        text_to_speech.speak("Bir hata oluştu efendim.")


def _execute_system(cmd: str, args: list) -> None:
    try:
        if cmd == "shutdown":
            text_to_speech.speak("Bilgisayar kapatılıyor.")
            from core.power_manager import immediate_shutdown
            immediate_shutdown()

        elif cmd == "restart":
            text_to_speech.speak("Yeniden başlatılıyor.")
            from core.power_manager import immediate_restart
            immediate_restart()

        elif cmd == "sleep":
            text_to_speech.speak("Uyku moduna geçiliyor.")
            from core.power_manager import sleep_pc
            sleep_pc()

        elif cmd == "hibernate":
            text_to_speech.speak("Hazırda bekleme moduna geçiliyor.")
            from core.power_manager import hibernate_pc
            hibernate_pc()

        elif cmd == "screenshot":
            import mss
            from PIL import Image
            import datetime
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                path = Path.home() / "Desktop" / f"ekran_{datetime.datetime.now().strftime('%H%M%S')}.jpg"
                img.save(str(path), "JPEG", quality=85)
            text_to_speech.speak("Ekran görüntüsü masaüstüne kaydedildi.")

        elif cmd == "status":
            from core.system_info import get_cpu_info, get_ram_info, get_gpu_info
            cpu = get_cpu_info()
            ram = get_ram_info()
            gpu = get_gpu_info()
            msg = f"CPU yüzde {cpu['percent']:.0f}, RAM yüzde {ram['percent']:.0f} kullanımda."
            if gpu["available"] and gpu["gpus"]:
                g = gpu["gpus"][0]
                msg += f" GPU yüzde {g['usage']} kullanımda, sıcaklık {g['temp']} derece."
            text_to_speech.speak(msg)

        elif cmd == "volume_up":
            from core.audio_controller import volume_up
            new = volume_up(10)
            text_to_speech.speak(f"Ses yüzde {new}.")

        elif cmd == "volume_down":
            from core.audio_controller import volume_down
            new = volume_down(10)
            text_to_speech.speak(f"Ses yüzde {new}.")

        elif cmd == "volume_set":
            level = args[0] if args else None
            if level is not None:
                from core.audio_controller import set_volume
                new = set_volume(int(level))
                text_to_speech.speak(f"Ses yüzde {new} olarak ayarlandı.")

        elif cmd == "mute":
            from core.audio_controller import toggle_mute
            muted = toggle_mute()
            text_to_speech.speak("Sessiz." if muted else "Ses açık.")

        elif cmd == "lock":
            text_to_speech.speak("Ekran kilitleniyor.")
            from core.display_manager import lock_screen
            lock_screen()

        elif cmd == "clipboard":
            from core.clipboard_manager import get_clipboard
            content = get_clipboard()
            if content:
                text_to_speech.speak(f"Panoda: {content[:80]}")
            else:
                text_to_speech.speak("Pano boş.")

        elif cmd == "gpu":
            from core.system_info import get_gpu_info
            gpu = get_gpu_info()
            if gpu["available"] and gpu["gpus"]:
                g = gpu["gpus"][0]
                text_to_speech.speak(f"{g['name']}: yüzde {g['usage']} kullanım, {g['temp']} derece.")
            else:
                text_to_speech.speak("GPU bilgisi alınamadı.")

        elif cmd == "brightness_set":
            level = args[0] if args else None
            if level is not None:
                from core.display_manager import set_brightness
                set_brightness(int(level))
                text_to_speech.speak(f"Parlaklık yüzde {level} olarak ayarlandı.")

        elif cmd == "windows":
            from core.window_manager import get_windows
            windows = get_windows()
            text_to_speech.speak(f"{len(windows)} açık pencere var.")

        elif cmd == "help":
            text_to_speech.speak(
                "Sesli komutlar: hava durumu, hatırlatıcı kur, sistem durumu, "
                "ekran görüntüsü, ses aç, ses kıs, sessiz, kilitle, pano, "
                "bilgisayarı kapat, yeniden başlat, uyku, uygulama adı aç."
            )

        elif cmd == "launch":
            target = args[0] if args else ""
            if target:
                from core.launcher import open_app, open_url
                if any(target.startswith(p) for p in ("http", "www.")):
                    ok, _ = open_url(target)
                else:
                    ok, _ = open_app(target)
                text_to_speech.speak(f"{target} açıldı." if ok else f"{target} açılamadı.")
            else:
                text_to_speech.speak("Ne açmak istediğinizi söyleyin.")

        elif cmd == "open_file":
            target = args[0] if args else ""
            if target:
                from core.launcher import find_and_open
                ok, _ = find_and_open(target)
                text_to_speech.speak(f"{target} açıldı." if ok else f"{target} bulunamadı.")

        elif cmd == "open_url":
            url = args[0] if args else ""
            if url:
                from core.launcher import open_url
                ok, _ = open_url(url)
                text_to_speech.speak("Tarayıcıda açıldı." if ok else "Açılamadı.")

        elif cmd == "open_folder":
            folder = args[0] if args else ""
            if folder:
                from core.launcher import open_folder
                ok, _ = open_folder(folder)
                text_to_speech.speak("Klasör açıldı." if ok else "Klasör bulunamadı.")

        elif cmd == "close_proc":
            target = args[0] if args else ""
            if target:
                from core.process_manager import kill_process
                ok, _ = kill_process(target)
                text_to_speech.speak(f"{target} kapatıldı." if ok else f"{target} bulunamadı.")

        else:
            text_to_speech.speak("Bu komutu anlayamadım.")

    except Exception as e:
        print(f"[SES] Sistem komutu hatası ({cmd}): {e}")
        text_to_speech.speak("Bir hata oluştu.")


def _execute(text: str):
    print(f"[SES] NLU analiz ediliyor: '{text}'")
    result = _groq_nlu(text)
    intent = result.get("intent", "general")
    params = result.get("params", {})
    print(f"[SES] Intent: {intent}, params: {params}")
    _notify("transcript", text)
    _handle_intent(intent, params)




def start(indicator=None):
    if indicator:
        set_indicator(indicator)

    # TTS başlat ve hazır olmasını bekle
    text_to_speech.start()
    text_to_speech.wait_ready()

    # STT modelini/API'yi hazırla — hazır olunca "ready" bildir
    _notify("loading")

    def _on_model_ready():
        _notify("ready")
        print("[SES] Ses asistanı hazır.")

    speech_recognizer.preload(on_complete=_on_model_ready)

    global _hotkey, _wake_word_listener
    _hotkey = HotkeyListener(on_start=_on_start, on_stop=_on_stop)
    _hotkey.start()

    # 'Bürküt' kelime tetikleyicisi
    from voice.wake_word import WakeWordListener
    _wake_word_listener = WakeWordListener(
        on_wake=_on_start,
        is_busy_fn=lambda: _busy.locked(),
    )
    _wake_word_listener.start()

    global _wake_listener
    from voice.wake_clap import WakeGestureListener
    _wake_listener = WakeGestureListener(on_wake=_on_start)
    _wake_listener.start()
    print("[SES] Çift alkış dinleyicisi başlatıldı.")

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.audio_recorder import AudioRecorder
from voice.hotkey_listener import HotkeyListener
from voice import speech_recognizer, text_to_speech, shared_state
from voice.command_parser import parse


_recorder = AudioRecorder()
_busy = threading.Lock()
_wake_listener = None


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
        print("[SES] Kayıt başladı...")
        _recorder.start()
    except Exception as e:
        print(f"[SES] Kayıt başlatma hatası: {e}")
        _notify("error", str(e))
        _busy.release()


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


def _execute(text: str):
    command, args = parse(text)
    print(f"[SES] Komut: {command}, args: {args}")

    try:
        if command == "shutdown":
            text_to_speech.speak("Bilgisayar kapatılıyor.")
            from core.power_manager import immediate_shutdown
            immediate_shutdown()

        elif command == "restart":
            text_to_speech.speak("Yeniden başlatılıyor.")
            from core.power_manager import immediate_restart
            immediate_restart()

        elif command == "sleep":
            text_to_speech.speak("Uyku moduna geçiliyor.")
            from core.power_manager import sleep_pc
            sleep_pc()

        elif command == "hibernate":
            text_to_speech.speak("Hazırda bekleme moduna geçiliyor.")
            from core.power_manager import hibernate_pc
            hibernate_pc()

        elif command == "screenshot":
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

        elif command == "status":
            from core.system_info import get_cpu_info, get_ram_info, get_gpu_info
            cpu = get_cpu_info()
            ram = get_ram_info()
            gpu = get_gpu_info()
            msg = f"CPU yüzde {cpu['percent']:.0f}, RAM yüzde {ram['percent']:.0f} kullanımda."
            if gpu["available"] and gpu["gpus"]:
                g = gpu["gpus"][0]
                msg += f" GPU yüzde {g['usage']} kullanımda, sıcaklık {g['temp']} derece."
            text_to_speech.speak(msg)

        elif command == "volume_up":
            from core.audio_controller import volume_up
            new = volume_up(10)
            text_to_speech.speak(f"Ses yüzde {new}.")

        elif command == "volume_down":
            from core.audio_controller import volume_down
            new = volume_down(10)
            text_to_speech.speak(f"Ses yüzde {new}.")

        elif command == "volume_set":
            level = args[0] if args else None
            if level is not None:
                from core.audio_controller import set_volume
                new = set_volume(int(level))
                text_to_speech.speak(f"Ses yüzde {new} olarak ayarlandı.")

        elif command == "mute":
            from core.audio_controller import toggle_mute
            muted = toggle_mute()
            text_to_speech.speak("Sessiz." if muted else "Ses açık.")

        elif command == "lock":
            text_to_speech.speak("Ekran kilitleniyor.")
            from core.display_manager import lock_screen
            lock_screen()

        elif command == "clipboard":
            from core.clipboard_manager import get_clipboard
            content = get_clipboard()
            if content:
                preview = content[:80]
                text_to_speech.speak(f"Panoda: {preview}")
            else:
                text_to_speech.speak("Pano boş.")

        elif command == "gpu":
            from core.system_info import get_gpu_info
            gpu = get_gpu_info()
            if gpu["available"] and gpu["gpus"]:
                g = gpu["gpus"][0]
                text_to_speech.speak(
                    f"{g['name']}: yüzde {g['usage']} kullanım, {g['temp']} derece."
                )
            else:
                text_to_speech.speak("GPU bilgisi alınamadı.")

        elif command == "brightness_set":
            level = args[0] if args else None
            if level is not None:
                from core.display_manager import set_brightness
                set_brightness(int(level))
                text_to_speech.speak(f"Parlaklık yüzde {level} olarak ayarlandı.")

        elif command == "windows":
            from core.window_manager import get_windows
            windows = get_windows()
            text_to_speech.speak(f"{len(windows)} açık pencere var.")

        elif command == "help":
            text_to_speech.speak(
                "Şu komutları anlıyorum: sistem durumu, ekran görüntüsü, ses aç, ses kıs, "
                "sessiz, kilitle, pano, bilgisayarı kapat, yeniden başlat, uyku, ve uygulama adı aç."
            )

        elif command == "launch":
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

        elif command == "open_file":
            target = args[0] if args else ""
            if target:
                from core.launcher import find_and_open
                ok, _ = find_and_open(target)
                text_to_speech.speak(f"{target} açıldı." if ok else f"{target} bulunamadı.")

        elif command == "open_url":
            url = args[0] if args else ""
            if url:
                from core.launcher import open_url
                ok, _ = open_url(url)
                text_to_speech.speak("Tarayıcıda açıldı." if ok else "Açılamadı.")

        elif command == "open_folder":
            folder = args[0] if args else ""
            if folder:
                from core.launcher import open_folder
                ok, _ = open_folder(folder)
                text_to_speech.speak("Klasör açıldı." if ok else "Klasör bulunamadı.")

        elif command == "close_proc":
            target = args[0] if args else ""
            if target:
                from core.process_manager import kill_process
                ok, _ = kill_process(target)
                text_to_speech.speak(f"{target} kapatıldı." if ok else f"{target} bulunamadı.")

        else:
            text_to_speech.speak(f"Bu komutu anlayamadım.")
            print(f"[SES] Bilinmeyen komut: {command} — '{text}'")

    except Exception as e:
        print(f"[SES] Komut çalıştırma hatası ({command}): {e}")
        text_to_speech.speak("Bir hata oluştu.")


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
        text_to_speech.speak("Ses asistanı hazır. Kontrol artı boşluk veya çift alkış ile aktif edin.")
        print("[SES] Ses asistanı hazır.")

    speech_recognizer.preload(on_complete=_on_model_ready)

    listener = HotkeyListener(on_start=_on_start, on_stop=_on_stop)
    listener.start()

    global _wake_listener
    from voice.wake_clap import WakeGestureListener
    _wake_listener = WakeGestureListener(on_wake=_on_start)
    _wake_listener.start()
    print("[SES] Çift alkış dinleyicisi başlatıldı.")

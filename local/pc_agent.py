"""
BÜRKÜT Local PC Agent
---------------------
PC başladığında çalışır. Render'daki Telegram botu ile HTTP polling üzerinden
iletişim kurar ve donanım komutlarını yerel makinede çalıştırır.

Çalıştırmak için: pythonw local/start_agent.pyw  (sessiz)
                  python  local/pc_agent.py       (konsolla)
"""

import os
import sys
import json
import time
import base64
import threading
from pathlib import Path

# Proje kökünü path'e ekle
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

import requests

RENDER_URL  = os.environ.get("RENDER_URL", "").rstrip("/")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")
POLL_INTERVAL = 1.5  # saniye


def _log(msg: str) -> None:
    print(f"[PC-AGENT] {msg}", flush=True)


# ── Render ile iletişim ───────────────────────────────────────────────────────

def poll() -> dict | None:
    """Render bot'tan bekleyen komut al."""
    try:
        r = requests.get(
            f"{RENDER_URL}/agent/poll",
            headers={"X-Agent-Token": AGENT_TOKEN},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        _log(f"Poll hatası: {e}")
    return None


def send_result(cmd_id: str, ok: bool, data=None, error: str = "") -> None:
    """Komut sonucunu Render bot'a gönder."""
    try:
        requests.post(
            f"{RENDER_URL}/agent/result",
            headers={"X-Agent-Token": AGENT_TOKEN},
            json={"id": cmd_id, "ok": ok, "data": data, "error": error},
            timeout=5,
        )
    except Exception as e:
        _log(f"Sonuç gönderme hatası: {e}")


# ── Komut işleyiciler ─────────────────────────────────────────────────────────

def _cmd_screenshot(params: dict) -> tuple[bool, object]:
    import mss
    from PIL import Image
    import io
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
    return True, base64.b64encode(buf.getvalue()).decode()


def _cmd_system_status(params: dict) -> tuple[bool, object]:
    from core.system_info import get_full_status
    return True, get_full_status()


def _cmd_mouse_move(params: dict) -> tuple[bool, object]:
    from core.keyboard_mouse import move_mouse
    move_mouse(int(params["x"]), int(params["y"]))
    return True, None


def _cmd_mouse_click(params: dict) -> tuple[bool, object]:
    from core.keyboard_mouse import click
    click(int(params["x"]), int(params["y"]))
    return True, None


def _cmd_type_text(params: dict) -> tuple[bool, object]:
    import pyperclip
    from core.keyboard_mouse import press_key
    pyperclip.copy(params["text"])
    press_key("ctrl", "v")
    return True, None


def _cmd_press_key(params: dict) -> tuple[bool, object]:
    from core.keyboard_mouse import press_key, hotkey
    keys_raw = params.get("keys", "").strip().lower()
    if not keys_raw:
        return False, "Tuş belirtilmedi."
    # "ctrl+c" → ["ctrl","c"]  |  "enter" → ["enter"]
    keys = [k.strip() for k in keys_raw.replace("+", " ").split() if k.strip()]
    if not keys:
        return False, "Geçersiz tuş."
    if len(keys) == 1:
        press_key(keys[0])
    else:
        hotkey(*keys)
    label = "+".join(keys).upper()
    return True, f"✅ `{label}` tuşuna basıldı."


def _cmd_open_app(params: dict) -> tuple[bool, object]:
    from core.process_manager import start_process
    ok_flag, msg = start_process(params["app"])
    return ok_flag, msg


def _cmd_volume(params: dict) -> tuple[bool, object]:
    from core.audio_controller import get_volume_info, set_volume
    if "level" in params:
        lvl = set_volume(int(params["level"]))
        return True, f"Ses %{lvl}"
    return True, get_volume_info()


def _cmd_open_url(params: dict) -> tuple[bool, object]:
    from core.launcher import open_url
    ok_flag, msg = open_url(params["url"])
    return ok_flag, msg


def _cmd_webcam_photo(params: dict) -> tuple[bool, object]:
    from core.media_manager import take_webcam_photo
    buf = take_webcam_photo()
    buf.seek(0)
    return True, base64.b64encode(buf.read()).decode()


def _cmd_audio_record(params: dict) -> tuple[bool, object]:
    duration = int(params.get("duration", 10))
    from core.media_manager import record_audio
    path = record_audio(duration)
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    import os as _os2; _os2.unlink(path)
    return True, {"data": data, "duration": duration}


def _cmd_full_status(params: dict) -> tuple[bool, object]:
    from core.system_info import get_full_status
    return True, get_full_status()


def _cmd_process_list(params: dict) -> tuple[bool, object]:
    from core.process_manager import get_running_processes, format_process_list
    procs = get_running_processes(params.get("filter", ""))[:10]
    return True, format_process_list(procs)


def _cmd_programs_list(params: dict) -> tuple[bool, object]:
    from core.process_manager import get_user_applications, format_process_list
    return True, format_process_list(get_user_applications())


def _cmd_network_info(params: dict) -> tuple[bool, object]:
    from core.system_info import get_network_info
    return True, get_network_info()


def _cmd_shutdown(params: dict) -> tuple[bool, object]:
    delay = int(params.get("delay", 0))
    from core.power_manager import immediate_shutdown
    def _do():
        if delay: time.sleep(delay)
        immediate_shutdown()
    threading.Thread(target=_do, daemon=True).start()
    return True, f"🔴 PC {'kapatılıyor' if not delay else f'{delay}s sonra kapatılacak'}..."


def _cmd_restart(params: dict) -> tuple[bool, object]:
    delay = int(params.get("delay", 0))
    from core.power_manager import immediate_restart
    def _do():
        if delay: time.sleep(delay)
        immediate_restart()
    threading.Thread(target=_do, daemon=True).start()
    return True, f"🔁 PC {'yeniden başlatılıyor' if not delay else f'{delay}s sonra yeniden başlatılacak'}..."


def _cmd_sleep(params: dict) -> tuple[bool, object]:
    from core.power_manager import sleep_pc
    threading.Thread(target=sleep_pc, daemon=True).start()
    return True, "😴 PC uyku moduna geçiyor..."


def _cmd_hibernate(params: dict) -> tuple[bool, object]:
    from core.power_manager import hibernate_pc
    threading.Thread(target=hibernate_pc, daemon=True).start()
    return True, "💤 PC hazırda beklemeye geçiyor..."


def _cmd_cancel_shutdown(params: dict) -> tuple[bool, object]:
    from core.power_manager import cancel_scheduled_shutdown
    ok = cancel_scheduled_shutdown()
    return True, "✅ Zamanlayıcı iptal edildi." if ok else "ℹ️ Aktif zamanlayıcı yok."


def _cmd_shutdown_status(params: dict) -> tuple[bool, object]:
    from core.power_manager import get_shutdown_status
    return True, get_shutdown_status()


def _cmd_kill_process(params: dict) -> tuple[bool, object]:
    from core.process_manager import kill_process
    ok, msg = kill_process(params.get("identifier", ""))
    return ok, msg


def _cmd_run_process(params: dict) -> tuple[bool, object]:
    from core.process_manager import start_process
    ok, msg = start_process(params.get("program", ""))
    return ok, msg


def _cmd_browse_files(params: dict) -> tuple[bool, object]:
    from core.file_manager import list_directory, format_directory_listing
    listing = list_directory(params.get("path", ""))
    if "error" in listing:
        return False, listing["error"]
    return True, {"text": format_directory_listing(listing), "files": listing.get("files", [])}


def _cmd_search_files(params: dict) -> tuple[bool, object]:
    from core.file_manager import search_files, format_search_results
    q = params.get("query", "")
    return True, format_search_results(search_files(q), q)


def _cmd_download_file(params: dict) -> tuple[bool, object]:
    import os as _os3
    from pathlib import Path as _Path
    path = params.get("path", "")
    if not _os3.path.isfile(path):
        return False, f"Dosya bulunamadı: {path}"
    size = _os3.path.getsize(path)
    if size > 45 * 1024 * 1024:
        return False, f"Dosya çok büyük ({size // (1024*1024)} MB). Max 45 MB."
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return True, {"data": data, "name": _Path(path).name, "size": size}


def _cmd_mute(params: dict) -> tuple[bool, object]:
    from core.audio_controller import toggle_mute
    now_muted = toggle_mute()
    return True, "🔇 Sessiz moda geçildi." if now_muted else "🔊 Ses açıldı."


def _cmd_brightness(params: dict) -> tuple[bool, object]:
    from core.display_manager import get_brightness, set_brightness
    if "level" in params:
        lvl = set_brightness(int(params["level"]))
        return True, f"☀️ Parlaklık %{lvl} olarak ayarlandı."
    return True, get_brightness()


def _cmd_gpu_info(params: dict) -> tuple[bool, object]:
    from core.system_info import get_gpu_info
    return True, get_gpu_info()


def _cmd_lock_screen(params: dict) -> tuple[bool, object]:
    from core.display_manager import lock_screen
    lock_screen()
    return True, "🔒 Ekran kilitlendi."


def _cmd_windows_list(params: dict) -> tuple[bool, object]:
    from core.window_manager import get_windows, get_active_window
    return True, {"windows": get_windows(), "active": get_active_window()}


def _cmd_close_window_fn(params: dict) -> tuple[bool, object]:
    from core.window_manager import close_window
    title = params.get("title", "")
    ok = close_window(title)
    return ok, f"✅ Kapatıldı: `{title}`" if ok else f"❌ Bulunamadı: `{title}`"


def _cmd_focus_window_fn(params: dict) -> tuple[bool, object]:
    from core.window_manager import focus_window
    title = params.get("title", "")
    ok = focus_window(title)
    return ok, f"✅ Odaklanıldı: `{title}`" if ok else f"❌ Bulunamadı: `{title}`"


def _cmd_clipboard_get(params: dict) -> tuple[bool, object]:
    from core.clipboard_manager import get_clipboard
    return True, get_clipboard() or ""


def _cmd_clipboard_set(params: dict) -> tuple[bool, object]:
    from core.clipboard_manager import set_clipboard
    set_clipboard(params.get("text", ""))
    return True, "✅ Panoya yazıldı."


def _cmd_run_claude(params: dict) -> tuple[bool, object]:
    import os, groq
    from dotenv import load_dotenv
    load_dotenv()
    prompt = params.get("prompt", "").strip()
    if not prompt:
        return False, "Prompt boş."
    try:
        client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Sen Bürküt'sün. Kayra'nın kişisel yapay zeka asistanısın. Türkçe yanıt ver."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
        )
        output = completion.choices[0].message.content.strip() or "(çıktı yok)"
        return True, output
    except Exception as e:
        return False, str(e)


def _cmd_show_notification(params: dict) -> tuple[bool, object]:
    from core.notifier import show_overlay
    text = params.get("text", "").strip()
    duration = int(params.get("duration", 8))
    if not text:
        return False, "Mesaj boş."
    show_overlay(text, duration=duration)
    return True, "Bildirim gösterildi."


_HANDLERS = {
    # Mevcut
    "screenshot":    _cmd_screenshot,
    "system_status": _cmd_system_status,
    "mouse_move":    _cmd_mouse_move,
    "mouse_click":   _cmd_mouse_click,
    "type_text":     _cmd_type_text,
    "open_app":      _cmd_open_app,
    "volume":        _cmd_volume,
    "open_url":      _cmd_open_url,
    "ping":          lambda p: (True, "pong"),
    # Yeni
    "webcam_photo":    _cmd_webcam_photo,
    "audio_record":    _cmd_audio_record,
    "full_status":     _cmd_full_status,
    "process_list":    _cmd_process_list,
    "programs_list":   _cmd_programs_list,
    "network_info":    _cmd_network_info,
    "shutdown":        _cmd_shutdown,
    "restart":         _cmd_restart,
    "sleep":           _cmd_sleep,
    "hibernate":       _cmd_hibernate,
    "cancel_shutdown": _cmd_cancel_shutdown,
    "shutdown_status": _cmd_shutdown_status,
    "kill_process":    _cmd_kill_process,
    "run_process":     _cmd_run_process,
    "browse_files":    _cmd_browse_files,
    "search_files":    _cmd_search_files,
    "download_file":   _cmd_download_file,
    "mute":            _cmd_mute,
    "brightness":      _cmd_brightness,
    "gpu_info":        _cmd_gpu_info,
    "lock_screen":     _cmd_lock_screen,
    "windows_list":    _cmd_windows_list,
    "close_window":    _cmd_close_window_fn,
    "focus_window":    _cmd_focus_window_fn,
    "clipboard_get":   _cmd_clipboard_get,
    "clipboard_set":   _cmd_clipboard_set,
    "run_claude":      _cmd_run_claude,
    "press_key":          _cmd_press_key,
    "show_notification":  _cmd_show_notification,
}


def execute(cmd: dict) -> None:
    """Komutu çalıştır ve sonucu Render'a gönder (ayrı thread'de çağrılır)."""
    action  = cmd.get("action", "")
    params  = cmd.get("params", {})
    cmd_id  = cmd.get("id", "")

    _log(f"→ {action} {params}")

    handler = _HANDLERS.get(action)
    if handler is None:
        send_result(cmd_id, False, error=f"Bilinmeyen komut: {action}")
        return

    try:
        ok, data = handler(params)
        send_result(cmd_id, ok, data)
    except Exception as e:
        _log(f"Komut hatası ({action}): {e}")
        send_result(cmd_id, False, error=str(e))


# ── Startup bildirimi ─────────────────────────────────────────────────────────

def _send_startup_photo() -> None:
    """PC açılışında webcam fotoğrafı Telegram'a gönder."""
    token = os.environ.get("BOT_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    owner = os.environ.get("OWNER_ID", "") or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not owner:
        _log("Startup fotoğrafı atlandı: BOT_TOKEN veya OWNER_ID eksik")
        return
    try:
        from core.media_manager import take_webcam_photo
        buf = take_webcam_photo()
        for cid in [c.strip() for c in owner.split(",") if c.strip()]:
            buf.seek(0)
            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={"chat_id": cid, "caption": "👁️ PC açıldı — webcam görüntüsü"},
                    files={"photo": ("webcam.jpg", buf, "image/jpeg")},
                    timeout=15,
                )
                _log(f"Startup fotoğrafı gönderildi → {cid}")
            except Exception as e:
                _log(f"Fotoğraf gönderilemedi ({cid}): {e}")
    except Exception as e:
        _log(f"Webcam fotoğrafı alınamadı: {e}")


# ── Widget ve ses asistanı başlatıcılar ───────────────────────────────────────

def _start_widget() -> None:
    try:
        from widget.main_widget import start_widget
        threading.Thread(target=start_widget, daemon=True).start()
        _log("Widget başlatıldı.")
    except Exception as e:
        _log(f"Widget başlatılamadı: {e}")


def _start_voice(indicator=None) -> None:
    try:
        from voice.voice_assistant import start as voice_start
        threading.Thread(target=voice_start, args=(indicator,), daemon=True).start()
        _log("Ses asistanı başlatıldı.")
    except Exception as e:
        _log(f"Ses asistanı başlatılamadı: {e}")


# ── Ana döngü ─────────────────────────────────────────────────────────────────

def main() -> None:
    if not RENDER_URL:
        _log("HATA: .env dosyasına RENDER_URL ekleyin  (örn: https://burkut-bot.onrender.com)")
        sys.exit(1)
    if not AGENT_TOKEN:
        _log("HATA: .env dosyasına AGENT_TOKEN ekleyin")
        sys.exit(1)

    _log(f"Render bağlantısı: {RENDER_URL}")

    _send_startup_photo()
    _start_widget()
    _start_voice()

    _log("Komut polling başladı...")
    while True:
        cmd = poll()
        if cmd and cmd.get("type") != "idle":
            threading.Thread(target=execute, args=(cmd,), daemon=True).start()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

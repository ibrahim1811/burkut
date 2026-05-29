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


_HANDLERS = {
    "screenshot":    _cmd_screenshot,
    "system_status": _cmd_system_status,
    "mouse_move":    _cmd_mouse_move,
    "mouse_click":   _cmd_mouse_click,
    "type_text":     _cmd_type_text,
    "open_app":      _cmd_open_app,
    "volume":        _cmd_volume,
    "open_url":      _cmd_open_url,
    "ping":          lambda p: (True, "pong"),
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

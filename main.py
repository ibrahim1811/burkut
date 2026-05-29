#!/usr/bin/env python3
"""
BÜRKÜT — Telegram PC Kontrol Botu
Telegram aracılığıyla PC'yi uzaktan yönetin.
"""

import sys
import asyncio
import signal
import threading
import time
from pathlib import Path

# Proje kök dizinini Python path'ine ekle
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Telegram mesaj boyut limiti (güvenli taraf)
_MSG_LIMIT = 4000

from utils.config_manager import load_config, get_config
from utils.logger import setup_logger, get_logger
from bot import handlers, callbacks
from bot.messages import BOT_STARTED


logger = setup_logger()

_last_startup_notify: float = 0.0  # spam koruması


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.error import Conflict, NetworkError, TimedOut
    if isinstance(context.error, Conflict):
        logger.warning("Telegram Conflict: Başka bir instance aktif. 30sn sonra tekrar denenecek...")
        await asyncio.sleep(30)
        return
    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning(f"Ağ hatası (geçici): {context.error}")
        return
    logger.error(f"Telegram hata: {context.error}")


def register_handlers(app: Application) -> None:
    # Temel komutlar
    app.add_handler(CommandHandler("start", handlers.cmd_start))    # Telegram zorunlu
    app.add_handler(CommandHandler("baslat", handlers.cmd_start))
    app.add_handler(CommandHandler("yardim", handlers.cmd_help))
    app.add_handler(CommandHandler("menu", handlers.cmd_menu))

    # Sistem izleme
    app.add_handler(CommandHandler("durum", handlers.cmd_status))
    app.add_handler(CommandHandler("ekran", handlers.cmd_screenshot))
    app.add_handler(CommandHandler("foto", handlers.cmd_foto))
    app.add_handler(CommandHandler("ses", handlers.cmd_ses))
    app.add_handler(CommandHandler("islemler", handlers.cmd_processes))
    app.add_handler(CommandHandler("ag", handlers.cmd_network))

    # Güç yönetimi
    app.add_handler(CommandHandler("kapat", handlers.cmd_shutdown))
    app.add_handler(CommandHandler("yenibaslat", handlers.cmd_restart))
    app.add_handler(CommandHandler("uyku", handlers.cmd_sleep))
    app.add_handler(CommandHandler("hazirda", handlers.cmd_hibernate))
    app.add_handler(CommandHandler("iptal", handlers.cmd_cancel_shutdown))
    app.add_handler(CommandHandler("kapanma_durum", handlers.cmd_shutdown_status))

    # Program kontrolü
    app.add_handler(CommandHandler("programlar", handlers.cmd_programs))
    app.add_handler(CommandHandler("sonlandir", handlers.cmd_kill))
    app.add_handler(CommandHandler("calistir", handlers.cmd_run))

    # Dosya işlemleri
    app.add_handler(CommandHandler("gozat", handlers.cmd_browse))
    app.add_handler(CommandHandler("indir", handlers.cmd_download))
    app.add_handler(CommandHandler("ara", handlers.cmd_search))
    app.add_handler(CommandHandler("hizligonder", handlers.cmd_quicksend))

    # Bildirimler
    app.add_handler(CommandHandler("bildirim", handlers.cmd_notify))
    app.add_handler(CommandHandler("bosta_bildir", handlers.cmd_alert_when_idle))
    app.add_handler(CommandHandler("program_bitince", handlers.cmd_alert_when_process))
    app.add_handler(CommandHandler("klasor_izle", handlers.cmd_monitor_folder))
    app.add_handler(CommandHandler("izlemeyi_durdur", handlers.cmd_stop_monitoring))

    # Ses & Ekran kontrolü
    app.add_handler(CommandHandler("volume", handlers.cmd_volume))
    app.add_handler(CommandHandler("sessiz", handlers.cmd_mute))
    app.add_handler(CommandHandler("parlaklik", handlers.cmd_brightness))
    app.add_handler(CommandHandler("kilitle", handlers.cmd_lock))
    app.add_handler(CommandHandler("gpu", handlers.cmd_gpu))

    # Pencere yönetimi
    app.add_handler(CommandHandler("pencereler", handlers.cmd_windows))
    app.add_handler(CommandHandler("pencere_kapat", handlers.cmd_close_window))
    app.add_handler(CommandHandler("pencere_odak", handlers.cmd_focus_window))

    # Pano
    app.add_handler(CommandHandler("pano", handlers.cmd_clipboard))
    app.add_handler(CommandHandler("pano_yaz", handlers.cmd_clipboard_write))

    # Mouse & Klavye
    app.add_handler(CommandHandler("fare", handlers.cmd_mouse_move))
    app.add_handler(CommandHandler("tikla", handlers.cmd_click))
    app.add_handler(CommandHandler("yaz", handlers.cmd_type))

    # Launcher
    app.add_handler(CommandHandler("ac", handlers.cmd_open))

    # Ses asistanı
    app.add_handler(CommandHandler("asistan", handlers.cmd_voice_status))

    # ── AI / Bürküt komutları ─────────────────────────────────────────────────
    app.add_handler(CommandHandler("burkut", handlers.cmd_burkut))
    app.add_handler(CommandHandler("sifirla", handlers.cmd_sifirla))
    app.add_handler(CommandHandler("model", handlers.cmd_model))
    app.add_handler(CommandHandler("hava", handlers.cmd_hava))
    app.add_handler(CommandHandler("haber", handlers.cmd_haber))
    app.add_handler(CommandHandler("hatirlatici", handlers.cmd_hatirlatici))
    app.add_handler(CommandHandler("oku", handlers.cmd_oku))
    app.add_handler(CommandHandler("kod", handlers.cmd_kod_analiz))

    # Callback query handler (inline keyboard)
    app.add_handler(CallbackQueryHandler(callbacks.callback_handler))

    # Belge/dosya gönderme handler — önce AI kod analizi, sonra normal handler
    app.add_handler(
        MessageHandler(filters.Document.ALL, handlers.handle_document_ai)
    )
    app.add_handler(
        MessageHandler(filters.Document.ALL, handlers.handle_document)
    )

    # Düz metin → Bürküt AI (komut dışı mesajlar)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handlers.handle_ai_message,
        )
    )

    # Bilinmeyen komutlar (en sona eklenmeli)
    app.add_handler(
        MessageHandler(filters.COMMAND, handlers.cmd_unknown)
    )

    logger.info("Tüm handler'lar kaydedildi.")


async def post_init(app: Application) -> None:
    """Bot başladıktan sonra owner'a bildirim ve kamera fotoğrafı gönder."""
    global _last_startup_notify
    cfg = get_config()
    owner_ids = cfg.get("authorized_users", [])

    # Son bildirimden 5 dakika geçmediyse tekrar gönderme
    now = time.time()
    if now - _last_startup_notify > 300 and owner_ids:
        _last_startup_notify = now
        for uid in owner_ids:
            try:
                await app.bot.send_message(
                    chat_id=uid,
                    text=BOT_STARTED,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning(f"Owner bildirimi gönderilemedi (ID: {uid}): {e}")

    # Başlangıç kamera fotoğrafı — local ortamda pc_agent.py halleder, Render'da webcam yok
    if not _os.environ.get("PORT") and cfg.get("startup_webcam_photo", True) and owner_ids:
        try:
            from core.media_manager import take_webcam_photo
            from core.offline_queue import is_online, enqueue_photo
            loop = asyncio.get_running_loop()
            buf = await loop.run_in_executor(None, take_webcam_photo)
            if is_online():
                for uid in owner_ids:
                    buf.seek(0)
                    try:
                        await app.bot.send_photo(
                            chat_id=uid,
                            photo=buf,
                            caption="👁️ PC açıldı — webcam görüntüsü",
                        )
                    except Exception as e:
                        logger.warning(f"Başlangıç kamera fotoğrafı gönderilemedi (ID: {uid}): {e}")
                        buf.seek(0)
                        enqueue_photo(uid, buf, "👁️ PC açıldı — webcam görüntüsü")
            else:
                for uid in owner_ids:
                    buf.seek(0)
                    enqueue_photo(uid, buf, "👁️ PC açıldı — webcam görüntüsü")
                logger.info("Başlangıç: internet yok, webcam fotoğrafı kuyruğa alındı.")
        except Exception as e:
            logger.warning(f"Başlangıç kamera fotoğrafı alınamadı: {e}")

    # Bürküt brain'e Telegram gönderici bağla
    from ai.brain import set_telegram_sender

    bot_loop = asyncio.get_running_loop()

    async def _send_msg(chat_id: int, text: str) -> None:
        await app.bot.send_message(chat_id=chat_id, text=text)

    def _tg_send_sync(chat_id: int, text: str) -> None:
        """Herhangi bir thread'den çağrılabilir — bot loop'unda çalışır."""
        try:
            future = asyncio.run_coroutine_threadsafe(
                _send_msg(chat_id, text), bot_loop
            )
            # Hataları logla — sessiz kayıpları önle
            def _log_err(f):
                exc = f.exception()
                if exc:
                    logger.warning(f"Telegram mesajı gönderilemedi: {exc}")
            future.add_done_callback(_log_err)
        except Exception as e:
            logger.warning(f"Telegram schedule hatası: {e}")

    set_telegram_sender(_tg_send_sync)

    # Widget ve ses asistanını başlat
    _start_widget_and_voice()

    # Hatırlatıcı kontrol döngüsünü başlat
    _start_reminder_checker(app)

    # Offline kuyruk izleyicisini başlat
    _start_offline_queue_watcher(app)

    logger.info("🦅 BÜRKÜT başlatıldı ve hazır.")


async def post_shutdown(app: Application) -> None:
    logger.info("BÜRKÜT kapatılıyor.")


def _start_widget_and_voice():
    """Widget ve ses asistanını başlatır — sadece local ortamda (PORT env yok)."""
    if _os.environ.get("PORT"):
        # Render/cloud ortamı — widget/ses local/pc_agent.py tarafından başlatılır
        return
    try:
        from widget.main_widget import start_widget
        widget_thread = threading.Thread(target=start_widget, daemon=True)
        widget_thread.start()
        logger.info("Masaüstü widget thread'i başlatıldı.")
    except Exception as e:
        logger.warning(f"Widget başlatılamadı: {e}")



# ── Local PC agent relay ──────────────────────────────────────────────────────
import os as _os
import queue as _queue
import uuid as _uuid

_AGENT_TOKEN       = _os.environ.get("AGENT_TOKEN", "")
_agent_cmd_queue:  _queue.Queue = _queue.Queue()   # Render → agent
_agent_results:    dict         = {}                # cmd_id → result dict
_agent_results_lock             = threading.Lock()
_agent_last_seen:  float        = 0.0              # son poll zamanı


def agent_is_online() -> bool:
    """Son 10 saniye içinde poll geldiyse agent bağlı sayılır."""
    return (time.time() - _agent_last_seen) < 10


async def send_to_agent(action: str, params: dict, timeout: float = 12.0):
    """
    Komutu agent kuyruğuna ekle, sonucu bekle.
    Agent çevrimdışıysa None döner.
    """
    if not agent_is_online():
        return None
    cmd_id = str(_uuid.uuid4())
    _agent_cmd_queue.put({"id": cmd_id, "action": action, "params": params})
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.4)
        with _agent_results_lock:
            if cmd_id in _agent_results:
                return _agent_results.pop(cmd_id)
    return None


def _start_health_server() -> None:
    """UptimeRobot health + local PC agent relay — sadece PORT env var varsa başlar."""
    port_str = _os.environ.get("PORT", "")
    if not port_str:
        return
    try:
        import time as _time
        from flask import Flask, request, jsonify
        health_app = Flask(__name__)

        @health_app.route("/health")
        def health():
            status = "online" if agent_is_online() else "offline"
            return jsonify({"status": "ok", "agent": status}), 200

        @health_app.route("/")
        def index():
            return "🦅 BÜRKÜT aktif", 200

        @health_app.route("/agent/poll")
        def agent_poll():
            global _agent_last_seen
            token = request.headers.get("X-Agent-Token", "")
            if _AGENT_TOKEN and token != _AGENT_TOKEN:
                return "Unauthorized", 401
            _agent_last_seen = _time.time()
            try:
                cmd = _agent_cmd_queue.get_nowait()
                return jsonify(cmd)
            except _queue.Empty:
                return jsonify({"type": "idle"})

        @health_app.route("/agent/result", methods=["POST"])
        def agent_result():
            token = request.headers.get("X-Agent-Token", "")
            if _AGENT_TOKEN and token != _AGENT_TOKEN:
                return "Unauthorized", 401
            data = request.get_json(force=True)
            with _agent_results_lock:
                _agent_results[data["id"]] = data
            return "OK", 200

        port = int(port_str)
        t = threading.Thread(
            target=lambda: health_app.run(host="0.0.0.0", port=port, use_reloader=False),
            daemon=True,
        )
        t.start()
        logger.info(f"Health+Agent server port {port}'de başladı.")
    except Exception as e:
        logger.warning(f"Health server başlatılamadı: {e}")


def _start_offline_queue_watcher(app: Application) -> None:
    """Offline kuyruk izleyicisini bot event loop'unda başlatır."""
    try:
        from core.offline_queue import start_queue_watcher
        loop = asyncio.get_event_loop()
        loop.create_task(start_queue_watcher(app.bot))
        logger.info("Offline kuyruk izleyicisi başlatıldı.")
    except Exception as e:
        logger.warning(f"Offline kuyruk izleyicisi başlatılamadı: {e}")


def _start_reminder_checker(app: Application) -> None:
    """Hatırlatıcı kontrolcüsünü başlatır."""
    try:
        from ai.calendar_mgr import set_notify_callback, start_reminder_checker

        async def _notify(chat_id: int, text: str) -> None:
            try:
                await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Hatırlatıcı bildirimi gönderilemedi: {e}")

        set_notify_callback(_notify)
        start_reminder_checker()
        logger.info("Hatırlatıcı kontrolcüsü başlatıldı.")
    except Exception as e:
        logger.warning(f"Hatırlatıcı kontrolcüsü başlatılamadı: {e}")


def main() -> None:
    # Konfigürasyon yükleme
    try:
        cfg = load_config()
    except FileNotFoundError as e:
        print(f"\n❌ HATA: {e}\n")
        sys.exit(1)

    token = cfg.get("telegram_bot_token", "")
    if not token or token == "BOT_TOKEN_HERE":
        print("\n❌ HATA: config.json içinde geçerli bir bot token giriniz!\n")
        sys.exit(1)

    authorized = cfg.get("authorized_users", [])
    if not authorized or authorized == [123456789]:
        print("\n⚠️  UYARI: config.json'da authorized_users listesini kendi Telegram ID'nizle güncelleyin!\n")

    logger.info("BÜRKÜT başlatılıyor...")
    logger.info(f"Yetkili kullanıcı sayısı: {len(authorized)}")

    # Application oluştur
    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    register_handlers(app)
    app.add_error_handler(error_handler)

    # UptimeRobot health endpoint (Render'da PORT env var varsa aktif olur)
    _start_health_server()

    logger.info("Polling başlatılıyor...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()

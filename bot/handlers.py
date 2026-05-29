import io
import uuid
import asyncio
from pathlib import Path
from telegram import Update, Bot
from telegram.ext import ContextTypes
from utils.security import (
    authorized_only, rate_limit, validate_file_path,
    is_safe_extension, store_pending_confirmation, is_authorized,
)
from utils.logger import get_logger, log_command
from utils.helpers import format_bytes, parse_time, format_seconds, truncate
from utils.config_manager import get_config
from bot.keyboards import (
    main_menu_keyboard, confirm_keyboard, back_to_menu_keyboard,
    upload_paths_keyboard, process_actions_keyboard,
)
from bot.messages import WELCOME, HELP, LOADING

logger = get_logger()


async def _agent_cmd(update: Update, action: str, params: dict, timeout: float = 15.0):
    """PC agent'a komut gönder. Çevrimdışı/timeout/hata durumunda kullanıcıya bildir."""
    from bot.agent_relay import send_to_agent, agent_is_online
    if not agent_is_online():
        await update.message.reply_text("🔌 PC agent çevrimdışı — PC'de `python local/pc_agent.py` çalışıyor mu?")
        return None
    result = await send_to_agent(action, params, timeout)
    if result is None:
        await update.message.reply_text("⏰ PC agent yanıt vermedi (timeout).")
        return None
    if not result.get("ok"):
        await update.message.reply_text(f"❌ PC hatası: {result.get('error', '?')}")
        return None
    return result


# ── AI oturum yönetimi ────────────────────────────────────────────────────────
# Her kullanıcıya kalıcı oturum ID'si atanır (bot yeniden başlayınca sıfırlanır)
_ai_sessions: dict[int, str] = {}
_ai_models:   dict[int, str] = {}   # Kullanıcı başına seçilen model


def _get_session(user_id: int) -> str:
    if user_id not in _ai_sessions:
        _ai_sessions[user_id] = str(uuid.uuid4())
    return _ai_sessions[user_id]


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Uzun metinleri Telegram limit altında parçalara böl."""
    if len(text) <= max_len:
        return [text]
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at < 100:
            split_at = text.rfind(" ", 0, max_len)
        if split_at < 1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    return parts


# ── Yardımcı: Webcam fotoğrafı çek ve gönder ────────────────────────────────
async def _take_and_send_webcam_photo(bot: Bot, chat_id: int, caption: str = None) -> None:
    try:
        from core.media_manager import take_webcam_photo
        loop = asyncio.get_running_loop()
        buf = await loop.run_in_executor(None, take_webcam_photo)
    except Exception as e:
        logger.error(f"Webcam fotoğrafı hatası: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Webcam fotoğrafı alınamadı: {e}")
        return

    from core.offline_queue import is_online, enqueue_photo
    caption_text = caption or "📷 Webcam görüntüsü"

    if not is_online():
        enqueue_photo(chat_id, buf, caption_text)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="📵 İnternet yok — fotoğraf kuyruğa alındı, bağlantı gelince gönderilecek.",
            )
        except Exception:
            pass
        return

    try:
        buf.seek(0)
        await bot.send_photo(chat_id=chat_id, photo=buf, caption=caption_text)
    except Exception as e:
        logger.warning(f"Webcam gönderilemedi, kuyruğa alınıyor: {e}")
        enqueue_photo(chat_id, buf, caption_text)


# ── Yardımcı: Ekran görüntüsü al ve gönder ───────────────────────────────────
async def _take_and_send_screenshot(bot: Bot, chat_id: int) -> None:
    try:
        import mss
        import mss.tools
        cfg = get_config()
        quality = cfg.get("auto_screenshot_quality", 85)

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            from PIL import Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            buf.seek(0)
    except Exception as e:
        logger.error(f"Ekran görüntüsü hatası: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Ekran görüntüsü alınamadı: {e}")
        return

    from core.offline_queue import is_online, enqueue_photo
    caption_text = f"📸 Ekran görüntüsü\n🖥️ {monitor['width']}x{monitor['height']} px"

    if not is_online():
        enqueue_photo(chat_id, buf, caption_text)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="📵 İnternet yok — ekran görüntüsü kuyruğa alındı, bağlantı gelince gönderilecek.",
            )
        except Exception:
            pass
        return

    try:
        buf.seek(0)
        await bot.send_photo(chat_id=chat_id, photo=buf, caption=caption_text)
    except Exception as e:
        logger.warning(f"Ekran görüntüsü gönderilemedi, kuyruğa alınıyor: {e}")
        enqueue_photo(chat_id, buf, caption_text)


# ── Temel komutlar ────────────────────────────────────────────────────────────
@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/start")
    await update.message.reply_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu_keyboard())


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/help")
    await update.message.reply_text(HELP, parse_mode="Markdown")


@authorized_only
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/menu")
    await update.message.reply_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu_keyboard())


# ── Sistem izleme ─────────────────────────────────────────────────────────────
@authorized_only
@rate_limit("status", seconds=10)
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/status")
    msg = await update.message.reply_text("⏳ Sistem bilgileri toplanıyor...")
    result = await _agent_cmd(update, "full_status", {})
    if result:
        await msg.edit_text(result["data"], parse_mode="Markdown")


@authorized_only
@rate_limit("foto", seconds=30)
async def cmd_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/foto")
    msg = await update.message.reply_text("📷 Kameradan fotoğraf çekiliyor...")
    result = await _agent_cmd(update, "webcam_photo", {}, timeout=20.0)
    if result:
        import base64 as _b64
        buf = io.BytesIO(_b64.b64decode(result["data"]))
        await context.bot.send_photo(update.effective_chat.id, photo=buf, caption="📷 Webcam görüntüsü")
        await msg.delete()


@authorized_only
@rate_limit("ses", seconds=30)
async def cmd_ses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    duration = 10
    if context.args:
        try:
            duration = int(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "❌ Geçersiz süre. Örnek: `/ses 15`", parse_mode="Markdown"
            )
            return

    cfg = get_config()
    max_dur = cfg.get("max_audio_duration", 120)
    if not (1 <= duration <= max_dur):
        await update.message.reply_text(
            f"❌ Süre 1-{max_dur} saniye arasında olmalı.", parse_mode="Markdown"
        )
        return

    log_command(user.id, user.username or "unknown", f"/ses {duration}")
    msg = await update.message.reply_text(f"🎙️ {duration} saniyelik ses kaydediliyor...")
    result = await _agent_cmd(update, "audio_record", {"duration": duration}, timeout=duration + 10.0)
    if result:
        import base64 as _b64
        d = result["data"]
        audio_bytes = _b64.b64decode(d["data"])
        buf = io.BytesIO(audio_bytes)
        buf.name = "kayit.ogg"
        await context.bot.send_audio(
            chat_id=update.effective_chat.id,
            audio=buf,
            title=f"Ses kaydı ({duration}s)",
            duration=d["duration"],
        )
        await msg.delete()


@authorized_only
@rate_limit("screenshot", seconds=60)
async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/screenshot")
    msg = await update.message.reply_text("📸 Ekran görüntüsü alınıyor...")
    result = await _agent_cmd(update, "screenshot", {}, timeout=20.0)
    if result:
        import base64 as _b64
        buf = io.BytesIO(_b64.b64decode(result["data"]))
        await context.bot.send_photo(update.effective_chat.id, photo=buf, caption="📸 Ekran görüntüsü")
        await msg.delete()


@authorized_only
@rate_limit("processes", seconds=15)
async def cmd_processes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    filter_name = context.args[0] if context.args else ""
    log_command(user.id, user.username or "unknown", f"/processes {filter_name}")
    msg = await update.message.reply_text("⏳ Süreçler listeleniyor...")
    result = await _agent_cmd(update, "process_list", {"filter": filter_name})
    if result:
        await msg.edit_text(result["data"], parse_mode="Markdown", reply_markup=back_to_menu_keyboard())


@authorized_only
async def cmd_network(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/network")
    result = await _agent_cmd(update, "network_info", {})
    if result:
        net = result["data"]
        text = (
            f"🌐 *Ağ Durumu*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏠 Yerel IP: `{net['local_ip']}`\n"
            f"📤 Gönderilen: `{format_bytes(net['bytes_sent'])}`\n"
            f"📥 Alınan: `{format_bytes(net['bytes_recv'])}`\n"
            f"🔗 Aktif bağlantı: `{net['connections']}`"
        )
        await update.message.reply_text(text, parse_mode="Markdown")


# ── Güç yönetimi ──────────────────────────────────────────────────────────────
@authorized_only
async def cmd_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    time_str = " ".join(args) if args else ""
    log_command(user.id, user.username or "unknown", f"/shutdown {time_str}")

    delay = parse_time(time_str) if time_str else 0

    if delay == 0:
        store_pending_confirmation(user.id, "shutdown_now", {})
        await update.message.reply_text(
            "🔴 *PC'yi HEMEN kapatmak istediğinizden emin misiniz?*",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard("shutdown_now"),
        )
    else:
        store_pending_confirmation(
            user.id, f"shutdown_timed_shutdown_{delay}", {}
        )
        await update.message.reply_text(
            f"⏱️ *{format_seconds(delay)}* içinde kapatma zamanlanacak.\n\nOnaylıyor musunuz?",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard(f"shutdown_timed_shutdown_{delay}"),
        )


@authorized_only
async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    time_str = " ".join(args) if args else ""
    log_command(user.id, user.username or "unknown", f"/restart {time_str}")

    delay = parse_time(time_str) if time_str else 0

    if delay == 0:
        store_pending_confirmation(user.id, "restart_now", {})
        await update.message.reply_text(
            "🔁 *PC'yi HEMEN yeniden başlatmak istediğinizden emin misiniz?*",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard("restart_now"),
        )
    else:
        store_pending_confirmation(
            user.id, f"shutdown_timed_restart_{delay}", {}
        )
        await update.message.reply_text(
            f"⏱️ *{format_seconds(delay)}* içinde yeniden başlatma zamanlanacak.\n\nOnaylıyor musunuz?",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard(f"shutdown_timed_restart_{delay}"),
        )


@authorized_only
async def cmd_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/sleep")
    store_pending_confirmation(user.id, "sleep_now", {})
    await update.message.reply_text(
        "😴 *PC'yi uyku moduna almak istediğinizden emin misiniz?*",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard("sleep_now"),
    )


@authorized_only
async def cmd_hibernate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/hibernate")
    store_pending_confirmation(user.id, "hibernate_now", {})
    await update.message.reply_text(
        "💤 *PC'yi hazırda bekletmek istediğinizden emin misiniz?*",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard("hibernate_now"),
    )


@authorized_only
async def cmd_cancel_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/cancel_shutdown")
    result = await _agent_cmd(update, "cancel_shutdown", {})
    if result:
        await update.message.reply_text(result["data"])


@authorized_only
async def cmd_shutdown_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/shutdown_status")
    result = await _agent_cmd(update, "shutdown_status", {})
    if result:
        status = result["data"]
        if status:
            action_label = "Kapatma" if status["action"] == "shutdown" else "Yeniden başlatma"
            await update.message.reply_text(
                f"⏱️ *Aktif Zamanlayıcı*\n"
                f"İşlem: `{action_label}`\n"
                f"Kalan süre: `{format_seconds(status['remaining'])}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("ℹ️ Aktif bir zamanlayıcı yok.")


# ── Program kontrolü ──────────────────────────────────────────────────────────
@authorized_only
async def cmd_programs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    filter_name = context.args[0] if context.args else ""
    log_command(user.id, user.username or "unknown", f"/programs {filter_name}")
    msg = await update.message.reply_text("⏳ Uygulamalar listeleniyor...")
    if filter_name:
        result = await _agent_cmd(update, "process_list", {"filter": filter_name})
    else:
        result = await _agent_cmd(update, "programs_list", {})
    if result:
        await msg.edit_text(result["data"], parse_mode="Markdown", reply_markup=back_to_menu_keyboard())


@authorized_only
async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/kill [program_adı veya PID]`\nÖrnek: `/kill chrome`",
            parse_mode="Markdown",
        )
        return

    identifier = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/kill {identifier}")

    store_pending_confirmation(user.id, "kill_process", {"pid": identifier})
    await update.message.reply_text(
        f"⚠️ *`{identifier}`* sürecini kapatmak istediğinizden emin misiniz?",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard("kill_process"),
    )


@authorized_only
async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/run [program]`\nÖrnek: `/run notepad` veya `/run chrome`",
            parse_mode="Markdown",
        )
        return
    program = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/run {program}")
    result = await _agent_cmd(update, "run_process", {"program": program})
    if result:
        await update.message.reply_text(result["data"], parse_mode="Markdown")


# ── Dosya işlemleri ───────────────────────────────────────────────────────────
@authorized_only
async def cmd_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    path_str = " ".join(args) if args else ""
    log_command(user.id, user.username or "unknown", f"/browse {path_str}")

    from core.file_manager import (
        list_directory, format_directory_listing,
        get_default_paths, store_browse_session,
    )

    if not path_str:
        paths = get_default_paths()
        lines = ["📁 *Varsayılan Konumlar*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
        for p in paths:
            lines.append(f"📂 `{p}`")
        lines.append("\nKullanım: `/browse C:\\Users\\...`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # Güvenlik kontrolü
    valid, error = validate_file_path(path_str)
    if not valid:
        await update.message.reply_text(f"🚫 {error}", parse_mode="Markdown")
        return

    msg = await update.message.reply_text("⏳ Klasör içeriği yükleniyor...")
    result = await _agent_cmd(update, "browse_files", {"path": path_str})
    if result:
        d = result["data"]
        store_browse_session(user.id, path_str, d["files"])
        from utils.helpers import truncate
        await msg.edit_text(truncate(d["text"]), parse_mode="Markdown", reply_markup=back_to_menu_keyboard())


@authorized_only
async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım:\n`/download [tam_yol]`\n`/download [numara]` (browse'dan sonra)",
            parse_mode="Markdown",
        )
        return

    identifier = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/download {identifier}")

    from core.file_manager import get_browse_session, send_file

    # Numara ile download
    if identifier.isdigit():
        session = get_browse_session(user.id)
        if not session:
            await update.message.reply_text(
                "❌ Aktif dosya oturumu yok. Önce `/browse` komutunu kullanın.",
                parse_mode="Markdown",
            )
            return
        idx = int(identifier) - 1
        if idx < 0 or idx >= len(session["files"]):
            await update.message.reply_text(f"❌ Geçersiz numara. 1-{len(session['files'])} arası girin.")
            return
        file_path = session["files"][idx]["path"]
    else:
        file_path = identifier

    # Güvenlik kontrolleri
    valid, error = validate_file_path(file_path)
    if not valid:
        await update.message.reply_text(f"🚫 {error}", parse_mode="Markdown")
        return

    safe, ext_error = is_safe_extension(file_path)
    if not safe:
        await update.message.reply_text(f"🚫 {ext_error}", parse_mode="Markdown")
        return

    msg = await update.message.reply_text(f"📤 `{Path(file_path).name}` indiriliyor...")
    agent_result = await _agent_cmd(update, "download_file", {"path": file_path}, timeout=30.0)
    if agent_result:
        import base64 as _b64
        d = agent_result["data"]
        buf = io.BytesIO(_b64.b64decode(d["data"]))
        buf.name = d["name"]
        await context.bot.send_document(update.effective_chat.id, document=buf, filename=d["name"])
        await msg.delete()


@authorized_only
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/search [dosya_adı]`\nÖrnek: `/search rapor.pdf`",
            parse_mode="Markdown",
        )
        return

    query = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/search {query}")

    msg = await update.message.reply_text(f"🔍 `{query}` aranıyor...")
    result = await _agent_cmd(update, "search_files", {"query": query}, timeout=20.0)
    if result:
        from utils.helpers import truncate
        await msg.edit_text(truncate(result["data"]), parse_mode="Markdown")


@authorized_only
async def cmd_quicksend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        cfg = get_config()
        qf = cfg.get("quick_files", {})
        if not qf:
            await update.message.reply_text("❌ Kısayol dosyası tanımlanmamış.")
            return
        lines = ["📌 *Mevcut kısayollar:*\n"]
        for k, v in qf.items():
            lines.append(f"  `{k}` → `{v}`")
        lines.append("\nKullanım: `/quicksend [kısayol]`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    shortcut = context.args[0].lower()
    log_command(user.id, user.username or "unknown", f"/quicksend {shortcut}")

    cfg = get_config()
    qf = cfg.get("quick_files", {})
    file_path = qf.get(shortcut)

    if not file_path:
        await update.message.reply_text(f"❌ `{shortcut}` kısayolu bulunamadı.", parse_mode="Markdown")
        return

    msg = await update.message.reply_text(f"📤 `{shortcut}` gönderiliyor...")
    agent_result = await _agent_cmd(update, "download_file", {"path": file_path}, timeout=30.0)
    if agent_result:
        import base64 as _b64
        d = agent_result["data"]
        buf = io.BytesIO(_b64.b64decode(d["data"]))
        buf.name = d["name"]
        await context.bot.send_document(update.effective_chat.id, document=buf, filename=d["name"])
        await msg.delete()


# ── Dosya yükleme (gelen dosya) ───────────────────────────────────────────────
@authorized_only
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    doc = update.message.document
    log_command(user.id, user.username or "unknown", f"[dosya gönderildi] {doc.file_name}")

    # Güvenlik: uzantı kontrolü
    safe, error = is_safe_extension(doc.file_name)
    if not safe:
        await update.message.reply_text(f"🚫 {error}", parse_mode="Markdown")
        return

    # Boyut kontrolü
    max_bytes = get_config().get("max_file_size_mb", 50) * 1024 * 1024
    if doc.file_size > max_bytes:
        await update.message.reply_text(
            f"❌ Dosya çok büyük ({format_bytes(doc.file_size)}). "
            f"Maksimum: {format_bytes(max_bytes)}"
        )
        return

    context.user_data["pending_upload"] = {
        "file_id": doc.file_id,
        "filename": doc.file_name,
        "size": doc.file_size,
    }

    from core.file_manager import get_default_paths
    paths = get_default_paths()

    await update.message.reply_text(
        f"📥 *`{doc.file_name}`* ({format_bytes(doc.file_size)}) alındı.\n\nNereye kaydedilsin?",
        parse_mode="Markdown",
        reply_markup=upload_paths_keyboard(paths),
    )


# ── Bildirimler ───────────────────────────────────────────────────────────────
@authorized_only
async def cmd_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/notify [mesaj]`\nÖrnek: `/notify Kahve demle!`",
            parse_mode="Markdown",
        )
        return
    message = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/notify {message}")
    await update.message.reply_text(f"🔔 *Hatırlatma:*\n\n{message}", parse_mode="Markdown")


@authorized_only
async def cmd_alert_when_idle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "❌ Kullanım: `/alert_when_idle [dakika]`\nÖrnek: `/alert_when_idle 10`",
            parse_mode="Markdown",
        )
        return

    minutes = int(context.args[0])
    log_command(user.id, user.username or "unknown", f"/alert_when_idle {minutes}")

    chat_id = update.effective_chat.id

    async def notify(msg: str):
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    from core.scheduler import IdleMonitor, add_monitor
    monitor = IdleMonitor(minutes, notify)
    loop = asyncio.get_running_loop()
    add_monitor(f"idle_{user.id}", monitor, loop)

    await update.message.reply_text(
        f"✅ PC *{minutes} dakika* boşta kalırsa bildirim gönderilecek.",
        parse_mode="Markdown",
    )


@authorized_only
async def cmd_alert_when_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/alert_when_process [process.exe]`",
            parse_mode="Markdown",
        )
        return

    process_name = context.args[0]
    log_command(user.id, user.username or "unknown", f"/alert_when_process {process_name}")
    chat_id = update.effective_chat.id

    async def notify(msg: str):
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    from core.scheduler import ProcessWatcher, add_monitor
    watcher = ProcessWatcher(process_name, notify)
    loop = asyncio.get_running_loop()
    add_monitor(f"process_{process_name}_{user.id}", watcher, loop)

    await update.message.reply_text(
        f"✅ *`{process_name}`* kapandığında bildirim gönderilecek.",
        parse_mode="Markdown",
    )


@authorized_only
async def cmd_monitor_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/monitor_folder [klasör_yolu]`",
            parse_mode="Markdown",
        )
        return

    folder_path = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/monitor_folder {folder_path}")

    valid, error = validate_file_path(folder_path)
    if not valid:
        await update.message.reply_text(f"🚫 {error}", parse_mode="Markdown")
        return

    if not Path(folder_path).is_dir():
        await update.message.reply_text(f"❌ `{folder_path}` bir klasör değil.", parse_mode="Markdown")
        return

    chat_id = update.effective_chat.id

    async def notify(msg: str):
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    from core.scheduler import FolderMonitor, add_monitor
    monitor = FolderMonitor(folder_path, notify, user.id)
    loop = asyncio.get_running_loop()
    add_monitor(f"folder_{user.id}", monitor, loop)

    await update.message.reply_text(
        f"✅ `{folder_path}` klasörü izleniyor.\nYeni dosya eklendiğinde bildirim alacaksınız.",
        parse_mode="Markdown",
    )


@authorized_only
async def cmd_stop_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/stop_monitoring")
    from core.scheduler import stop_all_monitors
    count = stop_all_monitors()
    await update.message.reply_text(
        f"🛑 {count} aktif monitör durduruldu." if count else "ℹ️ Aktif monitör yok."
    )


# ── Ses seviyesi ─────────────────────────────────────────────────────────────
@authorized_only
async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/volume")

    from core.audio_controller import get_volume_info, set_volume

    if context.args:
        try:
            level = int(context.args[0])
            new_level = set_volume(level)
            await update.message.reply_text(
                f"🔊 Ses seviyesi *%{new_level}* olarak ayarlandı.", parse_mode="Markdown"
            )
        except (ValueError, Exception) as e:
            await update.message.reply_text(f"❌ Hata: {e}")
        return

    result = await _agent_cmd(update, "volume", {})
    if result:
        info = result["data"]
        muted_label = " (🔇 Sessiz)" if info["muted"] else ""
        bar_filled = int(info["level"] / 10)
        bar = "▓" * bar_filled + "░" * (10 - bar_filled)
        await update.message.reply_text(
            f"🔊 *Ses Seviyesi*\n[{bar}] `%{info['level']}`{muted_label}",
            parse_mode="Markdown",
        )


@authorized_only
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/sessiz")
    result = await _agent_cmd(update, "mute", {})
    if result:
        await update.message.reply_text(result["data"], parse_mode="Markdown")


# ── Parlaklık ─────────────────────────────────────────────────────────────────
@authorized_only
async def cmd_brightness(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/parlaklik")

    from core.display_manager import get_brightness, set_brightness

    if context.args:
        try:
            level = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Geçersiz değer.")
            return
        result = await _agent_cmd(update, "brightness", {"level": level})
        if result:
            await update.message.reply_text(result["data"], parse_mode="Markdown")
        return

    result = await _agent_cmd(update, "brightness", {})
    if result:
        brightness = result["data"]
        if brightness < 0:
            await update.message.reply_text("❌ Parlaklık bilgisi alınamadı (harici monitör olabilir).")
            return
        bar_filled = int(brightness / 10)
        bar = "▓" * bar_filled + "░" * (10 - bar_filled)
        await update.message.reply_text(f"☀️ *Parlaklık*\n[{bar}] `%{brightness}`", parse_mode="Markdown")


# ── Ekran kilitle ─────────────────────────────────────────────────────────────
@authorized_only
async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/kilitle")
    result = await _agent_cmd(update, "lock_screen", {})
    if result:
        await update.message.reply_text(result["data"])


# ── GPU durumu ────────────────────────────────────────────────────────────────
@authorized_only
async def cmd_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/gpu")
    result = await _agent_cmd(update, "gpu_info", {})
    if result:
        gpu_data = result["data"]
        if not gpu_data["available"]:
            await update.message.reply_text(f"❌ GPU bilgisi alınamadı: {gpu_data.get('error', '?')}")
            return
        lines = ["🎮 *GPU Durumu*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
        for g in gpu_data["gpus"]:
            usage_bar = "▓" * int(g["usage"] / 10) + "░" * (10 - int(g["usage"] / 10))
            vram_pct = round(g["vram_used"] / g["vram_total"] * 100) if g["vram_total"] > 0 else 0
            vram_bar = "▓" * int(vram_pct / 10) + "░" * (10 - int(vram_pct / 10))
            lines.append(
                f"*{g['name']}*\n"
                f"  GPU  [{usage_bar}] `{g['usage']}%`\n"
                f"  VRAM [{vram_bar}] `{format_bytes(g['vram_used'])} / {format_bytes(g['vram_total'])}`\n"
                f"  Sıcaklık: `{g['temp']}°C`\n"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Pencere yönetimi ──────────────────────────────────────────────────────────
@authorized_only
async def cmd_windows(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/pencereler")
    result = await _agent_cmd(update, "windows_list", {})
    if result:
        d = result["data"]
        windows, active = d["windows"], d["active"]
        if not windows:
            await update.message.reply_text("ℹ️ Açık pencere bulunamadı.")
            return
        lines = ["🪟 *Açık Pencereler*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
        for i, w in enumerate(windows[:20], 1):
            marker = "▶" if w["title"] == active else "  "
            minimized = " (küçültülmüş)" if w["minimized"] else ""
            lines.append(f"`{i:2}.` {marker} {w['title'][:45]}{minimized}")
        lines.append(f"\n_Toplam: {len(windows)} pencere_")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized_only
async def cmd_close_window(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/pencere_kapat [pencere başlığı]`", parse_mode="Markdown"
        )
        return
    title = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/pencere_kapat {title}")
    result = await _agent_cmd(update, "close_window", {"title": title})
    if result:
        await update.message.reply_text(result["data"], parse_mode="Markdown")


@authorized_only
async def cmd_focus_window(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/pencere_odak [pencere başlığı]`", parse_mode="Markdown"
        )
        return
    title = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/pencere_odak {title}")
    result = await _agent_cmd(update, "focus_window", {"title": title})
    if result:
        await update.message.reply_text(result["data"], parse_mode="Markdown")


# ── Pano ─────────────────────────────────────────────────────────────────────
@authorized_only
async def cmd_clipboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/pano")
    result = await _agent_cmd(update, "clipboard_get", {})
    if result:
        content = result["data"]
        if not content:
            await update.message.reply_text("📋 Pano boş.")
            return
        preview = content[:500] + ("..." if len(content) > 500 else "")
        await update.message.reply_text(
            f"📋 *Pano İçeriği* ({len(content)} karakter)\n━━━━━━━━━━━━━━━━━━━━━━\n{preview}",
            parse_mode="Markdown",
        )


@authorized_only
async def cmd_clipboard_write(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("❌ Kullanım: `/pano_yaz [metin]`", parse_mode="Markdown")
        return
    text = " ".join(context.args)
    log_command(user.id, user.username or "unknown", "/pano_yaz")
    result = await _agent_cmd(update, "clipboard_set", {"text": text})
    if result:
        await update.message.reply_text(f"✅ Panoya yazıldı: `{text[:100]}`", parse_mode="Markdown")


# ── Mouse & Klavye ────────────────────────────────────────────────────────────
@authorized_only
async def cmd_mouse_move(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Kullanım: `/fare [x] [y]`\nÖrnek: `/fare 500 300`", parse_mode="Markdown"
        )
        return
    try:
        x, y = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Geçersiz koordinat.")
        return
    log_command(user.id, user.username or "unknown", f"/fare {x} {y}")
    result = await _agent_cmd(update, "mouse_move", {"x": x, "y": y})
    if result:
        await update.message.reply_text(f"🖱️ Fare `({x}, {y})` koordinatına taşındı.", parse_mode="Markdown")


@authorized_only
async def cmd_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Kullanım: `/tikla [x] [y]`\nÖrnek: `/tikla 500 300`", parse_mode="Markdown"
        )
        return
    try:
        x, y = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Geçersiz koordinat.")
        return
    log_command(user.id, user.username or "unknown", f"/tikla {x} {y}")
    result = await _agent_cmd(update, "mouse_click", {"x": x, "y": y})
    if result:
        await update.message.reply_text(f"🖱️ `({x}, {y})` koordinatına tıklandı.", parse_mode="Markdown")


@authorized_only
async def cmd_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/yaz [metin]`\nÖrnek: `/yaz Merhaba dünya`", parse_mode="Markdown"
        )
        return
    text = " ".join(context.args)
    log_command(user.id, user.username or "unknown", "/yaz")
    result = await _agent_cmd(update, "type_text", {"text": text})
    if result:
        await update.message.reply_text(f"⌨️ Yazıldı: `{text[:100]}`", parse_mode="Markdown")


# ── Launcher ──────────────────────────────────────────────────────────────────
@authorized_only
async def cmd_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/ac [uygulama/url/dosya]`\n"
            "Örnekler:\n`/ac chrome`\n`/ac https://youtube.com`\n`/ac rapor.pdf`",
            parse_mode="Markdown",
        )
        return

    target = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/ac {target}")

    if target.startswith(("http://", "https://", "www.")):
        result = await _agent_cmd(update, "open_url", {"url": target})
    else:
        result = await _agent_cmd(update, "open_app", {"app": target})
    if result:
        await update.message.reply_text(result["data"], parse_mode="Markdown")


# ── Ses asistanı durumu ───────────────────────────────────────────────────────
@authorized_only
async def cmd_voice_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/asistan")
    await update.message.reply_text(
        "🎙️ *Ses Asistanı*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Aktif — PC'de arka planda çalışıyor\n\n"
        "**Nasıl Kullanılır:**\n"
        "1. PC'de `Ctrl+Space` tuşlarına bas ve tut\n"
        "2. Türkçe komutunu söyle\n"
        "3. Tuşları bırak\n"
        "4. Yanıt sesli olarak verilir\n\n"
        "**Örnek Komutlar:**\n"
        "• _\"sistem durumu\"_ → RAM/CPU/GPU bilgisi\n"
        "• _\"chrome aç\"_ → Chrome başlar\n"
        "• _\"sesi yükselt\"_ → Ses +10\n"
        "• _\"ekran görüntüsü al\"_ → Ekran kaydedilir\n"
        "• _\"bilgisayarı kapat\"_ → Kapatma başlar\n"
        "• _\"rapor.pdf dosyasını aç\"_ → Dosyayı bulup açar",
        parse_mode="Markdown",
    )


# ── Bilinmeyen komut handler ──────────────────────────────────────────────────
async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(
        "❓ Bilinmeyen komut. `/yardim` ile tüm komutları görebilirsiniz.\n"
        "Veya doğrudan mesaj yazarak Bürküt ile konuşabilirsin! 🦅",
        parse_mode="Markdown",
    )


# ════════════════════════════════════════════════════════════════════════════════
# AI — BÜRKÜT Asistan Handler'ları
# ════════════════════════════════════════════════════════════════════════════════

async def _send_ai_response(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    thinking_msg,
    text_response: str,
    action_results: list,
    images: list,
) -> None:
    """AI yanıtını Telegram'a gönder (metin + eylem sonuçları + görüntüler)."""
    chat_id = update.effective_chat.id

    # Ana metin yanıtı
    if text_response:
        parts = _split_message(text_response)
        try:
            await thinking_msg.edit_text(parts[0], parse_mode="Markdown")
        except Exception:
            try:
                await thinking_msg.edit_text(parts[0])
            except Exception:
                pass
        for part in parts[1:]:
            try:
                await context.bot.send_message(chat_id=chat_id, text=part, parse_mode="Markdown")
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=part)
    else:
        try:
            await thinking_msg.delete()
        except Exception:
            pass

    # Eylem sonuçları
    for result in action_results:
        if not result:
            continue
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=truncate(result), parse_mode="Markdown"
            )
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=truncate(result))

    # Görüntüler (ekran görüntüsü vb.)
    for img_bytes in images:
        try:
            buf = io.BytesIO(img_bytes)
            buf.name = "screenshot.jpg"
            await context.bot.send_photo(chat_id=chat_id, photo=buf)
        except Exception as e:
            logger.error(f"Görüntü gönderme hatası: {e}")


@authorized_only
async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Düz metin mesajlarını AI beynine yönlendir."""
    user = update.effective_user
    message_text = update.message.text

    if not message_text or not message_text.strip():
        return

    log_command(user.id, user.username or "unknown", f"[AI] {message_text[:60]}")
    session_id = _get_session(user.id)

    thinking_msg = await update.message.reply_text("🦅 Bürküt düşünüyor...")

    try:
        from ai.brain import BurkutBrain, MODEL
        model = _ai_models.get(user.id, MODEL)
        brain = BurkutBrain(session_id, model=model)
        text_resp, action_results, images = await brain.chat(
            message_text, update.effective_chat.id
        )
    except Exception as e:
        logger.error(f"AI hata: {e}", exc_info=True)
        await thinking_msg.edit_text(f"❌ Bürküt hata verdi: {e}")
        return

    await _send_ai_response(update, context, thinking_msg, text_resp, action_results, images)


@authorized_only
async def cmd_burkut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/burkut [mesaj] — BÜRKÜT ile AI sohbet."""
    user = update.effective_user

    if not context.args:
        session_id = _get_session(user.id)
        await update.message.reply_text(
            "🦅 *Bürküt hazır!*\n\n"
            "Bana doğrudan mesaj yazabilirsin, ya da:\n"
            "`/burkut [sorun/komut]`\n\n"
            "Örnekler:\n"
            "• `Sistem durumunu göster`\n"
            "• `Chrome'u aç ve YouTube'a git`\n"
            "• `Python ile merhaba dünya yaz`\n"
            "• `Istanbul hava durumu nedir?`\n"
            "• `30 dakika sonra kahve iç hatırlat`\n\n"
            "Geçmişi sıfırlamak için: `/sifirla`",
            parse_mode="Markdown",
        )
        return

    message_text = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/burkut {message_text[:60]}")
    session_id = _get_session(user.id)

    thinking_msg = await update.message.reply_text("🦅 Bürküt düşünüyor...")

    try:
        from ai.brain import BurkutBrain
        brain = BurkutBrain(session_id)
        text_resp, action_results, images = await brain.chat(
            message_text, update.effective_chat.id
        )
    except Exception as e:
        logger.error(f"AI hata: {e}", exc_info=True)
        await thinking_msg.edit_text(f"❌ Bürküt hata verdi: {e}")
        return

    await _send_ai_response(update, context, thinking_msg, text_resp, action_results, images)


@authorized_only
async def cmd_sifirla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/sifirla — Mevcut AI konuşma geçmişini temizle."""
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/sifirla")
    session_id = _get_session(user.id)

    from ai.memory import clear_session
    clear_session(session_id)
    # Yeni oturum oluştur
    _ai_sessions[user.id] = str(uuid.uuid4())

    await update.message.reply_text(
        "🔄 Konuşma geçmişi sıfırlandı. Yeni bir oturum başlatıldı! 🦅",
        parse_mode="Markdown",
    )


@authorized_only
async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/model [isim] — Kullanılan AI modelini değiştir veya listele."""
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/model")

    from ai.brain import get_available_models, is_groq_available

    if not is_groq_available():
        await update.message.reply_text(
            "❌ Groq API anahtarı eksik. `.env` dosyasına `GROQ_API_KEY` ekle.",
            parse_mode="Markdown",
        )
        return

    if not context.args:
        models = get_available_models()
        if not models:
            await update.message.reply_text("⚠️ Yüklü model bulunamadı.")
            return
        lines = ["🤖 *Yüklü Modeller*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
        for m in models:
            lines.append(f"• `{m}`")
        lines.append("\nDeğiştirmek için: `/model llama3`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    model_name = context.args[0]
    session_id = _get_session(user.id)

    from ai.brain import BurkutBrain
    brain = BurkutBrain(session_id)
    ok = brain.set_model(model_name)

    # Kalıcı olarak sakla — sonraki BurkutBrain örnekleri bu modeli kullanır
    _ai_models[user.id] = brain.model
    context.user_data["ai_model"] = brain.model

    if ok:
        await update.message.reply_text(
            f"✅ Model değiştirildi: `{brain.model}`", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"⚠️ `{model_name}` bulunamadı, yine de deneniyor. "
            f"Yüklemek için terminalde:\n`ollama pull {model_name}`",
            parse_mode="Markdown",
        )


@authorized_only
async def cmd_hava(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/hava [şehir] — Hava durumu."""
    user = update.effective_user
    city = " ".join(context.args) if context.args else "Istanbul"
    log_command(user.id, user.username or "unknown", f"/hava {city}")

    msg = await update.message.reply_text("⏳ Hava durumu alınıyor...")
    from ai.news_weather import get_weather
    text = get_weather(city)
    try:
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception:
        await msg.edit_text(text)


@authorized_only
async def cmd_haber(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/haber [kategori] — Güncel haberler."""
    user = update.effective_user
    category = context.args[0] if context.args else "genel"
    log_command(user.id, user.username or "unknown", f"/haber {category}")

    msg = await update.message.reply_text("⏳ Haberler alınıyor...")
    from ai.news_weather import get_news
    text = get_news(category)
    try:
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception:
        await msg.edit_text(text)


@authorized_only
async def cmd_hatirlatici(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/hatirlatici [metin] [zaman] veya /hatirlatici liste"""
    user = update.effective_user
    log_command(user.id, user.username or "unknown", "/hatirlatici")

    if not context.args:
        await update.message.reply_text(
            "⏰ *Hatırlatıcı Kullanımı*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "`/hatirlatici liste` — Aktif hatırlatmalar\n"
            "`/hatirlatici [metin] [zaman]`\n\n"
            "Zaman örnekleri:\n"
            "• `30 dakika sonra`\n"
            "• `2 saat sonra`\n"
            "• `yarın sabah`\n"
            "• `15:30`\n"
            "• `akşam`\n\n"
            "Örnek: `/hatirlatici Toplantı var 30 dakika sonra`",
            parse_mode="Markdown",
        )
        return

    if context.args[0].lower() == "liste":
        from ai.calendar_mgr import get_reminders_text
        text = get_reminders_text(update.effective_chat.id)
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    # Son bölümü zaman, geri kalanı metin olarak ayır
    args = context.args
    # Zaman anahtar kelimeleri
    time_keywords = {"dakika", "dk", "saat", "gün", "gun", "yarın", "yarin",
                     "sabah", "öğle", "ogle", "akşam", "aksam", "gece", "sonra"}

    # Sondaki kelimeleri sırayla kontrol et — zaman kısmını bul
    split_idx = len(args)
    for i in range(len(args) - 1, -1, -1):
        if args[i].lower() in time_keywords or args[i].replace(":", "").isdigit():
            split_idx = i
            break

    if split_idx == 0:
        await update.message.reply_text(
            "❌ Zaman belirtmelisin. Örnek: `/hatirlatici Kahve 30 dakika sonra`",
            parse_mode="Markdown",
        )
        return

    text_part = " ".join(args[:split_idx])
    when_part = " ".join(args[split_idx:])

    from ai.calendar_mgr import add_calendar_event
    ok, result_msg = add_calendar_event(update.effective_chat.id, text_part, when_part)
    try:
        await update.message.reply_text(result_msg, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(result_msg)


@authorized_only
async def cmd_oku(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/oku [url] — URL içeriğini al ve Bürküt'e analiz ettir."""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/oku [url]`\nÖrnek: `/oku https://github.com/...`",
            parse_mode="Markdown",
        )
        return

    url = context.args[0]
    log_command(user.id, user.username or "unknown", f"/oku {url}")

    thinking_msg = await update.message.reply_text("🌐 Site okunuyor ve analiz ediliyor...")
    session_id = _get_session(user.id)

    try:
        from ai.brain import BurkutBrain
        brain = BurkutBrain(session_id)
        message = f"Bu URL'yi oku, analiz et ve özetle: {url}"
        text_resp, action_results, images = await brain.chat(
            message, update.effective_chat.id, prefetch_urls=True
        )
    except Exception as e:
        await thinking_msg.edit_text(f"❌ Hata: {e}")
        return

    await _send_ai_response(update, context, thinking_msg, text_resp, action_results, images)


@authorized_only
async def cmd_kod_analiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/kod [dosya_yolu] — Kod dosyasını Bürküt'e analiz ettir."""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: `/kod [dosya_yolu]`\n"
            "Örnek: `/kod C:\\Users\\Kayra\\PcBot\\main.py`",
            parse_mode="Markdown",
        )
        return

    file_path = " ".join(context.args)
    log_command(user.id, user.username or "unknown", f"/kod {file_path}")

    thinking_msg = await update.message.reply_text("🔍 Kod analiz ediliyor...")
    session_id = _get_session(user.id)

    try:
        from ai.brain import analyze_code_file
        text_resp, action_results, images = await analyze_code_file(
            file_path, session_id, update.effective_chat.id
        )
    except Exception as e:
        await thinking_msg.edit_text(f"❌ Hata: {e}")
        return

    await _send_ai_response(update, context, thinking_msg, text_resp, action_results, images)


@authorized_only
async def handle_document_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gönderilen metin/kod dosyalarını AI'ya analiz ettir (mevcut handle_document ile birlikte çalışır)."""
    doc = update.message.document
    # Sadece metin/kod uzantıları için AI analizi yap
    code_extensions = {
        ".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml",
        ".xml", ".md", ".txt", ".sh", ".bat", ".ps1", ".c", ".cpp",
        ".java", ".go", ".rs", ".php", ".rb", ".sql",
    }
    ext = Path(doc.file_name).suffix.lower()
    if ext not in code_extensions:
        return  # Diğer dosyalar için mevcut handler devam eder

    user = update.effective_user
    caption = update.message.caption or ""
    log_command(user.id, user.username or "unknown", f"[AI dosya] {doc.file_name}")

    thinking_msg = await update.message.reply_text(
        f"🔍 `{doc.file_name}` analiz ediliyor..."
    )

    try:
        # Dosyayı geçici olarak indir
        import tempfile
        tg_file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, mode="wb"
        ) as tmp:
            await tg_file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        from ai.brain import analyze_code_file
        question = caption if caption else f"Bu dosyayı analiz et: {doc.file_name}"
        session_id = _get_session(user.id)

        from ai.brain import BurkutBrain
        content = Path(tmp_path).read_text(encoding="utf-8", errors="replace")
        brain = BurkutBrain(session_id)
        text_resp, action_results, images = await brain.chat(
            f"{question}\n\n```{ext.lstrip('.')}\n{content[:5000]}\n```",
            update.effective_chat.id,
            prefetch_urls=False,
        )
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        await thinking_msg.edit_text(f"❌ Dosya analiz hatası: {e}")
        return

    await _send_ai_response(update, context, thinking_msg, text_resp, action_results, images)

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from utils.security import (
    authorized_only, get_pending_confirmation,
    clear_pending_confirmation, store_pending_confirmation,
)
from utils.logger import get_logger, log_command
from bot.keyboards import (
    main_menu_keyboard, power_menu_keyboard, files_menu_keyboard,
    confirm_keyboard, notify_menu_keyboard, back_to_menu_keyboard,
    control_menu_keyboard,
)
from bot.messages import HELP

logger = get_logger()


async def _agent_cb(query, action: str, params: dict, timeout: float = 15.0):
    """Callback içinden PC agent'a komut gönder."""
    from bot.agent_relay import send_to_agent, agent_is_online
    if not agent_is_online():
        await query.edit_message_text("🔌 PC agent çevrimdışı.")
        return None
    result = await send_to_agent(action, params, timeout)
    if result is None:
        await query.edit_message_text("⏰ PC agent yanıt vermedi.")
        return None
    if not result.get("ok"):
        await query.edit_message_text(f"❌ PC hatası: {result.get('error', '?')}")
        return None
    return result


@authorized_only
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    user = update.effective_user
    chat_id = query.message.chat_id

    log_command(user.id, user.username or "unknown", f"[callback] {data}")

    # ── Menü navigasyonu ──────────────────────────────────────────────────
    if data == "menu_main":
        from bot.messages import WELCOME
        await query.edit_message_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu_keyboard())

    elif data == "menu_power":
        await query.edit_message_text(
            "⚡ *Güç Yönetimi*\nBir işlem seçin:",
            parse_mode="Markdown",
            reply_markup=power_menu_keyboard(),
        )

    elif data == "menu_files":
        await query.edit_message_text(
            "📁 *Dosya İşlemleri*\nBir işlem seçin:",
            parse_mode="Markdown",
            reply_markup=files_menu_keyboard(),
        )

    elif data == "menu_control":
        await query.edit_message_text(
            "🎛️ *PC Kontrol*\nSes, parlaklık, pencere ve pano işlemleri:",
            parse_mode="Markdown",
            reply_markup=control_menu_keyboard(),
        )

    elif data == "cmd_gpu":
        result = await _agent_cb(query, "gpu_info", {})
        if result:
            from utils.helpers import format_bytes
            gpu_data = result["data"]
            if not gpu_data["available"]:
                await query.edit_message_text(f"❌ GPU bilgisi alınamadı: {gpu_data.get('error', '')}", reply_markup=back_to_menu_keyboard())
            else:
                lines = ["🎮 *GPU Durumu*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
                for g in gpu_data["gpus"]:
                    usage_bar = "▓" * int(g["usage"] / 10) + "░" * (10 - int(g["usage"] / 10))
                    vram_pct = round(g["vram_used"] / g["vram_total"] * 100) if g["vram_total"] > 0 else 0
                    vram_bar = "▓" * int(vram_pct / 10) + "░" * (10 - int(vram_pct / 10))
                    lines.append(f"*{g['name']}*\n  GPU  [{usage_bar}] `{g['usage']}%`\n  VRAM [{vram_bar}] `{format_bytes(g['vram_used'])} / {format_bytes(g['vram_total'])}`\n  Sıcaklık: `{g['temp']}°C`\n")
                await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data == "cmd_volume":
        result = await _agent_cb(query, "volume", {})
        if result:
            info = result["data"]
            muted_label = " (🔇 Sessiz)" if info["muted"] else ""
            bar_filled = int(info["level"] / 10)
            bar = "▓" * bar_filled + "░" * (10 - bar_filled)
            await query.edit_message_text(
                f"🔊 *Ses Seviyesi*\n[{bar}] `%{info['level']}`{muted_label}\n\nDeğiştirmek için: `/volume [0-100]`",
                parse_mode="Markdown", reply_markup=control_menu_keyboard(),
            )

    elif data == "cmd_mute":
        result = await _agent_cb(query, "mute", {})
        if result:
            await query.edit_message_text(result["data"], reply_markup=control_menu_keyboard())

    elif data == "cmd_brightness":
        result = await _agent_cb(query, "brightness", {})
        if result:
            brightness = result["data"]
            if brightness < 0:
                text = "❌ Parlaklık bilgisi alınamadı (harici monitör olabilir)."
            else:
                bar_filled = int(brightness / 10)
                bar = "▓" * bar_filled + "░" * (10 - bar_filled)
                text = f"☀️ *Parlaklık*\n[{bar}] `%{brightness}`\n\nDeğiştirmek için: `/parlaklik [0-100]`"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=control_menu_keyboard())

    elif data == "cmd_lock":
        result = await _agent_cb(query, "lock_screen", {})
        if result:
            await query.edit_message_text(result["data"])

    elif data == "cmd_windows":
        result = await _agent_cb(query, "windows_list", {})
        if result:
            d = result["data"]
            windows, active = d["windows"], d["active"]
            if not windows:
                text = "ℹ️ Açık pencere bulunamadı."
            else:
                lines = ["🪟 *Açık Pencereler*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
                for i, w in enumerate(windows[:15], 1):
                    marker = "▶" if w["title"] == active else "  "
                    minimized = " ↓" if w["minimized"] else ""
                    lines.append(f"`{i:2}.` {marker} {w['title'][:40]}{minimized}")
                text = "\n".join(lines)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=control_menu_keyboard())

    elif data == "cmd_clipboard":
        result = await _agent_cb(query, "clipboard_get", {})
        if result:
            content = result["data"]
            if not content:
                text = "📋 Pano boş."
            else:
                preview = content[:400] + ("..." if len(content) > 400 else "")
                text = f"📋 *Pano* ({len(content)} karakter)\n━━━━━━━━━━━━━━━━━━━━━━\n{preview}"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=control_menu_keyboard())

    elif data == "cmd_voice_status":
        await query.edit_message_text(
            "🎙️ *Ses Asistanı*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📌 Aktif — PC'de arka planda çalışıyor\n\n"
            "`Ctrl+Space` tuşlarına bas ve tut → konuş → bırak",
            parse_mode="Markdown",
            reply_markup=control_menu_keyboard(),
        )

    elif data == "menu_notify":
        await query.edit_message_text(
            "🔔 *Bildirim Yönetimi*\nBir işlem seçin:",
            parse_mode="Markdown",
            reply_markup=notify_menu_keyboard(),
        )

    elif data == "cmd_help":
        await query.edit_message_text(HELP, parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    # ── Sistem komutları ──────────────────────────────────────────────────
    elif data == "cmd_status":
        await query.edit_message_text("⏳ Sistem bilgileri toplanıyor...")
        result = await _agent_cb(query, "full_status", {})
        if result:
            await query.edit_message_text(result["data"], parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data == "cmd_screenshot":
        await query.edit_message_text("📸 Ekran görüntüsü alınıyor...")
        result = await _agent_cb(query, "screenshot", {}, timeout=20.0)
        if result:
            import base64 as _b64, io as _io
            buf = _io.BytesIO(_b64.b64decode(result["data"]))
            await context.bot.send_photo(chat_id, photo=buf, caption="📸 Ekran görüntüsü")
            await query.delete_message()

    elif data == "cmd_processes":
        result = await _agent_cb(query, "process_list", {"filter": ""})
        if result:
            await query.edit_message_text(result["data"], parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data == "cmd_network":
        result = await _agent_cb(query, "network_info", {})
        if result:
            from utils.helpers import format_bytes
            net = result["data"]
            text = (
                f"🌐 *Ağ Durumu*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏠 Yerel IP: `{net['local_ip']}`\n"
                f"📤 Gönderilen: `{format_bytes(net['bytes_sent'])}`\n"
                f"📥 Alınan: `{format_bytes(net['bytes_recv'])}`\n"
                f"🔗 Aktif bağlantı: `{net['connections']}`"
            )
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    # ── Güç yönetimi ─────────────────────────────────────────────────────
    elif data == "power_shutdown":
        store_pending_confirmation(user.id, "shutdown_now", {})
        await query.edit_message_text(
            "🔴 *PC'yi kapatmak istediğinizden emin misiniz?*\nBu işlem geri alınamaz!",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard("shutdown_now"),
        )

    elif data == "power_restart":
        store_pending_confirmation(user.id, "restart_now", {})
        await query.edit_message_text(
            "🔁 *PC'yi yeniden başlatmak istediğinizden emin misiniz?*",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard("restart_now"),
        )

    elif data == "power_sleep":
        store_pending_confirmation(user.id, "sleep_now", {})
        await query.edit_message_text(
            "😴 *PC'yi uyku moduna almak istediğinizden emin misiniz?*",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard("sleep_now"),
        )

    elif data == "power_hibernate":
        store_pending_confirmation(user.id, "hibernate_now", {})
        await query.edit_message_text(
            "💤 *PC'yi hazırda bekletmek istediğinizden emin misiniz?*",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard("hibernate_now"),
        )

    elif data == "power_cancel":
        result = await _agent_cb(query, "cancel_shutdown", {})
        if result:
            await query.edit_message_text(result["data"], reply_markup=power_menu_keyboard())

    elif data == "power_status":
        result = await _agent_cb(query, "shutdown_status", {})
        if result:
            from utils.helpers import format_seconds
            status = result["data"]
            if status:
                action_label = "Kapatma" if status["action"] == "shutdown" else "Yeniden başlatma"
                await query.edit_message_text(
                    f"⏱️ *Aktif Zamanlayıcı*\nİşlem: {action_label}\nKalan süre: `{format_seconds(status['remaining'])}`",
                    parse_mode="Markdown", reply_markup=power_menu_keyboard(),
                )
            else:
                await query.edit_message_text("ℹ️ Aktif zamanlayıcı yok.", reply_markup=power_menu_keyboard())

    # ── Onay mekanizması ─────────────────────────────────────────────────
    elif data.startswith("confirm_yes_"):
        action = data[len("confirm_yes_"):]
        await _handle_confirmation(query, user, context, action, chat_id)

    elif data == "confirm_no":
        clear_pending_confirmation(user.id)
        await query.edit_message_text("❌ İşlem iptal edildi.", reply_markup=back_to_menu_keyboard())

    # ── Süreç kapatma ────────────────────────────────────────────────────
    elif data.startswith("kill_pid_"):
        pid = data[len("kill_pid_"):]
        store_pending_confirmation(user.id, f"kill_process", {"pid": pid})
        await query.edit_message_text(
            f"⚠️ PID `{pid}` sürecini kapatmak istiyor musunuz?",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard("kill_process"),
        )

    # ── Dosya işlemleri ──────────────────────────────────────────────────
    elif data == "file_browse_default":
        from core.file_manager import get_default_paths
        from bot.keyboards import files_menu_keyboard
        paths = get_default_paths()
        lines = ["📁 *Varsayılan Konumlar*\n"]
        for i, p in enumerate(paths, 1):
            from pathlib import Path
            lines.append(f"`{i}.` {Path(p).name}: `{p}`")
        lines.append("\n`/gozat [yol]` komutuyla klasöre göz atın.")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data == "file_search":
        await query.edit_message_text(
            "🔍 Aramak istediğiniz dosya adını yazın:\n`/ara dosya_adı`",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
        )

    elif data == "file_download_help":
        await query.edit_message_text(
            "📤 *Dosya Gönderme (PC→Telegram)*\n\n"
            "`/gozat` ile klasöre göz atın, ardından:\n"
            "`/indir [numara]` veya `/indir [tam yol]`",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
        )

    elif data == "file_upload_help":
        await query.edit_message_text(
            "📥 *Dosya Alma (Telegram→PC)*\n\n"
            "Bana bir dosya gönderin, nereye kaydedeceğinizi soracağım.",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
        )

    elif data.startswith("file_dl_"):
        index = int(data[len("file_dl_"):])
        session = None
        from core.file_manager import get_browse_session
        session = get_browse_session(user.id)
        if not session or index >= len(session["files"]):
            await query.edit_message_text("❌ Oturum süresi doldu. Tekrar `/browse` kullanın.")
            return
        file_info = session["files"][index]
        await query.edit_message_text(f"📤 `{file_info['name']}` gönderiliyor...")
        from core.file_manager import send_file
        success, msg = await send_file(context.bot, chat_id, file_info["path"])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data.startswith("upload_path_"):
        idx = int(data[len("upload_path_"):])
        from core.file_manager import get_default_paths
        paths = get_default_paths()
        if idx >= len(paths):
            await query.edit_message_text("❌ Geçersiz seçim.")
            return
        pending = context.user_data.get("pending_upload")
        if not pending:
            await query.edit_message_text("❌ Yüklenecek dosya bulunamadı.")
            return
        save_path = paths[idx]
        await query.edit_message_text(f"📥 Dosya indiriliyor...\n`{pending['filename']}`")
        from core.file_manager import receive_file
        success, msg = await receive_file(
            context.bot, pending["file_id"], save_path, pending["filename"]
        )
        context.user_data.pop("pending_upload", None)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    # ── Bildirim yönetimi ────────────────────────────────────────────────
    elif data == "notify_stop_all":
        from core.scheduler import stop_all_monitors
        count = stop_all_monitors()
        await query.edit_message_text(
            f"🛑 {count} aktif monitör durduruldu.",
            reply_markup=back_to_menu_keyboard(),
        )

    elif data == "notify_idle":
        await query.edit_message_text(
            "💤 Kaç dakika boşta kaldığında bildirim gönderilsin?\n`/bosta_bildir [dakika]`",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
        )

    elif data == "notify_folder":
        await query.edit_message_text(
            "📂 İzlenecek klasör yolunu belirtin:\n`/klasor_izle C:\\klasör\\yolu`",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
        )

    elif data == "notify_process":
        await query.edit_message_text(
            "🔔 İzlenecek program adını belirtin:\n`/program_bitince chrome.exe`",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
        )


async def _handle_confirmation(query, user, context, action: str, chat_id: int) -> None:
    from utils.security import get_pending_confirmation, clear_pending_confirmation
    pending = get_pending_confirmation(user.id)
    clear_pending_confirmation(user.id)

    if action == "shutdown_now":
        await query.edit_message_text("🔴 PC kapatılıyor...")
        await _agent_cb(query, "shutdown", {"delay": 0})

    elif action == "restart_now":
        await query.edit_message_text("🔁 PC yeniden başlatılıyor...")
        await _agent_cb(query, "restart", {"delay": 0})

    elif action == "sleep_now":
        await query.edit_message_text("😴 PC uyku moduna alınıyor...")
        await _agent_cb(query, "sleep", {})

    elif action == "hibernate_now":
        await query.edit_message_text("💤 PC hazırda beklemeye alınıyor...")
        await _agent_cb(query, "hibernate", {})

    elif action.startswith("shutdown_timed_"):
        parts = action.split("_")
        delay = int(parts[-1])
        action_type = parts[-2]
        from utils.helpers import format_seconds
        label = "kapatma" if action_type == "shutdown" else "yeniden başlatma"
        result = await _agent_cb(query, action_type, {"delay": delay})
        if result:
            await query.edit_message_text(f"✅ {format_seconds(delay)} içinde {label} zamanlandı.")

    elif action == "kill_process":
        if pending and "pid" in pending["data"]:
            pid = pending["data"]["pid"]
            await query.edit_message_text(f"🔄 PID {pid} kapatılıyor...")
            result = await _agent_cb(query, "kill_process", {"identifier": pid})
            if result:
                from bot.keyboards import back_to_menu_keyboard
                await query.edit_message_text(result["data"], parse_mode="Markdown", reply_markup=back_to_menu_keyboard())
        else:
            await query.edit_message_text("❌ Süreç bilgisi bulunamadı.")

    else:
        await query.edit_message_text(f"✅ İşlem onaylandı: `{action}`", parse_mode="Markdown")

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
        from core.system_info import get_gpu_info
        from utils.helpers import format_bytes
        gpu_data = get_gpu_info()
        if not gpu_data["available"]:
            await query.edit_message_text(
                f"❌ GPU bilgisi alınamadı: {gpu_data.get('error', '')}",
                reply_markup=back_to_menu_keyboard(),
            )
        else:
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
            await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data == "cmd_volume":
        from core.audio_controller import get_volume_info
        info = get_volume_info()
        muted_label = " (🔇 Sessiz)" if info["muted"] else ""
        bar_filled = int(info["level"] / 10)
        bar = "▓" * bar_filled + "░" * (10 - bar_filled)
        await query.edit_message_text(
            f"🔊 *Ses Seviyesi*\n[{bar}] `%{info['level']}`{muted_label}\n\n"
            f"Değiştirmek için: `/volume [0-100]`",
            parse_mode="Markdown",
            reply_markup=control_menu_keyboard(),
        )

    elif data == "cmd_mute":
        from core.audio_controller import toggle_mute
        now_muted = toggle_mute()
        label = "🔇 Sessiz" if now_muted else "🔊 Sesli"
        await query.edit_message_text(
            f"{label} moda geçildi.",
            reply_markup=control_menu_keyboard(),
        )

    elif data == "cmd_brightness":
        from core.display_manager import get_brightness
        brightness = get_brightness()
        if brightness < 0:
            text = "❌ Parlaklık bilgisi alınamadı (harici monitör olabilir)."
        else:
            bar_filled = int(brightness / 10)
            bar = "▓" * bar_filled + "░" * (10 - bar_filled)
            text = (
                f"☀️ *Parlaklık*\n[{bar}] `%{brightness}`\n\n"
                f"Değiştirmek için: `/parlaklik [0-100]`"
            )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=control_menu_keyboard())

    elif data == "cmd_lock":
        from core.display_manager import lock_screen
        lock_screen()
        await query.edit_message_text("🔒 Ekran kilitlendi.")

    elif data == "cmd_windows":
        from core.window_manager import get_windows, get_active_window
        windows = get_windows()
        active = get_active_window()
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
        from core.clipboard_manager import get_clipboard
        content = get_clipboard()
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
        from core.system_info import get_full_status
        status = get_full_status()
        await query.edit_message_text(status, parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data == "cmd_screenshot":
        await query.edit_message_text("📸 Ekran görüntüsü alınıyor...")
        from bot.handlers import _take_and_send_screenshot
        await _take_and_send_screenshot(context.bot, chat_id)
        await query.delete_message()

    elif data == "cmd_processes":
        from core.process_manager import get_running_processes, format_process_list
        procs = get_running_processes()[:10]
        text = format_process_list(procs)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_to_menu_keyboard())

    elif data == "cmd_network":
        from core.system_info import get_network_info
        from utils.helpers import format_bytes
        net = get_network_info()
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
        from core.power_manager import cancel_scheduled_shutdown
        if cancel_scheduled_shutdown():
            await query.edit_message_text(
                "✅ Zamanlı kapatma/yeniden başlatma iptal edildi.",
                reply_markup=power_menu_keyboard(),
            )
        else:
            await query.edit_message_text(
                "ℹ️ Aktif bir zamanlayıcı bulunamadı.",
                reply_markup=power_menu_keyboard(),
            )

    elif data == "power_status":
        from core.power_manager import get_shutdown_status
        from utils.helpers import format_seconds
        status = get_shutdown_status()
        if status:
            action_label = "Kapatma" if status["action"] == "shutdown" else "Yeniden başlatma"
            await query.edit_message_text(
                f"⏱️ *Aktif Zamanlayıcı*\n"
                f"İşlem: {action_label}\n"
                f"Kalan süre: `{format_seconds(status['remaining'])}`",
                parse_mode="Markdown",
                reply_markup=power_menu_keyboard(),
            )
        else:
            await query.edit_message_text(
                "ℹ️ Aktif zamanlayıcı yok.",
                reply_markup=power_menu_keyboard(),
            )

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
    from core.power_manager import (
        immediate_shutdown, immediate_restart, sleep_pc, hibernate_pc,
        schedule_shutdown,
    )
    from core.process_manager import kill_process
    from utils.security import get_pending_confirmation, clear_pending_confirmation

    pending = get_pending_confirmation(user.id)
    clear_pending_confirmation(user.id)

    async def notify_user(msg: str):
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    if action == "shutdown_now":
        await query.edit_message_text("🔴 PC kapatılıyor...")
        immediate_shutdown()

    elif action == "restart_now":
        await query.edit_message_text("🔁 PC yeniden başlatılıyor...")
        immediate_restart()

    elif action == "sleep_now":
        await query.edit_message_text("😴 PC uyku moduna alınıyor...")
        sleep_pc()

    elif action == "hibernate_now":
        await query.edit_message_text("💤 PC hazırda beklemeye alınıyor...")
        hibernate_pc()

    elif action.startswith("shutdown_timed_"):
        parts = action.split("_")
        delay = int(parts[-1])
        action_type = parts[-2]  # "shutdown" or "restart"
        from utils.helpers import format_seconds
        label = "kapatma" if action_type == "shutdown" else "yeniden başlatma"
        await query.edit_message_text(
            f"✅ {format_seconds(delay)} içinde {label} zamanlandı."
        )
        await schedule_shutdown(action_type, delay, notify_user)

    elif action == "kill_process":
        if pending and "pid" in pending["data"]:
            pid = pending["data"]["pid"]
            await query.edit_message_text(f"🔄 PID {pid} kapatılıyor...")
            success, msg = kill_process(pid)
            from bot.keyboards import back_to_menu_keyboard
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=back_to_menu_keyboard())
        else:
            await query.edit_message_text("❌ Süreç bilgisi bulunamadı.")

    else:
        await query.edit_message_text(f"✅ İşlem onaylandı: `{action}`", parse_mode="Markdown")

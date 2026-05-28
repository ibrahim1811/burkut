from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🖥️ Sistem Durumu", callback_data="cmd_status"),
            InlineKeyboardButton("📸 Ekran Görüntüsü", callback_data="cmd_screenshot"),
        ],
        [
            InlineKeyboardButton("⚡ Güç Yönetimi", callback_data="menu_power"),
            InlineKeyboardButton("🔄 Süreçler", callback_data="cmd_processes"),
        ],
        [
            InlineKeyboardButton("📁 Dosya İşlemleri", callback_data="menu_files"),
            InlineKeyboardButton("🌐 Ağ Durumu", callback_data="cmd_network"),
        ],
        [
            InlineKeyboardButton("🔔 Bildirimler", callback_data="menu_notify"),
            InlineKeyboardButton("🎛️ Kontrol", callback_data="menu_control"),
        ],
        [
            InlineKeyboardButton("🎮 GPU Durumu", callback_data="cmd_gpu"),
            InlineKeyboardButton("❓ Yardım", callback_data="cmd_help"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def control_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🔊 Ses Seviyesi", callback_data="cmd_volume"),
            InlineKeyboardButton("☀️ Parlaklık", callback_data="cmd_brightness"),
        ],
        [
            InlineKeyboardButton("🔇 Sessiz/Sesli", callback_data="cmd_mute"),
            InlineKeyboardButton("🔒 Ekranı Kilitle", callback_data="cmd_lock"),
        ],
        [
            InlineKeyboardButton("🪟 Açık Pencereler", callback_data="cmd_windows"),
            InlineKeyboardButton("📋 Pano", callback_data="cmd_clipboard"),
        ],
        [
            InlineKeyboardButton("🎙️ Ses Asistanı", callback_data="cmd_voice_status"),
            InlineKeyboardButton("🔙 Ana Menü", callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def power_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🔴 Kapat", callback_data="power_shutdown"),
            InlineKeyboardButton("🔁 Yeniden Başlat", callback_data="power_restart"),
        ],
        [
            InlineKeyboardButton("😴 Uyku", callback_data="power_sleep"),
            InlineKeyboardButton("💤 Hazırda Beklet", callback_data="power_hibernate"),
        ],
        [
            InlineKeyboardButton("⏱️ Zamanlayıcı Durumu", callback_data="power_status"),
            InlineKeyboardButton("❌ Zamanlayıcıyı İptal Et", callback_data="power_cancel"),
        ],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(action: str, extra: str = "") -> InlineKeyboardMarkup:
    data_yes = f"confirm_yes_{action}"
    if extra:
        data_yes = f"confirm_yes_{action}_{extra}"
    buttons = [
        [
            InlineKeyboardButton("✅ Evet, Onayla", callback_data=data_yes),
            InlineKeyboardButton("❌ İptal", callback_data="confirm_no"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def files_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📂 Klasöre Göz At", callback_data="file_browse_default"),
            InlineKeyboardButton("🔍 Dosya Ara", callback_data="file_search"),
        ],
        [
            InlineKeyboardButton("📤 Dosya Gönder (PC→Telegram)", callback_data="file_download_help"),
            InlineKeyboardButton("📥 Dosya Al (Telegram→PC)", callback_data="file_upload_help"),
        ],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def process_actions_keyboard(pid: int, name: str) -> InlineKeyboardMarkup:
    safe_name = name[:20].replace(" ", "_")
    buttons = [
        [
            InlineKeyboardButton(
                f"❌ '{name[:15]}' Kapat",
                callback_data=f"kill_pid_{pid}",
            )
        ],
        [InlineKeyboardButton("🔙 Süreç Listesi", callback_data="cmd_processes")],
    ]
    return InlineKeyboardMarkup(buttons)


def file_actions_keyboard(file_index: int, file_name: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                f"📤 İndir ({file_name[:20]})",
                callback_data=f"file_dl_{file_index}",
            )
        ],
        [InlineKeyboardButton("🔙 Geri", callback_data="file_browse_default")],
    ]
    return InlineKeyboardMarkup(buttons)


def notify_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("💤 Boşta Bildir", callback_data="notify_idle"),
            InlineKeyboardButton("📂 Klasör İzle", callback_data="notify_folder"),
        ],
        [
            InlineKeyboardButton("🔔 Program Kapanınca Bildir", callback_data="notify_process"),
            InlineKeyboardButton("🛑 Tüm Bildirimleri Durdur", callback_data="notify_stop_all"),
        ],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def upload_paths_keyboard(paths: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for i, p in enumerate(paths[:4]):
        from pathlib import Path
        name = Path(p).name or p
        buttons.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"upload_path_{i}")])
    buttons.append([InlineKeyboardButton("❌ İptal", callback_data="confirm_no")])
    return InlineKeyboardMarkup(buttons)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="menu_main")]
    ])

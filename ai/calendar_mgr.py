"""
Hatırlatıcı ve takvim yöneticisi.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional

from .memory import add_reminder, get_pending_reminders, mark_reminder_done, list_reminders
from utils.logger import get_logger

logger = get_logger()

_notify_callback: Optional[Callable] = None
_tts_callback: Optional[Callable] = None
_checker_running: bool = False


def set_notify_callback(callback: Callable) -> None:
    """bot → burası: (chat_id, text) alır ve Telegram'a gönderir."""
    global _notify_callback
    _notify_callback = callback


def set_tts_callback(callback: Callable) -> None:
    """Sesli uyarı için TTS callback — voice_assistant tarafından atanır."""
    global _tts_callback
    _tts_callback = callback


async def _check_loop() -> None:
    logger.info("Hatırlatıcı kontrol döngüsü başlatıldı.")
    while True:
        try:
            pending = get_pending_reminders()
            for rem in pending:
                sent = False
                if _notify_callback:
                    try:
                        result = _notify_callback(
                            rem["chat_id"],
                            f"⏰ *Hatırlatma!*\n\n{rem['text']}",
                        )
                        if asyncio.iscoroutine(result):
                            await result
                        sent = True
                    except Exception as e:
                        logger.error(f"Bildirim gönderilemedi: {e}")
                else:
                    sent = True  # callback yok, yine de tamamlandı say
                if sent:
                    if _tts_callback:
                        try:
                            _tts_callback(f"Efendim, hatırlatmanız var: {rem['text']}")
                        except Exception as e:
                            logger.error(f"TTS hatırlatma hatası: {e}")
                    try:
                        from core.notifier import show_overlay
                        show_overlay(f"⏰ Hatırlatma!\n{rem['text']}", duration=10)
                    except Exception as e:
                        logger.error(f"Overlay hatırlatma hatası: {e}")
                    mark_reminder_done(rem["id"])
        except Exception as e:
            logger.error(f"Hatırlatıcı kontrol hatası: {e}")
        await asyncio.sleep(30)


def start_reminder_checker() -> None:
    """Mevcut event loop'a hatırlatıcı kontrol görevi ekle."""
    global _checker_running
    if _checker_running:
        return
    _checker_running = True   # create_task'tan ÖNCE set et (çift başlatmayı önle)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_check_loop())
    except RuntimeError as e:
        _checker_running = False
        logger.error(f"Hatırlatıcı checker başlatılamadı: {e}")


# ── Zaman çözümleme ───────────────────────────────────────────────────────────

def parse_when(time_str: str) -> Optional[datetime]:
    """
    Türkçe zaman ifadelerini datetime'a çevirir.
    Örnekler:
      "5 dakika sonra", "2 saat sonra", "yarın", "15:30",
      "20:00", "sabah", "öğle", "akşam", "gece"
    """
    now = datetime.now()
    s = time_str.strip().lower()

    # Dakika/saat/gün sonra
    import re
    m = re.match(r"(\d+)\s*(dakika|dk|saat|gün|gun)\s*sonra", s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit in ("dakika", "dk"):
            return now + timedelta(minutes=n)
        elif unit == "saat":
            return now + timedelta(hours=n)
        elif unit in ("gün", "gun"):
            return now + timedelta(days=n)

    # Özel kelimeler
    if "yarın" in s or "yarin" in s:
        base = now + timedelta(days=1)
        if "sabah" in s:
            return base.replace(hour=8, minute=0, second=0, microsecond=0)
        elif "öğle" in s or "ogle" in s:
            return base.replace(hour=12, minute=0, second=0, microsecond=0)
        elif "akşam" in s or "aksam" in s:
            return base.replace(hour=18, minute=0, second=0, microsecond=0)
        return base.replace(hour=9, minute=0, second=0, microsecond=0)

    TIME_MAP = {
        "sabah":  8, "öğle": 12, "ogle": 12, "öğleden sonra": 14,
        "ikindi": 16, "akşam": 18, "aksam": 18, "gece": 21,
    }
    for kw, hour in TIME_MAP.items():
        if kw in s:
            t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if t <= now:
                t += timedelta(days=1)
            return t

    # HH:MM formatı
    m2 = re.search(r"(\d{1,2}):(\d{2})", s)
    if m2:
        h, mi = int(m2.group(1)), int(m2.group(2))
        t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)
        return t

    return None


def add_calendar_event(chat_id: int, text: str, when_str: str) -> tuple:
    """(success: bool, message: str) döndürür."""
    when_dt = parse_when(when_str)
    if when_dt is None:
        return False, (
            f"❌ Zaman anlaşılamadı: `{when_str}`\n\n"
            "Örnekler:\n"
            "• `30 dakika sonra`\n"
            "• `2 saat sonra`\n"
            "• `yarın sabah`\n"
            "• `akşam`\n"
            "• `15:30`"
        )

    rid = add_reminder(chat_id, text, when_dt.isoformat())
    formatted = when_dt.strftime("%d.%m.%Y %H:%M")
    return True, f"✅ Hatırlatma eklendi!\n📝 {text}\n⏰ {formatted} — ID: `{rid}`"


def get_reminders_text(chat_id: int) -> str:
    reminders = list_reminders(chat_id)
    if not reminders:
        return "📅 Aktif hatırlatma yok."

    lines = ["📅 *Hatırlatmalarım*", "━━━━━━━━━━━━━━━━━━━━━━"]
    for i, r in enumerate(reminders, 1):
        try:
            when_dt = datetime.fromisoformat(r["when"])
            when_str = when_dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            when_str = r.get("when", "?")
        lines.append(f"{i}. ⏰ `{when_str}` — {r['text']}")
        lines.append(f"   ID: `{r['id']}`")

    return "\n".join(lines)

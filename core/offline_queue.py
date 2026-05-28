"""
İnternet yokken fotoğraf/ses/mesaj kuyruğa alır,
bağlantı gelince otomatik gönderir.
5 günden eski öğeler otomatik silinir.
"""

import asyncio
import io
import json
import shutil
import socket
import time
import uuid
from pathlib import Path

from utils.logger import get_logger

logger = get_logger()

_BASE_DIR = Path(__file__).parent.parent
QUEUE_DIR = _BASE_DIR / "data" / "offline_queue"
QUEUE_INDEX = QUEUE_DIR / "queue.json"
MAX_AGE_DAYS = 5
CHECK_INTERVAL = 30  # saniye


# ── İnternet kontrolü ─────────────────────────────────────────────────────────

def is_online() -> bool:
    """TCP bağlantısıyla internet var mı kontrol et."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except OSError:
        return False


# ── Kuyruk okuma / yazma ──────────────────────────────────────────────────────

def _load() -> list:
    if not QUEUE_INDEX.exists():
        return []
    try:
        return json.loads(QUEUE_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(queue: list) -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_INDEX.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Temizlik ──────────────────────────────────────────────────────────────────

def _purge_old(queue: list) -> list:
    """5 günden eski öğeleri kuyruktan ve diskten sil."""
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    kept = []
    for item in queue:
        if item.get("ts", 0) < cutoff:
            fp = item.get("file_path")
            if fp:
                try:
                    Path(fp).unlink(missing_ok=True)
                except Exception:
                    pass
            logger.info(f"Offline kuyruk: eski öğe silindi [{item.get('id','?')}]")
        else:
            kept.append(item)
    return kept


def purge_old_items() -> None:
    """Sadece temizlik yapmak istediğinde çağır."""
    queue = _purge_old(_load())
    _save(queue)


def queue_size() -> int:
    return len(_load())


# ── Kuyruğa ekleme ────────────────────────────────────────────────────────────

def enqueue_photo(chat_id: int, buf: io.BytesIO, caption: str = "") -> None:
    """BytesIO fotoğrafı diske kaydedip kuyruğa ekle."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    item_id = uuid.uuid4().hex[:10]
    dest = QUEUE_DIR / f"photo_{item_id}.jpg"
    buf.seek(0)
    dest.write_bytes(buf.read())

    queue = _purge_old(_load())
    queue.append({
        "id": item_id,
        "type": "photo",
        "chat_id": chat_id,
        "file_path": str(dest),
        "caption": caption,
        "ts": time.time(),
    })
    _save(queue)
    logger.info(f"Offline kuyruk: fotoğraf eklendi [{item_id}]")


def enqueue_audio(chat_id: int, file_path: str, title: str = "", duration: int = 0) -> None:
    """Ses dosyasını kuyruk klasörüne kopyalayıp kuyruğa ekle."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    item_id = uuid.uuid4().hex[:10]
    src = Path(file_path)
    dest = QUEUE_DIR / f"audio_{item_id}{src.suffix}"
    shutil.copy2(src, dest)

    queue = _purge_old(_load())
    queue.append({
        "id": item_id,
        "type": "audio",
        "chat_id": chat_id,
        "file_path": str(dest),
        "title": title,
        "duration": duration,
        "ts": time.time(),
    })
    _save(queue)
    logger.info(f"Offline kuyruk: ses eklendi [{item_id}]")


def enqueue_message(chat_id: int, text: str) -> None:
    """Metin mesajını kuyruğa ekle."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    item_id = uuid.uuid4().hex[:10]

    queue = _purge_old(_load())
    queue.append({
        "id": item_id,
        "type": "text",
        "chat_id": chat_id,
        "text": text,
        "ts": time.time(),
    })
    _save(queue)
    logger.info(f"Offline kuyruk: metin eklendi [{item_id}]")


# ── Kuyruğu işle ──────────────────────────────────────────────────────────────

async def process_queue(bot) -> int:
    """Kuyruktaki tüm öğeleri göndermeyi dene. Gönderilenleri sil."""
    queue = _purge_old(_load())
    if not queue:
        _save(queue)
        return 0

    sent_ids = []
    remaining = []

    for item in queue:
        try:
            if item["type"] == "photo":
                fp = Path(item["file_path"])
                if fp.exists():
                    with open(fp, "rb") as f:
                        await bot.send_photo(
                            chat_id=item["chat_id"],
                            photo=f,
                            caption=item.get("caption", ""),
                        )
                    fp.unlink(missing_ok=True)
                sent_ids.append(item["id"])

            elif item["type"] == "audio":
                fp = Path(item["file_path"])
                if fp.exists():
                    with open(fp, "rb") as f:
                        await bot.send_audio(
                            chat_id=item["chat_id"],
                            audio=f,
                            title=item.get("title", "Ses kaydı"),
                            duration=item.get("duration", 0),
                        )
                    fp.unlink(missing_ok=True)
                sent_ids.append(item["id"])

            elif item["type"] == "text":
                await bot.send_message(
                    chat_id=item["chat_id"],
                    text=item["text"],
                )
                sent_ids.append(item["id"])

        except Exception as e:
            logger.warning(f"Offline kuyruk gönderme hatası [{item['id']}]: {e}")
            remaining.append(item)

    _save(remaining)

    if sent_ids:
        logger.info(f"Offline kuyruk: {len(sent_ids)} öğe gönderildi.")

    return len(sent_ids)


# ── Arka plan izleyicisi ──────────────────────────────────────────────────────

async def start_queue_watcher(bot) -> None:
    """
    Her 30 saniyede interneti kontrol eder.
    Bağlantı yeniden sağlandığında kuyruğu işler ve owner'a bildirim gönderir.
    """
    was_online = is_online()
    logger.info(f"Offline kuyruk izleyicisi başladı (başlangıç durum: {'online' if was_online else 'offline'})")

    while True:
        await asyncio.sleep(CHECK_INTERVAL)

        try:
            now_online = is_online()

            if now_online and not was_online:
                logger.info("İnternet bağlantısı yeniden sağlandı — kuyruk işleniyor...")
                await process_queue(bot)

            elif now_online and queue_size() > 0:
                # İnternet var, kuyruğa bir şeyler kalmış (önceki deneme başarısız olmuş)
                await process_queue(bot)

            was_online = now_online

        except Exception as e:
            logger.error(f"Offline kuyruk izleyici hatası: {e}")

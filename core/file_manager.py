import os
import io
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Callable
import aiofiles
from telegram import Bot
from utils.helpers import format_bytes, progress_bar
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()

CHUNK_SIZE = 20 * 1024 * 1024  # 20MB chunk
MAX_TELEGRAM_FILE = 50 * 1024 * 1024  # 50MB Telegram limiti

# Aktif browse session'ları: { user_id: {"path": str, "files": list} }
_browse_sessions: dict[int, dict] = {}


def get_default_paths() -> list[str]:
    cfg = get_config()
    return cfg.get("allowed_download_paths", [])


def list_directory(path_str: str) -> dict:
    path = Path(path_str)
    if not path.exists():
        return {"error": f"Klasör bulunamadı: `{path_str}`"}
    if not path.is_dir():
        return {"error": f"`{path_str}` bir klasör değil."}

    items = {"dirs": [], "files": [], "path": str(path)}

    try:
        for entry in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            try:
                stat = entry.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M")
                if entry.is_dir():
                    items["dirs"].append({
                        "name": entry.name,
                        "path": str(entry),
                        "modified": modified,
                    })
                else:
                    items["files"].append({
                        "name": entry.name,
                        "path": str(entry),
                        "size": stat.st_size,
                        "size_str": format_bytes(stat.st_size),
                        "modified": modified,
                    })
            except PermissionError:
                continue
    except PermissionError:
        return {"error": "Bu klasöre erişim izniniz yok."}

    return items


def store_browse_session(user_id: int, path: str, files: list) -> None:
    _browse_sessions[user_id] = {"path": path, "files": files}


def get_browse_session(user_id: int) -> dict | None:
    return _browse_sessions.get(user_id)


def format_directory_listing(listing: dict) -> str:
    if "error" in listing:
        return f"❌ {listing['error']}"

    path = listing["path"]
    dirs = listing["dirs"]
    files = listing["files"]

    lines = [f"📁 *{Path(path).name or path}*\n`{path}`\n━━━━━━━━━━━━━━━━━━━━━━\n"]

    if dirs:
        lines.append("📂 *Klasörler:*")
        for d in dirs[:20]:
            lines.append(f"  📁 `{d['name']}`")

    if files:
        lines.append("\n📄 *Dosyalar:*")
        for i, f in enumerate(files[:30], 1):
            lines.append(
                f"  `{i:2d}.` 📄 {f['name']}\n"
                f"       `{f['size_str']}` • {f['modified']}"
            )

    if not dirs and not files:
        lines.append("_(Bu klasör boş)_")

    total = len(dirs) + len(files)
    lines.append(f"\n_Toplam: {len(dirs)} klasör, {len(files)} dosya_")
    return "\n".join(lines)


async def send_file(bot: Bot, chat_id: int, file_path: str, progress_msg=None) -> tuple[bool, str]:
    path = Path(file_path)

    if not path.exists():
        return False, f"Dosya bulunamadı: `{file_path}`"

    if not path.is_file():
        return False, "Bu bir dosya değil."

    size = path.stat().st_size
    max_mb = get_config().get("max_file_size_mb", 50) * 1024 * 1024

    if size > max_mb:
        return False, (
            f"Dosya boyutu ({format_bytes(size)}) izin verilen "
            f"limitin ({format_bytes(max_mb)}) üzerinde."
        )

    if size > MAX_TELEGRAM_FILE:
        return False, (
            f"Telegram'ın maksimum dosya boyutu 50MB'dır. "
            f"Dosya boyutu: {format_bytes(size)}"
        )

    try:
        if progress_msg:
            await progress_msg.edit_text(
                f"📤 Dosya gönderiliyor...\n`{path.name}`\nBoyut: {format_bytes(size)}"
            )

        async with aiofiles.open(path, "rb") as f:
            content = await f.read()

        await bot.send_document(
            chat_id=chat_id,
            document=io.BytesIO(content),
            filename=path.name,
            caption=f"📄 `{path.name}`\n💾 {format_bytes(size)}",
            parse_mode="Markdown",
        )
        logger.info(f"Dosya gönderildi: {path.name} ({format_bytes(size)})")
        return True, f"✅ `{path.name}` başarıyla gönderildi."
    except Exception as e:
        logger.error(f"Dosya gönderme hatası: {e}")
        return False, f"❌ Dosya gönderilirken hata oluştu: {e}"


async def receive_file(bot: Bot, file_id: str, save_path: str, filename: str, progress_msg=None) -> tuple[bool, str]:
    save_dir = Path(save_path)
    if not save_dir.exists():
        save_dir.mkdir(parents=True, exist_ok=True)

    dest = save_dir / filename

    try:
        tg_file = await bot.get_file(file_id)

        if progress_msg:
            await progress_msg.edit_text(f"📥 Dosya indiriliyor...\n`{filename}`")

        await tg_file.download_to_drive(str(dest))

        size = dest.stat().st_size
        logger.info(f"Dosya alındı: {filename} ({format_bytes(size)})")
        return True, f"✅ `{filename}` kaydedildi.\nKonum: `{dest}`\nBoyut: {format_bytes(size)}"
    except Exception as e:
        logger.error(f"Dosya alma hatası: {e}")
        return False, f"❌ Dosya alınırken hata oluştu: {e}"


def search_files(query: str, search_paths: list[str] = None) -> list[dict]:
    if not search_paths:
        search_paths = get_default_paths()

    results = []
    query_lower = query.lower()

    for base_path in search_paths:
        base = Path(base_path)
        if not base.exists():
            continue
        try:
            for entry in base.rglob("*"):
                if len(results) >= 50:
                    break
                try:
                    if entry.is_file() and query_lower in entry.name.lower():
                        stat = entry.stat()
                        results.append({
                            "name": entry.name,
                            "path": str(entry),
                            "size": stat.st_size,
                            "size_str": format_bytes(stat.st_size),
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                        })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            continue

    return results


def format_search_results(results: list[dict], query: str) -> str:
    if not results:
        return f"🔍 `{query}` için sonuç bulunamadı."

    lines = [f"🔍 *'{query}' arama sonuçları ({len(results)} dosya)*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"`{i:2d}.` 📄 {r['name']}\n"
            f"       `{r['size_str']}` • {r['modified']}\n"
            f"       `{r['path']}`\n"
        )
    return "\n".join(lines)

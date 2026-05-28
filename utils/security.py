import time
import functools
from pathlib import Path
from typing import Callable
from utils.config_manager import get_config
from utils.logger import get_logger, log_command

logger = get_logger()

# { (user_id, action): last_call_timestamp }
_rate_limit_store: dict[tuple, float] = {}

# Onay bekleyen işlemler: { user_id: {"action": str, "callback": callable} }
_pending_confirmations: dict[int, dict] = {}


def is_authorized(user_id: int) -> bool:
    cfg = get_config()
    return user_id in cfg.get("authorized_users", [])


def authorized_only(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not is_authorized(user.id):
            logger.warning(f"Yetkisiz erişim girişimi - User: {user.id} (@{user.username})")
            msg = update.effective_message
            log_command(user.id, user.username or "unknown", (msg.text if msg else None) or "?", "YETKİSİZ")
            if msg:
                await msg.reply_text(
                    "🚫 *Erişim Reddedildi*\n\nBu botu kullanma yetkiniz bulunmuyor.",
                    parse_mode="Markdown",
                )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def rate_limit(action: str, seconds: int = 60):
    """Belirli bir eylemi saniyede bir kez sınırla."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            key = (user_id, action)
            now = time.time()
            last_call = _rate_limit_store.get(key, 0)

            if now - last_call < seconds:
                remaining = int(seconds - (now - last_call))
                await update.message.reply_text(
                    f"⏳ Bu komutu çok sık kullanıyorsunuz.\n"
                    f"Lütfen *{remaining} saniye* bekleyin.",
                    parse_mode="Markdown",
                )
                return

            _rate_limit_store[key] = now
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


def validate_file_path(path_str: str) -> tuple[bool, str]:
    """
    Path traversal saldırılarına karşı dosya yolunu doğrula.
    Returns (is_valid, error_message)
    """
    cfg = get_config()
    allowed_paths = cfg.get("allowed_download_paths", [])

    try:
        target = Path(path_str).resolve()
    except Exception:
        return False, "Geçersiz dosya yolu."

    # Path traversal kontrolü: .. veya null byte içeriyor mu?
    if ".." in path_str or "\x00" in path_str:
        logger.warning(f"Path traversal girişimi engellendi: {path_str}")
        return False, "Güvenli olmayan dosya yolu tespit edildi."

    # İzin verilen klasörler içinde mi?
    for allowed in allowed_paths:
        allowed_resolved = Path(allowed).resolve()
        try:
            target.relative_to(allowed_resolved)
            return True, ""
        except ValueError:
            continue

    return False, f"Bu konuma erişim izniniz yok.\nİzin verilen konumlar:\n" + "\n".join(
        f"• {p}" for p in allowed_paths
    )


def is_safe_extension(filename: str) -> tuple[bool, str]:
    cfg = get_config()
    blocked = cfg.get("blocked_file_extensions", [])
    ext = Path(filename).suffix.lower()
    if ext in blocked:
        return False, f"`.{ext}` uzantılı dosyalar güvenlik nedeniyle engellenmiştir."
    return True, ""


def store_pending_confirmation(user_id: int, action: str, data: dict) -> None:
    _pending_confirmations[user_id] = {"action": action, "data": data}


def get_pending_confirmation(user_id: int) -> dict | None:
    return _pending_confirmations.get(user_id)


def clear_pending_confirmation(user_id: int) -> None:
    _pending_confirmations.pop(user_id, None)

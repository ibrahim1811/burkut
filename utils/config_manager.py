import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.json"


def _config_from_env() -> dict:
    """config.json yoksa (Render/cloud) environment variable'lardan config üret."""
    authorized = []
    chat_id_str = os.environ.get("TELEGRAM_CHAT_ID", "")
    if chat_id_str:
        try:
            authorized = [int(x.strip()) for x in chat_id_str.split(",") if x.strip()]
        except ValueError:
            pass
    return {
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "authorized_users": authorized,
        "startup_webcam_photo": False,
        "auto_screenshot_quality": 85,
        "max_audio_duration": 120,
        "max_file_size_mb": 50,
        "quick_files": {},
    }


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # Env var varsa config.json'daki değerleri override et
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            cfg["telegram_bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
        if os.environ.get("TELEGRAM_CHAT_ID"):
            try:
                cfg["authorized_users"] = [
                    int(x.strip())
                    for x in os.environ["TELEGRAM_CHAT_ID"].split(",")
                    if x.strip()
                ]
            except ValueError:
                pass
        return cfg

    # config.json yok → Render/cloud ortamı
    cfg = _config_from_env()
    if not cfg["telegram_bot_token"]:
        raise FileNotFoundError(
            "config.json bulunamadı ve TELEGRAM_BOT_TOKEN env var'ı da tanımlı değil.\n"
            "Render → Environment Variables kısmına ekleyin."
        )
    return cfg


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get(key: str, default=None):
    try:
        cfg = load_config()
        return cfg.get(key, default)
    except Exception:
        return default


_config_cache: dict | None = None


def get_config() -> dict:
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def reload_config() -> dict:
    global _config_cache
    _config_cache = load_config()
    return _config_cache

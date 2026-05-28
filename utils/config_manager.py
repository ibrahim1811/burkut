import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json bulunamadı: {CONFIG_PATH}\n"
            "Lütfen config.json dosyasını oluşturup bot token ve kullanıcı ID'sini girin."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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

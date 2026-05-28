import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "app.log"
ACTIVITY_LOG_FILE = LOGS_DIR / "activity.log"

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("burkut")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Konsol handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Dosya handler (30 gün rotasyon)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE, when="midnight", backupCount=30, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("burkut")


def log_command(user_id: int, username: str, command: str, result: str = "OK"):
    activity_logger = logging.getLogger("burkut.activity")

    if not activity_logger.handlers:
        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        handler = logging.handlers.TimedRotatingFileHandler(
            ACTIVITY_LOG_FILE, when="midnight", backupCount=30, encoding="utf-8"
        )
        handler.setFormatter(formatter)
        activity_logger.addHandler(handler)
        activity_logger.setLevel(logging.INFO)

    activity_logger.info(
        f"[User: {user_id} (@{username})] Komut: {command} | Sonuç: {result}"
    )


logger = setup_logger()

import re
from datetime import timedelta


def format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


def format_uptime(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} gün")
    if hours:
        parts.append(f"{hours} saat")
    if minutes:
        parts.append(f"{minutes} dakika")
    if secs and not days:
        parts.append(f"{secs} saniye")

    return " ".join(parts) if parts else "0 saniye"


def parse_time(time_str: str) -> int:
    """
    Zaman string'ini saniyeye çevirir.
    Örnekler: "30" -> 1800, "1h" -> 3600, "2h30m" -> 9000, "30m" -> 1800
    Sayı tek başına dakika olarak alınır.
    """
    if not time_str:
        return 0

    time_str = time_str.strip().lower()

    # Sadece sayı ise dakika kabul et
    if time_str.isdigit():
        return int(time_str) * 60

    total_seconds = 0
    pattern = r"(\d+)\s*(h|saat|m|min|dakika|s|sn|saniye)?"
    matches = re.findall(pattern, time_str)

    for value, unit in matches:
        value = int(value)
        if unit in ("h", "saat"):
            total_seconds += value * 3600
        elif unit in ("m", "min", "dakika", ""):
            total_seconds += value * 60
        elif unit in ("s", "sn", "saniye"):
            total_seconds += value

    return total_seconds


def format_seconds(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} saniye"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m} dakika {s} saniye" if s else f"{m} dakika"
    else:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        parts = [f"{h} saat"]
        if m:
            parts.append(f"{m} dakika")
        return " ".join(parts)


def progress_bar(current: int, total: int, length: int = 10) -> str:
    if total == 0:
        return "▓" * length
    filled = int(length * current / total)
    empty = length - filled
    percent = int(100 * current / total)
    bar = "▓" * filled + "░" * empty
    return f"[{bar}] {percent}%"


def truncate(text: str, max_len: int = 4000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def mask_path(path: str) -> str:
    """Log'larda hassas path bilgisini maskele."""
    import re
    return re.sub(r"C:/Users/[^/]+", "C:/Users/***", path.replace("\\", "/"))

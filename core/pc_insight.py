import io
import os
import time
from datetime import datetime
from pathlib import Path

import psutil

from utils.helpers import format_bytes

RECENT_HOURS = 24
RECENT_SCAN_SECONDS = 8
RECENT_SKIP_DIRS = {"AppData", "node_modules", "__pycache__", "venv", "site-packages", "dist", "build", "logs"}


def capture_desktop_jpeg(max_side: int = 1600, quality: int = 75) -> bytes:
    import mss
    from PIL import Image
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def slowness_facts() -> str:
    procs = list(psutil.process_iter(["name", "memory_info"]))
    for p in procs:
        try:
            p.cpu_percent(None)
        except psutil.Error:
            pass
    total_cpu = psutil.cpu_percent(interval=1.5)
    cores = psutil.cpu_count() or 1

    usage: dict[str, list[float]] = {}
    for p in procs:
        try:
            name = p.info["name"] or "?"
            cpu = p.cpu_percent(None) / cores
            ram = p.info["memory_info"].rss if p.info["memory_info"] else 0
        except psutil.Error:
            continue
        if name.lower() in ("system idle process", "idle"):
            continue
        entry = usage.setdefault(name, [0.0, 0.0, 0])
        entry[0] += cpu
        entry[1] += ram
        entry[2] += 1

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.home().anchor)
    io1 = psutil.disk_io_counters()
    time.sleep(1)
    io2 = psutil.disk_io_counters()
    disk_mb_s = ((io2.read_bytes + io2.write_bytes) - (io1.read_bytes + io1.write_bytes)) / 1024 / 1024

    top_cpu = sorted(usage.items(), key=lambda kv: kv[1][0], reverse=True)[:6]
    top_ram = sorted(usage.items(), key=lambda kv: kv[1][1], reverse=True)[:6]
    lines = [
        f"Toplam CPU: %{total_cpu:.0f}",
        f"RAM: %{ram.percent:.0f} ({format_bytes(ram.used)} / {format_bytes(ram.total)})",
        f"Sistem diski: %{disk.percent:.0f} dolu, {format_bytes(disk.free)} boş",
        f"Disk aktivitesi: {disk_mb_s:.1f} MB/sn",
        f"Açık kalma süresi: {(time.time() - psutil.boot_time()) / 3600:.0f} saat",
        "En çok CPU kullananlar: " + ", ".join(f"{n} %{v[0]:.0f} ({v[2]} süreç)" for n, v in top_cpu),
        "En çok RAM kullananlar: " + ", ".join(f"{n} {format_bytes(v[1])}" for n, v in top_ram),
    ]
    return "\n".join(lines)


def recent_activity_facts() -> str:
    from core.window_manager import get_windows, get_active_window
    windows = [w["title"] for w in get_windows() if w["title"].strip() and not w["minimized"]][:20]
    active = get_active_window()

    cutoff = time.time() - RECENT_HOURS * 3600
    deadline = time.monotonic() + RECENT_SCAN_SECONDS
    recent: list[tuple[float, str]] = []
    for root, dirs, files in os.walk(Path.home()):
        if time.monotonic() > deadline:
            break
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in RECENT_SKIP_DIRS]
        for name in files:
            full = os.path.join(root, name)
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            if mtime > cutoff:
                recent.append((mtime, full))
    recent.sort(reverse=True)

    home = str(Path.home())
    lines = [f"Şu an aktif pencere: {active or '-'}", "Açık pencereler:"]
    lines += [f"- {t}" for t in windows]
    lines.append(f"Son {RECENT_HOURS} saatte değişen dosyalar (yeniden eskiye):")
    lines += [
        f"- {datetime.fromtimestamp(m).strftime('%H:%M')} {p.replace(home, '~')}"
        for m, p in recent[:25]
    ]
    return "\n".join(lines)

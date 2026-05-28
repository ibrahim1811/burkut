import time
import socket
import psutil
import platform
from datetime import datetime
from utils.helpers import format_bytes, format_uptime

_cache: dict = {}
_cache_ttl = 5  # saniye


def _cached(key: str, func):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _cache_ttl:
        return _cache[key]["value"]
    value = func()
    _cache[key] = {"value": value, "ts": now}
    return value


def get_cpu_info() -> dict:
    def _get():
        return {
            "percent": psutil.cpu_percent(interval=1),
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
            "freq": psutil.cpu_freq(),
        }
    return _cached("cpu", _get)


def get_ram_info() -> dict:
    def _get():
        vm = psutil.virtual_memory()
        return {
            "total": vm.total,
            "used": vm.used,
            "available": vm.available,
            "percent": vm.percent,
        }
    return _cached("ram", _get)


def get_disk_info() -> list[dict]:
    def _get():
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                })
            except PermissionError:
                continue
        return disks
    return _cached("disk", _get)


def get_network_info() -> dict:
    def _get():
        net_io = psutil.net_io_counters()
        addrs = psutil.net_if_addrs()

        local_ip = "Bilinmiyor"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        connections = len(psutil.net_connections())

        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "local_ip": local_ip,
            "connections": connections,
        }
    return _cached("network", _get)


def get_uptime() -> float:
    return time.time() - psutil.boot_time()


def get_temperature() -> str:
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return "Sıcaklık bilgisi mevcut değil"
        lines = []
        for name, entries in temps.items():
            for entry in entries:
                lines.append(f"{name}: {entry.current:.1f}°C")
        return "\n".join(lines[:5]) if lines else "Sıcaklık bilgisi mevcut değil"
    except (AttributeError, Exception):
        return "Sıcaklık bilgisi mevcut değil (Windows)"


def get_full_status() -> str:
    cpu = get_cpu_info()
    ram = get_ram_info()
    disks = get_disk_info()
    net = get_network_info()
    uptime = get_uptime()

    cpu_freq = ""
    if cpu["freq"]:
        cpu_freq = f" @ {cpu['freq'].current:.0f} MHz"

    disk_lines = ""
    for d in disks:
        bar_filled = int(d["percent"] / 10)
        bar = "▓" * bar_filled + "░" * (10 - bar_filled)
        disk_lines += (
            f"  `{d['device']}` [{bar}] {d['percent']:.1f}%\n"
            f"  {format_bytes(d['used'])} / {format_bytes(d['total'])} "
            f"(Boş: {format_bytes(d['free'])})\n"
        )

    ram_bar_filled = int(ram["percent"] / 10)
    ram_bar = "▓" * ram_bar_filled + "░" * (10 - ram_bar_filled)

    cpu_bar_filled = int(cpu["percent"] / 10)
    cpu_bar = "▓" * cpu_bar_filled + "░" * (10 - cpu_bar_filled)

    temp = get_temperature()

    status = (
        f"🖥️ *BÜRKÜT — Sistem Durumu*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💻 *İşlemci*\n"
        f"  [{cpu_bar}] `{cpu['percent']:.1f}%`{cpu_freq}\n"
        f"  {cpu['count_physical']} fiziksel / {cpu['count_logical']} mantıksal çekirdek\n\n"
        f"🧠 *RAM*\n"
        f"  [{ram_bar}] `{ram['percent']:.1f}%`\n"
        f"  {format_bytes(ram['used'])} / {format_bytes(ram['total'])}\n\n"
        f"💾 *Diskler*\n"
        f"{disk_lines}\n"
        f"🌐 *Ağ*\n"
        f"  Yerel IP: `{net['local_ip']}`\n"
        f"  Gönderilen: {format_bytes(net['bytes_sent'])}\n"
        f"  Alınan: {format_bytes(net['bytes_recv'])}\n"
        f"  Aktif bağlantı: {net['connections']}\n\n"
        f"⏱️ *Uptime*: {format_uptime(uptime)}\n\n"
        f"🌡️ *Sıcaklık*\n  {temp}\n\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    return status


def get_gpu_info() -> dict:
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            count = pynvml.nvmlDeviceGetCount()
            gpus = []
            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                name = pynvml.nvmlDeviceGetName(handle)
                gpus.append({
                    "index": i,
                    "name": name,
                    "usage": util.gpu,
                    "vram_used": mem.used,
                    "vram_total": mem.total,
                    "vram_free": mem.free,
                    "temp": temp,
                })
            return {"available": True, "gpus": gpus}
        finally:
            pynvml.nvmlShutdown()
    except Exception as e:
        return {"available": False, "error": str(e)}


def get_top_processes(n: int = 10) -> list[dict]:
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            if info["cpu_percent"] is not None:
                processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda x: (x.get("cpu_percent") or 0), reverse=True)
    return processes[:n]

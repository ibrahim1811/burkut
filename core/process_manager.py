import os
import subprocess
import psutil
from utils.logger import get_logger
from utils.helpers import format_bytes

logger = get_logger()

PROGRAM_SHORTCUTS = {
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "notepad": "notepad.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
    "vscode": "Code.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "taskmgr": "taskmgr.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "vlc": "vlc.exe",
    "steam": "steam.exe",
    "telegram": "Telegram.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
}

SYSTEM_PROCESS_NAMES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe", "fontdrvhost.exe",
    "dwm.exe", "svchost.exe", "spoolsv.exe",
}


def get_running_processes(filter_name: str = "") -> list[dict]:
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
        try:
            info = proc.info
            name_lower = (info["name"] or "").lower()
            if name_lower in SYSTEM_PROCESS_NAMES:
                continue
            if filter_name and filter_name.lower() not in name_lower:
                continue
            mem = info["memory_info"]
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": round(info["cpu_percent"] or 0, 1),
                "memory": mem.rss if mem else 0,
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda x: x["memory"], reverse=True)
    return processes


def get_user_applications() -> list[dict]:
    """Penceresi olan / kullanıcı uygulamalarını listele."""
    apps = []
    seen_names = set()

    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            name = info["name"] or ""
            name_lower = name.lower()

            if name_lower in SYSTEM_PROCESS_NAMES:
                continue
            if name_lower in seen_names:
                continue

            mem = info["memory_info"]
            if mem and mem.rss > 10 * 1024 * 1024:  # 10MB üstü
                seen_names.add(name_lower)
                apps.append({
                    "pid": info["pid"],
                    "name": name,
                    "cpu_percent": round(info["cpu_percent"] or 0, 1),
                    "memory": mem.rss,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    apps.sort(key=lambda x: x["memory"], reverse=True)
    return apps[:20]


def kill_process(identifier: str) -> tuple[bool, str]:
    """
    Adı veya PID'i verilen süreci kapat.
    Returns (success, message)
    """
    killed = []
    errors = []

    # PID ile kapatma
    if identifier.isdigit():
        pid = int(identifier)
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.terminate()
            proc.wait(timeout=3)
            killed.append(f"{name} (PID: {pid})")
            logger.info(f"Süreç kapatıldı: {name} (PID: {pid})")
        except psutil.NoSuchProcess:
            return False, f"PID {pid} bulunamadı."
        except psutil.AccessDenied:
            return False, f"PID {pid} kapatmak için yetkiniz yok."
        except psutil.TimeoutExpired:
            try:
                proc.kill()
                killed.append(f"(PID: {pid}) - zorla kapatıldı")
            except Exception as e:
                errors.append(str(e))
    else:
        # İsme göre kapatma
        name_lower = identifier.lower()
        # Shortcut varsa gerçek adı al
        real_name = PROGRAM_SHORTCUTS.get(name_lower, identifier).lower()

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if (proc.info["name"] or "").lower() == real_name or \
                   (proc.info["name"] or "").lower().startswith(name_lower):
                    proc.terminate()
                    proc.wait(timeout=3)
                    killed.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
                    logger.info(f"Süreç kapatıldı: {proc.info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except psutil.TimeoutExpired:
                try:
                    proc.kill()
                    killed.append(f"{proc.info['name']} - zorla kapatıldı")
                except Exception as e:
                    errors.append(str(e))

    if not killed and not errors:
        return False, f"`{identifier}` adlı çalışan süreç bulunamadı."

    msg = ""
    if killed:
        msg += "✅ Kapatıldı:\n" + "\n".join(f"  • {k}" for k in killed)
    if errors:
        msg += "\n❌ Hatalar:\n" + "\n".join(f"  • {e}" for e in errors)

    return bool(killed), msg


def start_process(program: str) -> tuple[bool, str]:
    """Bir programı başlat."""
    name_lower = program.lower().strip('"').strip("'")
    real_name = PROGRAM_SHORTCUTS.get(name_lower, program)

    try:
        if os.path.isabs(real_name) or os.path.exists(real_name):
            subprocess.Popen([real_name], shell=False)
        else:
            subprocess.Popen(real_name, shell=True)
        logger.info(f"Program başlatıldı: {real_name}")
        return True, f"✅ `{real_name}` başlatıldı."
    except FileNotFoundError:
        return False, f"❌ `{real_name}` bulunamadı."
    except PermissionError:
        return False, f"❌ `{real_name}` için yetkiniz yok."
    except Exception as e:
        logger.error(f"Program başlatma hatası: {e}")
        return False, f"❌ Hata: {e}"


def format_process_list(processes: list[dict]) -> str:
    if not processes:
        return "Çalışan süreç bulunamadı."

    lines = ["🔄 *Çalışan Süreçler (RAM'e göre)*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, p in enumerate(processes, 1):
        lines.append(
            f"`{i:2d}.` {p['name']}\n"
            f"     PID: `{p['pid']}` | CPU: `{p['cpu_percent']}%` | RAM: `{format_bytes(p['memory'])}`\n"
        )
    return "\n".join(lines)

import asyncio
import time
import os
import threading
from pathlib import Path
from typing import Callable
from utils.logger import get_logger

logger = get_logger()

# Aktif monitörler: { key: {"task": Task, "description": str} }
_monitors: dict[str, dict] = {}


class FolderMonitor:
    def __init__(self, folder_path: str, callback: Callable, user_id: int):
        self.folder_path = Path(folder_path)
        self.callback = callback
        self.user_id = user_id
        self._known_files: set = set()
        self._running = False
        self._task: asyncio.Task | None = None

    def _get_files(self) -> set:
        try:
            return {str(f) for f in self.folder_path.iterdir() if f.is_file()}
        except Exception:
            return set()

    async def start(self):
        self._known_files = self._get_files()
        self._running = True
        logger.info(f"Klasör monitörü başlatıldı: {self.folder_path}")

        while self._running:
            await asyncio.sleep(5)
            current = self._get_files()
            new_files = current - self._known_files
            if new_files:
                for f in new_files:
                    name = Path(f).name
                    size = Path(f).stat().st_size if Path(f).exists() else 0
                    from utils.helpers import format_bytes
                    await self.callback(
                        f"📂 *Yeni dosya algılandı!*\n"
                        f"Klasör: `{self.folder_path}`\n"
                        f"Dosya: `{name}`\n"
                        f"Boyut: {format_bytes(size)}"
                    )
            self._known_files = current

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()


class IdleMonitor:
    def __init__(self, idle_minutes: int, callback: Callable):
        self.idle_seconds = idle_minutes * 60
        self.callback = callback
        self._running = False
        self._notified = False

    def _get_idle_time(self) -> float:
        """Windows'ta son kullanıcı aktivitesinden geçen süre (saniye)."""
        try:
            import ctypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(lii)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0
        except Exception:
            return 0

    async def start(self):
        self._running = True
        while self._running:
            await asyncio.sleep(30)
            idle = self._get_idle_time()
            if idle >= self.idle_seconds and not self._notified:
                self._notified = True
                await self.callback(
                    f"💤 *PC boşta kaldı!*\n"
                    f"Boşta kalma süresi: {int(idle // 60)} dakika"
                )
            elif idle < self.idle_seconds:
                self._notified = False

    def stop(self):
        self._running = False


class ProcessWatcher:
    def __init__(self, process_name: str, callback: Callable):
        self.process_name = process_name.lower()
        self.callback = callback
        self._running = False
        self._was_running = False

    def _is_running(self) -> bool:
        import psutil
        for proc in psutil.process_iter(["name"]):
            try:
                if (proc.info["name"] or "").lower() == self.process_name:
                    return True
            except Exception:
                continue
        return False

    async def start(self):
        self._running = True
        self._was_running = self._is_running()

        while self._running:
            await asyncio.sleep(10)
            is_now = self._is_running()
            if self._was_running and not is_now:
                await self.callback(
                    f"🔔 *Program Kapandı!*\n`{self.process_name}` artık çalışmıyor."
                )
                self._running = False
            self._was_running = is_now

    def stop(self):
        self._running = False


def add_monitor(key: str, monitor_obj, loop: asyncio.AbstractEventLoop) -> asyncio.Task:
    task = loop.create_task(monitor_obj.start())
    _monitors[key] = {"task": task, "monitor": monitor_obj, "description": key}
    return task


def stop_monitor(key: str) -> bool:
    if key in _monitors:
        mon = _monitors[key]
        mon["monitor"].stop()
        mon["task"].cancel()
        del _monitors[key]
        return True
    return False


def stop_all_monitors() -> int:
    count = len(_monitors)
    for key in list(_monitors.keys()):
        stop_monitor(key)
    return count


def list_monitors() -> list[str]:
    return list(_monitors.keys())

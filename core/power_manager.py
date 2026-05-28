import os
import sys
import asyncio
import platform
from utils.logger import get_logger

logger = get_logger()

# Aktif zamanlayıcı task
_shutdown_task: asyncio.Task | None = None
_shutdown_info: dict | None = None  # {"action": "shutdown"|"restart", "delay": int, "scheduled_at": float}


def _get_os() -> str:
    return platform.system().lower()


def _execute_shutdown(delay_seconds: int = 0) -> bool:
    try:
        if _get_os() == "windows":
            os.system(f"shutdown /s /t {delay_seconds}")
        else:
            minutes = delay_seconds // 60
            os.system(f"shutdown -h +{minutes}")
        return True
    except Exception as e:
        logger.error(f"Kapatma komutu hatası: {e}")
        return False


def _execute_restart(delay_seconds: int = 0) -> bool:
    try:
        if _get_os() == "windows":
            os.system(f"shutdown /r /t {delay_seconds}")
        else:
            minutes = delay_seconds // 60
            os.system(f"shutdown -r +{minutes}")
        return True
    except Exception as e:
        logger.error(f"Yeniden başlatma komutu hatası: {e}")
        return False


def _execute_sleep() -> bool:
    try:
        if _get_os() == "windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif _get_os() == "darwin":
            os.system("pmset sleepnow")
        else:
            os.system("systemctl suspend")
        return True
    except Exception as e:
        logger.error(f"Uyku modu hatası: {e}")
        return False


def _execute_hibernate() -> bool:
    try:
        if _get_os() == "windows":
            os.system("shutdown /h")
        elif _get_os() == "darwin":
            os.system("pmset hibernatemode 25 && pmset sleepnow")
        else:
            os.system("systemctl hibernate")
        return True
    except Exception as e:
        logger.error(f"Hazırda bekleme hatası: {e}")
        return False


def cancel_os_shutdown() -> bool:
    try:
        if _get_os() == "windows":
            os.system("shutdown /a")
        else:
            os.system("shutdown -c")
        return True
    except Exception as e:
        logger.error(f"Kapatma iptali hatası: {e}")
        return False


async def schedule_shutdown(
    action: str,
    delay_seconds: int,
    notify_callback=None,
) -> bool:
    """
    action: "shutdown" | "restart"
    delay_seconds: kaç saniye sonra
    notify_callback: async callable(message: str) - kullanıcıya bildirim gönderir
    """
    global _shutdown_task, _shutdown_info

    import time

    if _shutdown_task and not _shutdown_task.done():
        _shutdown_task.cancel()

    _shutdown_info = {
        "action": action,
        "delay": delay_seconds,
        "scheduled_at": time.time(),
    }

    action_label = "kapatma" if action == "shutdown" else "yeniden başlatma"

    async def _run():
        warnings = [30 * 60, 15 * 60, 5 * 60, 60]  # saniye
        loop = asyncio.get_running_loop()
        start = loop.time()

        for warn_before in warnings:
            if warn_before >= delay_seconds:
                continue
            wait = delay_seconds - warn_before - (loop.time() - start)
            if wait > 0:
                await asyncio.sleep(wait)
                remaining_min = warn_before // 60
                msg = f"⚠️ *{remaining_min} dakika* içinde {action_label} gerçekleşecek!"
                if notify_callback:
                    try:
                        await notify_callback(msg)
                    except Exception:
                        pass

        # Son bekleme
        elapsed = loop.time() - start
        final_wait = delay_seconds - elapsed
        if final_wait > 0:
            await asyncio.sleep(final_wait)

        logger.info(f"Zamanlı {action_label} çalıştırılıyor.")
        if action == "shutdown":
            _execute_shutdown(0)
        else:
            _execute_restart(0)

    _shutdown_task = asyncio.create_task(_run())
    return True


def cancel_scheduled_shutdown() -> bool:
    global _shutdown_task, _shutdown_info
    if _shutdown_task and not _shutdown_task.done():
        _shutdown_task.cancel()
        _shutdown_task = None
        _shutdown_info = None
        cancel_os_shutdown()
        return True
    return False


def get_shutdown_status() -> dict | None:
    import time
    if not _shutdown_info or (_shutdown_task and _shutdown_task.done()):
        return None
    elapsed = time.time() - _shutdown_info["scheduled_at"]
    remaining = max(0, _shutdown_info["delay"] - elapsed)
    return {
        "action": _shutdown_info["action"],
        "remaining": int(remaining),
        "total": _shutdown_info["delay"],
    }


def immediate_shutdown() -> bool:
    return _execute_shutdown(0)


def immediate_restart() -> bool:
    return _execute_restart(0)


def sleep_pc() -> bool:
    return _execute_sleep()


def hibernate_pc() -> bool:
    return _execute_hibernate()

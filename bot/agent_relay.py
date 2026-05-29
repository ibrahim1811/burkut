"""Render → Local PC Agent relay. Tüm PC komutları buradan geçer."""
import os
import queue
import threading
import time
import uuid
import asyncio

AGENT_TOKEN: str = os.environ.get("AGENT_TOKEN", "")

_cmd_queue:   queue.Queue = queue.Queue()
_results:     dict        = {}
_results_lock             = threading.Lock()
_last_seen:   float       = 0.0


def agent_is_online() -> bool:
    return (time.time() - _last_seen) < 20


def update_last_seen() -> None:
    global _last_seen
    _last_seen = time.time()


def get_next_cmd() -> dict | None:
    try:
        return _cmd_queue.get_nowait()
    except queue.Empty:
        return None


def store_result(data: dict) -> None:
    with _results_lock:
        _results[data["id"]] = data


async def send_to_agent(action: str, params: dict, timeout: float = 15.0) -> dict | None:
    if not agent_is_online():
        return None
    cmd_id = str(uuid.uuid4())
    _cmd_queue.put({"id": cmd_id, "action": action, "params": params})
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(0.3)
        with _results_lock:
            if cmd_id in _results:
                return _results.pop(cmd_id)
    return None

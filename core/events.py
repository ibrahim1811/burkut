"""Bürküt OS Event Bus — süreç içi pub/sub.

Saf stdlib: Render dahil her ortamda import edilebilir.
Kullanım:
    from core.events import bus
    bus.subscribe("PC_BOOTED", lambda e: ...)
    bus.emit("PC_BOOTED", {"hostname": "..."})
"""

import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    type: str
    data: dict
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"type": self.type, "data": self.data, "ts": self.ts}


class EventBus:
    HISTORY_SIZE = 200

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[Event], Any]]] = {}
        self._lock = threading.Lock()
        self.history: deque[Event] = deque(maxlen=self.HISTORY_SIZE)

    def subscribe(self, event_type: str, callback: Callable[[Event], Any]) -> None:
        """event_type "*" ise tüm olayları alır."""
        with self._lock:
            self._subs.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], Any]) -> None:
        with self._lock:
            if callback in self._subs.get(event_type, []):
                self._subs[event_type].remove(callback)

    def emit(self, event_type: str, data: dict | None = None) -> Event:
        event = Event(event_type, data or {})
        self.history.append(event)
        with self._lock:
            callbacks = list(self._subs.get(event_type, [])) + list(self._subs.get("*", []))
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                traceback.print_exc()
        return event


bus = EventBus()

# Standart olay adları
PC_BOOTED = "PC_BOOTED"
COMMAND_RECEIVED = "COMMAND_RECEIVED"
TOOL_EXECUTED = "TOOL_EXECUTED"
MEMORY_ADDED = "MEMORY_ADDED"
REMINDER_DUE = "REMINDER_DUE"
AI_RESPONSE = "AI_RESPONSE"

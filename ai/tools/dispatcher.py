"""Tool Dispatcher — AI hiçbir zaman Windows API'sini doğrudan çağırmaz.

AI → dispatch("open_program", {...}) → tool → core/*.
Her çağrı audit_log'a yazılır ve TOOL_EXECUTED olayı yayınlanır.
"""

import importlib
import pkgutil
import traceback
from typing import Callable

from core import events

_REGISTRY: dict[str, Callable[..., tuple[bool, str]]] = {}


def tool(name: str):
    def decorator(fn: Callable[..., tuple[bool, str]]):
        _REGISTRY[name] = fn
        return fn
    return decorator


def _load_tools() -> None:
    import ai.tools as pkg
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name != "dispatcher":
            importlib.import_module(f"ai.tools.{mod.name}")


def available() -> list[str]:
    if not _REGISTRY:
        _load_tools()
    return sorted(_REGISTRY)


def dispatch(name: str, params: dict | None = None, actor: str = "ai") -> tuple[bool, str]:
    if not _REGISTRY:
        _load_tools()
    params = params or {}

    fn = _REGISTRY.get(name)
    if fn is None:
        return False, f"Bilinmeyen tool: {name}"

    try:
        ok, msg = fn(**params)
    except TypeError as e:
        ok, msg = False, f"Geçersiz parametre: {e}"
    except Exception:
        ok, msg = False, f"Tool hatası:\n{traceback.format_exc(limit=2)}"

    try:
        from memory import store
        store.audit(actor=actor, channel="tool", action=name, params=params,
                    result=msg[:500], success=ok)
    except Exception:
        pass
    events.bus.emit(events.TOOL_EXECUTED, {"tool": name, "params": params, "success": ok})
    return ok, msg

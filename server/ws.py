import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core import system_info
from server.auth import ws_auth

router = APIRouter()

PUSH_INTERVAL = 2.0


@router.websocket("/ws/stats")
async def ws_stats(ws: WebSocket) -> None:
    if not ws_auth(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        while True:
            payload = await asyncio.to_thread(_collect)
            await ws.send_json(payload)
            await asyncio.sleep(PUSH_INTERVAL)
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    if not ws_auth(ws):
        await ws.close(code=4401)
        return
    await ws.accept()

    from core.events import bus
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def on_event(event) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event.to_dict())

    bus.subscribe("*", on_event)
    try:
        for old in list(bus.history)[-50:]:
            await ws.send_json(old.to_dict())
        while True:
            await ws.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe("*", on_event)


def _collect() -> dict:
    return {
        "cpu": system_info.get_cpu_info(),
        "ram": system_info.get_ram_info(),
        "gpu": system_info.get_gpu_info(),
        "network": system_info.get_network_info(),
    }
